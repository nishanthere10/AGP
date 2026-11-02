#!/usr/bin/env bash
# step2_smoke_test.sh — Step 2: verify llama-completion flags and run a
# single-task end-to-end smoke test before executing the full pilot.
#
# Checks (in order):
#   1. Binary exists and responds to --help
#   2. --no-conversation is listed in help output
#   3. --single-turn is listed in help output
#   4. --no-display-prompt is listed in help output
#   5. Single generation completes (rc=0, non-empty stdout)
#   6. extract_body parses the output ({"fix": ...})
#   7. sandbox evaluator runs and returns a numeric exit code
#
# Usage: bash scripts/step2_smoke_test.sh [--task Python/0]
#
# All output is also written to reports/step2_smoke_test.log

set -euo pipefail

PROJ="/home/aaksh/projects/LocalAgentBench"
BIN="$PROJ/third_party/llama.cpp/build/bin/llama-completion"
MODEL="$PROJ/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
GRAMMAR="$PROJ/scripts/response.gbnf"
PQ="$PROJ/third_party/dataset/humanevalpack_python_test.parquet"
EVAL="$PROJ/scripts/evaluate_candidate.py"
VENV_PY="$PROJ/.venv/bin/python"
WORKDIR="$PROJ/pilot_workdir"
LOG="$PROJ/reports/step2_smoke_test.log"
TASK="${1:-Python/0}"

# strip --task prefix if passed
if [[ "$TASK" == --task* ]]; then
    TASK="${2:-Python/0}"
fi

PASS=0
FAIL=0

ts() { date '+%H:%M:%S'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }
ok()  { log "  PASS: $*"; ((PASS++)); }
err() { log "  FAIL: $*"; ((FAIL++)); }

mkdir -p "$(dirname "$LOG")"
echo "=== Step 2 smoke test: $(date) ===" >> "$LOG"
log "Project: $PROJ"
log "Task:    $TASK"

# ─── Check 1: binary exists ───────────────────────────────────────────────────
log ""
log "Check 1: binary exists"
if [[ -x "$BIN" ]]; then
    ok "$BIN"
else
    err "binary not found or not executable: $BIN"
    log "FATAL: cannot continue without binary"
    exit 1
fi

# ─── Check 2-4: flags present in --help ───────────────────────────────────────
log ""
log "Check 2-4: required flags in --help"
HELP_OUT=$("$BIN" --help 2>&1 || true)
HELP_LINES=$(echo "$HELP_OUT" | wc -l)
log "  --help output: $HELP_LINES lines"

for FLAG in "--no-conversation" "--single-turn" "--no-display-prompt"; do
    if echo "$HELP_OUT" | grep -q -- "$FLAG"; then
        ok "flag $FLAG present in --help"
    else
        err "flag $FLAG NOT found in --help"
    fi
done

# Save full help for audit
echo "$HELP_OUT" > "$PROJ/reports/llama_completion_help.txt"
log "  Full --help saved to reports/llama_completion_help.txt"

# ─── Check 5: single generation ───────────────────────────────────────────────
log ""
log "Check 5: single generation (task $TASK, config B, 64 tokens)"
mkdir -p "$WORKDIR"

# Extract prompt fields from dataset
PROMPT_FILE="/tmp/smoke_prompt_$$.txt"
BODY_FILE="/tmp/smoke_body_$$.py"

"$VENV_PY" - <<'PYEOF' "$TASK" "$PROMPT_FILE"
import sys
import pyarrow.parquet as pq
from pathlib import Path

ROOT = Path("/home/aaksh/projects/LocalAgentBench")
PQ = ROOT / "third_party/dataset/humanevalpack_python_test.parquet"

task_id = sys.argv[1]
out_file = sys.argv[2]

rows = {r["task_id"]: r for r in pq.read_table(PQ).to_pylist()}
if task_id not in rows:
    print(f"ERROR: task {task_id} not in dataset", file=sys.stderr)
    sys.exit(1)

row = rows[task_id]
prompt = (
    'Below is a Python function with a bug. Respond with ONLY a JSON object of the form '
    '{"fix": "<the complete corrected function body>"}. Do not write anything else.\n\n'
    + row["instruction"] + "\n\n"
    + row["declaration"] + "\n# BUGGY:\n" + row["buggy_solution"]
)

with open(out_file, "w") as f:
    f.write(prompt)
print(f"Prompt written ({len(prompt)} chars) -> {out_file}")
PYEOF

log "  Prompt written: $PROMPT_FILE"

SMOKE_LOG="/tmp/smoke_gen_$$.log"
SMOKE_TIME="/tmp/smoke_time_$$.txt"
SMOKE_OUT=""
GEN_RC=0

if [[ -x /usr/bin/time ]]; then
    /usr/bin/time -v -o "$SMOKE_TIME" \
        "$BIN" -m "$MODEL" -f "$PROMPT_FILE" \
        -n 64 -c 2048 -t 4 --temp 0.0 --seed 42 -ngl 0 \
        --no-conversation --single-turn --no-display-prompt \
        --grammar-file "$GRAMMAR" \
        --log-file "$SMOKE_LOG" \
        > /tmp/smoke_stdout_$$.txt 2>/tmp/smoke_stderr_$$.txt \
        || GEN_RC=$?
else
    "$BIN" -m "$MODEL" -f "$PROMPT_FILE" \
        -n 64 -c 2048 -t 4 --temp 0.0 --seed 42 -ngl 0 \
        --no-conversation --single-turn --no-display-prompt \
        --grammar-file "$GRAMMAR" \
        --log-file "$SMOKE_LOG" \
        > /tmp/smoke_stdout_$$.txt 2>/tmp/smoke_stderr_$$.txt \
        || GEN_RC=$?
fi

SMOKE_OUT=$(cat /tmp/smoke_stdout_$$.txt)
STDOUT_BYTES=${#SMOKE_OUT}
log "  Generation rc=$GEN_RC  stdout_bytes=$STDOUT_BYTES"
log "  First 200 chars of stdout: ${SMOKE_OUT:0:200}"

if [[ $GEN_RC -eq 0 ]]; then
    ok "generation rc=0"
else
    err "generation rc=$GEN_RC (expected 0)"
    log "  stderr tail: $(tail -20 /tmp/smoke_stderr_$$.txt)"
fi

if [[ $STDOUT_BYTES -gt 0 ]]; then
    ok "non-empty stdout ($STDOUT_BYTES bytes)"
else
    err "stdout is empty"
fi

# Latency and RSS from /usr/bin/time if available
if [[ -f "$SMOKE_TIME" ]]; then
    WALL=$(grep "Elapsed (wall clock)" "$SMOKE_TIME" | awk '{print $NF}' || echo "n/a")
    RSS=$(grep "Maximum resident set size" "$SMOKE_TIME" | awk '{print $NF}' || echo "n/a")
    log "  Wall time: $WALL  Peak RSS: ${RSS} kB"
fi

# ─── Check 6: extract_body parses output ──────────────────────────────────────
log ""
log "Check 6: extract_body parses output"

PARSE_RESULT=$("$VENV_PY" - <<PYEOF2
import json, sys

text = """$SMOKE_OUT"""
text = text.strip()

if not text:
    print("FAIL: empty output")
    sys.exit(1)

decoder = json.JSONDecoder()
idx = text.find("{")
while idx != -1:
    try:
        obj, _ = decoder.raw_decode(text[idx:])
        if isinstance(obj, dict) and "fix" in obj:
            body = obj["fix"]
            print(f"ok-json: fix={repr(body[:80])}")
            sys.exit(0)
    except ValueError:
        pass
    idx = text.find("{", idx + 1)

print(f"FAIL: no parseable {{\"fix\": ...}} found. Raw: {repr(text[:200])}")
sys.exit(1)
PYEOF2
) || PARSE_RC=$?

log "  parse result: $PARSE_RESULT"
if echo "$PARSE_RESULT" | grep -q "^ok-json:"; then
    ok "extract_body found {\"fix\": ...}"

    # Write extracted body for eval
    "$VENV_PY" - <<PYEOF3
import json, sys
from pathlib import Path

text = open("/tmp/smoke_stdout_$$.txt").read().strip()
decoder = json.JSONDecoder()
idx = text.find("{")
while idx != -1:
    try:
        obj, _ = decoder.raw_decode(text[idx:])
        if isinstance(obj, dict) and "fix" in obj:
            Path("$BODY_FILE").write_text(obj["fix"])
            print("body extracted OK")
            sys.exit(0)
    except ValueError:
        pass
    idx = text.find("{", idx + 1)
print("no fix found")
sys.exit(1)
PYEOF3

else
    err "extract_body failed: $PARSE_RESULT"
fi

# ─── Check 7: sandbox evaluator ───────────────────────────────────────────────
log ""
log "Check 7: sandbox evaluator"

if [[ ! -f "$BODY_FILE" ]]; then
    log "  Skipping (no body extracted in check 6)"
    err "sandbox eval skipped — no body"
else
    EVAL_RC=0
    EVAL_OUT=$("$VENV_PY" "$EVAL" \
        --task-id "$TASK" \
        --body-file "$BODY_FILE" \
        --timeout 10 2>&1) || EVAL_RC=$?

    log "  evaluator rc=$EVAL_RC  output: ${EVAL_OUT:0:200}"

    CATEGORY="unknown"
    case $EVAL_RC in
        0) CATEGORY="pass" ;;
        1) CATEGORY="assertion_fail" ;;
        2) CATEGORY="runtime_error" ;;
        3) CATEGORY="import_error" ;;
        4) CATEGORY="missing_entry" ;;
        5) CATEGORY="harness_error" ;;
    esac

    # Any numeric rc from evaluator (0-5) means the plumbing works
    if [[ $EVAL_RC -le 5 ]]; then
        ok "evaluator returned rc=$EVAL_RC ($CATEGORY) — plumbing works"
        if [[ $EVAL_RC -eq 0 ]]; then
            log "  Bonus: smoke test task PASSED the oracle on first try!"
        fi
    else
        err "evaluator returned unexpected rc=$EVAL_RC"
    fi
fi

# ─── Summary ──────────────────────────────────────────────────────────────────
log ""
log "=== Step 2 smoke test complete ==="
log "PASS: $PASS   FAIL: $FAIL"
log "Log: $LOG"

# Clean up temp files
rm -f "$PROMPT_FILE" /tmp/smoke_stdout_$$.txt /tmp/smoke_stderr_$$.txt \
       /tmp/smoke_time_$$.txt "$BODY_FILE"

if [[ $FAIL -gt 0 ]]; then
    log "RESULT: SMOKE TEST FAILED — do not proceed to pilot until failures are fixed."
    exit 1
else
    log "RESULT: SMOKE TEST PASSED — pilot may proceed."
    exit 0
fi
