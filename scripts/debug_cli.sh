#!/usr/bin/env bash
set -u
ROOT=/home/aaksh/projects/LocalAgentBench
cd "$ROOT"
timeout 300 ./third_party/llama.cpp/build/bin/llama-cli \
  -m models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf \
  -p 'hi' -n 8 -c 512 -t 4 --temp 0.0 > /tmp/f.out 2> /tmp/f.err
echo "TRUE_RC=$?"
echo "out_bytes=$(wc -c < /tmp/f.out) err_bytes=$(wc -c < /tmp/f.err)"
echo "=== stderr ==="
cat /tmp/f.err
echo "=== stdout ==="
cat /tmp/f.out
echo "=== ldd check ==="
ldd ./third_party/llama.cpp/build/bin/llama-cli | grep -E 'not found|ggml|llama' || true
echo "=== direct run no timeout ==="
./third_party/llama.cpp/build/bin/llama-cli --version
echo "=== env ==="
echo "TERM=${TERM:-unset} LANG=${LANG:-unset} NO_COLOR=${NO_COLOR:-unset}"
