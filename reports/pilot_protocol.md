# Stage 7 — Pilot Protocol (10 tasks, configurations A/B/C)

Date drafted: 2026-10-15
Status: Selection, prompt and settings frozen before any generation.
Revision: 2026-10-15 — §3 and §4 corrected after the invocation failure
(see `reports/invocation_failure_fix.md`). The task selection and sampling
settings are unchanged from the original freeze.

## 0. Gates

- Gate 2 (model): hash verified, llama.cpp binaries built.
- Gate 3 (sandbox): PASSED (13/13 probes, `reports/sandbox_validation.md`).
- Gate 4 (dataset): PASSED (164/164 oracle checks, `reports/dataset_audit.md`).
- Gate 7 (invocation): PASSED after fix — see `reports/invocation_failure_fix.md`.

## 1. Fixed settings (all configurations)

| Setting | Value |
|---|---|
| Model | `qwen2.5-coder-1.5b-instruct-q4_k_m.gguf` sha256 `cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046` |
| llama.cpp | commit `aa94f2086147cd4bfbcff818ce998dffce5fcb39`, CPU only, `-march=native` |
| Context | 4096 (never changed mid-pilot) |
| Threads | 4 |
| Sampling | `--temp 0.0`, `--seed 42` |
| Max new tokens | 512 per attempt |
| Test timeout | 10 s per sandbox run |
| Attempt budget | A: 1; B: 1; C: <=3 (initial + 2 repairs) |
| Concurrency | 1 model instance, sequential tasks |

## 2. Invocation (verified against our own build)

The complete `--help` of our binary is saved at
`reports/llama_completion_help.txt`. Every flag below is confirmed present
there.

```
llama-completion -m <model> -p <prompt> -n 512 -c 4096 -t 4 \
  --temp 0.0 --seed 42 -ngl 0 \
  --no-conversation --single-turn --no-display-prompt \
  [--grammar-file scripts/response.gbnf]      # B and C only
```

- `--no-conversation` (long form) or `-no-cnv` (short alias). The single-dash
  long form `-no-conversation` is **not** valid and caused run #1 to fail
  entirely.
- `--single-turn` (`-st`) confirmed: exits normally after one turn, rc=0.
- `--no-display-prompt` is supported by this build (help line 319) and is kept,
  so stdout contains only the completion and can be fed straight to a JSON
  parser.
- `llama-cli` is not used: at this commit it silently exits rc=0 with no output
  when stdin is closed.

## 3. Task selection (frozen before results)

Method: deterministic — take every 16th task id by numeric suffix over the 164
sorted task ids, i.e. `Python/{0,16,32,48,64,80,96,112,128,144}`, giving 10
tasks spread across the id range without looking at any model output.
Rationale: reproducible, independent of model behaviour, no cherry-picking.

Written to `results/pilot/task_selection.json` before any generation. The same
10 tasks are used for A, B and C.

## 4. Response contract (identical prompt for A, B and C)

**Authoritative source: `PROMPT_TEMPLATE` in `scripts/pilot_runner.py`.**
The formatted prompt is:

```
Below is a Python function with a bug. Respond with ONLY a JSON object of the form {"fix": "<the complete corrected function body>"}. Do not write anything else.

{instruction}

{declaration}
# BUGGY:
{buggy}
```

where `{instruction}` is the task's natural-language description, `{declaration}`
is the full function header (imports + `def` signature line, ending with `:\n`),
and `{buggy}` is the known-buggy body (indented lines only, no `def` line).

### 4a. Expected output format

The model must return **exactly one JSON object**, matching the GBNF grammar
`scripts/response.gbnf`:

```
{"fix": "<corrected body>"}
```

- The JSON object must contain **exactly one key**: `"fix"`.
- The value of `"fix"` must be a **JSON string** (double-quoted, properly
  escaped per RFC 7159 §7).
- The value must be the **corrected function body only** — the indented lines
  that go inside the `def` block, **not** a full function definition.
  Do not include the `def` signature line, decorators, or imports.
- Newlines inside the body are encoded as `\n` (JSON escape), not literal
  newlines.
- The output must contain nothing before the opening `{` or after the closing
  `}`.

**Valid example** (Python/0, `has_close_elements`):

```json
{"fix": "    for i in range(len(numbers)):\n        for j in range(i+1, len(numbers)):\n            if abs(numbers[i] - numbers[j]) < threshold:\n                return True\n    return False\n"}
```

**Invalid — full def included** (causes `import_error / IndentationError` at
evaluation, because `evaluate_candidate.py` prepends `declaration` which already
contains the `def` line):

```json
{"fix": "def has_close_elements(numbers, threshold):\n    for i in ...\n"}
```

**Invalid — not JSON**:

```
Here is the corrected function:
    for i in range(len(numbers)):
        ...
```

**Invalid — wrong key**:

```json
{"answer": "..."}
```

### 4b. Parsing rule

`extract_body` in `pilot_runner.py` applies `json.JSONDecoder().raw_decode`
starting from each `{` in the output (left to right) until an object containing
the key `"fix"` is found. This is the only authoritative parser; regex fallbacks
apply only when no parseable `{"fix": ...}` exists (config A raw-fallback path).

### 4c. Candidate construction

`evaluate_candidate.py` builds the executable candidate as:

```python
code = row["declaration"] + body
```

where `body` is the extracted `"fix"` string (verbatim, no stripping of the
`def` line). This means:

- A body-only value → correct concatenation → evaluator can reach the logic.
- A full-def value → double `def` → `IndentationError` → `import_error` (rc=3).

This confound is **not** silently corrected. Results with rc=3 from a
full-def output are a format failure, not a logic failure, and are reported as
such in §5 and in `reports/pilot_results.md`.

### 4d. Configuration differences

The A/B/C difference is **only** the decode-time GBNF constraint and attempt
budget:

- **A (naive):** one pass, no grammar, scored once, no repair.
- **B (grammar):** identical prompt plus `--grammar-file scripts/response.gbnf`,
  which constrains the decode to a valid `{"fix": "<string>"}` JSON object.
  Scored once; no feedback.
- **C (bounded repair):** identical to B. After each failed attempt the real
  sandboxed test output plus the previous candidate are appended to the prompt
  and a new attempt is made, up to 3 attempts total (initial + 2 repairs).

### 4e. Repair prompt (config C only)

When attempt `k` fails, the next attempt receives:

```
<base_prompt>

# Your previous fix (attempt k):
<extracted body or "<no output>">

Ground-truth test result: <category>
Test output:
<first 500 chars of evaluator stdout+stderr>
Respond with ONLY a JSON object of the form {"fix": "<the complete corrected function body>"}. Do not write anything else.
```

The repair prompt is saved verbatim to `result.json` as
`attempt_log[k]["repair_prompt_sent"]` for auditability.

### 4f. Error handling

| Failure mode | `extract` note | `eval.category` | Action |
|---|---|---|---|
| Empty stdout | `malformed: empty` | `malformed_output` | Recorded; no eval run |
| No `{` in output | `malformed: json error (...)` | `malformed_output` | Recorded; no eval run |
| JSON parse fails for all `{` | `malformed: json error (...)` | `malformed_output` | Raw fallback attempted |
| `"fix"` key absent | `malformed: json error (...)` | `malformed_output` | Raw fallback attempted |
| `"fix"` value not a string | `malformed: fix not a string` | `malformed_output` | Recorded; no eval run |
| `"fix"` value empty string | `malformed: empty fix` | `malformed_output` | Recorded; no eval run |
| Full def in `"fix"` | `ok-json` | `import_error` (rc=3) | Recorded as format failure |
| Logic bug in body | `ok-json` | `assertion_fail` (rc=1) | Recorded as logic failure |
| Pass | `ok-json` | `pass` (rc=0) | Success |

**Why the JSON prompt:** the plain `declaration + "# BUGGY:" + buggy` prompt
makes the model emit `# BUGGY:` / `# CORRECTED:` markers; a grammar that
accepts only `{"fix": ...}` never yields the expected key from that prompt.
The JSON instruction is what makes grammar-constrained configs behave as
intended (confirmed in `reports/debugging_findings.md` and
`reports/invocation_failure_fix.md`).

## 5. Known confound carried into this run

See §4c for the complete candidate-construction rule.

The accepted `"fix"` value is a **body-only** string (indented lines inside
the function, no `def` line). If the model returns a full function definition
(starting with `def …:`), `evaluate_candidate.py` concatenates
`declaration + full_def`, producing two stacked `def` lines; the first has no
body and Python raises `IndentationError`. This is recorded as `import_error`
(rc=3), indistinguishable at a glance from a missing-import failure.

This confound is **not** silently normalised: the pilot is run with the frozen
contract, all rc=3 results are kept as-is, and the share attributable to
full-def format violations vs genuine import problems is discussed in
`reports/pilot_results.md` §9.

If a future run corrects this, it must be done by updating the evaluator to
strip a leading `def` signature line before concatenation, documented in a
protocol revision, and re-run from scratch — not by post-hoc relabelling of
this pilot's results.

## 6. Execution rules

- Sequential: no concurrent model instances.
- Every attempt recorded to the results directory (raw generation, exit codes,
  timings, peak RSS). Malformed output, timeouts and harness errors are kept,
  never retried silently.
- No task removal; no re-runs to flip failures.
- Run #1 (`results/pilot_run1_invalid_flagerror/`) is invalidated by its
  `INVALID_RUN.md` and excluded from all reporting.

## 7. Reporting

`reports/pilot_results.md`: all 10x3 rows, success definition, failure
categories, attempts used, latency, peak RSS, no significance claims. Verdict
chosen from: proceed / floor effect / sandbox-or-hardware problem / protocol
redesign / insufficient evidence.
