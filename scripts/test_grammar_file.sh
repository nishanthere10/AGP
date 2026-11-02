#!/usr/bin/env bash
set -u
cd /home/aaksh/projects/LocalAgentBench
BIN=./third_party/llama.cpp/build/bin/llama-completion
MODEL=models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
OUT=results/inference_smoke
GRAMMAR=scripts/response.gbnf

echo "=== Test: grammar file $GRAMMAR ==="
timeout 60 "$BIN" -m "$MODEL" -p "Is this working?" -n 8 -c 64 -t 4 --temp 0.0 --seed 42 --no-conversation --single-turn --grammar-file "$GRAMMAR" > "$OUT/grammar_test.log" 2> "$OUT/grammar_test_err.log"
echo "rc=$?"
echo "stdout_len=$(wc -c < "$OUT/grammar_test.log")"
echo "--- stdout ---"
cat "$OUT/grammar_test.log"
echo "--- stderr ---"
cat "$OUT/grammar_test_err.log"