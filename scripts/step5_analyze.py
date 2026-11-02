#!/usr/bin/env python3
"""step5_analyze.py — Steps 5 & 6: analyze pilot results and produce
reports/pilot_results.md.

Reads results/pilot_v2/summary.json (written by pilot_runner.py) and
produces:
  - Per-task per-config table
  - Aggregate metrics per config: valid-output rate, syntax-valid rate,
    eval pass rate, repair recovery rate, mean latency, mean peak RSS
  - Failure mode breakdown
  - Config C: first-attempt vs post-repair performance
  - Cost analysis (extra attempts, extra latency)
  - Decision section: proceed / floor effect / other

Usage: python3 scripts/step5_analyze.py [--results results/pilot_v2]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path("/home/aaksh/projects/LocalAgentBench")


def load_summary(results_dir: Path) -> list[dict]:
    summary_file = results_dir / "summary.json"
    if not summary_file.exists():
        print(f"ERROR: {summary_file} not found. Has pilot_runner.py been run?",
              file=sys.stderr)
        sys.exit(1)
    return json.loads(summary_file.read_text())


def classify_attempts(record: dict) -> dict:
    """Extract key metrics from a single task-config result record."""
    attempts = record["attempt_log"]
    config = record["config"]

    # Valid output: at least one attempt produced parseable {"fix": ...}
    valid_outputs = [a for a in attempts if a["extract"].startswith("ok-")]
    any_valid = len(valid_outputs) > 0

    # Syntax valid: at least one eval rc was NOT import_error (3) or malformed
    # (i.e. the code at least ran, even if it failed)
    any_ran = any(
        a["eval"].get("rc") in (0, 1, 2) for a in attempts
    )

    # First-attempt pass
    a1 = attempts[0]
    first_pass = a1["eval"].get("rc") == 0

    # Final pass
    final_pass = record["final_success"]

    # Repair recovery (C only): final pass AND not first pass
    repair_recovered = (config == "C" and final_pass and not first_pass)

    # Latency: sum of wall times across attempts
    total_wall = sum(a["gen"].get("wall_s", 0) or 0 for a in attempts)

    # Peak RSS: max across attempts
    rss_vals = [a["gen"].get("peak_rss_kb") for a in attempts
                if a["gen"].get("peak_rss_kb") is not None]
    peak_rss = max(rss_vals) if rss_vals else None

    # Failure mode of first attempt
    a1_cat = a1["eval"].get("category", "unknown")
    a1_extract = a1.get("extract", "")

    return {
        "task_id": record["task_id"],
        "config": config,
        "attempts_used": record["attempts_used"],
        "any_valid_output": any_valid,
        "any_ran": any_ran,
        "first_pass": first_pass,
        "final_pass": final_pass,
        "repair_recovered": repair_recovered,
        "total_wall_s": round(total_wall, 1),
        "peak_rss_kb": peak_rss,
        "a1_extract": a1_extract,
        "a1_category": a1_cat,
        "initial_success": record["initial_success"],
    }


def aggregate(rows: list[dict]) -> dict:
    n = len(rows)
    if n == 0:
        return {}

    def rate(key):
        return round(sum(1 for r in rows if r[key]) / n, 3)

    def mean(key):
        vals = [r[key] for r in rows if r[key] is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    # Failure mode counts
    fail_modes: dict[str, int] = {}
    for r in rows:
        cat = r["a1_category"]
        fail_modes[cat] = fail_modes.get(cat, 0) + 1

    return {
        "n": n,
        "valid_output_rate": rate("any_valid_output"),
        "syntax_ran_rate": rate("any_ran"),
        "first_attempt_pass_rate": rate("first_pass"),
        "final_pass_rate": rate("final_pass"),
        "repair_recovery_rate": rate("repair_recovered"),
        "mean_wall_s": mean("total_wall_s"),
        "peak_rss_kb": mean("peak_rss_kb"),
        "failure_modes": fail_modes,
    }


def md_table(headers: list[str], rows: list[list]) -> str:
    widths = [max(len(str(h)), max((len(str(r[i])) for r in rows), default=0))
              for i, h in enumerate(headers)]
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    header = "| " + " | ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers)) + " |"
    lines = [header, sep]
    for row in rows:
        lines.append("| " + " | ".join(str(row[i]).ljust(widths[i]) for i in range(len(headers))) + " |")
    return "\n".join(lines)


def pct(v, total):
    if total == 0:
        return "n/a"
    return f"{v}/{total} ({100*v//total}%)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(ROOT / "results/pilot_v2"))
    args = ap.parse_args()

    results_dir = Path(args.results)
    summary = load_summary(results_dir)

    print(f"Loaded {len(summary)} records from {results_dir}/summary.json")

    # ── Per-record metrics ────────────────────────────────────────────────────
    metrics = [classify_attempts(r) for r in summary]

    by_config: dict[str, list] = {"A": [], "B": [], "C": []}
    for m in metrics:
        by_config[m["config"]].append(m)

    # ── Aggregate per config ──────────────────────────────────────────────────
    agg = {cfg: aggregate(rows) for cfg, rows in by_config.items()}

    # ── Print to terminal ─────────────────────────────────────────────────────
    print("\n=== Aggregate results per config ===")
    for cfg in "ABC":
        a = agg.get(cfg, {})
        if not a:
            print(f"Config {cfg}: no data")
            continue
        print(f"\nConfig {cfg} (n={a['n']}):")
        print(f"  Valid-output rate:        {a['valid_output_rate']:.0%}")
        print(f"  Syntax-ran rate:          {a['syntax_ran_rate']:.0%}")
        print(f"  First-attempt pass rate:  {a['first_attempt_pass_rate']:.0%}")
        print(f"  Final pass rate:          {a['final_pass_rate']:.0%}")
        if cfg == "C":
            print(f"  Repair recovery rate:     {a['repair_recovery_rate']:.0%}")
        print(f"  Mean wall time:           {a['mean_wall_s']} s")
        print(f"  Failure modes (a1):       {a['failure_modes']}")

    # ── Build pilot_results.md ────────────────────────────────────────────────
    TASKS = [f"Python/{i}" for i in range(0, 160, 16)]

    # Full per-task per-config detail table
    detail_rows = []
    for tid in TASKS:
        for cfg in "ABC":
            m = next((x for x in metrics if x["task_id"] == tid and x["config"] == cfg), None)
            if m is None:
                detail_rows.append([tid, cfg, "MISSING", "—", "—", "—", "—", "—", "—"])
                continue
            detail_rows.append([
                tid, cfg,
                m["attempts_used"],
                "✓" if m["any_valid_output"] else "✗",
                "✓" if m["any_ran"] else "✗",
                "✓" if m["first_pass"] else "✗",
                "✓" if m["final_pass"] else "✗",
                f"{m['total_wall_s']}s",
                m["a1_category"],
            ])

    detail_md = md_table(
        ["Task", "Cfg", "Attempts", "Valid JSON", "Ran", "Pass@1", "Pass@N", "Wall", "Failure Mode"],
        detail_rows
    )

    # Aggregate summary table
    agg_rows = []
    for cfg in "ABC":
        a = agg.get(cfg, {})
        if not a:
            agg_rows.append([cfg, "no data", "—", "—", "—", "—", "—", "—"])
            continue
        n = a["n"]
        agg_rows.append([
            cfg,
            n,
            f"{a['valid_output_rate']:.0%}",
            f"{a['syntax_ran_rate']:.0%}",
            f"{a['first_attempt_pass_rate']:.0%}",
            f"{a['final_pass_rate']:.0%}",
            f"{a['repair_recovery_rate']:.0%}" if cfg == "C" else "n/a",
            f"{a['mean_wall_s']}s",
        ])

    agg_md = md_table(
        ["Config", "N", "Valid JSON", "Ran", "Pass@1", "Pass@N", "Repair Recovery", "Mean Wall"],
        agg_rows
    )

    # Config C: first vs post-repair breakdown
    c_rows = by_config.get("C", [])
    c_first = sum(1 for r in c_rows if r["first_pass"])
    c_final = sum(1 for r in c_rows if r["final_pass"])
    c_recovered = sum(1 for r in c_rows if r["repair_recovered"])
    c_attempts = [r["attempts_used"] for r in c_rows]
    c_wall_a1 = [by_config.get("A", [{}])[i].get("total_wall_s", 0) for i in range(len(c_rows))]
    b_rows = by_config.get("B", [])

    # Extra latency: C total wall vs B total wall for same tasks
    c_total_wall = sum(r["total_wall_s"] for r in c_rows)
    b_total_wall = sum(r["total_wall_s"] for r in b_rows)
    extra_wall = round(c_total_wall - b_total_wall, 1)

    # Verdict logic
    a_pass = agg.get("A", {}).get("final_pass_rate", 0)
    b_pass = agg.get("B", {}).get("final_pass_rate", 0)
    c_pass = agg.get("C", {}).get("final_pass_rate", 0)
    c_valid = agg.get("C", {}).get("valid_output_rate", 0)

    if a_pass == 0 and b_pass == 0 and c_pass == 0:
        verdict = "floor_effect"
        verdict_note = ("All three configs achieve 0% pass rate on all 10 tasks. "
                        "This is a floor effect: the 1.5B model cannot solve any of these "
                        "bug-repair tasks in a single pass. This does not mean the "
                        "experimental design is broken — it means the model is too weak "
                        "for this task set, or the prompt/format contract needs revision.")
    elif c_valid < 0.5:
        verdict = "protocol_issue"
        verdict_note = ("Valid-output rate for C is below 50%, suggesting the JSON contract "
                        "is not being followed reliably even with grammar enforcement. "
                        "Investigate grammar file, prompt format, and model behavior.")
    elif c_pass > b_pass > a_pass:
        verdict = "proceed"
        verdict_note = ("Clear ordering C > B > A with non-trivial pass rates. "
                        "Proceeding to the full 164-task benchmark is supported by evidence.")
    elif b_pass >= c_pass and b_pass > a_pass:
        verdict = "proceed_with_note"
        verdict_note = ("B matches or exceeds C — repair loop has no marginal benefit on "
                        "this pilot. Proceed to full run with this note; collect more evidence.")
    else:
        verdict = "insufficient_evidence"
        verdict_note = ("No clear ordering or pattern. The pilot sample of 10 tasks is too "
                        "small to draw conclusions. Proceeding to the full run is needed "
                        "before any claim can be made.")

    # ── Pre-compute evidence table rows (safe formatting) ────────────────────
    def fmt_rate(a, key):
        v = a.get(key)
        return f"{v:.0%}" if isinstance(v, float) else "n/a"

    _evidence_rows = "\n".join(
        f"| {cfg} | {fmt_rate(agg.get(cfg, {}), 'first_attempt_pass_rate')} "
        f"| {fmt_rate(agg.get(cfg, {}), 'final_pass_rate')} "
        f"| {fmt_rate(agg.get(cfg, {}), 'valid_output_rate')} |"
        for cfg in "ABC"
    )

    # ── Write pilot_results.md ────────────────────────────────────────────────
    total_planned = 30
    total_completed = len(summary)
    missing = total_planned - total_completed

    # Gather any per-task result.json notes (raw generation issues)
    missing_runs = []
    for tid in TASKS:
        for cfg in "ABC":
            found = any(r["task_id"] == tid and r["config"] == cfg for r in summary)
            if not found:
                missing_runs.append(f"{tid}/{cfg}")

    report = f"""# Stage 7 — Pilot Results

Date: {__import__('datetime').date.today()}
Runner: `scripts/pilot_runner.py`
Results directory: `results/pilot_v2/`
Protocol: `reports/pilot_protocol.md`

## 1. Completion status

| Metric | Value |
|---|---|
| Planned executions | {total_planned} (10 tasks × 3 configs) |
| Completed | {total_completed} |
| Missing | {missing} |
| Protocol deviations | {'None' if missing == 0 else ', '.join(missing_runs)} |

{'All 30 planned executions completed.' if missing == 0 else f'**WARNING: {missing} executions missing: {missing_runs}**'}

## 2. Aggregate results by configuration

{agg_md}

Metric definitions:
- **Valid JSON**: at least one attempt produced a parseable `{{"fix": "..."}}` object.
- **Ran**: the candidate code at least executed (rc ∈ {{0,1,2}} — i.e., not import_error or malformed).
- **Pass@1**: first attempt passed the oracle (rc=0).
- **Pass@N**: any attempt passed (Pass@1 for A/B; up to 3 for C).
- **Repair Recovery** (C only): final pass AND first attempt did not pass.
- **Mean Wall**: mean total generation time across all attempts for that config.

## 3. Per-task per-configuration detail

{detail_md}

## 4. Configuration C: first-attempt vs post-repair

| Metric | Value |
|---|---|
| Pass@1 (first attempt) | {pct(c_first, len(c_rows))} |
| Pass@N (after ≤3 attempts) | {pct(c_final, len(c_rows))} |
| Repair recovery | {pct(c_recovered, len(c_rows))} |
| Tasks requiring 2+ attempts | {pct(sum(1 for r in c_rows if r['attempts_used'] >= 2), len(c_rows))} |
| Tasks requiring 3 attempts | {pct(sum(1 for r in c_rows if r['attempts_used'] == 3), len(c_rows))} |
| Extra wall time vs B (10 tasks total) | {extra_wall} s |
| Mean extra wall per task recovered | {'n/a' if c_recovered == 0 else str(round(extra_wall / c_recovered, 1)) + ' s'} |

## 5. Valid-output vs functional correctness

Grammar enforcement (B/C) constrains JSON structure but does **not** guarantee:
- Correct indentation of the body
- Absence of a leading `def` signature (causes `import_error` — see §9)
- Semantic correctness of the algorithm

A task can produce `ok-json` extraction and still fail with `assertion_fail` (wrong
algorithm) or `import_error` (format violation: full def returned instead of body).
These are distinct failure modes and are **not** merged in the tables above.

## 6. Failure mode analysis

"""

    # Per-config failure mode table
    for cfg in "ABC":
        a = agg.get(cfg, {})
        if a:
            fm = a.get("failure_modes", {})
            report += f"**Config {cfg}** first-attempt failure modes:\n\n"
            if fm:
                fm_rows = [[cat, count] for cat, count in sorted(fm.items(), key=lambda x: -x[1])]
                report += md_table(["Category", "Count"], fm_rows) + "\n\n"
            else:
                report += "_no data_\n\n"

    report += f"""
## 7. Resource measurements

| Config | Mean Wall (s) | Mean Peak RSS (MB) |
|---|---|---|
"""
    for cfg in "ABC":
        a = agg.get(cfg, {})
        if a:
            rss_mb = round(a.get("peak_rss_kb", 0) / 1024, 0) if a.get("peak_rss_kb") else "n/a"
            report += f"| {cfg} | {a.get('mean_wall_s', 'n/a')} | {rss_mb} |\n"

    report += f"""
## 8. Failures requiring investigation

The following records had `gen.rc != 0` or `harness_error` (eval.rc=5):
"""
    flagged = [m for m in metrics
               if m["a1_category"] in ("harness_error",) or
               any(a["gen"].get("rc", 0) != 0 for a in
                   next(r for r in summary
                        if r["task_id"] == m["task_id"] and r["config"] == m["config"]
                        )["attempt_log"])]
    if flagged:
        for m in flagged:
            report += f"- `{m['task_id']}` config {m['config']}: {m['a1_category']}\n"
    else:
        report += "None — all generation processes returned rc=0 and evaluator ran without harness errors.\n"

    report += f"""
## 9. Known confound: full-def vs body-only in `"fix"`

As documented in `reports/pilot_protocol.md` §4c and §5, `evaluate_candidate.py`
prepends `declaration` to the extracted body. If the model returns a complete
function definition (starting with `def ...:`), this yields two stacked `def`
lines and a Python `IndentationError` recorded as `import_error` (rc=3).

In this pilot, `import_error` results from B/C could be either:
- A genuine import failure (missing library, syntax error in code)
- A format violation (model returned full def instead of body-only)

The raw generation is preserved in `results/pilot_v2/<task>_<config>/body_a1.py`
for manual inspection. Any future run that wishes to fix this confound must
update the evaluator and re-run from scratch.

## 10. Decision: proceed to full 164-task benchmark?

**Verdict: `{verdict}`**

{verdict_note}

### Evidence summary

| Config | Pass@1 | Pass@N | Valid JSON |
|---|---|---|---|
{_evidence_rows}

### Caveats

- N=10 tasks is too small for statistical significance. Differences between A, B, C
  may be noise.
- The 1.5B quantized model at temp=0.0 is deterministic; there is no variance to
  average over within a config.
- The full-def confound (§9) may inflate `import_error` counts for B and C.
- No significance claims are made. This pilot is a readiness check, not a benchmark result.

### Changes required before full run

"""
    changes = []
    if verdict == "floor_effect":
        changes.append("Consider a stronger model or simpler task subset if the goal is to observe positive signal.")
        changes.append("Alternatively, proceed to full 164-task run — floor effect may not generalise, and 164 tasks provides more power.")
    if agg.get("B", {}).get("valid_output_rate", 1) < 0.7:
        changes.append("Grammar compliance below 70% in B/C — review grammar file and prompt format.")
    if missing > 0:
        changes.append(f"Re-run missing executions: {missing_runs}")
    changes.append("Investigate import_error cases to separate format failures from genuine import problems.")

    if changes:
        for c in changes:
            report += f"- {c}\n"
    else:
        report += "None identified.\n"

    report += "\n---\n_This report was generated by `scripts/step5_analyze.py`. Do not edit manually._\n"

    out_path = ROOT / "reports" / "pilot_results.md"
    out_path.write_text(report)
    print(f"\nReport written: {out_path}")

    # Also write machine-readable metrics
    metrics_path = results_dir / "analysis_metrics.json"
    metrics_path.write_text(json.dumps({
        "verdict": verdict,
        "aggregate": agg,
        "per_record": metrics,
    }, indent=1))
    print(f"Metrics written: {metrics_path}")

    # Exit 0 if no hard failures, 1 if floor effect or missing runs
    if missing > 0:
        print("\nWARNING: missing runs — report is incomplete.")
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
