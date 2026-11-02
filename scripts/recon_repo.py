#!/usr/bin/env python3
"""Read-only reconnaissance of the canonical LocalAgentBench repo."""
import subprocess
from pathlib import Path

ROOT = Path("/home/aaksh/projects/LocalAgentBench")


def sh(cmd):
    p = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True,
                       cwd=str(ROOT))
    return p.stdout.strip(), p.returncode


def section(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


section("GIT HEAD")
out, _ = sh("git rev-parse --abbrev-ref HEAD && git log --oneline -8")
print(out)

section("GIT STATUS (short)")
out, _ = sh("git status --short")
print(out if out else "(clean)")

section("REMOTES")
out, _ = sh("git remote -v")
print(out if out else "(none)")

section("TOP-LEVEL ENTRIES")
for p in sorted(Path(ROOT).iterdir()):
    kind = "dir " if p.is_dir() else "file"
    print(f"{kind} {p.name}")

section("CONFIGS / MANIFESTS / NOTEBOOKS")
for d in ("configs", "manifests", "notebooks"):
    dd = ROOT / d
    print(f"-- {d} --")
    if dd.exists():
        for p in sorted(dd.iterdir()):
            print("   ", p.name)
    else:
        print("   (missing)")

section("SCRIPTS (selected)")
for pat in ("canary", "pairing", "quant", "kaggle", "setup", "preflight",
            "validate_prep", "test_canary", "test_validate", "task_split",
            "verify_quant", "validate_dataset", "evaluate_candidate",
            "pilot_runner", "sandbox"):
    print(f"-- {pat} --")
    out, _ = sh(f"ls scripts | grep -E '{pat}'")
    print(out if out else "   (none)")

section("REPORTS")
out, _ = sh("ls reports")
print(out)

section("RESULTS DIRS (top level)")
out, _ = sh("find results -maxdepth 1 -type d | sort")
print(out)

section("FROZEN SELECTION FILES")
out, _ = sh("find results -name 'task_selection.json' -o -name '*split*.json' | sort")
print(out)

section("EVALUATOR REVISION")
out, _ = sh("grep -E 'EVALUATOR_REVISION|ROOT' scripts/evaluate_candidate.py | head -5")
print(out)

section("SANDBOX WRAPPER EXPOSED")
out, _ = sh("head -40 scripts/sandbox.sh")
print(out)
