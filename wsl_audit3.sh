#!/usr/bin/env bash
set -u
echo "== groups =="
id
echo "== projects dir =="
ls -la ~/projects 2>&1
echo "== existing llama.cpp / models =="
find /home/aaksh -maxdepth 4 -iname '*llama*' 2>/dev/null | head
find /home/aaksh -maxdepth 4 -name '*.gguf' 2>/dev/null | head
echo "== network =="
curl -sS -o /dev/null -w 'github: %{http_code} (%{time_total}s)\n' --max-time 15 https://github.com/ggml-org/llama.cpp 2>&1
curl -sS -o /dev/null -w 'hf: %{http_code} (%{time_total}s)\n' --max-time 15 https://huggingface.co 2>&1
echo "== git default branch config =="
git config --global init.defaultBranch 2>&1 || true
echo "== existing temp scripts cleanup marker =="
echo done
