#!/usr/bin/env bash
set -u
cd /home/aaksh/projects/LocalAgentBench
BIN=./third_party/llama.cpp/build/bin/llama-completion
MODEL=models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
OUT=/home/aaksh/projects/LocalAgentBench/results/inference_smoke
mkdir -p "$OUT"

echo "=== Test 1: --no-conversation --single-turn ==="
timeout 120 "$BIN" -m "$MODEL" -p 'Write a Python function that returns the nth Fibonacci number.' -n 64 -c 2048 -t 4 --temp 0.0 --seed 42 --no-conversation --single-turn > "$OUT/ts1.log" 2> "$OUT/ts1_err.log"
echo "rc=$?"
echo "out_bytes=$(wc -c < "$OUT/ts1.log") err_bytes=$(wc -c < "$OUT/ts1_err.log")"
echo "--- stdout/log ---"
cat "$OUT/ts1.log"
echo "--- stderr ---"
cat "$OUT/ts1_err.log"

echo ""
echo "=== Test 2: --no-conversation only (default interactive=false) ==="
timeout 120 "$BIN" -m "$MODEL" -p 'Write a Python function that returns the nth Fibonacci number.' -n 64 -c 2048 -t 4 --temp 0.0 --seed 42 --no-conversation > "$OUT/ts2.log" 2> "$OUT/ts2_err.log"
echo "rc=$?"
echo "out_bytes=$(wc -c < "$OUT/ts2.log") err_bytes=$(wc -c < "$OUT/ts2_err.log")"
echo "--- stdout/log ---"
cat "$OUT/ts2.log"
echo "--- stderr tail ---"
tail -3 "$OUT/ts2_err.log"

echo ""
echo "=== Test 3: --conversation only ==="
timeout 120 "$BIN" -m "$MODEL" -p 'Write a Python function that returns the nth Fibonacci number.' -n 64 -c 2048 -t 4 --temp 0.0 --seed 42 --conversation > "$OUT/ts3.log" 2> "$OUT/ts3_err.log"
echo "rc=$?"
echo "out_bytes=$(wc -c < "$OUT/ts3.log") err_bytes=$(wc -c < "$OUT/ts3_err.log")"
echo "--- stdout/log ---"
cat "$OUT/ts3.log"