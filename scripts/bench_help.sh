#!/usr/bin/env bash
set -u
cd /home/aaksh/projects/LocalAgentBench
./third_party/llama.cpp/build/bin/llama-bench --help 2>&1 | head -70
