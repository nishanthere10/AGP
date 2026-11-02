#!/usr/bin/env bash
set -u
cd /home/aaksh/projects/LocalAgentBench
ROOT=$PWD
BIN=$ROOT/third_party/llama.cpp/build/bin
MODEL=$ROOT/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
OUT=$ROOT/results/inference_smoke

echo "=== backend lines from comp1 stderr ==="
grep -iE 'backend|cpu|cuda|gpu|offload' "$OUT/comp1.err" | head -15

echo "=== llama-cli with stdin from /dev/null ==="
timeout 120 "$BIN/llama-cli" -m "$MODEL" -p 'hi' -n 16 -c 512 -t 4 --temp 0.0 \
  < /dev/null > "$OUT/cli_null.out" 2> "$OUT/cli_null.err"
echo "cli_rc=$? sizes: out=$(wc -c < "$OUT/cli_null.out") err=$(wc -c < "$OUT/cli_null.err")"
tail -5 "$OUT/cli_null.err"

echo "=== llama-cli with piped stdin line ==="
echo "hello" | timeout 120 "$BIN/llama-cli" -m "$MODEL" -p 'hi' -n 16 -c 512 -t 4 --temp 0.0 \
  > "$OUT/cli_pipe.out" 2> "$OUT/cli_pipe.err"
echo "cli_rc=$? sizes: out=$(wc -c < "$OUT/cli_pipe.out") err=$(wc -c < "$OUT/cli_pipe.err")"
