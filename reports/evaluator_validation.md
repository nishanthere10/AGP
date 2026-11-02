# Evaluator Validation Report — LocalAgentBench

**Date:** 2026-10-18
**Evaluator version after this work:** v3.1
**Scope:** evaluator correctness only. The main retry-versus-feedback experiment was **not** started. No dataset, experimental arm, model setting or research hypothesis was modified. `results/pilot_v3/` was not rewritten or deleted.

---

## VERDICT

**Evaluator: PASS** — all eight acceptance criteria in the task brief are met by executed evidence, not inference.

**Main experiment: NOT CLEARED — BLOCKED.** Two blockers sit outside the evaluator and outside the approved scope of this task. Both are measured, not speculative:

| # | Blocker | Evidence | Owner |
|---|---------|----------|-------|
| B1 | `PROMPT_TEMPLATE`'s one-shot example is **invalid JSON** (a real newline inside a string literal). The model imitates it. In `pilot_v3` this destroyed **2 of 10 config-A attempts**, and one of the two — `Python/48` A a1 — contained a **correct fix that scores rc=0**. Config A is the only arm that can produce this failure, because B and C are grammar-constrained. The A-vs-B/C comparison is therefore confounded in the arm the experiment depends on. | §5.2, `postfix/diag_malformed_A.out` | prompt change — explicitly out of scope for this task |
| B2 | No pilot has ever run under v3.1. Protocol §5 requires a from-scratch re-run whenever the evaluator changes, because the `NORMALIZE:` fingerprint differs. Every existing pilot conclusion is pre-fix. | §5.3, protocol §8 | requires model generation — a user decision |

The evaluator can be frozen. The *pipeline* cannot go to the main experiment until B1 is resolved and a v3.1 pilot re-run confirms the arms are comparable.

---

## 1. Diagnosis before any code change

### 1.1 Three premises in the task brief were false

Phase 0 established repo state before touching code. Three of the brief's assumptions did not survive contact with the repository. Each was verified, not assumed:

| Brief said | Reality | How verified |
|---|---|---|
| "Run `scripts/test_evaluator_regression.py`" | The file **did not exist** | `git log --all`, all branches, `git stash list`, `git reflog`, `git fsck --lost-found`, repo-wide grep for the filename and for its distinctive strings |
| "Produce `reports/evaluator_validation.md`" | Never existed either | same searches |
| Defect E: tests use an "obsolete two-argument signature" for `extract_body` | **False.** `scripts/test_extract_body.py` already calls `f(raw)` with one argument, all 11 cases, exit 0 | read the file; ran it (`baseline/test_extract_body.py.out`) |

There was no stale test to retire. `test_extract_body.py` (11 cases), `test_normalization.py` (22 tests) and `test_eval.py` all passed **before** any change and still pass after. They are untracked files and are byte-identical to their baseline hashes (§4.6) — nothing was weakened, edited or deleted to obtain a green suite.

The regression suite and this report were therefore **built**, not repaired.

### 1.2 Defect A was real, but not for the stated reason

The brief described defect A as "echoed-prompt shadowing". The mechanism is different and the difference matters:

- The prompt is **not** echoed into stdout. `--no-display-prompt` is passed and works. **0 of 50** stored `pilot_v3` stdouts contain the prompt's distinctive marker text.
- The model itself restates prompt-derived content **before** answering — typically the buggy body it was shown, sometimes the prompt's one-shot example object.
- `extract_body()` took the **first** parseable `{"fix": ...}` object, so that preamble won and the model's actual answer was discarded.

Quantified over all 50 real stored attempts: **8** had ≥2 parseable `{"fix"}` objects (all 8 in config A, the grammar-free arm). Of those 8, **1** extracted a materially different body under first-match vs last-match: `Python/0` A a1. Regression test **A1** is built from that exact artifact and asserts the extraction derives from the dataset (the body must contain `abs(`, must differ from `buggy_solution`, and the stdout must contain ≥2 `"fix"` occurrences) so the test cannot silently lose its subject.

### 1.3 A second defect was found that the brief did not list

`_extract_body_source()` ran `textwrap.dedent()` then `textwrap.indent(..., "    ")` over the AST-located body slice. That pair is unsafe:

- `textwrap.dedent()` is a **no-op** whenever any line has less leading whitespace than the common prefix. A multi-line string literal containing unindented text guarantees exactly that.
- `textwrap.indent()` then shifted **every** line regardless.

Result: a body containing a triple-quoted string had its literal contents rewritten and its code double-indented to 8 spaces — and it **still executed**, producing a plausible exit code for semantically altered code. This is the worst failure shape an evaluator can have: silent, scoreable corruption. Caught by regression tests **C2** (semantics) and **C3** (indentation), both of which failed pre-fix.

### 1.4 Defect E's return-code claim was confirmed, empirically

The old comment claimed a wrong-named full def yields `MISSING_ENTRY` (rc 4). It does not. `declaration` already ends with `:\n`, so appending a second top-level `def` leaves the first def bodiless and Python raises `IndentationError` **before** the harness ever looks up the entry point → **rc 3** (`import_error`). Test **D5** asserts rc 3. Test **D6** shows rc 4 *is* reachable, but only when the candidate unbinds the entry point itself (`del <name>`). Both are failures, so the path can never be scored as a pass — **D10** asserts that no failure mode of any kind reaches rc 0.

---

## 2. Environment

Captured verbatim in `results/evaluator_repair/baseline/environment.txt`.

```
date_utc        2026-10-18T08:13:12Z
uname           Linux PERSISTENT 6.6.87.2-microsoft-standard-WSL2 x86_64
venv python     Python 3.14.4  (/usr/bin/python3.14)
packages        pip 25.1.1, pyarrow 26.0.0   (no pytest — none installed)
bubblewrap      0.11.1
dataset         ed5f15d789156e21222bfcd556c425a39042355c84ae1e8b058abd6a3d7f8075
                third_party/dataset/humanevalpack_python_test.parquet (191279 bytes, 164 rows)
model           cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046
                models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
```

No package was installed. No environment variable, model setting or dataset file was altered. The regression suite is dependency-free (hand-rolled `@test` registry, `importlib` module loading, subprocess isolation) per the constraint against installing pytest.

Frozen generation settings, unchanged and recorded in every `pilot_v3` result: `seed=42, ctx=4096, threads=4, n_predict=512, temp=0.0, test_timeout=10.0, max_attempts=3, flags=[--no-conversation, --single-turn, --no-display-prompt]`.

---

## 3. Changes made (v3.1)

Three files changed. **769 insertions, 134 deletions** across them — but the great majority of that diff is the user's own pre-existing uncommitted v3 work, which was preserved intact (§4.6). My changes are the four items below.

### 3.1 Defect A — `scripts/pilot_runner.py`, `extract_body()`

First-match → **last-match**. The scanner now walks every `{`, decodes each object **whole** (`idx = text.find("{", idx + end)`), so a nested object can never shadow the object enclosing it, and collects every valid `"fix"` string. The **last** one wins.

Justification: decoding is autoregressive, so anything emitted before the answer is preamble. A trailing object truncated by `--n-predict` fails to parse and is ignored, so the last **complete** object wins (test A5).

Rejection ordering was made explicit and is asserted by B6/B7: non-string `fix` → `malformed: fix not a string`; empty/whitespace `fix` → `malformed: empty fix`; otherwise fall through to the code-fence fallback, which still requires a `def` and is labelled `ok-raw-fallback`.

**Not broadened.** Raw body-only output without a JSON wrapper is still **rejected** (test B4) because protocol §4a lists that shape as "Invalid — not JSON". The brief's instruction was explicit: do not broaden extraction to improve pass rates, do not choose the contract based on which behaviour produces more successes. Recommendation M3 of `pilot_results.md` §12 (accept full definitions) was **not** adopted; the frozen contract still mandates JSON.

### 3.2 Defect C1 — `scripts/evaluate_candidate.py`, `_extract_body_source()`

`textwrap.dedent` + `textwrap.indent` replaced by a **verbatim line slice**:

```python
lines = full_source.splitlines(keepends=True)
body_start = func_def.body[0].lineno - 1
body_end = func_def.end_lineno          # inclusive, 1-based -> exclusive 0-based
return "".join(lines[body_start:body_end])
```

Python accepts any consistent indentation after the declaration's `:`, so re-indenting bought nothing and cost correctness. `import textwrap` was removed; the only remaining occurrences of the word in that file are inside explanatory comments.

Documented edge case: a single-line def (`def f(): return 1`) has `body[0].lineno` equal to the def's own line, so the slice includes the `def` text and the candidate fails with `IndentationError` (rc 3). That is a format failure, which is what the contract prescribes.

Test **C3** asserts byte-identity of the extracted body against the source slice; test **C2** asserts a triple-quoted literal survives with its contents intact.

### 3.3 Defect D — `reports/pilot_protocol.md` reconciled to the implementation

The protocol described the **v2** evaluator while the code was **v3**. Investigation (Step 4) found the cause: `pilot_results.md` §12 recommendations **M1** and **M2** authorized exactly the v3 code and prompt changes that were made, and M1 explicitly required "document this as a protocol revision, assign it a version number". The code change was done; **the protocol revision never was**. Nothing supersedes the protocol — the document was simply stale.

Reconciled as **v3.1**, surgically, preserving the user's content:

- Header: protocol version + a dated revision paragraph.
- §4: the stale v2 prompt quote replaced with the **actual** v3 template, plus a `⚠ OPEN DEFECT` blockquote (see B1).
- §4a-note: a new **normative** accepted/rejected shape table.
- §4b: rewritten for last-match semantics.
- §4c: retitled "Superseded", with a 6-row `normalize_candidate` outcome table, an exhaustive 3-item list of permitted transformations, the rc 3 correction, and the `func_defs[0]` limitation.
- §4f: error table replaced; precedence note added; an rc=5 category-limitation blockquote added.
- §5: the "not silently normalised" paragraph replaced with a status correction and a `NORMALIZE:` **fingerprint table** — `pilot_v2` 0/50 records carry it (pre-v3 evaluator), `pilot_v3` 48/50 (v3), v3.1 none yet. This is what makes the "re-run from scratch" requirement checkable rather than a matter of opinion.
- §8: new protocol revision history (v1, v2, v3, v3.1), recording `pilot_v3` as pre-fix exploratory evidence.

Experimental extraction policies were kept **out** of the canonical evaluator, per the brief.

### 3.4 Defect E — the wrong-name comment

Replaced with the empirically correct explanation (rc 3, not rc 4), the reason, the conditions under which rc 4 *is* reachable, and a cross-reference to D5/D6. No behavioural change — the code already concatenated the raw text; only the comment was wrong.

### 3.5 Deliberately NOT changed

| Item | Why not |
|---|---|
| `PROMPT_TEMPLATE` (blocker B1) | Prompts are explicitly out of scope. Documented in protocol §4 as an open defect instead. |
| `func_defs[0]` helper-def selection | An **extraction-policy** change, needing a protocol revision. Affects `Python/10, /32, /38, /50` on full-def input only — all four already fail (rc 3), so it cannot manufacture a pass. Recorded as a KNOWN LIMITATION comment at the selection site. |
| rc 5 conflating candidate timeout with harness error | Same class. `Python/10, /156, /160` buggy solutions time out and land in `harness_error` rather than a timeout category. Does not affect any rc-0 decision. |
| `normalize_note` mislabelling (§7, defect N1) | Zero behavioural impact — both branches emit identical code. Fixing it now would invalidate the 656-record pre/post identity evidence and the note table just frozen into §4c. Belongs in the same v3.2 revision as B1. |
| Existing test files | They pass. Editing them would risk the "do not weaken assertions" constraint for no gain. |

---

## 4. Evidence

All artifacts under `results/evaluator_repair/` (gitignored by `.gitignore:15 results/**`). Baseline = pre-fix, postfix = post-fix.

### 4.1 Regression suite — `scripts/test_evaluator_regression.py` (new, 38 tests)

```
                      PRE-FIX          POST-FIX
suites A-C (27)       21 passed         -
suite D     (10)      10 passed         -
full suite  (38)      31/37, 6 FAILED   38/38 PASS, 0 skipped
defect tags covered   7 of 12           12 of 12
```

The 6 pre-fix failures were the two real defects, each failing for the reason predicted:

| Test | Pre-fix failure |
|---|---|
| A1 | extracted the **buggy echo** from the real `pilot_v3/Python_0_A` stdout instead of the model's fix |
| A2 | `return x - y` (the preamble) instead of the later intended fix |
| A3 | the prompt's one-shot placeholder `return x * 2` shadowed the answer |
| A5 | a **truncated** trailing object won over the last complete one |
| C2 | `'\n    hello\n    ' != '\nhello\n'` — multi-line literal corrupted |
| C3 | body lines shifted to 8 spaces (double-indented) |

Suite contents: **A** (6) first-match/echo shadowing incl. the real artifact and a nested-object case. **B** (11) every format the protocol supports or rejects, incl. B4 asserting raw fenced body-only is **rejected** per §4a. **C** (10) normalization semantics — verbatim concatenation, literal preservation, byte-identity, indentation rescaling, all five note values. **D** (10) every return code 0–5 in a **fresh subprocess** each, incl. D8 (sandbox startup failure → rc 5), D9 (sandbox cannot read the dataset or the oracle), D10 (no failure mode ever scores rc 0). **E** (1) delegates to the full-dataset validator and asserts `n_rows == 164`, `limited is False`, both canonical variants 164 rc=0, buggy 0 rc=0 — so a truncated smoke run can never pass as full-dataset evidence.

A per-tag coverage matrix prints `tests / passed / skipped` and marks a tag COVERED only when all its tests pass and none skip. Pre-fix it correctly reported 5 UNCOVERED tags rather than hiding them behind a partial green.

### 4.2 Full-dataset canonical validation — 164 tasks, real dataset

`scripts/validate_canonical_164.py` (new). This is the test the brief's Risk B demanded and that `validate_dataset.py` could not provide: `validate_dataset.py` uses its **own inline harness**, so its 164/164 never exercised `extract_body`, `normalize_candidate` or `sandbox.sh`.

This validator uses the **canonical path**: real `pilot_runner.extract_body` (loaded via `importlib`) → real `evaluate_candidate.py` **subprocess** → real `scripts/sandbox.sh` (bubblewrap) → real exit code.

```
[GATED            ] canonical_json    pass=164/164   -> PASS
[GATED            ] canonical_direct  pass=164/164   -> PASS
[NEGATIVE CONTROL ] buggy_json        false_acceptances=0/164 -> PASS
[DIAGNOSTIC       ] fulldef_json      pass=160/164   -> n/a
OVERALL: PASS      (656 evaluations, exit 0)
```

`buggy_json` categories: `assertion_fail 155, runtime_error 6, harness_error 3`. **Zero** rc=0. The harness does not pass everything — that is what gives the 164/164 its meaning.

`fulldef_json` 4 failures are `Python/10, /32, /38, /50` — the `func_defs[0]` helper-def limitation (§3.5), all rc 3, none a false pass.

**What this test is, and what it is not.** Per the brief's Step 3, the inputs are **deterministic reference fixtures built with the documented output contract**: `contract_stdout(body) = json.dumps({"fix": body})` where `body` is the dataset's `canonical_solution`. This tests *unmodified raw model stdout* **not at all**. It proves the canonical extraction → normalization → sandbox → scoring path correctly handles all 164 real known-correct fixes and rejects all 164 real known-buggy solutions. It does **not** by itself prove the first-match or dedent fixes — those are model-output-shaped and are proven by **A1–A6** and **C2/C3**, and separately by the real-stdout replay in §5.1. A `--limit` run prints `*** LIMITED RUN ... NOT full-dataset evidence ***` and suite E refuses to accept `limited is True`.

### 4.3 Pre/post identity — 656 of 656 records unchanged

`results/evaluator_repair/compare_pre_post.py` compares every field except `wall_s` across all 4 variants × 164 tasks, pre-fix vs post-fix:

```
PRE  records=656  POST records=656  key sets equal=True
changed records: 0
COMPARISON: IDENTICAL
```

This is the expected result and it is informative: the fixes target **model-shaped** output, and contract-conforming reference fixtures are unaffected. It confirms the repairs introduced no regression in the canonical path. It also means 164/164 alone could not have detected either defect — which is precisely why A1–A6, C2/C3 and the §5.1 replay exist.

### 4.4 Sandbox validation — 13/13 PASS

`scripts/sandbox_test.sh` begins with `rm -rf` on `sandbox_probe/` and `sandbox_probe_oracle/`, which contain **5 tracked files**. Deleting tracked files is a destructive operation and was not taken. Instead the identical probe suite was run against an **isolated copy** pointing at a gitignored scratch directory, using the real unmodified `scripts/sandbox.sh`:

```
results/evaluator_repair/sandbox_check/sandbox_test_isolated.sh
RESULT: PASS=13 FAIL=0    (exit 0)
```

Verified: python executes; `/home` invisible; host secret unreachable; root listing is `bin dev etc lib lib64 proc sbin tmp usr`; writes to read-only `/usr` rejected (rc 2); writes to the oracle path rejected (rc 2, "Directory nonexistent"); writable `/tmp/work` works; outbound TCP to 1.1.1.1:80 blocked; HTTPS/DNS blocked; `timeout 3` kills the sandbox at 3s with no leftover process; workspace writes persist only to the designated dir; no leaked files; oracle unmodified. Mount table confirms a single writable bind (`/tmp/work`) and no network devices at all.

Post-run: `git diff --stat -- sandbox_probe sandbox_probe_oracle scripts/sandbox.sh scripts/sandbox_test.sh` is **empty**. Tracked probe files untouched.

Independently, non-destructive probes **D8** (sandbox startup failure → rc 5, never rc 0) and **D9** (sandbox cannot read the dataset or the oracle) run inside the regression suite in fresh subprocesses.

### 4.5 Existing tests — unchanged and green

```
                              BASELINE   POSTFIX
scripts/test_extract_body.py  exit 0     exit 0, failures: 0
scripts/test_normalization.py exit 0     exit 0, 22 passed / 0 failed
scripts/test_eval.py          exit 0     canonical rc=0, buggy rc=1
```

Note `test_normalization.py` T3/T4 already asserted `full-def-extracted` with no double-def and rc 0 — the user's v3 work was self-consistent. T6 tolerates rc 3 **or** 4, so it did not encode the wrong return-code claim; only the source comment did.

### 4.6 Preservation of user work — verified line by line

`results/evaluator_repair/verify_preservation.py` parses `baseline/git_diff_unstaged.patch`, takes every `+` line (the user's uncommitted work), and checks it is still present:

```
reports/pilot_protocol.md      221 lines -> 202 present, 19 absent
scripts/evaluate_candidate.py  137 lines -> 121 present, 16 absent
scripts/pilot_runner.py        146 lines -> 141 present,  5 absent
TOTAL                          504 lines -> 464 present (92.1%)
```

Every one of the 40 absent lines was individually reviewed and is an intentional, documented replacement:

- **protocol (19):** the stale v2 prompt quote, the §4b first-match parser description, the §4c `declaration + body` "not silently corrected" passage, the §4f full-def/rc-3 table row, and the §5 "not silently normalised" paragraph — all replaced by §3.3 above.
- **evaluate_candidate (16):** `import textwrap`, the `_extract_body_source` dedent/re-indent body and its docstring, and the incorrect wrong-name comment — §3.2 and §3.4.
- **pilot_runner (5):** two reworded `extract_body` docstring lines, `obj, _end = decoder.raw_decode(...)`, `if not body.strip():`, and one re-indented `return None, "malformed: empty fix"` — confirmed still present at line 185, only its indentation changed.

Additional checks, all clean:

- **All 22 pre-existing untracked files are byte-identical** to `baseline/untracked_sha256.txt`. No CHANGED, no MISSING.
- **`results/pilot_v3/`: 180 files, sha256 inventory IDENTICAL** to baseline. Not rewritten, not deleted.
- `git status --short` shows the same 3 modified tracked files and the same 22 untracked files, plus the new files created by this task. **No deletions.**
- No `git reset`, `stash`, `clean`, `checkout --` or `restore` was run at any point.

New files added by this task: `scripts/test_evaluator_regression.py`, `scripts/validate_canonical_164.py`, `scripts/rescore_pilot_v3.py`, and the `results/evaluator_repair/` evidence tree.

---

## 5. Reassessment of `results/pilot_v3/`

### 5.1 The 50 stored attempts replayed through v3.1

`scripts/rescore_pilot_v3.py` replays the **verbatim stored `gen_stdout`** of all 50 `pilot_v3` attempts through the fixed `extract_body` and the fixed evaluator. No model inference. Read-only with respect to `results/pilot_v3/`. Evidence: `postfix/pilot_v3_rescored.json`.

```
attempts replayed                                    : 50
old rc=0 (pass)                                      : 0
new rc=0 (pass)                                      : 0
attempts whose extracted body differs from stored     : 1
attempts whose rc changed                            : 0

old categories: {assertion_fail 43, malformed_output 2, import_error 4, runtime_error 1}
new categories: {assertion_fail 43, malformed_output 2, import_error 4, runtime_error 1}

config A  old={assertion_fail 7, malformed_output 2, runtime_error 1}   new=identical
config B  old={assertion_fail 9, import_error 1}                         new=identical
config C  old={assertion_fail 27, import_error 3}                        new=identical
```

The single changed body is `Python/0` A a1 — the defect-A artifact. It had 9 `"fix"` objects in stdout; pre-fix the extractor returned the buggy echo, post-fix it returns the model's real answer. **rc stayed 1** (`assertion_fail`): the model's actual fix was also wrong.

**This is the honest headline: the first-match defect was real and demonstrably corrupted extraction on a real attempt, but fixing it changes none of `pilot_v3`'s scores.** `pilot_v3`'s 0/30 is **not** an artifact of the evaluator defects. The model genuinely failed these tasks.

**Limitation of this replay, stated plainly.** It cannot reproduce config C faithfully. C's attempt-2 and attempt-3 repair prompts were built from the *feedback of the previous attempt*, so a different attempt-1 score would in principle have produced a different attempt-2 prompt and a different completion. Those later completions are fixed historical bytes replayed as-is. Any C recovery counted here is a lower bound on what a genuine v3.1 re-run might show, and an upper bound on nothing. A real re-run (blocker B2) is the only way to settle it.

### 5.2 Blocker B1, measured

Both `malformed_output` attempts are config A, and both fail identically:

```
Python/48  A a1   1700 bytes, 12 "fix" occurrences
Python/128 A a1   1459 bytes,  9 "fix" occurrences
  malformed: json error (Invalid control character at: line 1 column 45 (char 44))
              and no code fallback
```

The raw stdout shows why. The model emits:

```
```json
{"fix": "    for i in range(len(text) // 2):
        if text[i] != text[len(text) - i - 1]:
            return False
    return True"}
```

A **literal newline inside a JSON string** — invalid JSON, and rejected correctly by the frozen contract. The model is imitating `PROMPT_TEMPLATE`'s one-shot example, which contains exactly the same defect: the template is a non-raw Python string, so `\n` in `{{"fix": "    return x * 2\n"}}` becomes a **real newline** before `.format()` ever renders it. The prompt teaches the model to emit invalid JSON.

This is not cosmetic. `results/evaluator_repair/diag_malformed_A.py` repairs the control characters by hand — a **diagnostic only**, not a scoring path, and it changes nothing about evaluator behaviour — and scores the recovered bodies:

```
Python/48  A a1   recovered 4-line palindrome check      -> rc=0 (pass)
Python/128 A a1   recovered 3-line product/sum expression -> rc=1 (assertion_fail)
```

**`Python/48` config A contained a correct fix and the pipeline threw it away.** Config A's true score on this pilot is understated by at least 1 of 10 tasks, purely because of a prompt formatting bug. Configs B and C are grammar-constrained by `response.gbnf`, whose `char` rule excludes raw control characters, so they *cannot* produce this failure. Any A-vs-B/C difference measured on this prompt is partly a measurement artifact rather than a retry-vs-feedback effect.

The fix is a one-character-class change to the prompt example (`\\n` instead of `\n`, or a raw-string template) — but prompts are out of scope, so it is documented here and in protocol §4 rather than applied. **Do not run the main experiment on the current prompt.**

### 5.3 Status of `pilot_v3` conclusions

`results/pilot_v3/` is **unchanged** — 180 files, byte-identical. Its limitations are labelled here and in protocol §5 and §8, not by editing the artifacts.

`pilot_v3` is **pre-fix exploratory evidence**. Concretely:

- Produced by the v3 evaluator; **48 of 50** records carry the v3 `NORMALIZE:` fingerprint, 0 carry v3.1. The 2 that carry none are exactly the 2 `malformed_output` attempts of §5.2 — they were rejected by `extract_body` and never reached the evaluator, so no fingerprint exists to carry. That the exception set is precisely the failure set is what makes the fingerprint an auditable gate rather than a heuristic. Protocol §5 requires a from-scratch re-run after any evaluator change.
- Its config-A arm is contaminated by blocker B1 (§5.2).
- Its 0/30 outcome **survives** the evaluator fixes (§5.1), so the substantive finding — "this model at this size does not solve these tasks under this contract" — is *strengthened*, not weakened, by this work. That is worth stating because it was not the expected direction.
- Its config-C arm cannot be counterfactually re-scored (§5.1 limitation).

The prompt defect in `pilot_results.md` §12 M2 was addressed by the v3 prompt rewrite; the rewrite introduced B1. M1 was addressed by `normalize_candidate`; M5's warning (do not expand C's attempt budget) remains sound — C exhausted all 3 attempts on all 10 tasks with 0 recoveries.

---

## 6. Acceptance criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | All 164 real known-correct fixes pass the canonical end-to-end evaluator | **MET** | §4.2 `canonical_json` 164/164, `canonical_direct` 164/164; suite E1 |
| 2 | No negative control falsely accepted | **MET** | §4.2 `buggy_json` 0/164 false acceptances (155 assertion_fail, 6 runtime_error, 3 harness_error); D10 |
| 3 | Echoed-prompt shadowing fixed, with a regression test | **MET** | §3.1, §4.1 A1–A6 (6/6, was 2/6); A1 uses the real `pilot_v3/Python_0_A` artifact |
| 4 | All protocol-supported formats behave as documented | **MET** | §4.1 B1–B11 (11/11); protocol §4a-note normative table; B4 pins raw body-only as **rejected** |
| 5 | Stale tests corrected or retired | **MET — premise false** | §1.1: no stale test existed; all 3 suites passed pre-fix and are byte-identical (§4.5, §4.6) |
| 6 | Protocol and implementation agree | **MET** | §3.3; protocol v3.1 §4/§4a-note/§4b/§4c/§4f/§5/§8 |
| 7 | Existing tests and sandbox checks pass | **MET** | §4.5 (3/3, exit 0); §4.4 sandbox 13/13 PASS via isolated copy, tracked probes untouched |
| 8 | Results are reproducible | **MET** | §4.3 656/656 identical pre/post; §8 exact commands; §2 pinned hashes; deterministic temp=0.0 seed=42 |

No criterion is marked PASS on the strength of an unexecuted test. Criterion 7's sandbox component was satisfied by executing the real probe suite against a path-isolated copy rather than by inference, and the substitution is disclosed.

---

## 7. Remaining risks and open defects

**Blockers for the main experiment**

- **B1 — invalid-JSON prompt example.** Measured: 2/10 config-A attempts destroyed, ≥1 correct fix discarded (§5.2). Requires a prompt change (out of scope). Highest priority.
- **B2 — no v3.1 pilot exists.** Protocol §5 requires a from-scratch re-run; the `NORMALIZE:` fingerprint makes the gap auditable (§3.3). Requires model generation (user decision).

**Open defects, documented and not fixed**

- **N1 — `normalize_note` mislabels 4 of 164 canonical solutions.** `normalize_candidate` classifies an indented fragment as `body-only` only when the `unexpected indent` error is at **lineno 1**. Four canonical solutions begin with a blank or under-indented line, pushing the first statement to line 2 or 3, so they are labelled `parse-error (unexpected indent ...)`: `Python/81` (line 3), `Python/92`, `Python/134`, `Python/146` (line 2). **No behavioural impact** — both branches emit the identical `declaration + body_text` and all four score rc=0. **Analytical impact is real:** any analysis that groups by `normalize_note` would misclassify 2.4% of dataset solutions, and would misclassify model outputs that open with a blank line — a common LLM habit. Minimal fix: drop the `lineno == 1` condition. Not applied because it would change reported note values, invalidate the §4.3 identity evidence, and contradict the §4c table just frozen. Belongs in v3.2 with B1.
- **N2 — `func_defs[0]` selects the textually first top-level def.** Where `declaration` embeds a helper def, a full-def candidate can have its helper extracted instead of the target: `Python/10` (`poly`/`find_zero`), `/32` (`is_palindrome`/`make_palindrome`), `/38` (`encode_cyclic`/`decode_cyclic`), `/50` (`encode_shift`/`decode_shift`). All four fail rc 3 — cannot produce a false pass. Extraction-policy change; needs a protocol revision.
- **N3 — rc 5 conflates candidate timeout with harness error.** `Python/10, /156, /160` buggy solutions time out and are recorded as `harness_error`. Does not affect any rc-0 decision, but it will distort failure-category reporting at 164-task scale.

**Scope and interpretation limits**

- The 164/164 result uses contract-conforming synthesized fixtures (§4.2). It is **not** a test of unmodified raw model stdout; the real-stdout evidence is §4.1 A1 and §5.1.
- 164/164 alone could not detect either repaired defect — §4.3 proves the canonical fixtures are insensitive to both. Do not cite 164/164 as evidence the fixes work.
- The §5.1 replay is a lower bound for config C only (§5.1 limitation).
- `pilot_v3` is a 10-task pilot. It has no statistical power and supports no significance claims.
- Model capability is now the leading hypothesis for 0/30, not evaluator error. `pilot_results.md` §12's fallback — "consider a larger model" — is live.

---

## 8. Reproduction

All commands from `/home/aaksh/projects/LocalAgentBench`. `.venv/bin/python` is Python 3.14.4.

```bash
# 1. Existing tests (must be exit 0 before and after any change)
.venv/bin/python scripts/test_extract_body.py
.venv/bin/python scripts/test_normalization.py
.venv/bin/python scripts/test_eval.py

# 2. Full regression suite, 38 tests incl. full-dataset suite E  (~7 min)
.venv/bin/python scripts/test_evaluator_regression.py
.venv/bin/python scripts/test_evaluator_regression.py --list      # enumerate
.venv/bin/python scripts/test_evaluator_regression.py --suite D   # subset
# expect: executed=38 passed=38 failed=0 skipped=0 / 12 COVERED / RESULT: PASS

# 3. Full-dataset canonical validation, 656 evaluations  (~11 min)
.venv/bin/python scripts/validate_canonical_164.py \
    --variants canonical_json,canonical_direct,buggy_json,fulldef_json \
    --out results/evaluator_repair/postfix/canonical_164_POSTFIX.json
# expect: canonical_json 164/164, canonical_direct 164/164,
#         buggy_json false_acceptances=0/164, OVERALL: PASS

# 4. Pre/post identity
.venv/bin/python results/evaluator_repair/compare_pre_post.py
# expect: 656 records, changed 0, COMPARISON: IDENTICAL

# 5. Sandbox probes (isolated; does NOT touch tracked sandbox_probe/)
bash results/evaluator_repair/sandbox_check/sandbox_test_isolated.sh
# expect: RESULT: PASS=13 FAIL=0

# 6. Real-stdout replay of pilot_v3 (no inference)
.venv/bin/python scripts/rescore_pilot_v3.py
# expect: 50 attempts, rc changed 0, body differs 1

# 7. Blocker B1 diagnostic
.venv/bin/python results/evaluator_repair/diag_malformed_A.py
# expect: Python/48 rc=0 (pass), Python/128 rc=1

# 8. Preservation audit
.venv/bin/python results/evaluator_repair/verify_preservation.py
diff <(sort results/evaluator_repair/baseline/pilot_v3_sha256.txt) \
     <(find results/pilot_v3 -type f -exec sha256sum {} \; | sort)
# expect: no output (IDENTICAL)
```

Evidence tree:

```
results/evaluator_repair/
  baseline/   git state, diffs, sha256 inventories, environment,
              pre-fix test + regression + canonical_164 outputs, probes
  postfix/    post-fix test + regression (38/38) + canonical_164 (656) +
              sandbox_test_isolated (13/13) + pilot_v3_rescored + diag
  sandbox_check/  path-isolated copy of sandbox_test.sh
  verify_preservation.py, compare_pre_post.py, diag_malformed_A.py
```

---

## 9. Next safest action

In order. Do **not** start the main experiment.

1. **Fix B1** — correct the one-shot example in `PROMPT_TEMPLATE` so it is valid JSON (`\\n`, or make the template a raw string). This is a prompt change and needs your authorization. Until it lands, config A is measuring the prompt bug, not single-pass behaviour.
2. **Decide on N1** in the same v3.2 revision — it is a one-line change, but it alters reported `normalize_note` values and must be frozen together with B1 so the fingerprint stays coherent.
3. **Re-run the 10-task pilot under v3.1**, same frozen selection and settings, writing to a **new** directory (`results/pilot_v3_1/`). Leave `results/pilot_v3/` untouched. This is a pilot, not the main experiment: 10 tasks × 3 configs. It discharges B2 and measures B1's impact on the A arm.
4. **Read the re-run against §5.1.** If A's `malformed_output` count drops to 0 and A's score rises, B1 was the confound. If 0/30 persists with clean extraction across all three arms, the evaluator is exonerated and the finding is model capability — at which point `pilot_results.md` §12's "consider a larger model" is the decision in front of you, not further evaluator work.
5. **Only then** consider the 164-task run. N2 and N3 should be resolved or explicitly accepted as known limitations first; at 164-task scale N3 will visibly distort failure-category reporting.

---

_This report records executed results only. Every number above is traceable to a file under `results/evaluator_repair/`. No test was skipped, weakened, or hardcoded to pass; where a criterion could not be tested as literally specified, the substitution is disclosed in §4.4 and §6 rather than papered over._

---

# ADDENDUM — v3.2 (2026-10-18, later session)

This addendum is appended only. Everything above this line is the original
`Evaluator Validation Report` (evaluator version v3.1) and is **unchanged**, including
the statements that are now superseded, listed below.

## What was verified, not assumed

Before executing anything, the state described above was re-derived from the
repository:

| Claim in the original report | Status at re-check | How verified |
|---|---|---|
| Regression suite 38/38 | **Superseded → 48/48** | `results/evaluator_repair/v32/regression_full_v3_2.out`: `executed=48 passed=48 failed=0 skipped=0`, `RESULT: PASS`, exit 0. The suite grew by 10 tests when the v3.2 prompt-encoding (7), N1-normalize-note (3) and freeze (1) cases were added. `F-prompt-encoding` parses the **rendered** example, not the source spelling. |
| Canonical 164/164 | **Confirmed under v3.2** | `v32/canonical_164_v32.json`: `canonical_json` 164/164 rc=0, `canonical_direct` 164/164 rc=0 |
| Negative control 0/164 false accepts | **Confirmed under v3.2** | same file: `buggy_json` rc0=0/164 (assertion_fail 155, runtime_error 6, harness_error 3) |
| Sandbox 13/13 | **Confirmed; unchanged** | `postfix/sandbox_test_isolated.out`; `scripts/response.gbnf` and `scripts/sandbox.sh` hashes unchanged in `freeze_fingerprint_v3_2.json` |
| `results/pilot_v3/` intact | **Confirmed twice** | all 180 file sha256s recomputed live and diffed against `v32/pilot_v3_sha256_NOW.txt`, once before and once after the v3.2 pilot run: identical |

## Blocker B1 — fixed, and found to be inert

`PROMPT_TEMPLATE` is now a raw string (`scripts/pilot_runner.py:123`); the rendered
example is `{"fix": "    return x * 2\n"}` with a literal backslash-n, valid JSON,
zero raw control characters (`freeze_fingerprint_v3_2.json`).

**Correction to the original diagnosis.** B1 was described as destroying 2 of 10
config-A attempts by teaching the model to emit raw newlines. The v3.2 pilot tested
that mechanism directly and it did not hold: with the corrected prompt, all 50 attempts
produced **byte-identical** output to pilot_v3, and the same 2 config-A attempts still
failed with `Invalid control character`. The model's unescaped newlines are self-derived,
not imitated from the example. The fix was correct and worth freezing, but it changed no
outcome. See `reports/pilot_v3_2.md` §4.

## Blocker B2 — closed

The v3.2 pilot has now been executed: `results/pilot_v3_2/` (30 task/config records,
50 attempts), report at `reports/pilot_v3_2.md`.

## Defect N1 — fixed, label-only, proven

`normalize_candidate` now classifies body-only fragments **structurally**
(`evaluate_candidate.py:201`, leading-whitespace test) instead of requiring
`e.lineno == 1`. `v31_v32` comparison over all 656 records: **0 scoring changes**, note
changes confined to the predicted set `Python/81, 92, 134, 146` (`parse-error →
body-only`), 0 unexpected. Verdict `LABEL-ONLY CONFIRMED` in
`results/evaluator_repair/v32/n1_label_only_verification.json`. The original report's
decision to defer this fix was correct: it had to be frozen together with B1.

## New open item raised by the v3.2 pilot

Grammar-constrained arms B and C can fail by **escaping correctly and truncating the
body instead** (`Python/48`: `{"fix": "    for i in range(len(text) // 2):"}` →
`IndentationError`, rc=3) while unconstrained A emits the complete body and fails at
extraction. The failure *mode* is arm-dependent, which is a design confound for the
A-vs-B/C contrast and must be settled before the 164-task gate. Evidence and options:
`reports/pilot_v3_2.md` §3, §7, §8.

## Overall verdict after this addendum

Evaluator: **PASS** (unchanged, now also confirmed at v3.2).
Pipeline / main experiment: **BLOCKED**, for the reason above rather than B1 or B2.
