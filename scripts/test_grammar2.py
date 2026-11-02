#!/usr/bin/env python3
import pyarrow.parquet as pq
import json
import re
import subprocess
import sys

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
test = t["test"]

# Prompt as used in the pilot: declaration + buggy marker
prompt = decl + "\n# BUGGY:\n" + buggy
with open("/tmp/prompt1.txt", "w") as f:
    f.write(prompt)
print(f"prompt_len={len(prompt)}")

# Test 1: plain completion
print("\n=== Test 1: plain completion ===")
p = subprocess.run(
    [BIN, "-m", MODEL, "-p", prompt, "-n", "128", "-c", "2048", "-t", "4",
     "--temp", "0.0", "--seed", "42", "--no-conversation", "--single-turn"],
    capture_output=True, text=True, timeout=180
)
print(f"rc={p.returncode}")
print(f"stdout_bytes={len(p.stdout)} stderr_bytes={len(p.stderr)}")
print("--- stdout ---")
print(p.stdout)
print("--- stderr (last 5 lines) ---")
for line in p.stderr.strip().split("\n")[-5:]:
    print(line)

# Test 2: grammar-constrained
print("\n=== Test 2: grammar-constrained ===")
p2 = subprocess.run(
    [BIN, "-m", MODEL, "-p", prompt, "-n", "128", "-c", "2048", "-t", "4",
     "--temp", "0.0", "--seed", "42", "--no-conversation", "--single-turn",
     "--grammar-file", GRAMMAR],
    capture_output=True, text=True, timeout=180
)
print(f"rc={p2.returncode}")
print(f"stdout_bytes={len(p2.stdout)} stderr_bytes={len(p2.stderr)}")
print("--- stdout ---")
print(p2.stdout)
print("--- stderr (last 5 lines) ---")
for line in p2.stderr.strip().split("\n")[-5:]:
    print(line)

# Test 3: extract JSON fix
print("\n=== Test 3: extract JSON fix ===")
text = p2.stdout
# find the JSON fix key
mm = re.search(r'"fix"', text)
print(f"find '\"fix\"' at position: {mm.start() if mm else 'NOT FOUND'}")
if mm:
    try:
        decoder = json.JSONDecoder()
        obj, idx = decoder.raw_decode(text[mm.start():])
        fix = obj.get("fix")
        print(f"fix field: {repr(fix[:200]) if fix else 'None'}")
        print(f"fix type: {type(fix).__name__}")
    except Exception as e:
        print(f"json error: {e}")
        # show surrounding text
        print(f"context: ...{text[mm.start():mm.start()+200]}...")
else:
    # no JSON key - show fenced code or last section
    m2 = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    if m2:
        print(f"fenced code ({len(m2.group(1))} chars): {repr(m2.group(1)[:200])}")
    else:
        print(f"last 500 chars: {repr(text[-500:])}")

# Also test plain output for comparison
print("\n=== Test 3b: plain completion JSON extraction ===")
mm2 = re.search(r'"fix"', p.stdout)
if mm2:
    try:
        decoder = json.JSONDecoder()
        obj, idx = decoder.raw_decode(p.stdout[mm2.start():])
        fix2 = obj.get("fix")
        print(f"plain fix: {repr(fix2[:200]) if fix2 else 'None'}")
    except Exception as e:
        print(f"plain json error: {e}")
else:
    print("no 'fix' key in plain output")
    m3 = re.search(r"```(?:python)?\s*\n(.*?)```", p.stdout, re.S)
    if m3:
        print(f"plain fenced: {repr(m3.group(1)[:200])}")