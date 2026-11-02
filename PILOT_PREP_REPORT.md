# LocalAgentBench Pilot Preparation Report

Date: 2026-10-15
Status: **ISSUES FOUND** — Pilot execution should NOT proceed until resolved

## 1. Prompt Format Inconsistency — CRITICAL

### Protocol specification (reports/pilot_protocol.md, §3):
> "Below is a Python function with a bug. Return ONLY the complete corrected function body
> (the lines inside the function, indented), nothing else."

### Actual code prompt (scripts/pilot_runner.py, PROMPT_TEMPLATE):
> "Below is a Python function with a bug. Respond with ONLY a JSON object of the form
> **{"fix": "<the complete corrected function body>"}**. Do not write anything else.

### Debugging finding (test_prompts.py, test_task_grammar.py):
- The **BUGGY-marker prompt** (`decl + "\n# BUGGY:\n" + buggy`) produces standard model output 
  with `# BUGGY:`/`# CORRECTED:` markers, NOT `{"fix": "..."}` JSON
- The **generic JSON prompt** (`"Respond with ONLY {"fix": "<...>"}. Do not write anything else."`) 
  produces valid `{"fix": "def find_max(lst): return max(lst)"}` with the grammar

### Impact:
- Config B (grammar-constrained) and Config C (bounded repair) **require** the JSON prompt 
  to produce valid `{"fix": "..."}` output
- Config A (naive) can use either format, but the harness post-processing must be consistent
- The protocol's plain-function-body prompt is **incompatible** with the grammar-constrained configs

### Resolution needed:
Update protocol §3 to match the working JSON prompt, OR update the code to use the plain function body prompt (which would require grammar modifications). The debugging confirmed the JSON prompt works; the plain function body prompt does not produce the expected output with the current grammar.

## 2. Task ID Mismatch — MINOR

### User's listed task IDs:
Python/0, 16, 32, 48, 64, 80, 96, 128 and 144 (9 tasks)

### Actual task selection (results/pilot/task_selection.json):
Python/0, Python/16, Python/32, Python/48, Python/64, Python/80, Python/96, **Python/112**, Python/128, Python/144 (10 tasks)

### Impact:
- The user missed Python/112 from their list
- The protocol and selection method explicitly include Python/112 (every 16th task from 0 to 163)

### Resolution:
The actual selection is correct at 10 tasks. The user's list should include Python/112.

## 3. `--no-display-prompt` Flag — NONEXISTENT

### User's concern:
> "Confirm that the working JSON prompt, `--no-display-prompt` flag, grammar, output extraction and feedback relay are all consistent with the frozen protocol."

### Reality check:
- The flag **`--no-display-prompt` does not exist** in llama-completion v0.6.0-dev
- The relevant flags for non-interactive completion are:
  - `--no-conversation` (confirmed working, rc=0)
  - `--single-turn` (confirmed working, ensures exit after one turn)
  - `--grammar-file` (confirmed working, constrains output to `{...}`)
  - `--seed`, `--temp`, `-t`, `-c`, `-n` (all confirmed working)

### Impact:
- Any reference to `--no-display-prompt` in protocol or code is erroneous
- The correct flag for plain completion mode is `--no-conversation`

### Resolution:
Remove any reference to `--no-display-prompt`; use `--no-conversation` instead.

## 4. Grammar-Prompt Compatibility — VERIFIED (but needs protocol update)

The grammar `response.gbnf` works, but ONLY with the JSON prompt:
```
"Respond with ONLY {"fix": "<the complete corrected function body>"}. Do not write anything else."
```

With the protocol's plain function body prompt, the grammar either:
- Fails to parse (rc=1), or
- Produces output with `# BUGGY:`/`# CORRECTED:` markers inside `{...}`, NOT `{"fix": "..."}` JSON

## 5. Output Extraction Consistency — NEEDS UPDATE

The harness extraction code (pilot_runner.py) tries BOTH:
1. JSON `{"fix": "..."}` extraction
2. Markdown fence stripping (````python ...```)

This dual approach is correct for the **JSON prompt** but would be incorrect for a **plain function body prompt**. Since the working setup uses the JSON prompt, the extraction code is correct as-is, but the protocol documentation should reflect this.

## Summary of Required Changes Before Pilot Execution

| Item | Current | Required | Change needed |
|---|---|---|---|
| Prompt format (§3) | "Return ONLY the complete corrected function body..." | 'Respond with ONLY {"fix": "<...>"}. Do not write anything else.' | Update protocol to match working JSON prompt |
| Task IDs listed by user | 9 tasks (missing Python/112) | 10 tasks (include Python/112) | Add Python/112 to user's list |
| `--no-display-prompt` flag | Referenced but nonexistent | Use `--no-conversation` | Fix flag reference |
| Grammar-prompt compatibility | Not explicitly documented | Documented: JSON prompt required with grammar | Add note to protocol |

## Recommendation

**Do not execute the 10-task pilot until the above inconsistencies are resolved.** The most critical issue is the prompt format: the protocol must be updated to specify the JSON prompt that works with the grammar, or the code must be changed to use a plain function body prompt (which would require grammar changes).

The debugging phase confirmed that the JSON prompt works with the existing grammar and harness. The protocol was drafted before this debugging was completed, so the mismatch is expected but must be resolved.

**Next step**: Update `reports/pilot_protocol.md` §3 to use the JSON prompt format, then the pilot can proceed with consistent settings.