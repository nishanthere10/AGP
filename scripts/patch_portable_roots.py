#!/usr/bin/env python3
"""Patch LocalAgentBench scripts to be path-portable.

Replaces every hardcoded  ROOT = Path("/home/aaksh/projects/LocalAgentBench") line
in scripts/*.py with a path derived from __file__ (repo root = scripts/..).

Idempotent: lines already portable are left unchanged.
Also swaps evaluator subprocess python to fall back to sys.executable when the
repo's .venv does not exist (e.g. Kaggle/Colab).
"""
import re
import sys
from pathlib import Path

ROOT = Path("/home/aaksh/projects/LocalAgentBench/scripts")

OLD_ROOT = 'ROOT = Path("/home/aaksh/projects/LocalAgentBench")'
NEW_ROOT = "ROOT = Path(__file__).resolve().parent.parent"

changed_files = []

for p in sorted(ROOT.glob("*.py")):
    text = p.read_text(encoding="utf-8")
    new = text
    if OLD_ROOT in new:
        new = new.replace(OLD_ROOT, NEW_ROOT)
    # Evaluator spawn fallback in pilot_runner.py and run_canary.py
    if p.name in ("pilot_runner.py", "run_canary.py"):
        new = new.replace(
            'subprocess.run(\n            [str(VENV_PY), str(EVAL), "--task-id", task["task_id"],',
            'subprocess.run(\n            [_py(), str(EVAL), "--task-id", task["task_id"],',
        )
        if "_py()" in new and "def _py()" not in new:
            helper = (
                "def _py() -> str:\n"
                "    \"\"\"Use the repo venv if present, else current interpreter.\"\"\"\n"
                "    venv = ROOT / \".venv/bin/python\"\n"
                "    return str(venv) if venv.exists() else sys.executable\n\n"
            )
            # insert helper after the imports/constant block
            new = new.replace("EVALUATOR_REVISION = _read_evaluator_revision()\n",
                              "EVALUATOR_REVISION = _read_evaluator_revision()\n\n" + helper)
    if new != text:
        p.write_text(new, encoding="utf-8")
        changed_files.append(p.name)

print("PATCHED:", len(changed_files))
for name in changed_files:
    print("  -", name)

sys.exit(0)
