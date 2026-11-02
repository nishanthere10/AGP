#!/usr/bin/env python3
"""Quick smoke checks for run_canary.py exit codes."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/aaksh/projects/LocalAgentBench")
PY = ROOT / ".venv/bin/python"
SCRIPT = ROOT / "scripts/run_canary.py"


def run(*args, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run([str(PY), str(SCRIPT), *args], capture_output=True,
                       text=True, env=e, cwd=str(ROOT))
    return p.returncode, (p.stderr or p.stdout).strip().splitlines()[-1:] if (p.stderr or p.stdout) else []


print("== dry-run (no models needed) ==")
rc, tail = run("--model-f16", "/nonexistent/f16.gguf",
               "--model-q8", "/nonexistent/q8.gguf", "--dry-run")
print("RC =", rc, "| tail:", tail)
assert rc == 0, "dry-run should exit 0"

print("== execute, missing model ==")
rc, tail = run("--model-f16", "/nonexistent/f16.gguf",
               "--model-q8", "/nonexistent/q8.gguf", "--execute")
print("RC =", rc, "| tail:", tail)
assert rc == 2, f"missing-model should exit 2, got {rc}"

print("== execute, missing env guard ==")
rc, tail = run("--model-f16", "/nonexistent/f16.gguf",
               "--model-q8", "/nonexistent/q8.gguf", "--execute",
               env={"LOCAL_AGENTBENCH_RUN_CANARY": "1"})
print("RC =", rc, "| tail:", tail)
assert rc == 2, "model check runs before env guard; should exit 2"

print("== duplicate task ids ==")
rc, tail = run("--model-f16", "/nonexistent/f16.gguf",
               "--model-q8", "/nonexistent/q8.gguf", "--dry-run",
               "--dev-tasks", "Python/0,Python/0")
print("RC =", rc, "| tail:", tail)
assert rc == 2, "duplicate ids should exit 2"

print("== unknown task id ==")
rc, tail = run("--model-f16", "/nonexistent/f16.gguf",
               "--model-q8", "/nonexistent/q8.gguf", "--dry-run",
               "--dev-tasks", "Python/9999")
print("RC =", rc, "| tail:", tail)
assert rc == 2, "unknown task should exit 2"

print("\nALL CANARY SMOKE TESTS PASS")
