#!/usr/bin/env python3
"""step3_validate_tasks.py — Step 3: verify the 10 frozen pilot tasks exist
in the dataset and print a summary of each one.

Checks:
  1. Each task ID in the frozen selection is present in the parquet file.
  2. Each task has non-empty: instruction, declaration, buggy_solution, test,
     entry_point.
  3. The canonical solution passes the oracle (sanity check that the dataset
     audit from Stage 6 still holds for pilot tasks specifically).
  4. The buggy solution fails the oracle (confirms the task is actually
     a bug-repair task, not a trivially-pass case).
  5. The configuration definitions match the protocol:
     A: no grammar, 1 attempt
     B: grammar, 1 attempt
     C: grammar, up to 3 attempts

Outputs a summary table and exits non-zero if any check fails.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/aaksh/projects/LocalAgentBench")
PQ = ROOT / "third_party/dataset/humanevalpack_python_test.parquet"
EVAL = ROOT / "scripts/evaluate_candidate.py"
VENV_PY = ROOT / ".venv/bin/python"
WORKDIR = ROOT / "pilot_workdir"
FROZEN_IDS = [f"Python/{i}" for i in range(0, 160, 16)]

# Config definitions per protocol
CONFIGS = {
    "A": {"grammar": False, "max_attempts": 1, "repair": False},
    "B": {"grammar": True,  "max_attempts": 1, "repair": False},
    "C": {"grammar": True,  "max_attempts": 3, "repair": True},
}


def load_tasks():
    import pyarrow.parquet as pq
    return {r["task_id"]: r for r in pq.read_table(PQ).to_pylist()}


def run_oracle(task_id: str, body: str) -> dict:
    """Run evaluate_candidate.py against a given body string."""
    WORKDIR.mkdir(exist_ok=True)
    cand = WORKDIR / "step3_cand.py"
    cand.write_text(body)
    try:
        p = subprocess.run(
            [str(VENV_PY), str(EVAL),
             "--task-id", task_id,
             "--body-file", str(cand),
             "--timeout", "10"],
            capture_output=True, text=True, timeout=25)
        rc = p.returncode
        note = (p.stdout + p.stderr).strip()[:200]
    except subprocess.TimeoutExpired:
        rc, note = 5, "HARNESS_TIMEOUT"
    cat = {0: "pass", 1: "assertion_fail", 2: "runtime_error",
           3: "import_error", 4: "missing_entry", 5: "harness_error"}.get(rc, "unknown")
    return {"rc": rc, "category": cat, "note": note}


def main():
    print("=" * 60)
    print("Step 3: Pilot task validation")
    print("=" * 60)

    # ── 1. Load dataset ──────────────────────────────────────────────────────
    try:
        all_tasks = load_tasks()
    except Exception as e:
        print(f"FATAL: cannot load dataset: {e}")
        sys.exit(1)

    print(f"\nDataset: {len(all_tasks)} tasks loaded from {PQ}")
    print(f"Frozen selection: {FROZEN_IDS}\n")

    passed = 0
    failed = 0
    rows = []

    for tid in FROZEN_IDS:
        row_ok = True
        issues = []

        # ── 2. Existence ─────────────────────────────────────────────────────
        if tid not in all_tasks:
            print(f"[FAIL] {tid}: NOT IN DATASET")
            failed += 1
            rows.append({"task_id": tid, "ok": False,
                         "canon_rc": "n/a", "buggy_rc": "n/a",
                         "issues": ["not_in_dataset"]})
            continue

        t = all_tasks[tid]

        # ── 3. Non-empty required fields ─────────────────────────────────────
        for field in ("instruction", "declaration", "buggy_solution",
                      "test", "entry_point"):
            if not t.get(field, "").strip():
                issues.append(f"empty_{field}")
                row_ok = False

        # ── 4. Canonical passes oracle ───────────────────────────────────────
        canon_body = t.get("canonical_solution", "")
        if not canon_body.strip():
            issues.append("empty_canonical_solution")
            canon_result = {"rc": -1, "category": "missing_canonical"}
            row_ok = False
        else:
            canon_result = run_oracle(tid, canon_body)
            if canon_result["rc"] != 0:
                issues.append(f"canonical_fails:{canon_result['category']}")
                row_ok = False

        # ── 5. Buggy fails oracle ────────────────────────────────────────────
        buggy_body = t.get("buggy_solution", "")
        if not buggy_body.strip():
            issues.append("empty_buggy_solution")
            buggy_result = {"rc": -1, "category": "missing_buggy"}
            row_ok = False
        else:
            buggy_result = run_oracle(tid, buggy_body)
            if buggy_result["rc"] == 0:
                issues.append("buggy_passes_oracle (trivial task!)")
                row_ok = False

        status = "PASS" if row_ok else "FAIL"
        if row_ok:
            passed += 1
        else:
            failed += 1

        # Print per-task line
        entry = t.get("entry_point", "?")
        decl_preview = t.get("declaration", "").split("\n")[0][:60]
        print(f"[{status}] {tid}  entry={entry}")
        print(f"       decl: {decl_preview}")
        print(f"       canonical rc={canon_result['rc']} ({canon_result['category']})")
        print(f"       buggy     rc={buggy_result['rc']} ({buggy_result['category']})")
        if issues:
            print(f"       ISSUES: {issues}")
        print()

        rows.append({
            "task_id": tid,
            "ok": row_ok,
            "entry_point": entry,
            "canon_rc": canon_result["rc"],
            "buggy_rc": buggy_result["rc"],
            "issues": issues,
        })

    # ── 6. Config definitions ────────────────────────────────────────────────
    print("─" * 60)
    print("Configuration definitions (per protocol §4d):")
    for cfg, defn in CONFIGS.items():
        print(f"  Config {cfg}: grammar={defn['grammar']}  "
              f"max_attempts={defn['max_attempts']}  repair={defn['repair']}")

    # Cross-check against pilot_runner.py constants
    runner = (ROOT / "scripts/pilot_runner.py").read_text()
    runner_checks = {
        "MAX_ATTEMPTS = 3": "C max_attempts=3",
        "grammar = config in (\"B\", \"C\")": "B/C grammar flag",
        "--no-conversation": "--no-conversation flag",
        "--single-turn": "--single-turn flag",
        "--no-display-prompt": "--no-display-prompt flag",
        "json.JSONDecoder": "JSONDecoder parser",
        "PROMPT_TEMPLATE": "PROMPT_TEMPLATE defined",
    }
    print("\nRunner cross-checks:")
    runner_ok = True
    for token, desc in runner_checks.items():
        if token in runner:
            print(f"  OK  {desc}")
        else:
            print(f"  !! MISSING: {desc} ('{token}' not found in pilot_runner.py)")
            runner_ok = False

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"TASK VALIDATION: {passed}/{len(FROZEN_IDS)} passed, {failed} failed")
    print(f"CONFIG CHECK:    {'OK' if runner_ok else 'ISSUES FOUND'}")

    # Write machine-readable result
    report = {
        "passed": passed,
        "failed": failed,
        "runner_checks_ok": runner_ok,
        "tasks": rows,
        "config_definitions": CONFIGS,
    }
    out = ROOT / "reports" / "step3_task_validation.json"
    out.write_text(json.dumps(report, indent=1))
    print(f"Detailed results: {out}")

    if failed > 0 or not runner_ok:
        print("\nRESULT: VALIDATION FAILED — fix issues before running pilot.")
        sys.exit(1)
    else:
        print("\nRESULT: ALL 10 TASKS VALID — pilot may proceed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
