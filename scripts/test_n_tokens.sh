#!/usr/bin/env bash
set -u
cd /home/aaksh/projects/LocalAgentBench
BIN=./third_party/llama.cpp/build/bin/llama-completion
MODEL=models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
OUT=results/inference_smoke
GRAMMAR=scripts/response.gbnf

check_fix() {
    local logfile=$1
    if grep -q '"fix"' "$logfile"; then
        echo "  HAS 'fix' key"
        # extract using python
        python3 -c "
import re, sys
text = open('$logfile').read()
m = re.search(r'\"fix\"\s*:\s*\"(.*?)\"', text)
if m:
    print('  fix value:', repr(m.group(1)[:200]))
else:
    print('  could not extract fix value')
    print('  last 300 chars:', repr(open('$logfile').read()[-300:]))
"
    else
        echo "  no 'fix' key"
        echo "  last 300 chars: $(tail -c 300 $logfile | cat -v)"
    fi
}

for N in 64 128 256; do
    echo "=== N=$N tokens ==="
    timeout 180 "$BIN" -m "$MODEL" -p "Fix the bug and return ONLY {\"fix\": \"<corrected function>\"}. No other text." -n $N -c 2048 -t 4 --temp 0.0 --seed 42 --no-conversation --single-turn --grammar-file "$GRAMMAR" > "$OUT/gen_N${N}.log" 2> "$OUT/gen_N${N}_err.log"
    echo "rc=$?"
    echo "stdout_len=$(wc -c < "$OUT/gen_N${N}.log")"
    echo "--- stdout ---"
    cat "$OUT/gen_N${N}.log"
    check_fix "$OUT/gen_N${N}.log"
    echo ""
done