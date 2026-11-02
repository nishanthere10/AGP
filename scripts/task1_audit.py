#!/usr/bin/env python3
"""task1_audit.py - Classify all pilot_v2 output types per task/attempt."""
import json
from pathlib import Path

ROOT = Path('/home/aaksh/projects/LocalAgentBench')
data = json.loads((ROOT / 'results/pilot_v2/summary.json').read_text())

def classify_body(content):
    """Classify the body file content type."""
    if not content.strip():
        return 'EMPTY'
    lines = content.strip().split('\n')
    first = lines[0].strip()
    if first.startswith('def '):
        return 'FULL_DEF'
    if first.startswith('```'):
        return 'MARKDOWN_FENCE'
    # Heuristic: code body starts with indentation or known keywords
    code_starters = ('    ', '\t', 'return ', 'if ', 'for ', 'while ', 'try:',
                     'with ', 'import ', 'from ', 'raise ', 'yield ', 'pass',
                     'result', 'count', 'n =', 's =', 'primes', 'begin', 'vowels')
    if any(first.startswith(s) for s in code_starters):
        return 'CODE_BODY'
    return 'PROSE'

print('=== TASK 1: OUTPUT TYPE AUDIT ===')
print()

# Summary counts
counts = {'FULL_DEF': 0, 'CODE_BODY': 0, 'PROSE': 0,
          'MARKDOWN_FENCE': 0, 'EMPTY': 0, 'NO_FILE': 0}

rows = []
for r in data:
    tid = r['task_id']
    cfg = r['config']
    for a in r['attempt_log']:
        att = a['attempt']
        body_file = ROOT / f'results/pilot_v2/{tid.replace("/","_")}_{cfg}/body_a{att}.py'
        extract = a['extract']
        eval_cat = a['eval'].get('category', '?')
        eval_note = a['eval'].get('note', '')[:80]

        if not body_file.exists():
            btype = 'NO_FILE'
            preview = f'[extract={extract[:60]}]'
        else:
            content = body_file.read_text()
            btype = classify_body(content)
            preview = content[:80].replace('\n', '\\n')

        counts[btype] = counts.get(btype, 0) + 1
        rows.append((tid, cfg, att, btype, preview, eval_cat, eval_note))

# Print full table
print(f'{"Task":<12} {"C":<2} {"A":<2} {"Type":<16} {"Content preview":<70} Eval')
print('-' * 120)
for tid, cfg, att, btype, preview, eval_cat, eval_note in rows:
    print(f'{tid:<12} {cfg:<2} {att:<2} {btype:<16} {preview[:68]:<70} {eval_cat}')

print()
print('=== SUMMARY COUNTS (all attempts across A/B/C) ===')
total = sum(counts.values())
for btype, n in sorted(counts.items(), key=lambda x: -x[1]):
    print(f'  {btype:<16}: {n}/{total}')

print()
print('=== ANALYSIS: Why import_error fires on FULL_DEF ===')
print('evaluate_candidate.py line 58: code = row["declaration"] + body_file_content')
print()
print('If body = "def f(...):\\n    body", then:')
print('  code = declaration + "def f(...):\\n    body"')
print('  = "...\\ndef f(...):\\n\\ndef f(...):\\n    body"')
print('  Python: IndentationError: expected indented block after function def on line N')
print()
print('If body = "    body_only", then:')
print('  code = declaration + "    body_only"')
print('  = "...\\ndef f(...):\\n    body_only" <- CORRECT')
print()

# Check specifically: for FULL_DEF cases, what does the full_def contain?
print('=== FULL_DEF CASES: is the algorithm actually correct? ===')
for r in data:
    tid = r['task_id']
    cfg = r['config']
    for a in r['attempt_log']:
        att = a['attempt']
        body_file = ROOT / f'results/pilot_v2/{tid.replace("/","_")}_{cfg}/body_a{att}.py'
        if body_file.exists():
            content = body_file.read_text()
            if classify_body(content) == 'FULL_DEF':
                print(f'\n{tid} {cfg} attempt {att}:')
                print(f'  eval: {a["eval"]["category"]} | {a["eval"].get("note","")[:100]}')
                print(f'  code: {content[:200]}')

print()
print('Done.')
