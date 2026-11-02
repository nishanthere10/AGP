#!/usr/bin/env bash
set -u
cd /home/aaksh/projects/LocalAgentBench
ROOT=$PWD
BIN=$ROOT/third_party/llama.cpp/build/bin
MODEL=$ROOT/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
OUT=$ROOT/results/inference_smoke
mkdir -p "$OUT"

echo "=== llama-completion attempt ==="
timeout 300 "$BIN/llama-completion" -m "$MODEL" \
  -p 'Write a Python function that returns the nth Fibonacci number.' \
  -n 64 -c 2048 -t 4 --temp 0.0 --seed 42 \
  --log-file "$OUT/comp1.log" \
  > "$OUT/comp1.out" 2> "$OUT/comp1.err"
echo "comp_rc=$?"
echo "sizes: out=$(wc -c < "$OUT/comp1.out") err=$(wc -c < "$OUT/comp1.err") log=$(wc -c < "$OUT/comp1.log" 2>/dev/null || echo 0)"
echo "--- stdout ---"
cat "$OUT/comp1.out"
echo "--- stderr tail ---"
tail -20 "$OUT/comp1.err"
echo "--- log tail ---"
tail -30 "$OUT/comp1.log" 2>/dev/null
