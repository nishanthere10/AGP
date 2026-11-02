#!/usr/bin/env python3
"""Import smoke test: import every core module to catch import-time crashes."""
import importlib
import sys
from pathlib import Path

ROOT = Path("/home/aaksh/projects/LocalAgentBench")
sys.path.insert(0, str(ROOT / "scripts"))

MODULES = [
    # Pure library modules only — NOT the notebook/doc validators, which
    # execute at import time (they call sys.exit when run as scripts).
    "pilot_runner",
    "evaluate_candidate",
    "run_canary",
    "validate_dataset",
    "validate_pairing_164",
    "verify_quant_artifacts",
    "task_split",
]

fail = 0
for m in MODULES:
    try:
        importlib.import_module(m)
        print("OK   import " + m)
    except Exception as e:
        fail += 1
        print("FAIL import " + m + ": " + repr(e))

print("IMPORT_SMOKE_FAILURES:", fail)
sys.exit(1 if fail else 0)
