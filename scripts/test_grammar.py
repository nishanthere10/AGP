#!/usr/bin/env bash
set -u
cd /home/aaksh/projects/LocalAgentBench
BIN=./third_party/llama.cpp/build/bin/llama-completion
MODEL=models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
OUT=/home/aaksh/projects/LocalAgentBench/results/inference_smoke
GRAMMAR=/home/aaksh/projects/LocalAgentBench/scripts/response.gbnf
TASK_PY=/home/aaksh/projects/LocalAgentBench/third_party/dataset/humanevalpack_python_test.parquet

# Get Python/0 task data
python3 -c "
import pyarrow.parquet as pq
t = pq.read_table('$TASK_PY').to_pylist()[0]
print(t['task_id'])
print('DECL:', repr(t['declaration']))
print('BUGGY:', repr(t['buggy_solution']))
print('CANON:', repr(t['canonical_solution']))
print('ENTRY:', t['entry_point'])
print('TEST:', repr(t['test']))
"

echo "=== Test 1: plain completion with HumanEvalPack prompt ==="
# Use the declaration + buggy solution as prompt (as the pilot would)
python3 -c "
import pyarrow.parquet as pq
t = pq.read_table('$TASK_PY').to_pylist()[0]
prompt = t['declaration'] + '\n# BUGGY:\n' + t['buggy_solution']
open('/tmp/prompt1.txt','w').write(prompt)
print('prompt_len:', len(prompt))
"

timeout 180 "$BIN" -m "$MODEL" -p "$(cat /tmp/prompt1.txt)" -n 128 -c 2048 -t 4 --temp 0.0 --seed 42 --no-conversation --single-turn > "$OUT/test1.log" 2> "$OUT/test1_err.log"
echo "rc=$?"
echo "--- stdout/log ---"
cat "$OUT/test1.log"
echo "--- stderr tail ---"
tail -5 "$OUT/test1_err.log"

echo ""
echo "=== Test 2: grammar-constrained with same prompt ==="
timeout 180 "$BIN" -m "$MODEL" -p "$(cat /tmp/prompt1.txt)" -n 128 -c 2048 -t 4 --temp 0.0 --seed 42 --no-conversation --single-turn --grammar-file "$GRAMMAR" > "$OUT/test2.log" 2> "$OUT/test2_err.log"
echo "rc=$?"
echo "--- stdout/log ---"
cat "$OUT/test2.log"
echo "--- stderr tail ---"
tail -5 "$OUT/test2_err.log"

echo ""
echo "=== Test 3: extract JSON fix from grammar output ==="
python3 -c "
import json, re, sys
text = open('$OUT/test2.log').read()
# find JSON object
m = re.search(r'\"\\\"fix\\\"\":', text)
if m:
    try:
        decoder = json.JSONDecoder()
        obj, idx = decoder.raw_decode(text[m.start():])
        fix = obj.get('fix')
        print('fix field:', repr(fix[:200]) if fix else 'None')
        print('type:', type(fix).__name__)
    except Exception as e:
        print('json error:', e)
else:
    print('no JSON fix key found')
    # show what we have
    m2 = re.search(r'```(?:python)?\s*\n(.*?)```', text, re.S)
    if m2:
        print('fenced code:', repr(m2.group(1)[:200]))
    else:
        # find last ``` or just show last 500 chars
        last = text.rfind('```')
        if last >= 0:
            print('after last ```:', repr(text[last:][:500]))
        else:
            print('last 500 chars:', repr(text[-500:]))
"