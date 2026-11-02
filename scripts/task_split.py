#!/usr/bin/env python3
"""task_split.py — frozen development/evaluation split for HumanEvalPack Python.

Context: the 12-task canary must not silently become part of the final
evaluation sample. This module defines an explicit, seeded, deterministic split:

  - dev  = 12 tasks (used only for canary/prompt/feasibility work)
  - eval = 152 tasks (primary confirmatory analysis)

Method: deterministic seeded selection — sort all 164 task ids; take every
14th starting at index 0 (0, 14, 28, ...) until 12 are collected, then the
remainder is the eval set. This is a mechanical, reproducible rule over the
existing 164 tasks; no tasks are invented or altered.

The frozen manifest is written to manifests/dev_eval_split.json and records the
method, seed, rationale, and the two disjoint id sets.

Usage:
  .venv/bin/python scripts/task_split.py --write      # (re)generate manifest
  .venv/bin/python scripts/task_split.py --verify      # check manifest invariants
Exit 0 only if all invariants hold.
"""
import argparse
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
PQ = ROOT / "third_party/dataset/humanevalpack_python_test.parquet"
MANIFEST = ROOT / "manifests/dev_eval_split.json"

SEED = 42
DEV_COUNT = 12
METHOD = ("sorted all task ids; take every 14th starting at index 0 until "
          "12 dev tasks collected; remainder is eval")
RATIONALE = (
    "Development tasks are used only for canary, prompt and feasibility work. "
    "They must never enter the confirmatory evaluation sample. The split is "
    "seeded and mechanical over the existing 164 tasks; no tasks are invented "
    "or altered.")


def load_all_task_ids() -> list[str]:
    rows = pq.read_table(PQ).to_pylist()
    ids = sorted(r["task_id"] for r in rows)
    if len(ids) != len(set(ids)):
        raise SystemExit("dataset contains duplicate task_ids")
    return ids


def compute_split(ids: list[str]) -> tuple[list[str], list[str]]:
    """Mechanical every-14th selection (seeded by METHOD constant)."""
    dev = ids[0::14][:DEV_COUNT]
    dev_set = set(dev)
    eval_ids = [t for t in ids if t not in dev_set]
    return dev, eval_ids


def write_manifest(ids: list[str]) -> dict:
    dev, eval_ids = compute_split(ids)
    manifest = {
        "schema_version": 1,
        "created": "2026-11-01",
        "method": METHOD,
        "method_seed": SEED,
        "rationale": RATIONALE,
        "dataset": "HumanEvalPack-Python (164 tasks)",
        "dev_count": len(dev),
        "eval_count": len(eval_ids),
        "total_count": len(ids),
        "dev_task_ids": dev,
        "eval_task_ids": eval_ids,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=1))
    return manifest


def verify_manifest() -> tuple[bool, str]:
    if not MANIFEST.exists():
        return False, f"manifest missing: {MANIFEST}"
    m = json.loads(MANIFEST.read_text())
    ids = load_all_task_ids()
    dev = m.get("dev_task_ids", [])
    eval_ids = m.get("eval_task_ids", [])
    dev_set, eval_set = set(dev), set(eval_ids)
    checks = [
        (len(dev) == DEV_COUNT, f"dev count = {len(dev)} != {DEV_COUNT}"),
        (len(eval_ids) == len(ids) - DEV_COUNT,
         f"eval count = {len(eval_ids)} != {len(ids) - DEV_COUNT}"),
        (dev_set.isdisjoint(eval_set), "dev and eval overlap"),
        (dev_set | eval_set == set(ids), "dev ∪ eval != all tasks"),
        (m.get("dev_count") == len(dev), "manifest dev_count mismatch"),
        (m.get("eval_count") == len(eval_ids), "manifest eval_count mismatch"),
        (len(ids) == 164, f"dataset has {len(ids)} tasks, expected 164"),
    ]
    for ok, msg in checks:
        if not ok:
            return False, msg
    return True, "all split invariants hold"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()

    ids = load_all_task_ids()
    if args.write:
        md = write_manifest(ids)
        print("WROTE", MANIFEST)
        print("dev=%d eval=%d total=%d" % (md["dev_count"], md["eval_count"],
                                           md["total_count"]))
        print("dev_task_ids:", md["dev_task_ids"])
        return 0
    if args.verify or True:
        ok, msg = verify_manifest()
        print(("VERIFY PASS: " if ok else "VERIFY FAIL: ") + msg)
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
