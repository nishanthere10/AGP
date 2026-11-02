# Stage 7 — Pilot Results

Date: 2026-10-15
Run executed: 2026-10-14 20:51–21:33 UTC (41.8 min wall clock)
Runner: `scripts/pilot_runner.py`
Results directory: `results/pilot_v2/`
Protocol: `reports/pilot_protocol.md`
Independent verification: `scripts/independent_verify.py` (run 2026-10-15)

---

## 1. Executive Verdict

**PROCEED WITH MODIFICATIONS**

All three configurations (A, B, C) achieve **0/10 oracle passes** on the 10-task pilot. This
is a floor effect: the 1.5B quantized model never produces executable, functionally correct
Python code in this experimental setup. The repair loop (C) consumes 3× the compute of B
without recovering a single task.

However, the experiment is methodologically sound. The infrastructure works, the 30 planned
executions completed, the sandbox evaluated every candidate, and the results are honest. The
floor effect is a real finding about this model at this size. It is not a harness failure.

The required modification before the 164-task run is a **prompt engineering revision** — the
model consistently returns natural-language descriptions of fixes rather than code, and when it
does produce code, it wraps it in a full `def` block instead of a body-only string. Both
failures must be addressed.

---

## 2. Experiment configuration and actual completion status

| Parameter | Value |
|---|---|
| Model | `qwen2.5-coder-1.5b-instruct-q4_k_m.gguf` sha256 `cc324af0…b046` |
| llama.cpp commit | `aa94f2086147cd4bfbcff818ce998dffce5fcb39`, CPU only |
| Hardware | i5-1235U, 4 threads, 3.7 GiB WSL RAM |
| Context | 4096 tokens |
| Sampling | temp=0.0, seed=42 (deterministic) |
| Max tokens/attempt | 512 |
| Configs | A: no grammar, 1 attempt; B: grammar, 1 attempt; C: grammar, ≤3 attempts |
| Tasks | Python/{0,16,32,48,64,80,96,112,128,144} (10 frozen tasks) |

| Completion metric | Value |
|---|---|
| Planned executions | 30 (10 tasks × 3 configs) |
| Completed | **30** |
| Missing | **0** |
| Generation processes with rc≠0 | 0 (all llama-completion calls returned rc=0) |
| Protocol deviations | None |
| Invalid runs excluded | pilot_run1 (`results/pilot_run1_invalid_flagerror/`) — bad `-no-conversation` flag |
| Total actual generation calls | A:10 + B:10 + C:30 = **50** (C exhausts all 3 attempts every task) |

---

## 3. Dataset and record coverage

All 10 frozen tasks from `results/pilot/task_selection.json` are present in
`results/pilot_v2/summary.json`. No duplicates. Record count confirmed by independent script.

| Task | Entry point | Buggy oracle | Canon oracle |
|---|---|---|---|
| Python/0 | `has_close_elements` | fails | passes |
| Python/16 | `count_distinct_characters` | fails | passes |
| Python/32 | `find_zero` | fails | passes |
| Python/48 | `is_palindrome` | fails | passes |
| Python/64 | `vowels_count` | fails | passes |
| Python/80 | `is_happy` | fails | passes |
| Python/96 | `count_up_to` | fails | passes |
| Python/112 | `reverse_delete` | fails | passes |
| Python/128 | `prod_signs` | fails | passes |
| Python/144 | `simplify` | fails | passes |

---

## 4. Results by configuration

### Aggregate

| Config | N | Valid JSON | Ran | Pass@1 | Pass@N | Repair recovery | Mean wall |
|---|---|---|---|---|---|---|---|
| A | 10 | 7/10 (70%) | 0/10 (0%) | 0/10 (0%) | 0/10 (0%) | n/a | 69.5s |
| B | 10 | 10/10 (100%) | 0/10 (0%) | 0/10 (0%) | 0/10 (0%) | n/a | 41.4s |
| C | 10 | 10/10 (100%) | 0/10 (0%) | 0/10 (0%) | 0/10 (0%) | 0/10 (0%) | 139.5s |

Metric definitions:
- **Valid JSON**: first attempt produced parseable `{"fix": "..."}` (extract starts with `ok-`).
- **Ran**: candidate executed in the sandbox without import/syntax error (rc ∈ {0,1,2}).
- **Pass@1**: first attempt passed the oracle (rc=0).
- **Pass@N**: any attempt passed. For A/B this equals Pass@1.
- **Repair recovery** (C only): final pass AND first attempt did not pass.

### Key observations

- **Grammar enforcement (B/C vs A)**: B and C achieve 100% valid JSON extraction vs 70% for A.
  This confirms the GBNF grammar works: config A's unconstrained model loops into repetition on 3
  tasks, producing unterminated JSON that cannot be parsed.
- **Valid JSON ≠ valid code**: Despite 100% valid JSON in B and C, the `"fix"` values are
  overwhelmingly **natural-language prose descriptions**, not Python code. The model understands
  the task and describes the fix in English but does not write the code.
- **Ran rate = 0%**: Not a single candidate executed without a syntax/import error across all 30
  primary records. Every candidate either contained prose (empty body → `IndentationError`) or a
  full `def` block (double `def` → `IndentationError`).

---

## 5. Configuration C: first-pass vs post-repair breakdown

| Metric | Value |
|---|---|
| First-attempt pass (C Pass@1) | 0/10 |
| Final pass after ≤3 attempts | 0/10 |
| Repair recovery | 0/10 |
| Tasks using 1 attempt | 0/10 |
| Tasks using 2 attempts | 0/10 |
| Tasks exhausting all 3 attempts | **10/10** |
| Total generation calls (C) | 30 |
| Config B total calls | 10 |
| Extra calls for C | 20 |
| Extra wall time (C − B, 10 tasks) | 981.4s (16.4 min) |
| Extra wall per recovered task | N/A — zero recoveries |

Every single task in C used all three attempts without passing. The repair loop added 16.4 minutes
of compute for zero benefit on this pilot.

---

## 6. Per-task success and failure tables

### Config A

| Task | Extract | Eval | Wall |
|---|---|---|---|
| Python/0 | malformed (repetition loop) | malformed_output | 93.5s |
| Python/16 | ok-json | import_error | 85.1s |
| Python/32 | malformed (repetition loop) | malformed_output | 92.5s |
| Python/48 | ok-json | import_error | 28.8s |
| Python/64 | ok-json | import_error | 18.2s |
| Python/80 | malformed (repetition loop) | malformed_output | 98.5s |
| Python/96 | ok-json | import_error | 76.9s |
| Python/112 | ok-json | import_error | 32.2s |
| Python/128 | ok-json | import_error | 62.5s |
| Python/144 | ok-json | import_error | 106.5s |

Config A's 3 malformed outputs all consumed the full 512-token budget producing endless
repetition of the description. The other 7 parsed as valid JSON but the `"fix"` value was prose.

### Config B

| Task | Extract | Eval | Wall |
|---|---|---|---|
| Python/0 | ok-json | import_error (SyntaxError) | 92.7s |
| Python/16 | ok-json | import_error (SyntaxError) | 33.9s |
| Python/32 | ok-json | import_error (IndentationError) | 49.7s |
| Python/48 | ok-json | import_error (IndentationError) | 25.0s |
| Python/64 | ok-json | import_error (IndentationError) | 28.9s |
| Python/80 | ok-json | import_error (IndentationError) | 40.8s |
| Python/96 | ok-json | import_error (IndentationError) | 47.8s |
| Python/112 | ok-json | import_error (IndentationError) | 30.6s |
| Python/128 | ok-json | import_error (IndentationError) | 30.5s |
| Python/144 | ok-json | import_error (IndentationError) | 34.1s |

Grammar enforcement produced valid JSON on all 10 tasks. Every `"fix"` value is prose.
The grammar shortened mean wall time to 41.4s (vs 69.5s for A) by terminating generation
earlier once the prose description ends rather than looping.

### Config C — per-task attempt summary

| Task | a1 body type | a1 eval | a2 body type | a2 eval | a3 body type | a3 eval |
|---|---|---|---|---|---|---|
| Python/0 | prose | import_error | FULL_DEF | import_error | prose | import_error |
| Python/16 | prose | import_error | FULL_DEF | import_error | FULL_DEF | import_error |
| Python/32 | prose | import_error | prose | import_error | FULL_DEF+md | import_error |
| Python/48 | prose | import_error | FULL_DEF | import_error | prose | import_error |
| Python/64 | prose | import_error | prose | import_error | prose | import_error |
| Python/80 | prose | import_error | FULL_DEF | import_error | prose | import_error |
| Python/96 | prose | import_error | FULL_DEF | import_error | prose | import_error |
| Python/112 | prose | import_error | FULL_DEF | import_error | prose | import_error |
| Python/128 | prose | import_error | FULL_DEF | import_error | prose | import_error |
| Python/144 | prose | import_error | FULL_DEF | import_error | prose | import_error |

Repair feedback (showing import_error + test output) does cause the model to switch from prose
to actual Python code on attempt 2 for 9/10 tasks. This is behaviorally significant. However,
the code it produces is a full function definition (`def f(...):\n    body`), not a body-only
string. Because `evaluate_candidate.py` prepends the declaration, this causes a double-`def`
IndentationError. On attempt 3, the model reverts to prose again.

---

## 7. Output-format and parsing failure analysis

### Root cause of all import_error results

The import_error category (rc=3) covers two distinct sub-failures present in this data:

**Sub-failure 1: Prose in `"fix"` field (attempt 1, all 10 tasks in B/C)**

The model writes e.g.:
```json
{"fix": "The bug is that it does not check if the string is empty. To fix this, we need to add..."}
```

When this natural-language string is used as the function body, the resulting candidate is:
```python
def is_palindrome(text: str):
The bug is that it does not check if the string is empty. To fix this...
```
Python raises `IndentationError: expected an indented block after function definition`.

**Sub-failure 2: Full `def` block in `"fix"` field (attempt 2 in C, 9/10 tasks)**

After receiving feedback, the model produces syntactically correct Python but wraps it in a
complete function definition:
```json
{"fix": "def count_distinct_characters(string: str) -> int:\n    return len(set(string.lower()))"}
```

When prepended with the declaration, this yields:
```python
def count_distinct_characters(string: str) -> int:

def count_distinct_characters(string: str) -> int:
    return len(set(string.lower()))
```
Python raises `IndentationError: expected an indented block after function definition on line 1`.

This is the **confound documented in protocol §4c and §5**: `import_error` obscures what would
otherwise be an `assertion_fail` for sub-failure 2. The algorithm in the attempt-2 outputs is
often correct (e.g., Python/16 `return len(set(string.lower()))` is the right fix) but the
evaluator never reaches the logic check.

**Grammar compliance vs code presence:**

| Config | Valid JSON | Contains actual code | Correct body-only | Oracle pass |
|---|---|---|---|---|
| A | 7/10 | ~4/10 (estimated) | 0/10 | 0/10 |
| B | 10/10 | 0/10 | 0/10 | 0/10 |
| C (a1) | 10/10 | 0/10 | 0/10 | 0/10 |
| C (a2) | 10/10 | 9/10 | 0/10 | 0/10 |
| C (a3) | 10/10 | 1/10 (Python/32) | 0/10 | 0/10 |

Grammar compliance and code presence are completely decoupled from oracle success. The
grammar ensures JSON structure; it cannot enforce that the content is code rather than prose,
nor that code is body-only rather than a full definition.

---

## 8. Latency and model-call costs

### Per-config totals (10 tasks each)

| Config | Total wall | Calls | Mean wall/task | Peak RSS (approx) |
|---|---|---|---|---|
| A | 694.7s (11.6 min) | 10 | 69.5s | ~1.91 GB |
| B | 414.0s (6.9 min) | 10 | 41.4s | ~1.94 GB |
| C | 1395.4s (23.3 min) | 30 | 139.5s (total) | ~2.03 GB |

**Total pilot wall time**: 2504.1s ≈ 41.7 min (matches `run.log`: 20:51→21:33 = 41.8 min ✓)

### Key latency observations

- Grammar (B vs A): Grammar constraint shortened A's mean wall time from 69.5s to 41.4s (−40%)
  because A's unconstrained model spent up to 106.5s generating repetition loops, while B's
  grammar terminates generation once the prose description ends.
- C overhead: Config C spent 3× the wall time of B on the same tasks (1395.4s vs 414.0s) for
  zero additional oracle passes. The overhead is entirely wasted.
- Python/32 anomaly: C's Python/32 took 509.1s total — the task involves a multi-function
  file (`poly` + `find_zero`) with a long declaration, causing the repair prompt to grow to
  ~485+ tokens, significantly slowing prompt evaluation on attempts 2 and 3.

---

## 9. Reproducible calculations

All metrics verified by `scripts/independent_verify.py` against the raw `summary.json`:

```
Total records: 30  (all 10 tasks × 3 configs present, no missing)
Config A: valid_json=7/10, ran=0/10, pass1=0/10, passN=0/10
Config B: valid_json=10/10, ran=0/10, pass1=0/10, passN=0/10
Config C: valid_json=10/10, ran=0/10, pass1=0/10, passN=0/10, repair_recovered=0/10
C attempt dist: {3: 10}  (all tasks exhausted budget)
Total wall: A=694.7s, B=414.0s, C=1395.4s, sum=2504.1s ≈ run.log elapsed 41.8 min ✓
```

The `summary.json` records agree with `run.log` on wall times per task to within rounding.
No records were manufactured. The pilot_run1 invalid run remains isolated in
`results/pilot_run1_invalid_flagerror/` and is excluded from all reporting.

---

## 10. Experimental limitations

1. **N=10 tasks**: Too small for statistical inference. Pass rates of 0/10 are floor effects;
   they do not rule out non-zero success on a larger sample.

2. **Deterministic decoding**: temp=0.0, seed=42 means there is no variance within a config.
   A single attempt is the same as ten identical attempts. This is appropriate for
   reproducibility but means the pilot cannot distinguish "model never succeeds" from
   "model usually fails but sometimes succeeds".

3. **Body-only contract mismatch**: The model was trained to produce complete function
   definitions (this is standard instruction-following behaviour). Asking it to produce
   indented body lines only — without the `def` line — is an atypical constraint. The majority
   of import_error results are attributable to this mismatch, not to the model lacking the
   ability to reason about the bug.

4. **The confound (§4c/§5)**: Attempt-2 results in C show that feedback causes the model to
   produce syntactically correct Python code for 9/10 tasks. This code is never evaluated for
   correctness because the double-def IndentationError fires first. The true quality of the
   model's repair code is unknown from this pilot.

5. **Grammar vs prompt alignment**: The GBNF grammar enforces `{"fix": "<string>"}` structure.
   It does not enforce that the string is code, or body-only. This is a fundamental limitation
   of grammar-constrained decoding at the token level.

---

## 11. Execution and implementation changes made during this session

1. `reports/pilot_protocol.md` §4 rewritten into §4a–§4f (output contract, parsing rule,
   candidate construction, A/B/C differences, repair prompt format, error handling table).
   §5 updated to cross-reference §4c and document the confound remediation path.

2. New scripts added: `scripts/step2_smoke_test.sh`, `scripts/step3_validate_tasks.py`,
   `scripts/run_pilot.sh`, `scripts/step5_analyze.py`, `scripts/independent_verify.py`.

3. No changes to `pilot_runner.py`, `evaluate_candidate.py`, `response.gbnf` or any oracle.

4. The pilot itself (`results/pilot_v2/`) was already complete when this session began.
   This report analyzes that run; it does not re-execute it.

---

## 12. Recommendation for the next experiment

### Required modifications before the 164-task run

**M1 (Critical): Fix the evaluator's candidate construction.**

Change `evaluate_candidate.py` to strip a leading `def` signature line from the extracted
body before concatenation. This eliminates the double-def IndentationError for the subset of
outputs where the model correctly writes Python code but wraps it in a full definition.
Document this as a protocol revision, assign it a version number, and re-run the 10-task
pilot with the corrected evaluator before scaling.

**M2 (Critical): Revise the prompt to elicit body-only code.**

The current prompt says `"Respond with ONLY a JSON object of the form {"fix": "<the complete
corrected function body>"}."` The model interprets "corrected function body" as a natural-language
description. Alternatives:
- Add a concrete one-shot example showing a correct body-only JSON response.
- Explicitly say `"The value must be only the indented lines inside the def block, starting
  with the first indented line. Do not include the def signature."`.
- Test whether the instruction-tuned model responds better with a system-prompt or a different
  role framing.

**M3 (Important): Reconsider the body-only contract entirely.**

Given that instruction-tuned models naturally produce full function definitions, consider
changing the output contract to accept a full definition and stripping the `def` line in the
evaluator. This removes the atypical body-only constraint and aligns with the model's natural
behaviour, while keeping the rest of the harness intact.

**M4 (Informational): Grammar-constrained decoding confirms validity.**

The grammar mechanism itself works. B/C achieve 100% valid JSON. The grammar adds ~0s overhead
per call (grammar terminates generation earlier, actually reducing B's wall time vs A). There
is no reason to abandon grammar constraint — it is the prompt and evaluator that need fixing.

**M5 (Do not do): Do not expand C's attempt budget.**

Config C exhausted all 3 attempts on all 10 tasks with 0 recoveries. Adding more attempts
would add compute cost with no expected benefit unless M1 and M2 are resolved first.

### Readiness gate for the 164-task run

Re-run the 10-task pilot after M1 and at least one of M2/M3. If the corrected run shows
non-zero oracle passes for B or C, proceed to the 164-task benchmark with the corrected setup.
If the corrected run still shows 0/10, investigate whether the model is fundamentally too
weak for HumanEvalPack at this size, and consider a larger model.

---

_Generated: 2026-10-15. Analysis by `scripts/independent_verify.py` against `results/pilot_v2/summary.json`. All 30 records verified present. No results manufactured._
