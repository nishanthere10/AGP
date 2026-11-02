"""Evaluator end-to-end regression suite (portable, no model, no sandbox).

Tests the EXACT pipeline: raw stdout -> extract_body -> normalize ->
HARNESS exec + score. Loads function defs verbatim from repo source so
it tracks the canonical evaluator without modifying it.

Run: python scripts/test_evaluator_regression.py  (exit 0 = all pass)
"""
import ast
import hashlib
import inspect
import json
import subprocess
import sys
from pathlib import Path

REPO = Path("C:/Users/kirti/coding/AGP")
PILOT_RUNNER = REPO / "scripts" / "pilot_runner.py"
EVALUATOR = REPO / "scripts" / "evaluate_candidate.py"
PARQUET_CANDIDATES = [
    REPO / "third_party" / "dataset" / "humanevalpack_python_test.parquet",
    Path("/home/aaksh/projects/LocalAgentBench/third_party/dataset/humanevalpack_python_test.parquet"),
]

PASS = 0
FAIL = 0
SKIP = 0
FAILURES = []


def record(ok, name, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        FAILURES.append((name, detail))
        print(f"  FAIL  {name}")
        if detail:
            print(f"        {detail[:400]}")


def record_skip(name, reason):
    global SKIP
    SKIP += 1
    print(f"  SKIP  {name} [{reason}]")


def _exec_defs(source, want):
    tree = ast.parse(source)
    keep = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in want:
            keep.append(node)
        elif isinstance(node, ast.Assign):
            tg = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if any(t in want for t in tg):
                keep.append(node)
    mod = ast.Module(body=keep, type_ignores=[])
    ns = {}
    exec("import json, re, ast, textwrap", ns)
    exec(compile(mod, "<extracted>", "exec"), ns)
    missing = [w for w in want if w not in ns]
    if missing:
        raise RuntimeError(f"could not extract {missing}")
    return ns


_pilot_src = PILOT_RUNNER.read_text(encoding="utf-8", errors="replace")
_eval_src = EVALUATOR.read_text(encoding="utf-8", errors="replace")
extract_body = _exec_defs(_pilot_src, {"extract_body"})["extract_body"]
_eval_ns = _exec_defs(_eval_src, {"normalize_candidate", "_sig_matches",
                                  "_extract_body_source", "HARNESS"})
normalize_candidate = _eval_ns["normalize_candidate"]
HARNESS = _eval_ns["HARNESS"]
fp = hashlib.sha256((_pilot_src[_pilot_src.find("def extract_body"):][:3000]
                     + _eval_src[_eval_src.find("def normalize_candidate"):][:6000]
                     ).encode()).hexdigest()[:16]
print(f"evaluator fp={fp} normalize_present={'def normalize_candidate' in _eval_src}")
print(f"extract_body signature: {inspect.signature(extract_body)}")
print("(existing test_extract_body.py calls it with 2 args -> stale, see report)")
def run_harness(code, entry, test, timeout=15):
    try:
        p = subprocess.run([sys.executable, "-I", "-c", HARNESS],
                           input=json.dumps({"code": code, "entry": entry, "test": test}),
                           capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()[:500]
    except subprocess.TimeoutExpired:
        return 5, "TIMEOUT"


def full_pipeline(raw_stdout, row):
    body, extract_note = extract_body(raw_stdout)
    if body is None:
        return {"body": None, "extract": extract_note, "rc": None,
                "category": "malformed_output", "note": extract_note}
    code, norm_note = normalize_candidate(body, row)
    rc, out = run_harness(code, row["entry_point"], row["test"])
    cat = {0: "pass", 1: "assertion_fail", 2: "runtime_error",
           3: "import_error", 4: "missing_entry", 5: "harness_error"}.get(rc, "unknown")
    return {"body": body, "extract": extract_note, "norm": norm_note,
            "rc": rc, "category": cat, "note": out, "code": code}


TASK_DOUBLE = {
    "task_id": "Synthetic/double", "entry_point": "double",
    "declaration": "def double(x):\n",
    "test": "assert double(2) == 4\nassert double(0) == 0\nassert double(-3) == -6\n",
    "canonical_solution": "    return x * 2\n",
    "buggy_solution": "    return x + 1\n",
}

print("=" * 64)
print("A. Extraction formats (raw stdout -> extract_body)")
print("=" * 64)
r = full_pipeline(json.dumps({"fix": TASK_DOUBLE["canonical_solution"]}), TASK_DOUBLE)
record(r["rc"] == 0, "A1 json body-only canonical passes",
       f"rc={r['rc']} {r.get('note')} extract={r.get('extract')} norm={r.get('norm')}")
r = full_pipeline(json.dumps({"fix": "def double(x):\n    return x * 2\n"}), TASK_DOUBLE)
record(r["rc"] == 0 and r.get("norm") == "full-def-extracted",
       "A2 json full-def normalized to pass (auditable note)",
       f"rc={r['rc']} norm={r.get('norm')} note={r.get('note')}")
fenced = "```python\ndef double(x):\n    return x * 2\n```"
body, note = extract_body(fenced)
record(body is not None and "return x * 2" in body, "A3 markdown fence extracts code",
       f"body={body!r} note={note}")
raw = "def double(x):\n    return x * 2"
body, note = extract_body(raw)
record(body is not None, "A4 raw code with def extracts", f"body={body!r} note={note}")
body, note = extract_body("    return x * 2\n")
record(body is None and note.startswith("malformed"),
       "A5 raw body-only w/o def is malformed (documents fallback gap)",
       f"body={body!r} note={note}")
echo = ('prompt text {"fix": "<the complete corrected function body>"} assistant '
        + json.dumps({"fix": TASK_DOUBLE["canonical_solution"]}))
body6, note6 = extract_body(echo)
# KNOWN BUG (auditor §I-1, progress_audit.md): extractor scans left-to-right
# and returns the FIRST {"fix":...} (the echoed prompt placeholder), not the
# model's answer. --no-display-prompt suppresses the echo in production runs,
# which is why the pilot still worked. Do NOT fix the evaluator here per task
# constraints; pin the behavior so any future change is deliberate.
record(body6 == "<the complete corrected function body>",
       "A6 echo+placeholder returns FIRST match (known auditor bug, pinned)",
       f"body={body6!r} note={note6}")
r = full_pipeline(json.dumps({"fix": "def double(x):\n    return x * 2\n"}), TASK_DOUBLE)
record(r["rc"] == 0, "A7 function-signature JSON format handled",
       f"rc={r['rc']} norm={r.get('norm')}")
print("=" * 64)
print("B. Negative controls (must NOT pass)")
print("=" * 64)
r = full_pipeline("", TASK_DOUBLE)
record(r["rc"] is None and r["category"] == "malformed_output", "B1 empty -> malformed, no eval", f"{r}")
r = full_pipeline("no json here, just words", TASK_DOUBLE)
record(r["rc"] is None, "B2 prose w/o code -> malformed, no eval", f"{r}")
r = full_pipeline(json.dumps({"fix": "The bug is it uses + instead of *. Fix with multiplication."}), TASK_DOUBLE)
record(r["rc"] is not None and r["rc"] != 0, "B3 prose fix rejected",
       f"rc={r['rc']} cat={r['category']} norm={r.get('norm')}")
r = full_pipeline(json.dumps({"fix": "    return x *\n"}), TASK_DOUBLE)
record(r["rc"] is not None and r["rc"] != 0, "B4 syntax error rejected",
       f"rc={r['rc']} cat={r['category']}")
r = full_pipeline(json.dumps({"fix": "    return x + 1\n"}), TASK_DOUBLE)
record(r["rc"] == 1, "B5 wrong fix -> assertion_fail, not pass", f"rc={r['rc']} cat={r['category']}")
r = full_pipeline(json.dumps({"fix": TASK_DOUBLE["buggy_solution"]}), TASK_DOUBLE)
record(r["rc"] != 0, "B6 buggy solution not accepted", f"rc={r['rc']}")
r = full_pipeline(json.dumps({"fix": "def triple(x):\n    return x * 3\n"}), TASK_DOUBLE)
record(r["rc"] is not None and r["rc"] != 0, "B7 wrong-name def rejected",
       f"rc={r['rc']} cat={r['category']} norm={r.get('norm')}")
body, note = extract_body(json.dumps({"fix": 42}))
record(body is None and "not a string" in note, "B8 non-string fix rejected", f"body={body!r} note={note}")
body, note = extract_body(json.dumps({"fix": "   "}))
record(body is None and "empty fix" in note, "B9 empty fix rejected", f"body={body!r} note={note}")
r = full_pipeline(json.dumps({"fix": "    return 1 // 0\n"}), TASK_DOUBLE)
record(r["rc"] == 2, "B10 runtime error categorized, not passed", f"rc={r['rc']} cat={r['category']}")
canon_code = TASK_DOUBLE["declaration"] + TASK_DOUBLE["canonical_solution"]
norm_code, _ = normalize_candidate("def double(x):\n    return x * 2\n", TASK_DOUBLE)
ns1, ns2 = {}, {}
exec(canon_code, ns1)
exec(norm_code, ns2)
same = all(ns1["double"](x) == ns2["double"](x) for x in (-3, 0, 2, 7))
record(same, "B11 normalization preserves semantics on correct fix", "")
print("=" * 64)
print("C. Reference fixes (dataset-grounded where available)")
print("=" * 64)
r = full_pipeline(json.dumps({"fix": TASK_DOUBLE["canonical_solution"]}), TASK_DOUBLE)
record(r["rc"] == 0, "C0 synthetic canonical passes", f"rc={r['rc']}")
r = full_pipeline(json.dumps({"fix": TASK_DOUBLE["buggy_solution"]}), TASK_DOUBLE)
record(r["rc"] != 0, "C0 synthetic buggy fails", f"rc={r['rc']}")
parquet = next((p for p in PARQUET_CANDIDATES if p.exists()), None)
if parquet is None:
    record_skip("C1 all-164 canonical fixes",
                "parquet absent in this checkout; run on WSL host with dataset")
else:
    try:
        import pyarrow.parquet as pq
        rows = pq.read_table(parquet).to_pylist()
        ok_load = True
    except Exception as e:
        record_skip("C1 all-164 canonical fixes", f"pyarrow load failed: {e}")
        rows = []
        ok_load = False
    if ok_load and rows:
        assert len(rows) == 164, f"expected 164 rows, got {len(rows)}"
        failed_ids = []
        passed_count = 0
        for row in rows:
            res = full_pipeline(json.dumps({"fix": row["canonical_solution"]}), row)
            if res["rc"] == 0:
                passed_count += 1
            else:
                failed_ids.append((row["task_id"], res["rc"], res["category"],
                                   res.get("norm"), res.get("note", "")[:120]))
        record(len(rows) == 164 and passed_count == 164,
               f"C1 canonical fixes pass {passed_count}/{len(rows)}",
               f"failed={failed_ids[:10]}")
        buggy_wrong = [row["task_id"] for row in rows
                       if full_pipeline(json.dumps({"fix": row["buggy_solution"]}), row)["rc"] == 0]
        record(len(buggy_wrong) == 0, "C2 buggy fixes fail on all 164",
               f"buggy-passing={buggy_wrong[:10]}")
print()
print("=" * 64)
print(f"RESULT: {PASS} passed, {FAIL} failed, {SKIP} skipped")
print("=" * 64)
if FAILURES:
    print("FAILURES:")
    for n, d in FAILURES:
        print(f" - {n}: {d[:300]}")
    sys.exit(1)
sys.exit(0)
