#!/usr/bin/env python3
"""Regression tests for scripts/task_split.py (dev/eval split invariants)."""
import importlib.util
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path("/home/aaksh/projects/LocalAgentBench")
spec = importlib.util.spec_from_file_location("ts", ROOT / "scripts/task_split.py")
ts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ts)

FAILED = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILED.append(name)


ids = ts.load_all_task_ids()
check("dataset has 164 unique ids", len(ids) == 164 and len(set(ids)) == 164)

dev, eval_ids = ts.compute_split(ids)
check("dev count = 12", len(dev) == 12)
check("eval count = 152", len(eval_ids) == 152)
check("dev ∩ eval = ∅", set(dev).isdisjoint(eval_ids))
check("dev ∪ eval = all", set(dev) | set(eval_ids) == set(ids))

# manifest write + verify
manifest = ts.write_manifest(ids)
path = ROOT / "manifests/dev_eval_split.json"
check("manifest written", path.exists())
check("manifest dev_count matches", manifest["dev_count"] == 12)
check("manifest eval_count matches", manifest["eval_count"] == 152)
check("manifest records method+rationale", manifest["method"] and manifest["rationale"])
ok, msg = ts.verify_manifest()
check("verify_manifest passes", ok)

# reloaded manifest must be stable (deterministic)
manifest2 = json.loads(path.read_text())
check("manifest deterministic", manifest2["dev_task_ids"] == dev)


def main() -> int:
    if FAILED:
        print("\n%d FAILED: %s" % (len(FAILED), FAILED))
        return 1
    print("\nALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
