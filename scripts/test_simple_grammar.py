#!/usr/bin/env python3
import pyarrow.parquet as pq
import subprocess
import sys
import os

ROOT = "/home/aaksh/projects/LocalAgentBench"
BIN = ROOT + "/third_party/llama.cpp/build/bin/llama-completion"
MODEL = ROOT + "/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
OUT = ROOT + "/results/inference_smoke"

# Write simple gbnf file first
with open("/tmp/simple_gbnf.txt", "w") as f:
    f.write('root ::= "OK" | "NO"\n')

prompt = "Is this test passing? "

print("=== Test with simple grammar ===")
p = subprocess.run(
    [BIN, "-m", MODEL, "-p", prompt, "-n", "8", "-c", "64", "-t", "4",
     "--temp", "0.0", "--seed", "42", "--no-conversation", "--single-turn",
     "--grammar-file", "/tmp/simple_gbnf.txt"],
    capture_output=True, text=True, timeout=60
)
print(f"rc={p.returncode}")
print(f"stdout={repr(p.stdout.strip())}")
print(f"stderr={p.stderr.strip()[-80:] if p.stderr else 'empty'}")

# Try without grammar for comparison
print("\n=== Without grammar ===")
p2 = subprocess.run(
    [BIN, "-m", MODEL, "-p", prompt, "-n", "8", "-c", "64", "-t", "4",
     "--temp", "0.0", "--seed", "42", "--no-conversation", "--single-turn"],
    capture_output=True, text=True, timeout=60
)
print(f"rc={p2.returncode}")
print(f"stdout={repr(p2.stdout.strip())}")