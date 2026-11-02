#!/usr/bin/env bash
set -u
cd /home/aaksh/projects/LocalAgentBench
CMD="./third_party/llama.cpp/build/bin/llama-cli -m models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf -p hi -n 8 -c 512 -t 4 --temp 0.0"
script -qec "$CMD" /tmp/tty.log > /dev/null 2>&1
echo "script_rc=$?"
echo "tty_log_bytes=$(wc -c < /tmp/tty.log)"
echo "=== tty log tail ==="
tail -c 3000 /tmp/tty.log | cat -v
