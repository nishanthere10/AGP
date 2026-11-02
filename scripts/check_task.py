#!/usr/bin/env python3
import pyarrow.parquet as pq
t = pq.read_table("/home/aaksh/projects/LocalAgentBench/third_party/dataset/humanevalpack_python_test.parquet").to_pylist()[0]
print("declaration:", repr(t["declaration"][:200]))
print("buggy_solution:", repr(t["buggy_solution"][:200]))