# Invocation Failure — Diagnosis and Fix

Date: 2026-10-15
Binary: `/home/aaksh/projects/LocalAgentBench/third_party/llama.cpp/build/bin/llama-completion`
Commit: `aa94f2086147cd4bfbcff818ce998dffce5fcb39` (CPU only)

## 1. Symptom

Pilot run #1 (`results/pilot_run1_invalid_flagerror/`) completed all 30
task-config combinations in ~0.0 s each with no inference. Every attempt:

```
rc = 1
stdout = ""
extract = "malformed: empty"
eval.rc = null, eval.category = "malformed_output"
stderr tail = error: invalid argument: -no-conversation
```

The process died during argument parsing, before the model was loaded.

## 2. Root cause

Our runner passed the flag as a **single dash** with the full name:

```python
cmd = [..., "-no-conversation", ""]     # <- invalid
```

`llama-completion --help` (saved verbatim to `reports/llama_completion_help.txt`,
432 lines) lists the accepted spellings as:

```
-cnv,  --conversation, -no-cnv, --no-conversation
                                        whether to run in conversation mode:
-st,   --single-turn                    run conversation for a single turn only, then exit when done
--display-prompt, --no-display-prompt   whether to print prompt at generation (default: true)
--grammar GRAMMAR                       BNF-like grammar to constrain generations
--grammar-file FNAME                    file to read grammar from
```

So the valid forms are the long `--no-conversation` or the short `-no-cnv`.
`-no-conversation` — single dash, long name — is not one of them, hence
`error: invalid argument`.

A stray empty-string argument `""` was also present from an earlier edit; it has
been removed.

### Flags audit (every flag the runner passes, checked against our own `--help`)

| Flag | Line in `llama_completion_help.txt` | Verdict |
|---|---|---|
| `-m/--model` | 152 | supported |
| `-p/--prompt` | 41 | supported |
| `-n/--predict` | 33 | supported |
| `-c/--ctx-size` | 31 | supported |
| `-t/--threads` | 25 | supported |
| `--temp` | 262 | supported |
| `-s/--seed` | 256 | supported |
| `-ngl/--gpu-layers` | 190 | supported |
| `--no-conversation` | 320 | supported (**was passed as `-no-conversation`**) |
| `--single-turn` | 322 | supported |
| `--no-display-prompt` | 319 | supported — kept |
| `--log-file` | 211 | supported |
| `--grammar-file` | 306 | supported |

## 3. Fix

```python
cmd = [str(BIN), "-m", str(MODEL), "-p", prompt,
       "-n", str(N_PREDICT), "-c", str(CTX), "-t", str(THREADS),
       "--temp", str(TEMP), "--seed", str(SEED), "-ngl", "0",
       "--no-conversation", "--single-turn", "--no-display-prompt",
       "--log-file", str(tag) + ".log"]
```

`--no-display-prompt` is retained because this binary's help confirms it is
supported, and it keeps stdout free of the echoed prompt, so the response can be
handed straight to a JSON parser.

## 4. Verification

### 4.1 `--single-turn` exits normally (step 2)

```
llama-completion -m <model> -f /tmp/st_prompt.txt -n 64 -c 2048 -t 4 \
  --temp 0.0 --seed 42 -ngl 0 \
  --no-conversation --single-turn --no-display-prompt
EXIT=0
STDOUT_BYTES=345
```

Exit code 0, prompt not echoed, 345 bytes of pure completion. Prompt eval and
generation timings printed as usual.

### 4.2 One task through A, then B, then C (step 4)

`results/config_validation/`, task `Python/0`:

| Config | gen rc | wall | extract | sandbox eval | peak RSS |
|---|---|---|---|---|---|
| A | 0 | 86.9 s | malformed (unterminated JSON, repetition loop) | n/a (`malformed_output`) | 1 908 512 KB |
| B | 0 | 26.8 s | `ok-json` | rc=3 `import_error` (SyntaxError) | 1 937 244 KB |
| C a1 | 0 | 24.7 s | `ok-json` | rc=3 `import_error` | 1 937 032 KB |
| C a2 | 0 | 23.0 s | `ok-json` | rc=3 `import_error` (IndentationError) | 1 955 592 KB |
| C a3 | 0 | 21.3 s | `ok-json` | rc=3 `import_error` | 1 955 676 KB |

Generation, JSON parsing and sandboxed evaluation all return real values now.

### 4.3 Config C receives genuine test feedback (step 5)

Attempt 2's repair prompt, taken verbatim from `result.json`, contains the
attempt-1 output and the real sandbox output:

```
# Your previous fix (attempt 1):
The bug in the function is that it compares every element with every other
element, ... Here's the corrected function body: {

Ground-truth test result: import_error
Test output:
IMPORT_ERROR: SyntaxError unterminated string literal (detected at line 5)
```

The model responded to the feedback: attempt 2 produced an actual function body
instead of prose — a direct behavioural change caused by the injected test
output. Feedback plumbing is proven end to end.

### 4.4 JSON parsing rather than regex (step 6)

`extract_body` now drives `json.JSONDecoder().raw_decode` over successive `{`
positions until an object carrying `"fix"` parses. 11 unit cases pass
(valid JSON, leading whitespace, escaped newlines, prose-then-JSON, unterminated
string, prose-only, empty, fence, raw fallback, non-string `fix`, missing key).

## 5. Remaining problems

### P1 — output contract mismatch: `fix` contains a full `def`, harness wants a body

`evaluate_candidate.py` builds the candidate as

```python
code = row["declaration"] + body
```

The declaration already ends with `def has_close_elements(...) -> bool:\n`. If
the model returns a *complete function definition* inside `"fix"`, the
concatenation yields two stacked `def` lines and the first has no body:

```
from typing import List


def has_close_elements(numbers: List[float], threshold: float) -> bool:

def has_close_elements(numbers: List[float], threshold: float) -> bool:
    for idx, elem in enumerate(numbers):
        ...
```

Measured on `Python/0` with the model's attempt-2 output from config C:

| Candidate built as | Evaluator rc | Category |
|---|---|---|
| `declaration + model_body` (model-as-is) | 3 | `import_error` — `IndentationError expected an indented block after function definition on line 4` |
| `declaration + body_only` (signature line stripped) | 1 | `assertion_fail` — the model's real semantic bug (`distance = elem - numbers[idx2]` with no `abs`) |

So the same model output is reported as a harness/indentation failure rather
than the logic failure it actually is. This conflates *did not follow the output
format* with *wrong algorithm*. It is **not** silently normalised: the pilot is
run with the frozen contract and the confound is reported here.

### P2 — small 1.5B model ignores the JSON contract in config A

Config A (no grammar) produced a repetition loop, ending in unterminated JSON.
This is a genuine model-quality result, not a harness fault.

### P3 — earlier sessions claimed `--no-display-prompt` does not exist

It does exist in this build (`--display-prompt, --no-display-prompt`, help line
319). That earlier claim was wrong and is corrected here.

## 6. Run #1 disposition

`results/pilot_run1_invalid_flagerror/INVALID_RUN.md` marks it invalid; no number
from it may be reported. The frozen selection is preserved at
`results/pilot/task_selection.json` (byte-identical copy). The regenerated pilot
is written to `results/pilot_v2/`.
