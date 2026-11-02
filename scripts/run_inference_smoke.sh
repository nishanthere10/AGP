#!/usr/bin/env bash
# run_inference_smoke.sh — Stage 4 controlled inference measurement.
#
# Usage: run_inference_smoke.sh <label> <n_predict> <ctx> <threads> [extra llama args...]
#
# Measures per run:
#   - llama.cpp's own timing lines (model load ms, prompt eval, generation speed)
#   - wall time, exit code  (/usr/bin/time -f)
#   - peak RSS of the process tree (/usr/bin/time -v -> Maximum resident set size)
#   - WSL memory before/after and swap usage (free -b)
#
# What each measurement includes/misses is documented in reports/inference_baseline.md.
set -u
ROOT=/home/aaksh/projects/LocalAgentBench
BIN=$ROOT/third_party/llama.cpp/build/bin
MODEL=$ROOT/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
OUTDIR=$ROOT/results/inference_smoke
LABEL=$1; N_PREDICT=$2; CTX=$3; THREADS=$4; shift 4

mkdir -p "$OUTDIR"
CMD=("$BIN/llama-cli" -m "$MODEL" -p "Write a Python function that returns the nth Fibonacci number." \
     -n "$N_PREDICT" -c "$CTX" -t "$THREADS" --temp 0.0 -no-cnv)
if [ $# -gt 0 ]; then CMD+=("$@"); fi

MEM_BEFORE=$(free -b | awk '/^Mem:/{print $2,$3,$7}/^Swap:/{print "swap",$2,$3}')
{
  echo "== label: $LABEL"
  echo "== date: $(date -Is)"
  echo "== cmd: ${CMD[*]}"
  echo "== mem_before: $MEM_BEFORE"
} | tee "$OUTDIR/$LABEL.meta"

# time -v gives peak RSS (max of the process, not tree-summed for children; llama-cli is single process tree)
/usr/bin/time -v -o "$OUTDIR/$LABEL.time" "${CMD[@]}" > "$OUTDIR/$LABEL.out" 2> "$OUTDIR/$LABEL.err"
RC=$?
MEM_AFTER=$(free -b | awk '/^Mem:/{print $2,$3,$7}/^Swap:/{print "swap",$2,$3}')
echo "== exit_code: $RC" | tee -a "$OUTDIR/$LABEL.meta"
echo "== mem_after: $MEM_AFTER" | tee -a "$OUTDIR/$LABEL.meta"
grep -E "Maximum resident set size|Elapsed \(wall" "$OUTDIR/$LABEL.time" | tee -a "$OUTDIR/$LABEL.meta"
echo "RC=$RC  out=$OUTDIR/$LABEL.out"
