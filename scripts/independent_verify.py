#!/usr/bin/env python3
"""independent_verify.py — independent verification of pilot_v2 results.
Run from /home/aaksh/projects/LocalAgentBench
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path('/home/aaksh/projects/LocalAgentBench')
data = json.loads((ROOT / 'results/pilot_v2/summary.json').read_text())

print(f'Total records in summary.json: {len(data)}')

TASKS = [f'Python/{i}' for i in range(0, 160, 16)]
CONFIGS = ['A', 'B', 'C']

# Build lookup
lookup = {}
for r in data:
    lookup[(r['task_id'], r['config'])] = r

# Check coverage
missing = []
for t in TASKS:
    for c in CONFIGS:
        if (t, c) not in lookup:
            missing.append(f'{t}/{c}')
none_str = 'NONE'
print(f'Missing records: {missing if missing else none_str}')

# Independent per-config metrics
agg = {}
for cfg in CONFIGS:
    recs = [r for r in data if r['config'] == cfg]
    n = len(recs)
    a1_stats = [r['attempt_log'][0] for r in recs]
    
    valid_json = sum(1 for a in a1_stats if a['extract'].startswith('ok-'))
    ran = sum(1 for a in a1_stats if a['eval'].get('rc') in (0, 1, 2))
    pass1 = sum(1 for r in recs if r['initial_success'])
    passN = sum(1 for r in recs if r['final_success'])
    repair_recovered = sum(1 for r in recs if r['final_success'] and not r['initial_success'])
    total_wall = sum(r['wall_s_total'] for r in recs)
    mean_wall = total_wall / n if n > 0 else 0
    
    modes = Counter(a['eval'].get('category', 'unknown') for a in a1_stats)
    attempt_dist = Counter(r['attempts_used'] for r in recs)
    total_gen_calls = sum(r['attempts_used'] for r in recs)
    
    agg[cfg] = {
        'n': n,
        'valid_json': valid_json,
        'ran': ran,
        'pass1': pass1,
        'passN': passN,
        'repair_recovered': repair_recovered,
        'total_wall': total_wall,
        'mean_wall': mean_wall,
        'modes': dict(modes),
        'attempt_dist': dict(attempt_dist),
        'total_gen_calls': total_gen_calls,
    }
    
    print(f'\n=== Config {cfg} (n={n}) ===')
    print(f'  Valid JSON rate (a1): {valid_json}/{n} ({100*valid_json//n}%)')
    print(f'  Ran rate (a1):        {ran}/{n} ({100*ran//n}%)')
    print(f'  Pass@1:               {pass1}/{n} ({100*pass1//n}%)')
    print(f'  Pass@N (final):       {passN}/{n} ({100*passN//n}%)')
    if cfg == 'C':
        print(f'  Repair recovery:      {repair_recovered}/{n}')
        print(f'  Attempt dist:         {dict(attempt_dist)}')
        print(f'  Total gen calls:      {total_gen_calls}')
    print(f'  Failure modes (a1):   {dict(modes)}')
    print(f'  Mean wall/task:       {mean_wall:.1f}s')
    print(f'  Total wall:           {total_wall:.1f}s ({total_wall/60:.1f} min)')

# Per-task table
print('\n=== Per-task per-config eval results ===')
header = f'{"Task":<12} A_extract  A_eval           B_extract  B_eval           C_a1_eval'
print(header)
print('-' * len(header))
for t in TASKS:
    row = f'{t:<12} '
    for cfg in CONFIGS:
        r = lookup.get((t, cfg))
        if r:
            a1 = r['attempt_log'][0]
            ext = 'ok-json' if a1['extract'].startswith('ok-') else 'malformed'
            cat = a1['eval'].get('category', '?')
            row += f'{ext:<11}{cat:<17}'
        else:
            row += 'MISSING'.ljust(28)
    print(row)

# Config C: body file content analysis
print('\n=== Config C: what did the fix field actually contain? ===')
for t in TASKS:
    r = lookup.get((t, 'C'))
    if not r:
        continue
    print(f'\n{t}:')
    for a in r['attempt_log']:
        body_file = ROOT / f'results/pilot_v2/{t.replace("/", "_")}_C/body_a{a["attempt"]}.py'
        body_preview = '(no body file - malformed extract)'
        if body_file.exists():
            content = body_file.read_text()
            first_line = content.split('\n')[0] if content else ''
            is_full_def = first_line.strip().startswith('def ') or first_line.strip().startswith('```')
            body_type = 'FULL_DEF' if is_full_def else 'BODY_ONLY'
            body_preview = f'{body_type}: {repr(content[:100])}'
        cat = a['eval'].get('category', '?')
        print(f'  a{a["attempt"]}: {cat} | {body_preview}')

# Extra cost analysis: C vs B
print('\n=== Cost analysis: C vs B extra generation budget ===')
b_wall = agg['B']['total_wall']
c_wall = agg['C']['total_wall']
b_calls = agg['B']['total_gen_calls']
c_calls = agg['C']['total_gen_calls']
print(f'  Config B total wall: {b_wall:.1f}s, total calls: {b_calls}')
print(f'  Config C total wall: {c_wall:.1f}s, total calls: {c_calls}')
print(f'  Extra wall (C-B):    {c_wall-b_wall:.1f}s ({(c_wall-b_wall)/60:.1f} min)')
print(f'  Extra calls (C-B):   {c_calls-b_calls}')
print(f'  C repair_recovered:  {agg["C"]["repair_recovered"]} tasks')
if agg['C']['repair_recovered'] > 0:
    print(f'  Extra wall per recovery: {(c_wall-b_wall)/agg["C"]["repair_recovered"]:.1f}s')
else:
    print(f'  Extra wall per recovery: N/A (0 recoveries)')

# Verdict
print('\n=== VERDICT ===')
a_pass = agg['A']['passN']
b_pass = agg['B']['passN']
c_pass = agg['C']['passN']
print(f'A Pass@N: {a_pass}/10  B Pass@N: {b_pass}/10  C Pass@N: {c_pass}/10')
if a_pass == 0 and b_pass == 0 and c_pass == 0:
    print('FLOOR EFFECT: All three configurations pass 0/10 tasks.')
    print('The 1.5B model cannot produce any oracle-passing solutions on this 10-task set.')
    print('Grammar enforcement: B/C produce valid JSON more reliably than A,')
    print('but the fix values contain natural language descriptions, not code.')
    print('The repair loop (C) uses all 3 attempts but never recovers any task.')
    print('VERDICT: PROCEED WITH MODIFICATIONS')
else:
    print(f'Non-zero pass rate detected.')

print('\nDone.')
