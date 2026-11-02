#!/usr/bin/env python3
"""Stage 6: verify buggy_solution fails its test and canonical_solution passes.

Runs each candidate in a fresh subprocess with a hard timeout. This executes
DATASET-provided code (trusted, published oracle), not model-generated code.
"""
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
PQ = ROOT / "third_party/dataset/humanevalpack_python_test.parquet"
OUT = ROOT / "results/dataset_validation.json"
PY = sys.executable
TIMEOUT = 10  # seconds per task run

HARNESS = '''
import sys
CODE = sys.stdin.read()
ns = {}
try:
    exec(CODE, ns)
except Exception as e:
    print("IMPORT_ERROR:", type(e).__name__, e)
    sys.exit(3)
entry = ENTRY
fn = ns.get(entry)
if fn is None:
    print("MISSING_ENTRY:", entry)
    sys.exit(4)
try:
    exec(TEST, ns)
except AssertionError:
    print("ASSERT_FAILED")
    sys.exit(1)
except Exception as e:
    print("RUNTIME_ERROR:", type(e).__name__, e)
    sys.exit(2)
print("PASSED")
sys.exit(0)
'''


def run_one(code: str, entry: str, test: str) -> dict:
    prog = HARNESS.replace("ENTRY", repr(entry)).replace("TEST", repr(test))
    t0 = time.monotonic()
    try:
        p = subprocess.run([PY, "-I", "-c", prog], input=code, capture_output=True,
                           text=True, timeout=TIMEOUT)
        rc = p.returncode
        out = (p.stdout + p.stderr).strip()[:300]
    except subprocess.TimeoutExpired:
        rc = -9
        out = "TIMEOUT"
    return {"rc": rc, "output": out, "wall_s": round(time.monotonic() - t0, 3)}


def main() -> None:
    rows = pq.read_table(PQ).to_pylist()
    results = []
    for r in rows:
        decl, entry, test = r["declaration"], r["entry_point"], r["test"]
        # full program = declaration + solution body
        buggy = run_one(decl + r["buggy_solution"], entry, test)
        canon = run_one(decl + r["canonical_solution"], entry, test)
        buggy_fails = buggy["rc"] != 0
        canon_passes = canon["rc"] == 0
        results.append({
            "task_id": r["task_id"],
            "buggy": buggy,
            "canonical": canon,
            "buggy_fails": buggy_fails,
            "canonical_passes": canon_passes,
        })
        print(f"{r['task_id']}: buggy_rc={buggy['rc']} canon_rc={canon['rc']}")

    summary = {
        "total": len(results),
        "buggy_fails": sum(x["buggy_fails"] for x in results),
        "canonical_passes": sum(x["canonical_passes"] for x in results),
        "both_ok": sum(x["buggy_fails"] and x["canonical_passes"] for x in results),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"summary": summary, "results": results}, indent=1))
    print("SUMMARY:", json.dumps(summary))
    anomalies = [x for x in results if not (x["buggy_fails"] and x["canonical_passes"])]
    print("ANOMALIES:", [x["task_id"] for x in anomalies])


if __name__ == "__main__":
    main()
