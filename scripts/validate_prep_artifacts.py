#!/usr/bin/env python3
"""validate_prep_artifacts.py — local validation gate for prepared artifacts.

Checks that every prepared script/notebook/config is syntactically valid and
that the regression tests pass. Safe to run anytime; does not execute any
experiment, model download, or quantization.

Usage: .venv/bin/python scripts/validate_prep_artifacts.py
Exit 0 = all green.
"""
import glob
import json
import subprocess
import sys
from pathlib import Path

root = Path("/home/aaksh/projects/LocalAgentBench")
venv = root / ".venv/bin/python"
fail = 0

SUITES = [
    "test_validate_pairing.py",
    "test_canary_smoke.py",
    "test_canary_gates.py",
    "test_task_split.py",
    "test_verify_quant_artifacts.py",
    "import_smoke.py",
]

BASH_PREP = [
    "scripts/setup_kaggle.sh",
    "scripts/run_kaggle_preflight.sh",
    "scripts/quantize_gguf.sh",
    "scripts/kaggle_sandbox_preflight.sh",
]


def run(label, cmd):
    global fail
    p = subprocess.run(cmd, capture_output=True, text=True)
    ok = p.returncode == 0
    print(("OK   " if ok else "FAIL ") + label)
    if not ok:
        fail += 1
        print(p.stdout[-2000:] if p.stdout else "")
        print(p.stderr[-2000:] if p.stderr else "")
    return ok


print("== BASH SYNTAX ==")
for f in BASH_PREP:
    run(f, ["bash", "-n", str(root / f)])

print("== PYTHON SYNTAX ==")
for f in ["scripts/run_canary.py", "scripts/validate_pairing_164.py",
          "scripts/task_split.py", "scripts/verify_quant_artifacts.py"]:
    run("py_compile " + f, [str(venv), "-m", "py_compile", str(root / f)])
for f in SUITES:
    run("py_compile scripts/" + f,
        [str(venv), "-m", "py_compile", str(root / "scripts" / f)])

print("== REGRESSION TESTS ==")
for suite in SUITES:
    run(suite, [str(venv), str(root / "scripts" / suite)])

print("== NOTEBOOK JSON ==")
for f in sorted(glob.glob(str(root / "notebooks/*.ipynb"))):
    try:
        json.load(open(f))
        print("OK   " + Path(f).name)
    except Exception as e:
        fail += 1
        print("FAIL " + Path(f).name + " " + str(e))

print("== DOCS ==")
run("validate_docs", [str(venv), str(root / "scripts/validate_docs.py")])

print("\nVALIDATION_FAILURES:", fail)
sys.exit(1 if fail else 0)
