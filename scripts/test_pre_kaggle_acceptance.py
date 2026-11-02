#!/usr/bin/env python3
"""Final acceptance gate for pre-Kaggle hardening.

Executes and asserts the fail-closed behaviors that must hold before the
project leaves the local phase. Read-only w.r.t. experiment artifacts.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/aaksh/projects/LocalAgentBench")
VENV = ROOT / ".venv/bin/python"
FAILED = []


def run(*args, cwd=None):
    p = subprocess.run([str(VENV), *args], capture_output=True, text=True,
                       cwd=cwd or str(ROOT))
    return p.returncode, (p.stdout + p.stderr)


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f" [{detail}]" if detail else ""))
    if not cond:
        FAILED.append(name)


# 1. Missing oracle -> validation failure (require-oracle)
rc, out = run("scripts/validate_pairing_164.py", "--require-oracle",
              "--oracle", "/nonexistent/oracle.json")
check("missing oracle -> nonzero exit", rc != 0, f"rc={rc}")

# 2. Duplicate/unknown task ids rejected (canary)
rc, out = run("scripts/run_canary.py", "--model-f16", "/none", "--model-q8",
              "/none", "--dry-run", "--dev-tasks", "Python/0,Python/0")
check("duplicate dev tasks -> rc=2", rc == 2, f"rc={rc}")
rc, out = run("scripts/run_canary.py", "--model-f16", "/none", "--model-q8",
              "/none", "--dry-run", "--dev-tasks", "Python/9999")
check("unknown task id -> rc=2", rc == 2, f"rc={rc}")
rc, out = run("scripts/run_canary.py", "--model-f16", "/none", "--model-q8",
              "/none", "--dry-run", "--dev-tasks", "Python/0")
check("non-12 dev set -> rc=2", rc == 2, f"rc={rc}")

# 3. Split invariants
rc, out = run("scripts/task_split.py", "--verify")
check("split verify -> rc=0", rc == 0, f"rc={rc}")

# 4. Quant artifact verifier fail-closed when nothing has provenance
rc, out = run("scripts/verify_quant_artifacts.py", "--require-all")
check("quant verifier require-all -> nonzero with no artifacts", rc != 0,
      f"rc={rc}")

# 5. Pairing with oracle -> PASS
rc, out = run("scripts/validate_pairing_164.py", "--require-oracle")
check("pairing with oracle -> PASS", rc == 0, f"rc={rc}")

print("\nACCEPTANCE_FAILURES:", len(FAILED))
sys.exit(1 if FAILED else 0)
