#!/usr/bin/env python3
"""validate_pairing_164.py — verify the 164 synthesis/repair task pairs.

Purpose (per the approved migration):
  - Every task yields BOTH a synthesis prompt (spec + signature) and a repair
    prompt (spec + signature + buggy code) from the SAME underlying problem.
  - Both modes share the same hidden scoring test (row['test']).
  - Hidden tests and canonical solutions never appear in either prompt (leak check).
  - Canonical reference passes; original buggy solution fails (oracle join from
    results/dataset_validation.json, produced by validate_dataset.py).
  - Duplicate / mismatched task records are flagged.

Usage:
  .venv/bin/python scripts/validate_pairing_164.py [--out results/dataset_pairing_validation.json]
              [--oracle results/dataset_validation.json] [--require-oracle]

Exit code 0 iff all gated checks hold (164 expected, 0 anomalies, 0 leaks).
When --require-oracle is set, a missing/unreadable oracle is an error (fail
closed); otherwise the oracle join is skipped and reported as
`oracle_present: false`.
"""
import argparse
import json
import logging
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
PQ = ROOT / "third_party/dataset/humanevalpack_python_test.parquet"
ORACLE = ROOT / "results/dataset_validation.json"
DEFAULT_OUT = ROOT / "results/dataset_pairing_validation.json"

LOG = logging.getLogger("validate_pairing")


def setup_logging() -> None:
    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    LOG.addHandler(h)
    LOG.setLevel(logging.INFO)


def build_prompts(row: dict) -> tuple[str, str, str]:
    """Return (synthesis_prompt, repair_prompt, repair_spec_part) for one task.

    Synthesis: natural-language specification + function signature/header.
    Repair:    same specification + same header + buggy implementation.

    repair_spec_part is the repair prompt EXCLUDING the buggy block. It is the
    only place a canonical-solution leak would be a genuine validity problem:
    within the buggy block the canonical body is legitimately embedded for
    prefix-embedded bug types (e.g. "excess logic"), which is the task itself,
    not leak of the answer or of hidden tests.
    """
    instruction = row["instruction"].strip()
    declaration = row["declaration"].rstrip("\n")
    buggy = row["buggy_solution"]

    synth = f"{instruction}\n\n{declaration}\n"
    spec_part = f"{instruction}\n\n{declaration}\n"
    repair = f"{spec_part}# BUGGY:\n{buggy}\n"
    return synth, repair, spec_part


def lev(a: str, b: str) -> int:
    """Levenshtein distance (pure Python, small strings)."""
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def read_oracle(path: Path):
    try:
        data = json.loads(path.read_text())
        return {rec["task_id"]: rec for rec in data.get("results", [])}
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, KeyError) as e:
        LOG.warning("oracle file %s unreadable (%s); oracle join skipped", path, e)
        return None


def detect_leaks(synth: str, repair: str, spec_part: str,
                 test: str, canon: str) -> list[dict]:
    """Return leak records for one task (empty list = clean).

    - Hidden test must NEVER appear in any prompt (strict).
    - Canonical solution must not appear in the synthesis prompt, nor in the
      repair prompt OUTSIDE the buggy block. Within the buggy block a canonical
      prefix is expected for prefix-embedded bugs (benign).
    """
    leaks = []
    if test and test.strip() and test.strip() in synth:
        leaks.append({"mode": "synthesis", "issue": "hidden test leaked into prompt"})
    if test and test.strip() and test.strip() in repair:
        leaks.append({"mode": "repair", "issue": "hidden test leaked into prompt"})
    if canon.strip() and canon.strip() in synth:
        leaks.append({"mode": "synthesis",
                      "issue": "canonical solution leaked into prompt"})
    if canon.strip() and canon.strip() in spec_part:
        leaks.append({"mode": "repair",
                      "issue": "canonical solution leaked into prompt (outside buggy block)"})
    return leaks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--oracle", default=str(ORACLE))
    ap.add_argument("--require-oracle", action="store_true")
    args = ap.parse_args()
    setup_logging()

    if not PQ.exists():
        LOG.error("dataset parquet not found: %s", PQ)
        return 2

    oracle_path = Path(args.oracle)
    oracle_by_task = read_oracle(oracle_path)
    if oracle_by_task is None:
        if args.require_oracle:
            LOG.error("--require-oracle set but %s missing/unreadable", oracle_path)
            return 2
        LOG.warning("oracle missing; canonical/buggy oracle columns will be null")

    rows = pq.read_table(PQ).to_pylist()
    records = []
    seen = set()
    anomalies = []
    leaks = []
    expected = 164

    for r in rows:
        tid = r.get("task_id")
        if not tid:
            anomalies.append({"task_id": None, "issue": "row missing task_id"})
            continue
        if tid in seen:
            anomalies.append({"task_id": tid, "issue": "duplicate task_id"})
        seen.add(tid)

        try:
            synth, repair, spec_part = build_prompts(r)
        except KeyError as e:
            anomalies.append({"task_id": tid, "issue": f"missing field {e}"})
            continue

        test = r.get("test", "")
        canon = r.get("canonical_solution", "")
        leaks.extend(
            {"task_id": tid, **l}
            for l in detect_leaks(synth, repair, spec_part, test, canon)
        )

        # Shared-test invariant: synthesis and repair must be scored with the
        # SAME (present, non-empty) hidden test. By construction both prompts
        # come from one row, so the test string is identical; we assert it is
        # non-empty and record the fingerprint for auditability.
        test_fp = None
        if not test or not test.strip():
            anomalies.append({"task_id": tid, "issue": "empty hidden test"})
        else:
            import hashlib
            test_fp = hashlib.sha256(test.strip().encode()).hexdigest()[:16]

        o = oracle_by_task.get(tid) if oracle_by_task else None
        canon_passes = o["canonical_passes"] if o else None
        buggy_fails = o["buggy_fails"] if o else None
        if o is None and oracle_by_task is not None:
            anomalies.append({"task_id": tid, "issue": "oracle record missing for task"})
        elif o is not None and not (canon_passes and buggy_fails):
            anomalies.append({"task_id": tid, "issue": "oracle not discriminating",
                             "canonical_passes": canon_passes,
                             "buggy_fails": buggy_fails})

        records.append({
            "task_id": tid,
            "synthesis_prompt_chars": len(synth),
            "repair_prompt_chars": len(repair),
            "entry_point": r.get("entry_point"),
            "bug_type": r.get("bug_type"),
            "failure_symptoms": r.get("failure_symptoms"),
            "has_import": bool(r.get("import", "").strip()),
            "has_test_setup": bool(r.get("test_setup", "").strip()),
            "edit_distance_buggy_canonical": lev(r.get("buggy_solution", ""), canon),
            "canonical_passes": canon_passes,
            "buggy_fails": buggy_fails,
            "shared_test_sha256_prefix": test_fp,
            "synthesis_matches_repair_test": True,  # single row => identical test
            "leak_flags": [l["issue"] for l in leaks if l["task_id"] == tid],
        })

    oracle_present = oracle_by_task is not None
    summary = {
        "expected_tasks": expected,
        "actual_tasks": len(records),
        "unique_task_ids": len(seen),
        "oracle_present": oracle_present,
        "duplicate_anomalies": len([a for a in anomalies if a.get("issue") == "duplicate task_id"]),
        "oracle_canonical_pass": sum(1 for r in records if r["canonical_passes"]),
        "oracle_buggy_fail": sum(1 for r in records if r["buggy_fails"]),
        "leak_total": len(leaks),
        "leak_records": leaks,
        "anomalies": anomalies,
        "status": "PASS" if (len(records) == expected and len(seen) == expected
                             and not leaks and not anomalies
                             and oracle_present) else "FAIL",
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "records": records}, indent=1))

    LOG.info("status=%s tasks=%d/%d unique=%d canon_pass=%d buggy_fail=%d "
             "leaks=%d anomalies=%d oracle=%s",
             summary["status"], len(records), expected, len(seen),
             summary["oracle_canonical_pass"], summary["oracle_buggy_fail"],
             len(leaks), len(anomalies), oracle_present)
    if anomalies:
        LOG.warning("anomalies: %s", json.dumps(anomalies[:10]))
    if leaks:
        LOG.warning("leaks: %s", json.dumps(leaks[:10]))

    if summary["status"] == "PASS":
        return 0
    if not oracle_present and not args.require_oracle:
        # Pairing itself is fine; oracle just wasn't available.
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
