#!/usr/bin/env python3
import pyarrow.parquet as pq
import subprocess
import json
import re
import os

ROOT = "/home/aaksh/projects/LocalAgentBench"
BIN = ROOT + "/third_party/llama.cpp/build/bin/llama-completion"
MODEL = ROOT + "/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
OUT = ROOT + "/results/inference_smoke"
GRAMMAR = ROOT + "/scripts/response.gbnf"
TASK_PQ = ROOT + "/third_party/dataset/humanevalpack_python_test.parquet"

t = pq.read_table(TASK_PQ).to_pylist()[0]
task_id = t["task_id"]
decl = t["declaration"]
buggy = t["buggy_solution"]
canon = t["canonical_solution"]
entry = t["entry_point"]
test_text = t["test"]

# Prompt as used: declaration + # BUGGY: + buggy solution
prompt = decl + "\n# BUGGY:\n" + buggy
with open("/tmp/task_prompt.txt", "w") as f:
    f.write(prompt)
print(f"prompt written, len={len(prompt)}")

# Test with grammar
print("\n=== Grammar-constrained (256 tokens) ===")
p = subprocess.run(
    [BIN, "-m", MODEL, "-p", prompt, "-n", "256", "-c", "2048", "-t", "4",
     "--temp", "0.0", "--seed", "42", "--no-conversation", "--single-turn",
     "--grammar-file", GRAMMAR],
    capture_output=True, text=True, timeout=180
)
print(f"rc={p.returncode}")
print(f"stdout_len={len(p.stdout)}")
print("--- stdout ---")
print(p.stdout)
print("--- stderr (last 5) ---")
for line in p.stderr.strip().split("\n")[-5:]:
    print(line)

# Extract fix key
print("\n=== Extract fix ===")
text = p.stdout
m = re.search(r'"fix"\s*:\s*"(.*?)"', text)
if m:
    print(f"fix value: {repr(m.group(1)[:300])}")
else:
    print("no 'fix' key found with regex")
    # show last 300 chars
    print(f"last 300 chars: {repr(text[-300:])}")

# Also show without grammar for comparison
print("\n=== Without grammar (256 tokens) ===")
p2 = subprocess.run(
    [BIN, "-m", MODEL, "-p", prompt, "-n", "256", "-c", "2048", "-t", "4",
     "--temp", "0.0", "--seed", "42", "--no-conversation", "--single-turn"],
    capture_output=True, text=True, timeout=180
)
print(f"rc={p2.returncode} len={len(p2.stdout)}")
print("--- stdout ---")
print(p2.stdout[:500] if p2.stdout else "empty")
# check for fix key in plain
m2 = re.search(r'"fix"', p2.stdout)
print(f"plain has 'fix' key: {m2 is not None}")
if m2:
    print(f"plain fix context: {repr(p2.stdout[m2.start():m2.start()+200])}")