#!/usr/bin/env python3
"""Stage 6: inspect HumanEvalPack python config (read-only, no execution)."""
import json
import pyarrow.parquet as pq

PQ = "/home/aaksh/projects/LocalAgentBench/third_party/dataset/humanevalpack_python_test.parquet"
t = pq.read_table(PQ)
print("rows:", t.num_rows)
print("cols:", t.column_names)
d = t.to_pylist()

ids = [r["task_id"] for r in d]
print("first5:", ids[:5])
print("last5:", ids[-5:])
print("unique:", len(set(ids)))

# bug_type / failure_symptoms distribution
from collections import Counter
print("bug_types:", Counter(r["bug_type"] for r in d))
print("bug_type none/empty:", sum(1 for r in d if not r["bug_type"]))
print("with import field non-empty:", sum(1 for r in d if r["import"]))
print("with test_setup non-empty:", sum(1 for r in d if r["test_setup"]))

# check buggy != canonical for all tasks
same = [r["task_id"] for r in d if r["buggy_solution"] == r["canonical_solution"]]
print("buggy==canonical count:", len(same), same[:5])

# show one example (truncated)
r = d[0]
for k in ["task_id", "entry_point", "bug_type", "failure_symptoms"]:
    print(f"{k}: {r[k]!r}")
print("prompt head:", r["prompt"][:120].replace("\n", "\\n"))
print("buggy head:", r["buggy_solution"][:200].replace("\n", "\\n"))
print("canonical head:", r["canonical_solution"][:200].replace("\n", "\\n"))
print("test head:", r["test"][:200].replace("\n", "\\n"))
print("example_test:", repr(r["example_test"][:200]) if r["example_test"] else None)
