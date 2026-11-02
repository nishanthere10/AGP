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
GRAMMAR = ROOT + "/scripts/response_v2.gbnf"
TASK_PQ = ROOT + "/third_party/dataset/humanevalpack_python_test.parquet"

t = pq.read_table(TASK_PQ).to_pylist()[0]
decl = t["declaration"]
buggy = t["buggy_solution"]
entry = t["entry_point"]
test_text = t["test"]

# Test prompts
prompts = {
    "just_declaration": decl,
    "fix_request": "Fix the bug in the following Python function and return the corrected function body as a JSON object {\"fix\": \"...\"}. No explanation, no markdown fences.\n\n" + decl,
    "minimal": decl + "\nPlease fix the bug above.",
}

grammar_works = []

for name, prompt in prompts.items():
    print(f"\n=== {name} ===")
    # plain
    p = subprocess.run(
        [BIN, "-m", MODEL, "-p", prompt, "-n", "64", "-c", "2048", "-t", "4",
         "--temp", "0.0", "--seed", "42", "--no-conversation", "--single-turn"],
        capture_output=True, text=True, timeout=120
    )
    print(f"  plain rc={p.returncode} len={len(p.stdout)}")
    plain_has_fix = '"fix"' in p.stdout
    
    # grammar
    p2 = subprocess.run(
        [BIN, "-m", MODEL, "-p", prompt, "-n", "64", "-c", "2048", "-t", "4",
         "--temp", "0.0", "--seed", "42", "--no-conversation", "--single-turn",
         "--grammar-file", GRAMMAR],
        capture_output=True, text=True, timeout=120
    )
    print(f"  grammar rc={p2.returncode} len={len(p2.stdout)}")
    gram_has_fix = '"fix"' in p2.stdout if p2.returncode == 0 else "FAILED"
    
    print(f"  plain has 'fix': {plain_has_fix}")
    print(f"  grammar has 'fix': {gram_has_fix}")
    
    # show last 300 chars of plain
    print(f"  plain last 300: {repr(p.stdout[-300:])}")
    print(f"  grammar last 300: {repr(p2.stdout[-300:]) if p2.returncode == 0 else 'FAILED'}")
    
    works = p2.returncode == 0 and '"fix"' in p2.stdout
    print(f"  grammar WORKS: {works}")
    promptname = name in grammar_works.append if works else grammar_works.append(None) or False

# Actually let me just collect results differently
print("\n\n=== SUMMARY ===")