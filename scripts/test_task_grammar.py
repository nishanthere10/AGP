#!/usr/bin/env bash
set -u
cd /home/aaksh/projects/LocalAgentBench
BIN=./third_party/llama.cpp/build/bin/llama-completion
MODEL=models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
OUT=results/inference_smoke
GRAMMAR=scripts/response.gbnf
TASK_PQ=/home/aaksh/projects/LocalAgentBench/third_party/dataset/humanevalpack_python_test.parquet

# Get Python/0 task data
python3 -c "
import pyarrow.parquet as pq
t = pq.read_table('$TASK_PQ').to_pylist()[0]
print(t['task_id'])
print('DECL:', repr(t['declaration']))
print('BUGGY:', repr(t['buggy_solution']))
print('CANON:', repr(t['canonical_solution']))
print('ENTRY:', t['entry_point'])
"

# Build prompt: declaration + buggy marker (as in pilot protocol)
python3 -c "
import pyarrow.parquet as pq
t = pq.read_table('$TASK_PQ').to_pylist()[0]
decl = t['declaration']
buggy = t['buggy_solution']
prompt = decl + '\n# BUGGY:\n' + buggy
open('/tmp/task_prompt.txt','w').write(prompt)
print('prompt_len:', len(prompt))
"

echo "=== Test: grammar with HumanEvalPack prompt ==="
timeout 180 "$BIN" -m "$MODEL" -p "$(cat /tmp/task_prompt.txt)" -n 256 -c 2048 -t 4 --temp 0.0 --seed 42 --no-conversation --single-turn --grammar-file "$GRAMMAR" > "$OUT/task_grammar.log" 2> "$OUT/task_grammar_err.log"
echo "rc=$?"
echo "stdout_len=$(wc -c < "$OUT/task_grammar.log")"
echo "--- stdout ---"
cat "$OUT/task_grammar.log"
echo "--- stderr (last 5) ---"
tail -5 "$OUT/task_grammar_err.log"

echo ""
echo "=== Extract fix from grammar output ==="
python3 -c "
import re, sys
text = open('$OUT/task_grammar.log').read()
print('full output length:', len(text))
# find 'fix' key
m = re.search(r'\"fix\"\s*:\s*\"(.*?)\"', text)
if m:
    print('fix value:', repr(m.group(1)[:300]))
else:
    print('no \"fix\" key found')
    # try looser
    m2 = re.search(r'\"fix\"\s*:', text)
    if m2:
        print('fix key at position:', m2.start())
        print('context:', repr(text[m2.start():m2.start()+200]))
    else:
        print('no fix key at all')
        # show last 300 chars
        print('last 300:', repr(text[-300:]))
"