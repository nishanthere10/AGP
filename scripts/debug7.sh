#!/usr/bin/env bash
set -u
cd /home/aaksh/projects/LocalAgentBench
ROOT=$PWD
BIN=$ROOT/third_party/llama.cpp/build/bin
MODEL=$ROOT/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
OUT=$ROOT/results/inference_smoke

echo "=== grammar-constrained run (response.gbnf) ==="
timeout 300 "$BIN/llama-completion" -m "$MODEL" \
  -p 'Fix the bug in this Python function and return JSON {"fix": "..."} with the corrected body:
def add(a, b):
    return a - b' \
  -n 96 -c 2048 -t 4 --temp 0.0 --seed 42 \
  --grammar-file "$ROOT/scripts/response.gbnf" \
  > "$OUT/grammar1.out" 2> "$OUT/grammar1.err"
echo "rc=$?"
echo "--- stdout ---"
cat "$OUT/grammar1.out"
echo "--- perf lines ---"
grep -E 'common_perf_print' "$OUT/grammar1.err"
