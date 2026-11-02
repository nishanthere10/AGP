#!/usr/bin/env python3
import pyarrow.parquet as pq
from pathlib import Path
PQ = Path('/home/aaksh/projects/LocalAgentBench/third_party/dataset/humanevalpack_python_test.parquet')
rows = {r['task_id']:r for r in pq.read_table(PQ).to_pylist()}
r = rows['Python/0']
print('P0 DECLARATION:', repr(r['declaration']))
print('P0 BUGGY:', repr(r['buggy_solution'][:150]))
print('P0 CANONICAL:', repr(r['canonical_solution'][:200]))
r2 = rows['Python/16']
print()
print('P16 DECL:', repr(r2['declaration']))
print('P16 CANONICAL:', repr(r2['canonical_solution']))
