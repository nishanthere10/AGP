#!/usr/bin/env python3
"""run_canary.py — baseline feasibility canary for the quantization experiment.

Runs a small, pre-declared set of PAIRED development tasks (synthesis + repair)
at F16 and Q8_0 and checks the frozen feasibility thresholds. Execution is
strictly gated: pass `--execute` AND set env LOCAL_AGENTBENCH_RUN_CANARY=1.

Outcome taxonomy (each cell receives exactly one `outcome`):
  model outcomes (scored, acceptable):
    pass                — evaluator rc=0
    fail_assertion      — evaluator rc=1
    fail_runtime        — evaluator rc=2
    fail_import         — evaluator rc=3
    fail_missing_entry  — evaluator rc=4
    extraction_rejected  — no usable def extracted (sub-kind recorded in
                           extract_info.kind / parse_error); scored as non-pass
  infrastructure / harness outcomes (NOT model failures, NEVER counted as pass):
    gen_failure         — generation subprocess errored (rc != 0) or raised
    eval_timeout        — evaluator timed out (rc=5)
    harness_error       — evaluator raised / returned rc=5 with no clear cause
    infra_error         — any unclassified exception in a stage

Verdict rules (BLOCKED / FAIL / PASS):
  - BLOCKED if ANY cell has a gen_failure, eval_timeout, harness_error, or
    infra_error, or if the run is incomplete (fewer cells than planned).
  - PASS only if the run is complete, has zero infrastructure outcomes, and the
    F16 thresholds are met in BOTH modes.
  - FAIL otherwise (complete, no infra errors, but thresholds not met).

Thresholds (configs/experiment_v1.yaml, approved 2026-11-01):
  extractable  >= 9/12 in EACH mode
  syntax-valid >= 8/12 in EACH mode
  functional    >= 3/12 in EACH mode   (F16)

Q8_0 is compared against F16; an unexpected Q8 collapse flags the artifact for
inspection rather than being treated as a genuine quantization effect.

Raw generation stdout is preserved per cell under <out>/raw/<cell>.txt so every
score is reproducible from artifacts.

The 12 dev tasks are EXCLUDED from the final confirmatory set (see
manifests/dev_eval_split.json and scripts/task_split.py).

Usage:
  .venv/bin/python scripts/run_canary.py \
      --model-f16 <f16.gguf> --model-q8 <q8.gguf> \
      [--dev-tasks Python/0,Python/14,...] [--out results/canary/] \
      [--execute] [--dry-run] [--log-level INFO]
"""
import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
LOG = logging.getLogger("canary")

# Reuse the REAL pilot_runner machinery (generate / extract_definition /
# evaluate / load_tasks) so the canary measures the same pipeline as the full
# experiment, not a parallel reinvented one.
sys.path.insert(0, str(ROOT / "scripts"))
import pilot_runner as pr  # noqa: E402

DEV_TASKS_DEFAULT = ["Python/%d" % i for i in range(0, 160, 16)][:12]

# Frozen thresholds (configs/experiment_v1.yaml)
F16_MIN = {"extractable": 9, "syntax_valid": 8, "functional": 3}

# Planned cells = 2 models x 2 modes x N tasks.
OUTCOMES = {
    "pass", "fail_assertion", "fail_runtime", "fail_import",
    "fail_missing_entry", "extraction_rejected",
    "gen_failure", "eval_timeout", "harness_error", "infra_error",
}
INFRA_OUTCOMES = {"gen_failure", "eval_timeout", "harness_error", "infra_error"}
MODEL_OUTCOMES = OUTCOMES - INFRA_OUTCOMES


def setup_logging(level: str) -> None:
    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    LOG.addHandler(h)
    LOG.setLevel(getattr(logging, level.upper(), logging.INFO))


def load_dev_tasks(args_task: str) -> list[str]:
    """Dev tasks: explicit --dev-tasks wins; else frozen manifest; else default."""
    if args_task and args_task.strip():
        return [t.strip() for t in args_task.split(",") if t.strip()]
    mf = ROOT / "manifests/dev_eval_split.json"
    if mf.exists():
        try:
            m = json.loads(mf.read_text())
            ids = m.get("dev_task_ids") or []
            LOG.info("dev tasks from frozen manifest %s", mf.name)
            return list(ids)
        except (json.JSONDecodeError, KeyError):
            LOG.warning("could not read dev_eval_split.json; using default")
    LOG.info("using default dev tasks")
    return list(DEV_TASKS_DEFAULT)


def build_prompts(row: dict) -> tuple[str, str]:
    """(synthesis_prompt, repair_prompt) — same spec, same signature."""
    instruction = row["instruction"].strip()
    declaration = row["declaration"].rstrip("\n")
    synth = f"{instruction}\n\n{declaration}\n"
    repair = f"{instruction}\n\n{declaration}\n# BUGGY:\n{row['buggy_solution']}\n"
    return synth, repair


def classify_eval(rc, note) -> str:
    """Map an evaluator return code to an outcome. rc=5 is ALWAYS harness."""
    return {
        0: "pass",
        1: "fail_assertion",
        2: "fail_runtime",
        3: "fail_import",
        4: "fail_missing_entry",
        5: "harness_error",
    }.get(rc, "harness_error")


def run_cell(task: dict, mode: str, prompt: str, model_path: Path,
             out_dir: Path, timeout: float) -> dict:
    """One generation -> extraction -> sandbox evaluation. Never raises.

    Each record carries a single `outcome` plus stage-specific detail, so a
    harness error can never be mistaken for a model failure.
    """
    rec = {
        "task_id": task["task_id"],
        "mode": mode,
        "model": model_path.name,
        "stage": "generate",
        "outcome": None,
        "gen": None,
        "extract": None,
        "extract_info": None,
        "eval": None,
        "raw_stdout": None,
    }
    cell_name = f"{task['task_id'].replace('/', '_')}_{mode}_{model_path.stem}"
    tag = out_dir / f"gen_{cell_name}"
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{cell_name}.txt"

    # --- stage: generate ---
    try:
        g = pr.generate(prompt, grammar=False, tag=str(tag), model=model_path)
    except Exception as e:  # pragma: no cover - defensive
        LOG.exception("generate failed for %s %s", task["task_id"], mode)
        rec.update({"stage": "generate", "outcome": "infra_error",
                    "detail": {"error": str(e)}})
        return rec

    gen_rc = g.get("rc")
    if gen_rc != 0:
        rec.update({"stage": "generate", "outcome": "gen_failure",
                    "gen": {"rc": gen_rc,
                            "wall_s": g.get("wall_s"),
                            "stderr_tail": (g.get("stderr") or "")[-1000:]}})
        try:
            raw_path.write_text(g.get("stdout") or "")
        except OSError:
            pass
        return rec

    rec["gen"] = {k: g.get(k) for k in
                  ("rc", "wall_s", "peak_rss_kb", "prompt_tokens",
                   "completion_tokens")}
    try:
        raw_path.write_text(g.get("stdout") or "")
    except OSError:
        pass
    rec["raw_stdout"] = str(raw_path)

    # --- stage: extract ---
    try:
        src, info = pr.extract_definition(g.get("stdout") or "", task)
        rec["extract"] = info.get("kind")
        rec["extract_info"] = info
    except Exception as e:  # pragma: no cover - defensive
        LOG.exception("extract_definition failed for %s %s", task["task_id"], mode)
        rec.update({"stage": "extract", "outcome": "infra_error",
                    "detail": {"error": str(e)}})
        return rec

    if src is None:
        rec.update({"stage": "extract", "outcome": "extraction_rejected",
                    "detail": {"kind": info.get("kind"),
                               "parse_error": info.get("parse_error")}})
        return rec

    # --- stage: evaluate ---
    try:
        ev = pr.evaluate(task, src)
    except Exception as e:  # pragma: no cover - defensive
        LOG.exception("evaluate failed for %s %s", task["task_id"], mode)
        rec.update({"stage": "evaluate", "outcome": "infra_error",
                    "detail": {"error": str(e)}})
        return rec

    rc = ev.get("rc")
    if rc is None:
        rec.update({"stage": "evaluate", "outcome": "infra_error",
                    "detail": ev})
    elif rc == 5:
        # Distinguish a genuine evaluator timeout from other harness errors.
        note = (ev.get("note") or "").upper()
        outcome = "eval_timeout" if "TIMEOUT" in note else "harness_error"
        rec.update({"stage": "evaluate", "outcome": outcome, "eval": ev})
    else:
        rec.update({"stage": "evaluate", "outcome": classify_eval(rc, ev),
                    "eval": ev})
    return rec


def summarize(records) -> dict:
    by_mode = {"synthesis": {}, "repair": {}}
    for rec in records:
        m = by_mode.setdefault(rec["mode"], {})
        m.setdefault("total", 0)
        m["total"] += 1
        outcome = rec["outcome"]
        if outcome == "pass":
            m["functional"] = m.get("functional", 0) + 1
        # "extractable" means a usable definition was extracted AND evaluation
        # ran. Only cells that reach the evaluate stage qualify; extraction-
        # rejected cells never do.
        if rec["stage"] == "evaluate":
            m["extractable"] = m.get("extractable", 0) + 1
        if outcome in ("pass", "fail_assertion", "fail_runtime"):
            m["syntax_valid"] = m.get("syntax_valid", 0) + 1
    return by_mode


def gate(summary: dict, thresholds: dict) -> tuple[str, dict]:
    """Apply frozen thresholds to F16 summary. Returns (status, details)."""
    details = {}
    ok = True
    for mode, m in summary.items():
        for key, lo in thresholds.items():
            got = m.get(key, 0)
            passed = got >= lo
            ok = ok and passed
            details.setdefault(mode, {})[key] = {"got": got, "need": lo,
                                                 "passed": passed}
    status = "PASS" if ok else "FAIL"
    return status, details


def decide(records, planned_cells: int, thresholds: dict) -> tuple[str, dict]:
    """Final verdict: BLOCKED / FAIL / PASS.

    - BLOCKED: any infrastructure outcome, or incomplete run.
    - PASS: complete, zero infra outcomes, thresholds met on F16.
    - FAIL: otherwise.
    """
    infra = [r for r in records if r["outcome"] in INFRA_OUTCOMES]
    complete = len(records) == planned_cells
    if infra or not complete:
        return "BLOCKED", {
            "planned_cells": planned_cells,
            "actual_cells": len(records),
            "infra_outcomes": [r["outcome"] for r in infra],
            "reason": ("infrastructure/outcome errors present" if infra
                       else "run incomplete"),
        }
    f16 = [r for r in records if r["model"].startswith("F16")]
    status, details = gate(summarize(f16), thresholds)
    return status, details


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model-f16", required=True)
    ap.add_argument("--model-q8", required=True)
    ap.add_argument("--dev-tasks", default="",
                    help="comma-separated dev task ids (default: frozen manifest)")
    ap.add_argument("--out", default=str(ROOT / "results/canary"))
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--execute", action="store_true",
                    help="actually run; otherwise plan-only")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    setup_logging(args.log_level)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    f16 = Path(args.model_f16)
    q8 = Path(args.model_q8)

    task_ids = load_dev_tasks(args.dev_tasks)
    if not task_ids:
        LOG.error("no dev tasks given")
        return 2
    if len(task_ids) != len(set(task_ids)):
        LOG.error("duplicate task ids in --dev-tasks")
        return 2
    if len(task_ids) != 12:
        LOG.error("dev task set must be exactly 12 (got %d)", len(task_ids))
        return 2
    try:
        tasks = pr.load_tasks(task_ids)
    except KeyError as e:
        LOG.error("unknown task id: %s", e)
        return 2
    except Exception:  # pragma: no cover - defensive
        LOG.exception("failed to load tasks")
        return 2
    LOG.info("loaded %d dev tasks", len(tasks))

    planned_cells = 2 * 2 * len(tasks)  # models x modes x tasks

    if args.dry_run or not args.execute:
        LOG.info("PLAN (dry-run): %d tasks x 2 modes x [F16, Q8_0] = %d cells",
                 len(tasks), planned_cells)
        for tid in task_ids:
            LOG.info("  task %s", tid)
        LOG.info("thresholds: %s", F16_MIN)
        if not args.execute:
            LOG.info("NOT executed: pass --execute (and set "
                     "LOCAL_AGENTBENCH_RUN_CANARY=1) to run.")
        return 0

    for label, p in (("F16", f16), ("Q8_0", q8)):
        if not p.exists():
            LOG.error("%s model not found: %s", label, p)
            return 2

    if os.environ.get("LOCAL_AGENTBENCH_RUN_CANARY") != "1":
        LOG.error("refusing to run: LOCAL_AGENTBENCH_RUN_CANARY != 1")
        return 3

    records = []
    t0 = time.monotonic()
    for model_label, model_path in (("F16", f16), ("Q8_0", q8)):
        LOG.info("using model artifact for %s: %s", model_label, model_path)
        for task in tasks:
            for mode in ("synthesis", "repair"):
                prompt = build_prompts(task)[0 if mode == "synthesis" else 1]
                rec = run_cell(task, mode, prompt, model_path, out_dir,
                               args.timeout)
                records.append(rec)
                LOG.info("%s %s %s: outcome=%s (stage=%s)",
                         model_label, task["task_id"], mode,
                         rec["outcome"], rec["stage"])

    status, verdict = decide(records, planned_cells, F16_MIN)
    summary = summarize([r for r in records if r["model"].startswith("F16")])
    q8_summary = summarize([r for r in records if r["model"].startswith("Q8")])

    result = {
        "status": status,
        "verdict": verdict,
        "wall_s": round(time.monotonic() - t0, 1),
        "thresholds": F16_MIN,
        "planned_cells": planned_cells,
        "actual_cells": len(records),
        "f16": summary,
        "q8": q8_summary,
        "records": records,
    }
    (out_dir / "canary_summary.json").write_text(json.dumps(result, indent=1))
    LOG.info("canary status: %s", status)
    LOG.info("F16 summary: %s", json.dumps(summary))
    LOG.info("Q8 summary: %s", json.dumps(q8_summary))
    if status == "BLOCKED":
        LOG.error("BLOCKED: %s", json.dumps(verdict))
        return 4
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
