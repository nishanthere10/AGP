#!/usr/bin/env python3
"""Regression tests for run_canary.py verdict logic (BLOCKED/FAIL/PASS)."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path("/home/aaksh/projects/LocalAgentBench")
spec = importlib.util.spec_from_file_location("rc", ROOT / "scripts/run_canary.py")
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)

FAILED = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILED.append(name)


def cell(outcome, model="F16", mode="synthesis", stage="evaluate"):
    return {"outcome": outcome, "model": model, "mode": mode, "stage": stage}


# --- decide(): infrastructure => BLOCKED (never a model failure) ------------
recs = [cell("pass"), cell("pass"), cell("harness_error")]
status, details = rc.decide(recs, planned_cells=3, thresholds=rc.F16_MIN)
check("harness_error -> BLOCKED", status == "BLOCKED")
check("BLOCKED reason records infra outcomes",
      "harness_error" in details["infra_outcomes"])

recs = [cell("pass"), cell("gen_failure")]
status, details = rc.decide(recs, planned_cells=3, thresholds=rc.F16_MIN)
check("gen_failure + incomplete -> BLOCKED", status == "BLOCKED")
check("incomplete flagged", details["actual_cells"] == 2)

# --- decide(): partial run can never PASS ------------------------------------
recs = [cell("pass")]  # only 1 of 48 planned
status, details = rc.decide(recs, planned_cells=48, thresholds=rc.F16_MIN)
check("partial run -> BLOCKED (not PASS)", status == "BLOCKED")

# --- decide(): complete + thresholds met => PASS ------------------------------
def full_pass_records(n=12):
    # 12 dev tasks x 2 models x 2 modes = 48 cells; F16 all pass
    out = []
    for model in ("F16", "Q8_0"):
        for mode in ("synthesis", "repair"):
            for _ in range(n):
                out.append({"outcome": "pass", "model": model, "mode": mode,
                            "stage": "evaluate"})
    return out

recs = full_pass_records(12)
status, _ = rc.decide(recs, planned_cells=48, thresholds=rc.F16_MIN)
check("complete all-pass -> PASS", status == "PASS")

# --- decide(): complete, no infra, thresholds unmet => FAIL ------------------
recs = full_pass_records(12)
for r in recs:
    if r["model"] == "F16":
        r["outcome"] = "extraction_rejected"
status, _ = rc.decide(recs, planned_cells=48, thresholds=rc.F16_MIN)
check("complete but floor -> FAIL", status == "FAIL")

# --- classify_eval -----------------------------------------------------------
check("eval rc=5 -> harness_error", rc.classify_eval(5, "") == "harness_error")
check("eval rc=0 -> pass", rc.classify_eval(0, "") == "pass")
check("eval rc=3 -> fail_import", rc.classify_eval(3, "") == "fail_import")
check("eval rc=99 -> harness_error", rc.classify_eval(99, "") == "harness_error")

# --- summarize counts ---------------------------------------------------------
recs = [
    {"outcome": "pass", "model": "F16", "mode": "synthesis", "stage": "evaluate"},
    {"outcome": "fail_assertion", "model": "F16", "mode": "synthesis",
     "stage": "evaluate"},
    {"outcome": "extraction_rejected", "model": "F16", "mode": "synthesis",
     "stage": "extract"},
]
s = rc.summarize(recs)
check("summarize functional=1", s["synthesis"]["functional"] == 1)
check("summarize extractable=2", s["synthesis"]["extractable"] == 2)
check("summarize syntax_valid=2", s["synthesis"]["syntax_valid"] == 2)


def test_model_path_passed():
    """The canary must generate with the explicit artifact path, not the
    module-level 1.5B MODEL default."""
    import tempfile
    calls = {}
    orig_gen, orig_ext, orig_eval = (rc.pr.generate, rc.pr.extract_definition,
                                     rc.pr.evaluate)

    def fake_gen(prompt, grammar, tag, model=None):
        calls["model"] = model
        return {"rc": 0,
                "stdout": "def f(x):\n    return x\n",
                "stderr": "",
                "wall_s": 0.1,
                "peak_rss_kb": None,
                "prompt_tokens": 10,
                "completion_tokens": 5}

    def fake_ext(raw, task):
        return raw, {"kind": "ok-def"}

    def fake_eval(task, src):
        return {"rc": 0, "category": "pass", "note": ""}

    rc.pr.generate, rc.pr.extract_definition, rc.pr.evaluate = (
        fake_gen, fake_ext, fake_eval)
    try:
        task = {"task_id": "Python/0", "instruction": "wr", "declaration": "def f(x):\n",
                "buggy_solution": "    return x + 1\n"}
        model = Path("/tmp/f16.gguf")
        with tempfile.TemporaryDirectory() as td:
            rec = rc.run_cell(task, "synthesis", "p", model, Path(td), 10.0)
            check("generate receives explicit model path", calls.get("model") == model)
            check("cell outcome is pass", rec["outcome"] == "pass")
    finally:
        rc.pr.generate, rc.pr.extract_definition, rc.pr.evaluate = (
            orig_gen, orig_ext, orig_eval)


test_model_path_passed()


def main() -> int:
    if FAILED:
        print("\n%d FAILED: %s" % (len(FAILED), FAILED))
        return 1
    print("\nALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
