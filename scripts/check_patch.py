import subprocess
import sys
from pathlib import Path

root = Path("/home/aaksh/projects/LocalAgentBench")
venv = root / ".venv/bin/python"
files = ["pilot_runner.py", "evaluate_candidate.py", "run_canary.py",
         "validate_dataset.py", "validate_pairing_164.py",
         "verify_quant_artifacts.py", "task_split.py"]
fail = 0
for f in files:
    p = subprocess.run([str(venv), "-m", "py_compile", str(root / "scripts" / f)],
                       capture_output=True, text=True)
    print(("OK   " if p.returncode == 0 else "FAIL ") + f)
    if p.returncode != 0:
        fail += 1
        print(p.stderr[-1000:])

# verify python insertion
pr = (root / "scripts/pilot_runner.py").read_text()
print("has _py helper:", "def _py()" in pr)
print("has _py() use:", "_py()" in pr)
print("hardcoded root remains:", 'Path("/home/aaksh' in pr)

sys.exit(1 if fail else 0)
