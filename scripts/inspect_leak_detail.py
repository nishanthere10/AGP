import json
import pyarrow.parquet as pq

rows = {r["task_id"]: r for r in pq.read_table(
    "third_party/dataset/humanevalpack_python_test.parquet").to_pylist()}

d = json.load(open("results/dataset_pairing_validation.json"))
leaks = d["summary"]["leak_records"]

for leak in leaks:
    tid = leak["task_id"]
    r = rows[tid]
    canon = r["canonical_solution"]
    buggy = r["buggy_solution"]
    print("=" * 70)
    print(tid, "| bug_type:", r.get("bug_type"), "| symptoms:", r.get("failure_symptoms"))
    idx = buggy.find(canon.strip())
    print("canonical in buggy at index:", idx)
    print("--- canonical (repr, first 200) ---")
    print(repr(canon[:200]))
    print("--- buggy (repr, first 300) ---")
    print(repr(buggy[:300]))
    # show what differs
    print("--- first divergence ---")
    n = min(len(canon), len(buggy))
    k = 0
    while k < n and canon[k] == buggy[k]:
        k += 1
    print("common prefix length:", k)
    print("canon[k:k+60]:", repr(canon[k:k+60]))
    print("buggy[k:k+60]:", repr(buggy[k:k+60]))
