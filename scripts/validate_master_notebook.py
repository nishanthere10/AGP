#!/usr/bin/env python3
"""Validate the master runtime notebook: JSON, per-cell Python syntax, no
interactive calls, and required key cells present."""
import ast
import json
import sys
from pathlib import Path

NB = Path("/home/aaksh/projects/LocalAgentBench/notebooks/LocalAgentBench_Master_Runtime.ipynb")

fail = 0


def check(name, cond, detail=""):
    global fail
    print(("PASS " if cond else "FAIL ") + name + (f" [{detail}]" if detail else ""))
    if not cond:
        fail += 1


# 1. JSON parse
try:
    nb = json.loads(NB.read_text())
    check("notebook parses as JSON", True)
except Exception as e:
    print("FAIL notebook JSON:", e)
    sys.exit(1)

# 2. Structure
cells = nb.get("cells", [])
check("has cells", len(cells) > 0, f"n={len(cells)}")
code_cells = [c for c in cells if c.get("cell_type") == "code"]
check("has code cells", len(code_cells) > 0, f"n={len(code_cells)}")

# 3. Per-cell syntax + forbidden patterns
forbidden = ["input(", "getpass", "raw_input", "Pause", "pause()", "sleep(3600"]
for i, c in enumerate(code_cells):
    src = "".join(c.get("source", []))
    try:
        ast.parse(src)
        check(f"cell {i} syntax", True)
    except SyntaxError as e:
        check(f"cell {i} syntax", False, f"{e}")
    for bad in forbidden:
        if bad in src:
            check(f"cell {i} has forbidden '{bad}'", False)
            break

# 4. Required stage markers present
joined = "\n".join("".join(c.get("source", [])) for c in code_cells)
for marker in ["stage(\"repo\"", "stage(\"deps\"", "stage(\"llama_build\"",
              "stage(\"sandbox_preflight\"", "stage(\"dataset_validate\"",
              "stage(\"model_download\"", "stage(\"quantize\"",
              "stage(\"verify_quant\"", "stage(\"canary\"",
              "FINAL VERDICT"]:
    check(f"marker present: {marker}", marker in joined)

print("\nNOTEBOOK_VALIDATION_FAILURES:", fail)
sys.exit(1 if fail else 0)
