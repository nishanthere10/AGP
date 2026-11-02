#!/usr/bin/env python3
"""Quick test of evaluate_candidate.py with known bodies for Python/0."""
import json
import subprocess
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path("/home/aaksh/projects/LocalAgentBench")
rows = {r["task_id"]: r for r in pq.read_table(ROOT / "third_party/dataset/humanevalpack_python_test.parquet").to_pylist()}
r = rows["Python/0"]

body_dir = ROOT / "pilot_workdir"
body_dir.mkdir(exist_ok=True)

cases = {
    "canonical": r["canonical_solution"],
    "buggy": r["buggy_solution"],
}
for name, body in cases.items():
    f = body_dir / f"test_{name}.py"
    f.write_text(body)
    p = subprocess.run(
        [str(ROOT / ".venv/bin/python"), str(ROOT / "scripts/evaluate_candidate.py"),
         "--task-id", "Python/0", "--body-file", str(f)],
        capture_output=True, text=True, timeout=30)
    print(f"{name}: rc={p.returncode} out={(p.stdout + p.stderr).strip()[:200]!r}")
