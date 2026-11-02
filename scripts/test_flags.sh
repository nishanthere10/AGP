#!/usr/bin/env bash
set -u
cd /home/aaksh/projects/LocalAgentBench
BIN=./third_party/llama.cpp/build/bin/llama-completion
MODEL=models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
OUT=/home/aaksh/projects/LocalAgentBench/results/inference_smoke
mkdir -p "$OUT"

echo "=== Test 1: --no-cnv --interactive false --single-turn ==="
timeout 120 "$BIN" -m "$MODEL" -p 'Write a Python function that returns the nth Fibonacci number.' -n 64 -c 2048 -t 4 --temp 0.0 --seed 42 --no-cnv --interactive false --single-turn > "$OUT/t1.log" 2> "$OUT/t1_err.log"
echo "rc=$?"
echo "out_bytes=$(wc -c < "$OUT/t1.log") err_bytes=$(wc -c < "$OUT/t1_err.log")"
echo "--- stdout/log ---"
cat "$OUT/t1.log"
echo "--- stderr ---"
cat "$OUT/t1_err.log"

echo ""
echo "=== Test 2: --no-cnv --interactive false (no --single-turn) ==="
timeout 120 "$BIN" -m "$MODEL" -p 'Write a Python function that returns the nth Fibonacci number.' -n 64 -c 2048 -t 4 --temp 0.0 --seed 42 --no-cnv --interactive false > "$OUT/t2.log" 2> "$OUT/t2_err.log"
echo "rc=$?"
echo "out_bytes=$(wc -c < "$OUT/t2.log") err_bytes=$(wc -c < "$OUT/t2_err.log")"
echo "--- stdout/log ---"
cat "$OUT/t2.log"
echo "--- stderr ---"
tail -5 "$OUT/t2_err.log"

echo ""
echo "=== Test 3: --no-cnv only (default interactive) ==="
timeout 120 "$BIN" -m "$MODEL" -p 'Write a Python function that returns the nth Fibonacci number.' -n 64 -c 2048 -t 4 --temp 0.0 --seed 42 --no-cnv > "$OUT/t3.log" 2> "$OUT/t3_err.log"
echo "rc=$?"
echo "out_bytes=$(wc -c < "$OUT/t3.log") err_bytes=$(wc -c < "$OUT/t3_err.log")"
echo "--- stdout/log ---"
head -5 "$OUT/t3.log"