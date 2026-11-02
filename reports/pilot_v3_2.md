# Pilot v3.2 — Clean Rerun Under the Corrected Prompt

Date: 2026-10-18
Run executed: 2026-10-18 10:32–11:32 UTC (60 min wall, single sequential model instance)
Runner: `scripts/pilot_runner.py --configs ABC --out results/pilot_v3_2`
Protocol: `reports/pilot_protocol.md` **v3.2**
Frozen fingerprint: `results/evaluator_repair/v32/freeze_fingerprint_v3_2.json`
Primary results: `results/pilot_v3_2/` (30 task/config directories, 50 attempts)
Analysis: `results/pilot_v3_2/analysis.json` (`scripts/analyze_pilot_v3_2.py`, read-only)
Run log: `results/pilot_v3_2_run.log`
Prior pilot for comparison: `results/pilot_v3/` (**not modified** — verified below)

---

## 1. Verdict

**Harness gate: PASS.** The v3.2 pilot ran cleanly end to end: all 30 planned
task/config executions completed, all 50 model attempts returned generation rc=0,
the sandbox evaluated every extracted candidate, and there were **zero infrastructure
failures** — no timeouts, no harness errors, no import of ground truth into the model
view. Both blockers recorded in `reports/evaluator_validation.md` are now closed:
**B1** (invalid-JSON prompt example) is fixed and frozen; **B2** (no pilot under the
corrected evaluator) is closed by this run.

**Experiment-readiness gate: BLOCKED.** The correction produced **byte-identical
model output** to pilot_v3 on all 50 attempts and the same 0/10 in all three arms.
The prompt defect therefore **affected no observed outcome**, which falsifies the
mechanism the previous audit assumed: the floor effect is not a harness artifact.
But the rerun also shows the floor is **not** arm-independent in its *cause* —
config A fails by emitting complete bodies with unescaped newlines, while the
grammar-constrained arms B and C fail by emitting escaped but **truncated** bodies
(§3, §7). The planned A-vs-B/C contrast is confounded at the serialisation layer, so
the 164-task experiment would measure decoding format, not repair capability.

---

## 2. Setup frozen before generation

All 30 records carry the same settings, verified from the artifacts rather than from
the protocol text:

| Setting | Value | Verified |
|---|---|---|
| Protocol revision | `v3.2` on all 30 records | yes |
| Evaluator revision | `v3.2` on all 30 records | yes |
| `PROMPT_TEMPLATE` sha256 | single value `3074dd57…60fe0d` across all 30 records | yes |
| Grammar | `None` for A; `response.gbnf` for B and C | yes (10/10/10) |
| `n_predict` / `temp` / `seed` | 512 / 0.0 / 42 | yes |
| `ctx` / `threads` / `-ngl` | 4096 / 4 / 0 | yes |
| Flags | `--no-conversation --single-turn --no-display-prompt` | yes (`gen_a1.time`) |
| Test timeout | 10 s per sandbox run | yes |
| Attempt budget | A: 1, B: 1, C: 3 | yes — A/B used 1, **all 10 C tasks used exactly 3** |
| Task selection | `Python/0,16,32,48,64,80,96,112,128,144` | `results/pilot_v3_2/task_selection.json` is byte-identical to the frozen `results/pilot/task_selection.json` |
| Model | `qwen2.5-coder-1.5b-instruct-q4_k_m.gguf` | run used `models/…` per recorded command line |

Per-arm prompt comparability: all three arms use the same base prompt
(`prompt_sha256` is unique per task/config pair = 30 distinct values, as expected
for 30 distinct tasks/functions, with one shared template hash). Config C additionally
sends sandboxed test feedback with the previous attempt's body
(`pilot_runner.py:335-348`); the repair prompt is recorded per attempt.

**Arms are comparable.** No unavoidable changes to experimental variables beyond the
two v3.2 corrections themselves (§4 of the protocol): raw-string prompt template and
the `normalize_note` label.

---

## 3. Primary results

Scored by the frozen v3.2 evaluator exactly as recorded; **no manual repair was
applied to any primary score.**

| Config | First-attempt success | Final success | Retry recovery | Attempts recorded |
|---|---|---|---|---|
| A — naive | 0 / 10 | 0 / 10 | n/a (budget 1) | 10 |
| B — grammar-constrained | 0 / 10 | 0 / 10 | n/a (budget 1) | 10 |
| C — bounded repair | 0 / 10 | 0 / 10 | 0 / 10 | 30 |

**Per-attempt failure categories (50 attempts)**

| Config | assertion_fail | runtime_error | import_error | extraction_error | pass |
|---|---|---|---|---|---|
| A | 7 | 1 | 0 | 2 | 0 |
| B | 9 | 0 | 1 | 0 | 0 |
| C (30) | 27 | 0 | 3 | 0 | 0 |

Failure modes worth naming individually (full detail in §7):

- **JSON / extraction errors: 2, both config A** (`Python/48`, `Python/128`) —
  `malformed: json error (Invalid control character …) and no code fallback`. The model
  wrote a correct multi-line body but put **raw newlines inside the JSON string** instead
  of `\n`. A and B share `Python/48`; A also has a `RUNTIME_ERROR` (`Python/96`,
  `NameError: name 'primes' is not defined` — body references a name outside itself).
- **`rc=3` syntax/import errors: 1 in B, 3 in C** — all on `Python/48`. The
  grammar-constrained arms produce a **truncated single-line** body instead:
  `{"fix": "    for i in range(len(text) // 2):"}` — valid JSON, valid extraction, but the
  loop body is cut off, giving `IndentationError: expected an indented block after 'for'
  statement`. Under the grammar the model escapes nothing; it terminates the string early.
- **Timeouts: 0. Infrastructure failures: 0.** All 50 attempts returned generation rc=0 and
  every one reached an evaluator verdict.
- Config C produced **2 distinct outputs per task** (3 attempts, the retry loop did
  change behaviour) and 10/10 tasks classified identically across all three attempts
  — the retry budget changed the wording of the wrong answer, not the answer.

---

## 4. Difference from pilot_v3 — the central finding

The v3.2 prompt is **not** the v3 prompt: the rendered example differs by one byte
(`{"fix": "    return x * 2\n"}` with a literal backslash-n, versus a real newline;
extracted from `gen_a1.time` in both runs — 726 vs 725 prompt bytes).

Despite the different input, **all 30 arms / 50 attempts produced byte-identical
`gen_stdout` to `results/pilot_v3/`**, with identical extract labels and identical
return codes. Category distributions match exactly (A 7/1/2, B 9/1, C 27/3).

Consequences:

1. **The original prompt defect affected no observed outcome.** It was real (the v3
   example was invalid JSON) but inert on this task set: the two config-A escaping
   failures are **self-derived, not imitated** — the model emits raw newlines inside its
   own string value regardless of how the example escapes them. Removing the bad example
   changed nothing.
2. **B1's predicted differential bias against config A does not exist** in this
   model/task set. The A-vs-B/C comparison was not confounded by it. Both pilots agree.
3. **The harness is deterministic.** Same seed, same temp, different prompt bytes,
   identical completions to the token budget — this is strong evidence that the
   recorded results are reproducible and that no nondeterministic layer (sandbox,
   extraction, retry) is perturbing scores.
4. **`results/pilot_v3/` is untouched.** I recomputed all 180 file sha256s live and
   diffed against `results/evaluator_repair/v32/pilot_v3_sha256_NOW.txt`: identical,
   before and after this run. The runner's own guard (`guard_out_root`) refuses to
   write into `pilot`, `pilot_v2` or `pilot_v3`.

Note on timing: generation was ~5× slower per token than pilot_v3 (e.g. `Python/16`
A, identical 76-char output: 96 s here vs 19 s in pilot_v3). WSL had been restarted
26 minutes before this run and `llama-completion` held only ~1.1 of 4 requested
threads while the VM sat ~76 % idle with zero swap used. This is an **environment
change, not an experimental one**; scores are unaffected (outputs are byte-identical)
and wall-clock figures are **not comparable** across the two pilots.

---

## 5. Costs

| Measure | Value |
|---|---|
| Model attempts | 50 (10 A + 10 B + 30 C) |
| Generation tokens | 22,321 (mean 446 / attempt) |
| Generation wall time | 3,472 s summed (~58 min of the 60-min run) |
| Peak model RSS | 1.94 GiB |
| Swap used during run | 0 |
| Sandbox evaluations | 50, each inside Bubblewrap, ≤10 s test timeout |
| Pilot cost ratio | C consumed 3× A/B compute for 0 recovered tasks |

---

## 6. Separate diagnostic evidence (not scored)

`results/evaluator_repair/v32/diag_escape_repair.py` / `.json` — takes the code the
model actually wrote inside the two malformed config-A JSON strings, confirms that
escaping the raw newlines alone makes the object valid JSON, and passes that body to
the frozen v3.2 evaluator through its normal `--body-file` path.

| Task | Primary verdict | Escape-repaired body verdict |
|---|---|---|
| `Python/48` | extraction_error (malformed JSON) | **rc=0 PASS** |
| `Python/128` | extraction_error (malformed JSON) | rc=1 assertion_fail |

So **one** of the two extraction failures concealed a genuinely correct fix; the other
was wrong regardless. If config A were scored on escape-repaired output it would be
1/10 rather than 0/10. **This repair was not applied to the primary score.** It is
recorded only as diagnostic evidence that the model's *semantics* are occasionally
right while its *serialisation* is not — a distinct failure mode from being wrong.

---

## 7. What this pilot establishes, conservatively

Established:
- The v3.2 pipeline is clean, frozen, deterministic and reproducible; every arm is
  comparable and every attempt is accounted for. This was the point of the rerun, and
  it succeeded.
- The prompt-encoding defect was inert. The v3 pilot's conclusions about scores are
  **not** invalidated by it, and no re-interpretation of pilot_v3 is needed.
- Config A's format failures are model-level JSON-escaping failures, not prompt
  imitation.
- The retry loop (C) is functioning mechanically — it sends real sandbox feedback and
  gets different output — and recovers nothing at this model size.

Not established:
- **Nothing about relative capability.** 0/10 in all three arms gives the A/B/C
  contrast no signal. On the full 164 tasks the same floor is expected, so the main
  experiment would most likely produce 0 vs 0 vs 0 and answer neither "does grammar
  constrained decoding help" nor "does bounded repair help".
- Research novelty, or that this model *cannot* solve the tasks: the diagnostic in §6
  shows at least one task where the model produced a correct body and lost only on
  serialisation.
- Any statistically meaningful difference: n = 10 tasks, single seed, greedy decoding.

Remaining confounds that the rerun did **not** remove — and one it *newly identified*:

- **New finding: grammar-constrained decoding can truncate multi-line bodies.** The
  `rc=3` failures are exclusively in the two constrained arms (1 in B, 3 in C) and
  exclusively `Python/48` — 4 of 40 constrained attempts, so this is a tendency
  observed on one task, not a rate. The constrained output there is
  `{"fix": "    for i in range(len(text) // 2):"}` — valid
  JSON, cleanly extracted, and a syntactically incomplete body. `response.gbnf` already
  JSON, cleanly extracted, and a syntactically incomplete body. `response.gbnf` already
  forbids raw control characters in string values (`char ::= [^"\\\x00-\x1F] | escape`),
  so constrained decoding cannot emit the literal newlines that config A emits; instead
  the model closes the string early. Config A, unconstrained, emits the *complete* body
  with unescaped newlines and dies at extraction. **The same task fails in opposite ways
  depending on the arm** — and note that `Python/48` fails in all three arms regardless,
  so the task itself is hard for this model; the point is that the *mode* of failure is
  arm-dependent. Any A-vs-B/C difference here may therefore be a decoding-format
  artefact rather than a capability effect, which is exactly what the experiment must
  avoid.
- **Serialization is the binding constraint, not semantics.** §6 shows at least one task
  (`Python/48` A) where the model wrote a correct fix and lost only because it could not
  escape it. The prompt correction did not change the semantics of a single attempt.
- **Known evaluator limitation** (`func_defs[0]` helper-def selection): `Python/10, 32,
  38, 50` fail rc=3 on full-`def` input. Documented, cannot produce a false pass, but
  it is an extraction-policy issue awaiting a protocol decision.
- Config C's attempt budget is spent on retries that are functionally equivalent: 2
  distinct outputs per task, 10/10 tasks classified identically across all three
  attempts. On `Python/48` it re-emitted the same truncated body three times.

---

## 8. Recommendation

**BLOCKED for the 164-task comparison** — not because the harness is untrustworthy
(it now is), but because the measured floor is arm-independent and the planned
contrast has nothing to discriminate on. Running 164 tasks × 3 arms at ~1–5 min/attempt
buys a foregone 0-vs-0-vs-0 result.

Next justified action, in order:

1. **Decide the output contract question** (cheap, no model runs). The arms currently
   fail in *arm-specific* ways at the serialisation layer: unconstrained A produces
   complete-but-unescaped bodies, grammar-constrained B/C produce escaped-but-truncated
   bodies. Until that is resolved, an A-vs-B/C difference cannot be attributed to
   capability. The realistic options:
   - (a) accept a **non-JSON body-only format for all arms** and use the grammar only as
     the manipulated variable in one arm, with the escaping requirement dropped from §4a;
   - (b) require valid JSON everywhere but give the model a **line-based or per-statement
     encoding** the grammar can express without forcing early string closure;
   - (c) keep §4a as is and accept that serialisation, not repair, is the measured
     variable — in which case the research question must be restated.
2. Re-freeze and re-run the 10-task pilot under the chosen contract (one more ~1 h run).
   A run is worth starting only if it can plausibly give a non-zero score to at least one
   arm.
3. Only then revisit the 164-task gate.

Do not scale to 164 tasks before step 2 produces at least one arm with a non-zero score.

---

## 9. Reproduction

```bash
cd /home/aaksh/projects/LocalAgentBench
# frozen fingerprint + full regression (no model needed)
.venv/bin/python scripts/test_evaluator_regression.py        # expect 48/48 PASS
.venv/bin/python scripts/validate_canonical_164.py           # expect 164/164, 0/164
# the pilot itself (~60 min under current machine speed)
.venv/bin/python scripts/pilot_runner.py --configs ABC --out results/pilot_v3_2   # guard refuses a non-empty dir
.venv/bin/python scripts/analyze_pilot_v3_2.py               # writes results/pilot_v3_2/analysis.json
# separate diagnostic (§6)
.venv/bin/python results/evaluator_repair/v32/diag_escape_repair.py
```

Files added by this phase: `results/pilot_v3_2/` (30 dirs + `summary.json` +
`analysis.json`), `results/pilot_v3_2_run.log`, `scripts/analyze_pilot_v3_2.py`,
`reports/pilot_v3_2.md`, the v3.2 addendum in `reports/evaluator_validation.md`.
Nothing else was modified; `results/pilot`, `results/pilot_v2`, `results/pilot_v3`
and the dataset are unchanged.
