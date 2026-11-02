#!/usr/bin/env python3
"""pilot_runner.py — LocalAgentBench A/B/C pilot orchestrator.

v3.3 (2026-10-18) — the arms are FEEDBACK conditions. Grammar-constrained
decoding is no longer an experimental variable; see reports/pilot_protocol.md §9.
  A: blind resampling      — retry the task with NO prior candidate and NO diagnostic
  B: placebo control       — prior candidate + generic failure notice, no diagnostic
  C: execution-feedback    — prior candidate + permitted execution diagnostic
All three arms: same prompt template, same UNCONSTRAINED decoding (no grammar in
any arm), same generation budget, same output contract, same evaluator, 3 attempts.
The first attempt of every arm is byte-identical (the base task prompt), so the
arms differ only in what they are given for attempts 2 and 3.

Historical (v3.2 and earlier): A = naive, B = + GBNF grammar, C = B + feedback.
Those runs live in results/pilot_v2 and results/pilot_v3[_2] and are frozen.

All generation goes through llama-completion (llama-cli in this commit is
interactive-only when stdin is closed — see reports/inference_baseline.md).
Invocation flags come from `llama-completion --help` of our own build (saved at
reports/llama_completion_help.txt): `--no-conversation` (the single-dash
`-no-conversation` is NOT a valid argument and caused the invalid first run),
`--single-turn`, and `--no-display-prompt` (suppresses the prompt echo so stdout
is pure completion).

Raw artifacts land in <OUT>/<task>_<config>/.

Usage: pilot_runner.py [--configs ABC] [--tasks Python/0,...] [--out DIR]
                       [--dry-run] [--force]
"""
import argparse
import ast
import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "third_party/llama.cpp/build/bin/llama-completion"
MODEL = ROOT / "models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
GRAMMAR = ROOT / "scripts/response.gbnf"
PQ = ROOT / "third_party/dataset/humanevalpack_python_test.parquet"
EVAL = ROOT / "scripts/evaluate_candidate.py"
DEFAULT_OUT = ROOT / "results/pilot_v2"
FROZEN_SELECTION = ROOT / "results/pilot/task_selection.json"   # frozen pre-run
WORKDIR = ROOT / "pilot_workdir"
VENV_PY = ROOT / ".venv/bin/python"
TIME_BIN = Path("/usr/bin/time")

# Frozen result directories that must never be written to again.
#
# run_config() does `shutil.rmtree(tdir)` on an existing task directory before
# regenerating it, so pointing --out at one of these would silently destroy
# frozen evidence — including results/pilot_v3/, which reports must keep
# referencing unchanged. guard_out_root() refuses before anything is created.
PROTECTED_RESULTS = (
    ROOT / "results/pilot",
    ROOT / "results/pilot_v2",
    ROOT / "results/pilot_v3",
    ROOT / "results/pilot_v3_2",
)


def guard_out_root(out_root: Path, force: bool = False) -> Path:
    """Refuse to run where existing results would be overwritten or deleted.

    Returns the resolved output root. Exits non-zero rather than proceeding if
      * it is, contains, or is contained by a PROTECTED_RESULTS directory, or
      * it already exists and is non-empty (unless --force).
    """
    resolved = out_root.resolve()
    for prot in PROTECTED_RESULTS:
        p = prot.resolve()
        if resolved == p or p in resolved.parents or resolved in p.parents:
            raise SystemExit(
                "REFUSING TO RUN: --out %s would write into frozen results %s.\n"
                "  run_config() deletes an existing task directory before\n"
                "  regenerating it, so this would destroy evidence that\n"
                "  reports/pilot_results.md and reports/evaluator_validation.md\n"
                "  cite. Choose a new directory, e.g. results/pilot_v3_3/."
                % (resolved, p))
    if resolved.exists() and any(resolved.iterdir()) and not force:
        raise SystemExit(
            "REFUSING TO RUN: --out %s already exists and is not empty.\n"
            "  Existing task directories would be deleted and regenerated.\n"
            "  Use a fresh directory, or pass --force to overwrite knowingly."
            % resolved)
    return resolved

# frozen settings (pilot_protocol.md)
SEED = 42
CTX = 4096
THREADS = 4
N_PREDICT = 512
TEMP = 0.0
TEST_TIMEOUT = 10.0
MAX_ATTEMPTS = 3

# ---------------------------------------------------------------------------
# Freeze attribution (protocol §8/§9). Recorded in every result.json so a
# pilot can never be silently mistaken for one produced under a different
# prompt, decoding configuration or evaluator revision.
# ---------------------------------------------------------------------------


def _read_evaluator_revision() -> str:
    """Read EVALUATOR_REVISION from the evaluator source without importing it."""
    m = re.search(r'^EVALUATOR_REVISION\s*=\s*"([^"]+)"',
                  EVAL.read_text(errors="replace"), re.M)
    return m.group(1) if m else "unknown"


EVALUATOR_REVISION = _read_evaluator_revision()

def _py() -> str:
    """Use the repo venv if present, else current interpreter."""
    venv = ROOT / ".venv/bin/python"
    return str(venv) if venv.exists() else sys.executable



def load_tasks(task_ids: list[str]) -> list[dict]:
    rows = {r["task_id"]: r for r in pq.read_table(PQ).to_pylist()}
    return [rows[t] for t in task_ids]


def select_tasks() -> list[str]:
    """Frozen deterministic selection: every 16th id = Python/{0,16,...,144}."""
    return [f"Python/{i}" for i in range(0, 160, 16)]


def generate(prompt: str, grammar: bool, tag: str, model: Path | None = None) -> dict:
    """One generation pass. Returns raw text + timings + exit code.

    model defaults to the module-level MODEL (1.5B historical default); callers
    such as the canary pass an explicit artifact path (e.g. F16/Q8 GGUF).
    """
    model_path = MODEL if model is None else model
    cmd = [str(BIN), "-m", str(model_path), "-p", prompt,
           "-n", str(N_PREDICT), "-c", str(CTX), "-t", str(THREADS),
           "--temp", str(TEMP), "--seed", str(SEED), "-ngl", "0",
           "--no-conversation", "--single-turn", "--no-display-prompt",
           "--log-file", str(tag) + ".log"]
    if grammar:
        cmd += ["--grammar-file", str(GRAMMAR)]

    use_time = TIME_BIN.exists()
    if use_time:
        cmd = [str(TIME_BIN), "-v", "-o", str(tag) + ".time"] + cmd

    t0 = time.monotonic()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=600, stdin=subprocess.DEVNULL)
        rc, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        rc = 124
        out = e.stdout or ""
        err = e.stderr or ""
        if isinstance(out, bytes):
            out = out.decode(errors="replace")
        if isinstance(err, bytes):
            err = err.decode(errors="replace")
    wall = time.monotonic() - t0

    peak_rss = None
    tfile = Path(str(tag) + ".time")
    if use_time and tfile.exists():
        m = re.search(r"Maximum resident set size \(kbytes\): (\d+)",
                      tfile.read_text(errors="replace"))
        if m:
            peak_rss = int(m.group(1))

    # Real token counts, read from llama.cpp's own perf line. Input tokens are
    # the arms' main cost difference (a repair prompt is longer than the base),
    # so they are measured rather than estimated.
    def _num(pattern):
        mm = re.search(pattern, err)
        return int(mm.group(1)) if mm else None

    return {"rc": rc, "stdout": out, "stderr": err,
            "wall_s": round(wall, 2), "peak_rss_kb": peak_rss,
            "prompt_tokens": _num(r"prompt eval time =.*?/\s+(\d+) tokens"),
            "completion_tokens": _num(r"\beval time =.*?/\s+(\d+) runs"),
            "cmd": cmd}


def extract_body(raw: str) -> tuple[str | None, str]:
    """Returns (body, note). Identical post-processing for A, B and C.

    The response is parsed with a real JSON parser (json.JSONDecoder.raw_decode)
    rather than by regex. Candidate object starts are found by scanning for '{';
    each successfully decoded object is consumed whole, so a nested object can
    never shadow the object enclosing it.

    LAST match wins, not first. Decoding is autoregressive, so anything the
    model emits before its answer is preamble — a restatement of the buggy body
    supplied in the prompt, or the prompt's own one-shot example object. Under
    first-match those shadowed the model's real fix (defect A, 2026-10-18 audit;
    reproduced from the real results/pilot_v3/Python_0_A stdout by regression
    test A1). A trailing object truncated by --n-predict fails to parse and is
    therefore ignored, so the last COMPLETE object wins.

    The regex is used only as a last-resort code-fence strip for config A's
    grammar-free fallback.
    """
    text = raw.strip()
    if not text:
        return None, "malformed: empty"

    decoder = json.JSONDecoder()
    bodies: list[str] = []
    saw_nonstring_fix = False
    saw_empty_fix = False
    last_err = "no '{' in output"
    idx = text.find("{")
    while idx != -1:
        try:
            obj, end = decoder.raw_decode(text[idx:])
        except ValueError as e:
            last_err = str(e).split("\n")[0]
            idx = text.find("{", idx + 1)
            continue
        if isinstance(obj, dict) and "fix" in obj:
            val = obj["fix"]
            if not isinstance(val, str):
                saw_nonstring_fix = True
            elif not val.strip():
                saw_empty_fix = True
            else:
                bodies.append(val)
        idx = text.find("{", idx + end)

    if bodies:
        return bodies[-1], "ok-json"
    if saw_nonstring_fix:
        return None, "malformed: fix not a string"
    if saw_empty_fix:
        return None, "malformed: empty fix"

    # No parseable {"fix": ...}. Grammar-free fallback (config A only, but the
    # same code path runs for every config).
    fence = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    candidate = fence.group(1) if fence else text
    candidate = candidate.strip()
    if "def " in candidate:
        return candidate, "ok-raw-fallback"
    return None, f"malformed: json error ({last_err}) and no code fallback"


# ---------------------------------------------------------------------------
# v3.3 output contract (pilot_protocol.md §9): ONE complete repaired function
# definition, raw Python source, nothing else. Chosen because the v3.2 pilot
# showed the JSON wrapper is the failure point, not the fix: unconstrained arm A
# emitted complete bodies with unescaped newlines (extraction failures) while the
# grammar-constrained arms emitted escaped but TRUNCATED bodies (rc=3). The same
# task failed in opposite ways depending on the arm, which confounds any A-vs-B/C
# comparison. Raw source removes the serialisation layer entirely: a multi-line
# function body is just text, with no escaping for the model to get wrong.
# ---------------------------------------------------------------------------
PROMPT_TEMPLATE_V3_3 = r"""Below is a Python function with a bug.

Reply with EXACTLY ONE complete Python function definition: the full corrected
`{entry}` function, including its `def {entry}(...)` line and its indented body.

Return raw Python source only. Do not add any explanation, comment, markdown
code fence, JSON, or any second function.

Example:

Given:
def double(x):
    return x + x + x

Correct response:
def double(x):
    return x * 2

Now fix this function:

{instruction}

{declaration}
{buggy}"""

# HISTORICAL — documents the v3.2 arm design, superseded for v3.3 by
# pilot_protocol.md §9. Kept attached to the frozen v3.2 template below because
# regression suite F still tests exactly that template.
#
# Identical prompt for A, B and C (pilot_protocol.md): the JSON contract is
# described in the prompt for ALL configs; the ONLY A-vs-B difference is the
# GBNF decode-time constraint.
#
# v3 change (2026-10-15): one-shot example added to show body-only code output.
# The example task is synthetic (not from the pilot set).
# The # BUGGY: marker has been removed; the buggy code is presented directly.
#
# v3.2 change (2026-10-18): the template is now a RAW string.
# It was previously a non-raw triple-quoted string, so the `\n` inside the
# one-shot example was consumed by Python's own string-literal parser and
# became a REAL newline before .format() ever ran. The model was therefore
# shown an invalid JSON example:
#     {"fix": "    return x * 2
#     "}
# and imitated it. Config A is grammar-free, so it reproduced the raw control
# character and every such attempt was rejected as `Invalid control character`.
# Configs B and C are constrained by scripts/response.gbnf, whose `char` rule
# excludes raw control characters, so they could not reproduce it — which made
# the defect a one-sided bias against arm A. Measured in pilot_v3: 2 of 10
# config-A attempts were destroyed this way, and one of them (Python/48 A a1)
# contained a fix that scores rc=0. See reports/evaluator_validation.md §5.2.
#
# As a raw string the template reads exactly as the model receives it, and the
# example renders as the valid JSON `{"fix": "    return x * 2\n"}`. Regression
# suite F asserts this against the RENDERED prompt, not the source spelling.
# Kept verbatim so the v3.2-era prompt assertions (regression suite F) can still
# be evaluated against the exact template that produced results/pilot_v3_2/, even
# though no v3.3 arm uses it. It is the frozen string from
# results/evaluator_repair/v32/freeze_fingerprint_v3_2.json
# (prompt_template_string_sha256 3074dd57…60fe0d).
PROMPT_TEMPLATE_V3_2 = r"""Below is a Python function with a bug. Return ONLY a JSON object with a single key "fix" whose value is the corrected function body (the indented lines inside the def block, not the def line itself). Do not explain or add anything else.

Example:
Given:
def double(x):
    return x + x + x

Correct response:
{{"fix": "    return x * 2\n"}}

Now fix this function:

{instruction}

{declaration}
{buggy}"""

PROMPT_TEMPLATE = PROMPT_TEMPLATE_V3_3
PROMPT_TEMPLATE_SHA256 = hashlib.sha256(PROMPT_TEMPLATE.encode()).hexdigest()
PROMPT_TEMPLATE_V3_2_SHA256 = hashlib.sha256(PROMPT_TEMPLATE_V3_2.encode()).hexdigest()
PROTOCOL_REVISION = "v3.3"
# The arms differ only by feedback text. These markers must never appear in the
# shared first-attempt prompt; they are asserted on by regression suite G.
PLACEBO_NOTICE = ("# Your previous attempt did not pass the tests. "
                  "No further information is available.")
FEEDBACK_HEADER = "# Your previous attempt:"


def render_base_prompt(task: dict) -> str:
    """The attempt-1 prompt. Byte-identical across A, B and C."""
    return PROMPT_TEMPLATE.format(
        entry=task["entry_point"], instruction=task["instruction"],
        declaration=task["declaration"], buggy=task["buggy_solution"])


def _decl_target_def(declaration: str):
    """The def header the dataset declares as the entry point.

    163 of the 164 `declaration` strings are an incomplete module (a bare
    `def name(...):` header with no body), so ast.parse fails by construction;
    the regex fallback reads the header text instead. This is used for
    signature RECORDING only — the executable candidate is always built as
    `declaration + <verbatim body block>` by evaluate_candidate.py, so the
    declaration's own annotations and defaults are what run.
    """
    try:
        tree = ast.parse(declaration)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                return node.args
    except SyntaxError:
        pass
    m = None
    for m in re.finditer(r"^def\s+(\w+)\s*\((.*)\)\s*(->.*)?:\s*$",
                         declaration, re.M):
        pass
    return m.group(2) if m else None


def extract_definition(raw: str, task: dict) -> tuple[str | None, dict]:
    """v3.3 contract extraction. Returns (source_or_None, info).

    Frozen policy (pilot_protocol.md §9.2). NO semantic repair is performed: no
    fence stripping, no code recovery from prose, no statement inference, no
    dedent/re-indent, no import injection, no selection of a favourable function
    when several are offered.

      1. empty                        -> malformed_output (kind=empty)
      2. whole response fails to parse
                                      -> rejected (kind=unparseable); includes
                                         markdown fences and prose, which are not
                                         valid Python and are NOT recovered from
      3. no top-level def             -> rejected (kind=no-target-def)
      4. >1 top-level def             -> rejected (kind=multiple-defs); the contract
                                         allows exactly one and choosing between them
                                         would be a semantic decision
      5. the one def's name != entry  -> rejected (kind=name-mismatch)
      else                            -> ok-def, the def sliced VERBATIM by its AST
                                         line span, plus recorded compliance flags
                                         (has_fence, extra_top_level, arglist_match)

    Compliance flags are recorded but do not change the verdict: a fenced or
    prose-wrapped answer is already rejected at step 2 because fences and prose
    do not parse, so the flags only ever appear on accepted candidates (e.g. a
    trailing comment line, which does parse).
    """
    info = {"kind": None, "has_fence": False, "extra_top_level": [],
            "arglist_match": None, "name": None}
    text = raw.strip()
    info["has_fence"] = "```" in text
    if not text:
        info["kind"] = "empty"
        return None, info

    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        info["kind"] = "unparseable"
        info["parse_error"] = f"{type(e).__name__}: {e}"
        return None, info

    defs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    nondef = [n for n in tree.body
              if not isinstance(n, (ast.FunctionDef, ast.Expr))]
    info["extra_top_level"] = [type(n).__name__ for n in nondef]
    if not defs:
        info["kind"] = "no-target-def"
        return None, info
    if len(defs) > 1:
        info["kind"] = "multiple-defs"
        info["names"] = [d.name for d in defs]
        return None, info

    d = defs[0]
    info["name"] = d.name
    if d.name != task["entry_point"]:
        info["kind"] = "name-mismatch"
        return None, info

    lines = text.splitlines(keepends=True)
    start = d.lineno - 1
    end = d.end_lineno                    # inclusive 1-based -> exclusive 0-based
    src = "".join(lines[start:end])
    if not src.strip():
        info["kind"] = "empty-def-source"
        return None, info

    dargs = _decl_target_def(task["declaration"])
    if isinstance(dargs, ast.arguments):
        info["arglist_match"] = (
            ast.unparse(dargs) == ast.unparse(d.args))
    elif dargs is not None:
        info["arglist_match"] = (
            re.sub(r"\s+", "", dargs) == re.sub(r"\s+", "", ast.unparse(d.args)))
    info["kind"] = "ok-def"
    return src, info


def evaluate(task: dict, body: str) -> dict:
    """Run the ground-truth test inside the sandbox.

    The body is written to a host-side file that is the only writable path the
    sandbox sees; the oracle test travels over stdin and is never model-writable.
    """
    cand = WORKDIR / "candidate.py"
    WORKDIR.mkdir(exist_ok=True)
    cand.write_text(body)
    try:
        p = subprocess.run(
            [_py(), str(EVAL), "--task-id", task["task_id"],
             "--body-file", str(cand), "--timeout", str(TEST_TIMEOUT)],
            capture_output=True, text=True, timeout=TEST_TIMEOUT + 15)
        rc = p.returncode
        note = (p.stdout + p.stderr).strip()[:500]
    except subprocess.TimeoutExpired:
        rc, note = 5, "HARNESS_TIMEOUT"
    cat = {0: "pass", 1: "assertion_fail", 2: "runtime_error",
           3: "import_error", 4: "missing_entry", 5: "harness_error"}.get(rc, "unknown")
    return {"rc": rc, "category": cat, "note": note}


def build_repair_prompt(config: str, base_prompt: str, attempt_no: int,
                        src: str | None, ev: dict) -> str:
    """The attempt-N>1 prompt for each feedback condition. Frozen policy §9.3.

    A blind      : the base task prompt, unchanged. No prior candidate, no diagnostic.
    B placebo    : base + the prior candidate + a generic failure notice, no
                   execution information of any kind.
    C feedback   : base + the prior candidate + the permitted execution diagnostic
                   (oracle category and sandbox output).

    Only the text after base_prompt differs; every arm re-states the same output
    contract so format instructions cannot drift between arms.
    """
    prior = src if src else "<no usable output>"
    tail = (
        "\n\nReply with EXACTLY ONE complete Python function definition: the full "
        "corrected function, including its `def` line and its indented body. Return "
        "raw Python source only; no explanation, comment, code fence, JSON, or "
        "second function."
    )
    if config == "A":
        return base_prompt
    if config == "B":
        return (base_prompt
                + "\n\n" + PLACEBO_NOTICE
                + "\n\n# Your previous attempt (attempt %d):\n%s" % (attempt_no, prior)
                + tail)
    if config == "C":
        return (base_prompt
                + "\n\n" + FEEDBACK_HEADER + " (attempt %d)\n%s" % (attempt_no, prior)
                + "\n\nGround-truth test result: %s" % ev.get("category")
                + "\nTest output:\n%s" % ev.get("note")
                + tail)
    raise ValueError("unknown config %r" % config)


def run_config(task: dict, config: str, out_root: Path) -> dict:
    tid = task["task_id"].replace("/", "_")
    tdir = out_root / f"{tid}_{config}"
    if tdir.exists():
        shutil.rmtree(tdir)
    tdir.mkdir(parents=True)

    base_prompt = render_base_prompt(task)
    prompt = base_prompt
    # v3.3: no arm is grammar-constrained. Decoding settings are a controlled
    # variable, not a treatment; the treatment is the feedback condition only.
    grammar = False
    attempts = []
    initial_success = False
    final_success = False

    for attempt_no in range(1, MAX_ATTEMPTS + 1):
        g = generate(prompt, grammar, str(tdir / f"gen_a{attempt_no}"))
        src, info = extract_definition(g["stdout"], task)
        rec = {"attempt": attempt_no,
               "gen": {k: g[k] for k in ("rc", "wall_s", "peak_rss_kb",
                                         "prompt_tokens", "completion_tokens")},
               "prompt_chars": len(prompt),
               "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
               "extract": info["kind"],
               "extract_info": info,
               "gen_stdout": g["stdout"],
               "gen_stderr_tail": g["stderr"][-2000:]}
        (tdir / f"raw_a{attempt_no}.txt").write_text(g["stdout"])
        if src is None:
            rec["eval"] = {"rc": None, "category": "extraction_rejected",
                           "note": info.get("parse_error") or info["kind"]}
        else:
            rec["eval"] = evaluate(task, src)
            (tdir / f"def_a{attempt_no}.py").write_text(src)
        attempts.append(rec)
        passed = rec["eval"]["rc"] == 0
        if attempt_no == 1:
            initial_success = passed
        if passed:
            final_success = True
            break

        # All three arms retry with the same budget; they differ only in the
        # feedback text. The exact prompt sent is recorded so the trace proves
        # which condition each arm was in. Only a prompt that WILL be used is
        # recorded — after the last allowed attempt there is no next prompt.
        if attempt_no == MAX_ATTEMPTS:
            break
        repair = build_repair_prompt(config, base_prompt, attempt_no,
                                     src, rec["eval"])
        rec["repair_prompt_sent"] = repair
        prompt = repair

    def _tot(key):
        vals = [a["gen"].get(key) for a in attempts]
        if not any(v is not None for v in vals):
            return None
        return sum(v for v in vals if v is not None)

    result = {
        "task_id": task["task_id"], "config": config,
        "initial_success": initial_success, "final_success": final_success,
        "attempts_used": len(attempts),
        "attempt_log": attempts,
        # Measured input/output token cost of this arm on this task. Arms are
        # expected to differ here: that difference IS the treatment's cost.
        "token_cost": {"prompt_tokens": _tot("prompt_tokens"),
                       "completion_tokens": _tot("completion_tokens")},
        "settings": {"seed": SEED, "ctx": CTX, "threads": THREADS,
                     "n_predict": N_PREDICT, "temp": TEMP,
                     "grammar": grammar, "ngl": 0, "max_attempts": MAX_ATTEMPTS,
                     "feedback_condition": {"A": "blind_resampling",
                                            "B": "placebo_control",
                                            "C": "execution_feedback"}[config],
                     "flags": ["--no-conversation", "--single-turn",
                               "--no-display-prompt"],
                     # Attribution, so a result can never be silently mistaken
                     # for one produced under a different prompt or evaluator.
                     "protocol_revision": PROTOCOL_REVISION,
                     "evaluator_revision": EVALUATOR_REVISION,
                     "prompt_template_sha256": PROMPT_TEMPLATE_SHA256,
                     "prompt_sha256": hashlib.sha256(
                         base_prompt.encode()).hexdigest()},
    }
    (tdir / "result.json").write_text(json.dumps(result, indent=1))
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", default="ABC")
    ap.add_argument("--tasks", default="",
                    help="comma-separated task ids; default = frozen selection")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="allow writing into an existing non-empty --out "
                         "(never allows a PROTECTED_RESULTS directory)")
    args = ap.parse_args()

    out_root = guard_out_root(Path(args.out), args.force)
    task_ids = [t.strip() for t in args.tasks.split(",") if t.strip()] \
        or select_tasks()

    tasks = load_tasks(task_ids)
    if args.dry_run:
        # Nothing is created, not even task_selection.json: a dry run that
        # populated --out would make the next real run fail guard_out_root's
        # "directory already exists and is not empty" check.
        print("would run:", task_ids, "configs:", args.configs, "->", out_root)
        return

    out_root.mkdir(parents=True, exist_ok=True)
    sel_path = out_root / "task_selection.json"
    if not sel_path.exists():
        if FROZEN_SELECTION.exists() and not args.tasks:
            # carry the pre-generation frozen selection forward verbatim
            shutil.copyfile(FROZEN_SELECTION, sel_path)
        else:
            sel_path.write_text(json.dumps(
                {"method": "every 16th numeric suffix over sorted Python/0..163",
                 "task_ids": task_ids}, indent=1))

    summary = []
    for config in args.configs:
        for task in tasks:
            t0 = time.monotonic()
            r = run_config(task, config, out_root)
            r["wall_s_total"] = round(time.monotonic() - t0, 1)
            summary.append(r)
            print(f"{config} {r['task_id']}: initial={r['initial_success']} "
                  f"final={r['final_success']} attempts={r['attempts_used']} "
                  f"wall={r['wall_s_total']}s", flush=True)
            subprocess.run(["free", "-h"], capture_output=True)

    (out_root / "summary.json").write_text(json.dumps(summary, indent=1))
    print("SUMMARY written:", out_root / "summary.json")


if __name__ == "__main__":
    main()
