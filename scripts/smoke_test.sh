#!/usr/bin/env bash
# Stage 4 smoke test — one short generation with the real model.
set -u
ROOT=/home/aaksh/projects/LocalAgentBench
BIN=$ROOT/third_party/llama.cpp/build/bin/llama-cli
MODEL=$ROOT/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
OUT=$ROOT/results/inference_smoke
mkdir -p "$OUT"

timeout 300 "$BIN" -m "$MODEL" \
  -p 'Write a Python function that returns the nth Fibonacci number.' \
  -n 64 -c 2048 -t 4 --temp 0.0 --seed 42 \
  > "$OUT/smoke1.out" 2> "$OUT/smoke1.err"
rc=$?
echo "SMOKE_RC=$rc"
echo "--- stdout (last 40 lines) ---"
tail -40 "$OUT/smoke1.out"
echo "--- stderr (last 40 lines) ---"
tail -40 "$OUT/smoke1.err"
echo "--- memory after ---"
free -h | head -2
