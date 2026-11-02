#!/usr/bin/env bash
# run_pilot.sh — Master orchestrator for LocalAgentBench Steps 2-6.
#
# Runs in order:
#   Step 2: Smoke test (flags + single-task end-to-end)
#   Step 3: Task validation (all 10 frozen tasks exist and oracle works)
#   Step 4: Full pilot (pilot_runner.py, 30 task-config records)
#   Step 5+6: Analysis and decision report (step5_analyze.py)
#
# Usage (from WSL, inside the project root):
#   bash scripts/run_pilot.sh
#
# Options:
#   --skip-smoke   skip Step 2 (use if already verified)
#   --skip-validate skip Step 3 (use if already verified)
#   --dry-run      pass --dry-run to pilot_runner.py (no actual inference)
#
# All output is logged to reports/run_pilot_<timestamp>.log

set -euo pipefail

PROJ="/home/aaksh/projects/LocalAgentBench"
VENV_PY="$PROJ/.venv/bin/python"
TS=$(date +%Y%m%d_%H%M%S)
LOG="$PROJ/reports/run_pilot_${TS}.log"
SKIP_SMOKE=0
SKIP_VALIDATE=0
DRY_RUN=""

for arg in "$@"; do
    case "$arg" in
        --skip-smoke)    SKIP_SMOKE=1 ;;
        --skip-validate) SKIP_VALIDATE=1 ;;
        --dry-run)       DRY_RUN="--dry-run" ;;
    esac
done

mkdir -p "$PROJ/reports"
tee_log() { tee -a "$LOG"; }

{
echo "========================================================"
echo " LocalAgentBench pilot run: $TS"
echo "========================================================"
echo "Project:  $PROJ"
echo "Log:      $LOG"
echo "Dry-run:  ${DRY_RUN:-no}"
echo ""

cd "$PROJ"

# ── Step 2: Smoke test ────────────────────────────────────────────────────────
if [[ $SKIP_SMOKE -eq 0 ]]; then
    echo "━━━ Step 2: Smoke test ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if bash scripts/step2_smoke_test.sh; then
        echo "[Step 2] PASSED"
    else
        echo "[Step 2] FAILED — aborting pilot. Check reports/step2_smoke_test.log"
        exit 1
    fi
    echo ""
else
    echo "[Step 2] Skipped (--skip-smoke)"
fi

# ── Step 3: Task validation ───────────────────────────────────────────────────
if [[ $SKIP_VALIDATE -eq 0 ]]; then
    echo "━━━ Step 3: Task validation ━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if "$VENV_PY" scripts/step3_validate_tasks.py; then
        echo "[Step 3] PASSED"
    else
        echo "[Step 3] FAILED — aborting pilot. Check reports/step3_task_validation.json"
        exit 1
    fi
    echo ""
else
    echo "[Step 3] Skipped (--skip-validate)"
fi

# ── Step 4: Execute pilot ─────────────────────────────────────────────────────
echo "━━━ Step 4: Execute pilot ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Running: $VENV_PY scripts/pilot_runner.py ${DRY_RUN}"
echo "Expected: 30 task-config records (10 tasks × 3 configs A/B/C)"
echo "Estimated time: ~60-90 min on i5-1235U @ 4 threads (9 tok/s generation)"
echo ""

PILOT_START=$(date +%s)
if "$VENV_PY" scripts/pilot_runner.py $DRY_RUN; then
    PILOT_END=$(date +%s)
    PILOT_WALL=$(( PILOT_END - PILOT_START ))
    echo ""
    echo "[Step 4] PASSED — wall time: ${PILOT_WALL}s"
else
    echo ""
    echo "[Step 4] pilot_runner.py exited non-zero. Check results/pilot_v2/"
    echo "         Attempting analysis on whatever records exist..."
fi
echo ""

# ── Steps 5+6: Analysis and report ───────────────────────────────────────────
echo "━━━ Steps 5+6: Analysis and decision report ━━━━━━━━━━━━━"
if [[ -n "$DRY_RUN" ]]; then
    echo "[Steps 5+6] Skipped (dry-run, no results to analyze)"
else
    if "$VENV_PY" scripts/step5_analyze.py; then
        echo "[Steps 5+6] PASSED — report written to reports/pilot_results.md"
    else
        ANALYZE_RC=$?
        if [[ $ANALYZE_RC -eq 2 ]]; then
            echo "[Steps 5+6] WARNING: report written but some runs are missing"
        else
            echo "[Steps 5+6] FAILED — check error output above"
            exit 1
        fi
    fi
fi
echo ""

echo "========================================================"
echo " Pilot run complete: $(date)"
echo " Reports:"
echo "   reports/step2_smoke_test.log"
echo "   reports/step3_task_validation.json"
echo "   results/pilot_v2/summary.json"
echo "   reports/pilot_results.md"
echo "========================================================"

} 2>&1 | tee_log

echo ""
echo "Full log: $LOG"
