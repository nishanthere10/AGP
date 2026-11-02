#!/usr/bin/env bash
set -u
cd /home/aaksh/projects/LocalAgentBench
ROOT=$PWD
BIN=$ROOT/third_party/llama.cpp/build/bin
MODEL=$ROOT/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
OUT=$ROOT/results/inference_smoke

echo "=== llama-cli under pty, stdin=/dev/null ==="
start=$(date +%s%N)
script -qec "$BIN/llama-cli -m $MODEL -p 'hi' -n 16 -c 512 -t 4 --temp 0.0" "$OUT/cli_pty.log" < /dev/null > /dev/null 2>&1
rc=$?
end=$(date +%s%N)
echo "rc=$rc elapsed_ms=$(( (end-start)/1000000 )) size=$(wc -c < "$OUT/cli_pty.log")"
echo "--- tail of pty log ---"
tail -c 2500 "$OUT/cli_pty.log" | cat -v | tail -40
