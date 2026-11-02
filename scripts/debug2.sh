#!/usr/bin/env bash
set -u
cd /home/aaksh/projects/LocalAgentBench
BIN=./third_party/llama.cpp/build/bin
$BIN/llama-cli --help > /tmp/cli_help.txt 2>&1
echo "=== cli log/verbosity flags ==="
grep -inE 'log|verbos' /tmp/cli_help.txt | head -20
echo "=== completion help (head) ==="
$BIN/llama-completion --help > /tmp/comp_help.txt 2>&1
head -30 /tmp/comp_help.txt
echo "=== completion log flags ==="
grep -inE 'log|verbos' /tmp/comp_help.txt | head -10
