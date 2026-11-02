#!/usr/bin/env python3
"""evaluate_candidate.py — host-side test oracle runner for LocalAgentBench.

Runs a candidate Python function body against the ground-truth test of a
HumanEvalPack task INSIDE the bubblewrap sandbox.

Security model:
  - The oracle test string is passed to the sandbox via stdin, never written
    to any model-writable path. The sandbox does not mount the dataset file.
  - The candidate code is passed via stdin as well (candidate never needs a
    writable file unless it writes temp files -> /tmp/work tmpfs).
  - Ground truth stays on the host; the sandbox cannot reach it (proven by
    sandbox_validation T3b).

Usage: evaluate_candidate.py --task-id Python/0 --body-file cand.py [--timeout 10]
Exit codes: 0 pass, 1 assertion fail, 2 runtime error, 3 import error, 4 no entry, 5 harness error.

v3 change (2026-10-15): candidate normalization using Python ast module.
  Previously: code = declaration + body_file_content (verbatim concatenation).
  Now:        normalize_candidate() inspects the body for a complete function
              definition and, if found, validates its name/signature and
              extracts the body block, replacing the raw concatenation.
  Normalization is recorded in the result so the trace is auditable.
  This implements recommendation M1 of reports/pilot_results.md §12.

v3.1 change (2026-10-18): the body block is now extracted VERBATIM.
  v3 ran textwrap.dedent() then textwrap.indent(..., "    ") over it, which
  silently corrupted candidates whose body contained a multi-line string
  literal with unindented text: dedent() became a no-op, indent() shifted every
  line anyway, and the resulting code still executed — producing a plausible
  exit code for semantically altered code. See _extract_body_source() and
  reports/evaluator_validation.md (defect C1).
  Also corrected the full-def-sig-mismatch comment, which claimed rc 4
  (missing_entry); the observed code is rc 3 (import_error).

v3.2 change (2026-10-18): diagnostic label only — defect N1.
  normalize_candidate() detected a body-only fragment with
  `"unexpected indent" in msg and e.lineno == 1`. A fragment opening with a
  blank or under-indented line puts its first statement on line 2 or 3, so four
  dataset canonical solutions (Python/81, /92, /134, /146) were labelled
  `parse-error (unexpected indent ...)` instead of `body-only`.
  The guard is now structural: the text must actually begin with whitespace.
  LABEL-ONLY. Both branches emitted the identical candidate
  `declaration + body_text`, so execution, scoring, return codes and the set of
  accepted candidates are unchanged — asserted by regression tests C11/C12/C13
  and by a 164-task byte-identity comparison.
  No change to anything written to stdout or stderr, so the recorded `note`
  field differs from v3.1 only in the NORMALIZE label for those four tasks.

The canonical body-only path is unchanged by all three revisions: an indented
fragment is still concatenated to `declaration` byte-for-byte.
"""
import argparse
import ast
import subprocess
import sys
from pathlib import Path

import pyarrow.parquet as pq

# Bumped on every change that alters evaluator behaviour or recorded labels.
# Read by the validation and freeze scripts so results are attributable to a
# revision without parsing this file's prose.
EVALUATOR_REVISION = "v3.2"

ROOT = Path(__file__).resolve().parent.parent
PQ = ROOT / "third_party/dataset/humanevalpack_python_test.parquet"
SANDBOX = ROOT / "scripts/sandbox.sh"
WORKDIR = ROOT / "pilot_workdir"   # the ONLY writable dir exposed to the sandbox
PY = sys.executable

HARNESS = r'''
import sys, json
payload = json.load(sys.stdin)
code, entry, test = payload["code"], payload["entry"], payload["test"]
ns = {}
try:
    exec(code, ns)
except Exception as e:
    print("IMPORT_ERROR:", type(e).__name__, e); sys.exit(3)
fn = ns.get(entry)
if fn is None:
    print("MISSING_ENTRY:", entry); sys.exit(4)
try:
    exec(test, ns)
except AssertionError:
    print("ASSERT_FAILED"); sys.exit(1)
except Exception as e:
    print("RUNTIME_ERROR:", type(e).__name__, e); sys.exit(2)
print("PASSED"); sys.exit(0)
'''


def load_task(task_id: str) -> dict:
    rows = pq.read_table(PQ).to_pylist()
    for r in rows:
        if r["task_id"] == task_id:
            return r
    raise SystemExit(f"unknown task: {task_id}")


def _sig_matches(found_def: ast.FunctionDef, expected_name: str,
                 expected_decl: str) -> tuple[bool, str]:
    """Check that found_def has the expected function name.

    We check name only (not full argument list) because the model sometimes
    omits type annotations or default values while keeping the logic correct.
    Signature mismatch is recorded but does not cause rejection on its own —
    the oracle will catch semantic mismatches.

    Returns (name_matches, note).
    """
    if found_def.name != expected_name:
        return False, f"name mismatch: got {found_def.name!r}, expected {expected_name!r}"
    return True, "name-match"


def _extract_body_source(full_source: str, func_def: ast.FunctionDef) -> str:
    """Return the source lines that form the body of func_def, VERBATIM.

    Line numbers come from the AST node: the body starts at
    func_def.body[0].lineno and ends at func_def.end_lineno (inclusive,
    Python 3.8+).

    The slice is returned unmodified — it is deliberately NOT dedented or
    re-indented. Python accepts any consistent indentation after the
    declaration's ':', so re-indenting buys nothing, and the previous
    dedent-then-indent pair was actively unsafe: textwrap.dedent() is a no-op
    whenever some line has less leading whitespace than the common prefix,
    which a multi-line string literal containing unindented text guarantees;
    textwrap.indent() then shifted every line regardless. The result was a
    double-indented body with rewritten string-literal contents that still
    executed, so it produced a plausible exit code instead of an error
    (defect C1, 2026-10-18 audit; regression tests C2/C3).

    Note: a single-line def ("def f(): return 1") has body[0].lineno equal to
    the def's own line, so the slice includes the "def" text and the candidate
    fails with IndentationError (rc 3). That is a format failure, which is what
    the contract prescribes for a non-body-only response.
    """
    lines = full_source.splitlines(keepends=True)
    # ast line numbers are 1-based
    body_start = func_def.body[0].lineno - 1
    body_end = func_def.end_lineno          # inclusive, 1-based → exclusive 0-based
    return "".join(lines[body_start:body_end])


def normalize_candidate(body_text: str, row: dict) -> tuple[str, str]:
    """Normalize the model output and construct the final executable candidate.

    Handles three cases:
      1. body_text is a valid body-only fragment (indented lines) — prepend
         declaration as-is.  ast.parse of indented lines yields SyntaxError
         ("unexpected indent"), which we detect and treat as body-only.
      2. body_text is a complete function definition with a compatible name —
         extract the body block and prepend the dataset declaration.
      3. body_text is invalid Python (not just indented), prose, or has an
         incompatible signature — prepend declaration anyway and let the
         sandbox report the error.

    Returns (code, normalization_note).
    normalization_note values:
      "body-only"            — body fragment (indented or empty), used as-is
      "full-def-extracted"   — full def found, body extracted, declaration replaced
      "full-def-sig-mismatch"— full def found but wrong function name, rejected
      "parse-error"          — ast.parse failed for reasons other than leading
                               indent (genuine syntax error in top-level code),
                               used as-is (sandbox will error)
      "prose"                — no code structure found; treated as body fragment
    """
    declaration = row["declaration"]
    entry_point = row["entry_point"]

    if not body_text.strip():
        return declaration + body_text, "body-only"

    # ── Try to parse the body_text as a Python module ─────────────────────────
    try:
        tree = ast.parse(body_text)
    except SyntaxError as e:
        # An "unexpected indent" error on a fragment that BEGINS with whitespace
        # means this is an indented body fragment — the correct input type.
        # Any other SyntaxError is a broken input.
        #
        # v3.2 (2026-10-18): the test used to be `e.lineno == 1`. That missed
        # fragments opening with a blank or under-indented line, because the
        # first *statement* then sits on line 2 or 3 while the error is still
        # "unexpected indent". Four dataset canonical solutions are shaped that
        # way (Python/81, /92, /134, /146) and were mislabelled `parse-error`
        # despite being ordinary body fragments — defect N1.
        #
        # The replacement is structural rather than merely dropping the lineno
        # guard. Dropping the guard alone would also label genuinely broken
        # input such as "x = 1\n    y = 2\n" as body-only; requiring the text to
        # actually start with whitespace does not (regression tests C11/C12).
        #
        # Label-only: this branch and the one below emit the identical candidate
        # `declaration + body_text`, so execution, scoring, return codes and the
        # set of accepted candidates are unchanged (regression test C13).
        msg = str(e)
        if "unexpected indent" in msg and body_text != body_text.lstrip():
            code = declaration + body_text
            return code, "body-only"
        # Genuine parse error in top-level code (e.g. truncated expression)
        code = declaration + body_text
        return code, f"parse-error ({msg[:80]})"

    # ── Look for a top-level function definition ───────────────────────────────
    func_defs = [node for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef)
                 and node.col_offset == 0]  # top-level only

    if not func_defs:
        # No function definition found — treat as body fragment
        code = declaration + body_text
        return code, "prose"

    # Use the first top-level function definition found (ast.walk yields
    # module-level statements in source order, so this is the textually first
    # top-level def).
    #
    # KNOWN LIMITATION (2026-10-18 audit, not fixed here): for the 4 tasks whose
    # `declaration` already contains a complete helper def — Python/10,
    # Python/32, Python/38, Python/50 — a full-def candidate has TWO top-level
    # defs and this selects the helper, producing full-def-sig-mismatch → rc 3.
    # Selecting the def whose name equals `entry_point` would fix it, but that
    # is an extraction-policy change and per pilot_protocol.md §5 requires a
    # documented protocol revision plus a re-run from scratch. It affects only
    # full-def output, which §4a already declares invalid; the canonical
    # body-only path (164/164) is unaffected.
    func_def = func_defs[0]
    name_ok, sig_note = _sig_matches(func_def, entry_point, declaration)

    if not name_ok:
        # Wrong function name — reject by concatenating the raw text.
        #
        # Observed return code is 3 (import_error), NOT 4 (missing_entry):
        # `declaration` already ends with ":\n", so appending a second
        # top-level `def` leaves the first def with no body and Python raises
        # IndentationError before the harness ever looks up the entry point.
        # rc 4 is reachable only if the candidate unbinds the entry point
        # itself. Verified by regression tests D5/D6. Both codes are failures,
        # so this path can never be scored as a pass.
        code = declaration + body_text
        return code, f"full-def-sig-mismatch ({sig_note})"

    # ── Extract body and use the dataset declaration ───────────────────────────
    try:
        body_block = _extract_body_source(body_text, func_def)
    except Exception as exc:
        # Extraction failed — fall back to raw concatenation
        code = declaration + body_text
        return code, f"full-def-extraction-failed ({exc})"

    code = declaration + body_block
    return code, "full-def-extracted"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--body-file", required=True)
    ap.add_argument("--timeout", type=float, default=10.0)
    args = ap.parse_args()

    row = load_task(args.task_id)
    body_text = Path(args.body_file).read_text()

    code, norm_note = normalize_candidate(body_text, row)

    import json
    payload = json.dumps({
        "code": code,
        "entry": row["entry_point"],
        "test": row["test"],
    })

    # Emit normalization note so pilot_runner.py captures it in stderr
    print(f"NORMALIZE: {norm_note}", file=sys.stderr, flush=True)

    WORKDIR.mkdir(exist_ok=True)
    # /usr/bin/python3, NOT the venv python: /home is not mounted in the sandbox.
    cmd = [str(SANDBOX), str(WORKDIR), "/usr/bin/python3", "-I", "-c", HARNESS]
    try:
        p = subprocess.run(cmd, input=payload, capture_output=True, text=True,
                           timeout=args.timeout)
        out = (p.stdout + p.stderr).strip()[:500]
        if out:
            print(out, file=sys.stderr, flush=True)
        return p.returncode if p.returncode in (0, 1, 2, 3, 4) else 5
    except subprocess.TimeoutExpired:
        print("TIMEOUT", file=sys.stderr, flush=True)
        return 5


if __name__ == "__main__":
    sys.exit(main())
