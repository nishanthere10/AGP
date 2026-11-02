#!/usr/bin/env bash
set -u
cd /home/aaksh/projects/LocalAgentBench
ROOT=$PWD
BIN=$ROOT/third_party/llama.cpp/build/bin
MODEL=$ROOT/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
OUT=$ROOT/results/inference_smoke

echo "=== llama-cli with --log-file, timed ==="
start=$(date +%s%N)
timeout 120 "$BIN/llama-cli" -m "$MODEL" -p 'hi' -n 16 -c 512 -t 4 --temp 0.0 \
  --log-file "$OUT/cli1.log" < /dev/null > "$OUT/cli1.out" 2> "$OUT/cli1.err"
rc=$?
end=$(date +%s%N)
echo "cli_rc=$rc elapsed_ms=$(( (end-start)/1000000 ))"
echo "sizes: out=$(wc -c < "$OUT/cli1.out") err=$(wc -c < "$OUT/cli1.err") log=$(wc -c < "$OUT/cli1.log" 2>/dev/null || echo NA)"
echo "--- log head ---"
head -20 "$OUT/cli1.log" 2>/dev/null
echo "--- log tail ---"
tail -20 "$OUT/cli1.log" 2>/dev/null
