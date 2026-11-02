#!/usr/bin/env python3
"""Regression tests for validate_pairing_164.py (leak logic + prompt builders).

Run: .venv/bin/python scripts/test_validate_pairing.py
Exit 0 = all pass.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path("/home/aaksh/projects/LocalAgentBench")
spec = importlib.util.spec_from_file_location(
    "vp", ROOT / "scripts/validate_pairing_164.py")
vp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vp)

FAILED = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILED.append(name)


def make_row(**over):
    row = {
        "instruction": "Write a function f(x) -> int.",
        "declaration": "def f(x) -> int:\n",
        "buggy_solution": "    return x + 1\n",
        "canonical_solution": "    return x\n",
        "test": "assert f(1) == 1\n",
        "entry_point": "f",
        "bug_type": "excess logic",
        "failure_symptoms": "incorrect output",
        "import": "",
        "test_setup": "",
    }
    row.update(over)
    return row


# --- build_prompts -----------------------------------------------------------
synth, repair, spec = vp.build_prompts(make_row())
check("synthesis contains instruction+declaration", "def f(x) -> int:" in synth)
check("synthesis does NOT contain buggy", "return x + 1" not in synth)
check("repair contains buggy", "return x + 1" in repair)
check("spec_part excludes buggy block", "BUGGY" not in spec and "return x + 1" not in spec)

# --- leak detection: canonical as prefix of buggy (benign, inside buggy) -----
row = make_row(buggy_solution="    return x + 1 + 1\n")
synth, repair, spec = vp.build_prompts(row)
# canonical "    return x\n" is NOT a substring here; use a true prefix case:
row = make_row(buggy_solution="    return x\n    return x + 1\n")
synth, repair, spec = vp.build_prompts(row)
canon = row["canonical_solution"]
check("benign: canonical inside buggy block not flagged in spec_part",
      canon.strip() not in spec)
check("benign: canonical inside buggy block not flagged in synth",
      canon.strip() not in synth)

# --- true leak: canonical injected into spec part ----------------------------
row = make_row(instruction="Write a function.\n    return x\n")  # canonical leaked in spec
_, _, spec = vp.build_prompts(row)
check("true leak: canonical in spec_part is detected",
      row["canonical_solution"].strip() in spec)

# --- hidden test leak (real leak, detectable) -------------------------------
row = make_row()
synth, repair, spec = vp.build_prompts(row)
# Introduce a genuine leak: the hidden test text appears verbatim in the spec.
leaky_instruction = row["instruction"] + "\n" + row["test"].strip()
synth2, repair2, spec2 = vp.build_prompts(make_row(instruction=leaky_instruction))
leaks = vp.detect_leaks(synth2, repair2, spec2, row["test"], row["canonical_solution"])
check("hidden test leak detected", any("hidden test" in l["issue"] for l in leaks))
check("clean row has zero leaks", len(vp.detect_leaks(synth, repair, spec,
      row["test"], row["canonical_solution"])) == 0)

# --- lev ---------------------------------------------------------------
check("lev: identical = 0", vp.lev("abc", "abc") == 0)
check("lev: insert = 1", vp.lev("abc", "abcd") == 1)
check("lev: substitute = 1", vp.lev("abc", "axc") == 1)

# --- missing oracle fail-closed -----------------------------------------
import subprocess
p = subprocess.run([str(ROOT / ".venv/bin/python"),
                    str(ROOT / "scripts/validate_pairing_164.py"),
                    "--require-oracle", "--oracle",
                    "/nonexistent/oracle.json"],
                   capture_output=True, text=True)
check("--require-oracle with missing oracle exits nonzero", p.returncode != 0)


def main() -> int:
    if FAILED:
        print("\n%d FAILED: %s" % (len(FAILED), FAILED))
        return 1
    print("\nALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
