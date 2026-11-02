#!/usr/bin/env python3
"""task5_inspect.py — inspect single-task validation results."""
import json
from pathlib import Path

ROOT = Path('/home/aaksh/projects/LocalAgentBench')
data = json.loads((ROOT / 'results/task5_single/summary.json').read_text())

for r in data:
    cfg = r['config']
    print(f'\n=== Config {cfg} (Python/16) pass={r["final_success"]} ===')
    for a in r['attempt_log']:
        att = a['attempt']
        ext = a['extract']
        ev = a['eval']
        stdout_preview = a['gen_stdout'][:300].replace('\n', '\\n')
        print(f'  Attempt {att}:')
        print(f'    gen stdout (300c): {stdout_preview}')
        print(f'    extract:           {ext}')
        rc = ev.get('rc')
        cat = ev['category']
        note = ev.get('note', '')[:150]
        print(f'    eval:              rc={rc} ({cat})')
        print(f'    eval note:         {note}')
        bf = ROOT / f'results/task5_single/Python_16_{cfg}/body_a{att}.py'
        if bf.exists():
            body = bf.read_text()
            first_line = body.split('\n')[0]
            starts_with_def = first_line.strip().startswith('def ')
            print(f'    body file:         {repr(body[:120])}')
            print(f'    body type:         {"FULL_DEF" if starts_with_def else "body-only/prose"}')
        # If C, show repair prompt excerpt
        if 'repair_prompt_sent' in a:
            rp = a['repair_prompt_sent']
            print(f'    repair_prompt:     ...{rp[-200:].replace(chr(10), chr(92)+"n")}')
