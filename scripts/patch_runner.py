#!/usr/bin/env python3
"""patch_runner.py — apply Task 2 prompt change to pilot_runner.py in-place.
Must be run from the project root in WSL.
"""
from pathlib import Path

src = Path('/home/aaksh/projects/LocalAgentBench/scripts/pilot_runner.py')
text = src.read_text()

OLD_PROMPT_BLOCK = '''\
# Identical prompt for A, B and C (pilot_protocol.md): the JSON contract is
# described in the prompt for ALL configs; the ONLY A-vs-B difference is the
# GBNF decode-time constraint.
PROMPT_TEMPLATE = """Below is a Python function with a bug. Respond with ONLY a JSON object of the form {{"fix": "<the complete corrected function body>"}}. Do not write anything else.

{instruction}

{declaration}
# BUGGY:
{buggy}"""'''

NEW_PROMPT_BLOCK = '''\
# Identical prompt for A, B and C (pilot_protocol.md): the JSON contract is
# described in the prompt for ALL configs; the ONLY A-vs-B difference is the
# GBNF decode-time constraint.
#
# v3 change (2026-10-15): one-shot example added to show body-only code output.
# The example task is synthetic (not from the pilot set).
# The # BUGGY: marker has been removed; the buggy code is presented directly.
PROMPT_TEMPLATE = """Below is a Python function with a bug. Return ONLY a JSON object with a single key "fix" whose value is the corrected function body (the indented lines inside the def block, not the def line itself). Do not explain or add anything else.

Example:
Given:
def double(x):
    return x + x + x

Correct response:
{{"fix": "    return x * 2\\n"}}

Now fix this function:

{instruction}

{declaration}
{buggy}"""'''

if OLD_PROMPT_BLOCK not in text:
    print('ERROR: old block not found — check whitespace')
    import sys; sys.exit(1)

text2 = text.replace(OLD_PROMPT_BLOCK, NEW_PROMPT_BLOCK, 1)

# Also update the repair prompt in run_config to use the same body-only phrasing
OLD_REPAIR = (
    '"\\nRespond with ONLY a JSON object of the form "\n'
    '                  \'{"fix": "<the complete corrected function body>"}. \'\n'
    '                  "Do not write anything else."'
)
NEW_REPAIR = (
    '"\\nReturn ONLY a JSON object with a single key \\"fix\\" whose value is "\n'
    '                  "the corrected function body (indented lines inside the def block, "\n'
    '                  "not the def line itself). Do not explain or add anything else."'
)

if OLD_REPAIR in text2:
    text2 = text2.replace(OLD_REPAIR, NEW_REPAIR, 1)
    print('Repair prompt updated.')
else:
    print('WARNING: repair prompt pattern not found — skipping (non-fatal).')

src.write_text(text2)
print('pilot_runner.py patched (Task 2 prompt change).')

# Verify
check = Path('/home/aaksh/projects/LocalAgentBench/scripts/pilot_runner.py').read_text()
assert 'one-shot example' in check, 'PROMPT_TEMPLATE update missing'
assert 'def double(x):' in check, 'Example missing'
assert '# BUGGY:' not in check or check.count('# BUGGY:') == 0, '# BUGGY: marker still present'
print('Verification: PASSED')
