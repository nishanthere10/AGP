#!/usr/bin/env python3
import pyarrow.parquet as pq
import json

ROOT = "/home/aaksh/projects/LocalAgentBench"
t = pq.read_table(f"{ROOT}/third_party/dataset/humanevalpack_python_test.parquet").to_pylist()[0]

print("=== HumanEvalPack Python/0 sample ===")
print("task_id:", t["task_id"])
print("prompt:", repr(t["prompt"][:300]))
print("buggy_solution:", repr(t["buggy_solution"][:300]))
print("canonical_solution:", repr(t["canonical_solution"][:300]))
print("entry_point:", t["entry_point"])
print("test:", repr(t["test"][:300]))
print("declaration:", repr(t["declaration"][:300]))

# Show exact prompt line-by-line if possible
lines = t["prompt"].split("\n")
print(f"\nprompt has {len(lines)} lines")
for i, line in enumerate(lines[:10]):
    print(f"  {i}: {repr(line[:80])}")

# Check for chat template markers
print(f"\nprompt ends with: {repr(t['prompt'][-100:])}")
print(f"canonical starts with: {repr(t['canonical_solution'][:100])}")
print(f"buggy starts with: {repr(t['buggy_solution'][:100])}")