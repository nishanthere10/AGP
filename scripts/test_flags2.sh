#!/usr/bin/env bash
set -u
cd /home/aaksh/projects/LocalAgentBench
BIN=./third_party/llama.cpp/build/bin/llama-completion
MODEL=models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
OUT=/home/aaksh/projects/LocalAgentBench/results/inference_smoke
mkdir -p "$OUT"

echo "=== Test A: --no-conversation --interactive false --single-turn ==="
timeout 120 "$BIN" -m "$MODEL" -p 'Write a Python function that returns the nth Fibonacci number.' -n 64 -c 2048 -t 4 --temp 0.0 --seed 42 --no-conversation --interactive false --single-turn > "$OUT/a1.log" 2> "$OUT/a1_err.log"
echo "rc=$?"
echo "out_bytes=$(wc -c < "$OUT/a1.log") err_bytes=$(wc -c < "$OUT/a1_err.log")"
echo "--- stdout/log ---"
cat "$OUT/a1.log"
echo "--- stderr ---"
cat "$OUT/a1_err.log"

echo ""
echo "=== Test B: --no-conversation only ==="
timeout 120 "$BIN" -m "$MODEL" -p 'Write a Python function that returns the nth Fibonacci number.' -n 64 -c 2048 -t 4 --temp 0.0 --seed 42 --no-conversation > "$OUT/b1.log" 2> "$OUT/b1_err.log"
echo "rc=$?"
echo "out_bytes=$(wc -c < "$OUT/b1.log") err_bytes=$(wc -c < "$OUT/b1_err.log")"
echo "--- stdout/log ---"
head -3 "$OUT/b1.log"

echo ""
echo "=== Test C: --conversation only ==="
timeout 120 "$BIN" -m "$MODEL" -p 'Write a Python function that returns the nth Fibonacci number.' -n 64 -c 2048 -t 4 --temp 0.0 --seed 42 --conversation > "$OUT/c1.log" 2> "$OUT/c1_err.log"
echo "rc=$?"
echo "out_bytes=$(wc -c < "$OUT/c1.log") err_bytes=$(wc -c < "$OUT/c1_err.log")"
echo "--- stdout/log ---"
head -3 "$OUT/c1.log"