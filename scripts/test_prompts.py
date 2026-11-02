#!/usr/bin/env python3
import pyarrow.parquet as pq
import subprocess
import sys
import json
import re

ROOT = "/home/aaksh/projects/LocalAgentBench"
BIN = ROOT + "/third_party/llama.cpp/build/bin/llama-completion"
MODEL = ROOT + "/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
OUT = ROOT + "/results/inference_smoke"
GRAMMAR = ROOT + "/scripts/response_v2.gbnf"
TASK_PQ = ROOT + "/third_party/dataset/humanevalpack_python_test.parquet"

t = pq.read_table(TASK_PQ).to_pylist()[0]
decl = t["declaration"]
buggy = t["buggy_solution"]
entry = t["entry_point"]

# Test 1: Prompt asking for pure JSON, no markers
prompt1 = "Fix the bug in this Python function and return ONLY a JSON object with one key \"fix\" containing the corrected function body. Do not include any explanation, markdown fences, or other text.\n\n" + decl + "\n# BUGGY:\n" + buggy

# Test 2: Prompt asking for JSON with explicit contract
prompt2 = 'Respond with ONLY a JSON object of the form {"fix": "<the complete corrected function body>"}. Do not write anything else.\n\n' + decl + "\n# BUGGY:\n" + buggy

# Test 3: Minimal prompt - just the function to fix
prompt3 = decl + "\nPlease fix the bug above and return the corrected code."

tests = [("prompt1", prompt1), ("prompt2", prompt2), ("prompt3", prompt3)]

for name, prompt in tests:
    print(f"\n=== {name} ===")
    # plain (no grammar)
    p = subprocess.run(
        [BIN, "-m", MODEL, "-p", prompt, "-n", "128", "-c", "2048", "-t", "4",
         "--temp", "0.0", "--seed", "42", "--no-conversation", "--single-turn"],
        capture_output=True, text=True, timeout=180
    )
    print(f"  plain rc={p.returncode} stdout_len={len(p.stdout)}")
    
    # grammar-constrained
    p2 = subprocess.run(
        [BIN, "-m", MODEL, "-p", prompt, "-n", "128", "-c", "2048", "-t", "4",
         "--temp", "0.0", "--seed", "42", "--no-conversation", "--single-turn",
         "--grammar-file", GRAMMAR],
        capture_output=True, text=True, timeout=180
    )
    print(f"  grammar rc={p2.returncode} stdout_len={len(p2.stdout)}")
    
    # extract 'fix' key from both
    for label, txt in [("plain", p.stdout), ("grammar", p2.stdout)]:
        mm = re.search(r'"fix"', txt)
        if mm:
            try:
                decoder = json.JSONDecoder()
                obj, idx = decoder.raw_decode(txt[mm.start():])
                fix = obj.get("fix")
                print(f"    {label} fix={repr(fix[:80]) if fix else 'None'}")
            except Exception as e:
                print(f"    {label} json error: {e}")
        else:
            print(f"    {label} no 'fix' key")
            # show last 200 chars
            print(f"    {label} last200={repr(txt[-200:])}")