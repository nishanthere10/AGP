# Stage 6 — Dataset Audit: HumanEvalPack (Python code-repair)

Date: 2026-10-10
Status: **PASSED** — official dataset usable as specified (164 Python repair tasks)

## Source and identity

| Field | Value |
|---|---|
| Dataset | `bigcode/humanevalpack` — `https://huggingface.co/datasets/bigcode/humanevalpack` |
| Revision pinned | `9a41762f73a8cb23bb5811b73d5aab164efcf378` (HEAD at audit time, lastModified 2025-08-19) |
| Correct config for code repair | **`python`** (default config) |
| Split | **`test`** — the only split |
| Record count | **164** (published `num_examples: 164`; verified locally: 164 rows, 164 unique IDs `Python/0` … `Python/163`) |
| License | **MIT** (dataset card `license: MIT`; the underlying HumanEval is also MIT) |
| Local file | `third_party/dataset/humanevalpack_python_test.parquet`, 191,279 bytes (matches published `download_size: 191279`), sha256 `ed5f15d789156e21222bfcd556c425a39042355c84ae1e8b058abd6a3d7f8075` |

## Fields (published schema, verified present locally)

`task_id, prompt, declaration, canonical_solution, buggy_solution, bug_type, failure_symptoms, entry_point, import, test_setup, test, example_test, signature, docstring, instruction`

- `import` and `test_setup` are **empty for all 164 Python tasks** → the Python tasks need no third-party dependencies (pure stdlib). Confirmed by execution: no import errors other than the intentional bug.
- `bug_type` distribution: value misuse 44, missing logic 33, excess logic 31, operator misuse 25, variable misuse 23, function misuse 8.
- `buggy_solution != canonical_solution` for all 164 tasks (0 identical).

## What the model sees vs. what the researcher keeps

Following the HumanEvalFix/OctoPack format:

- **Model-visible:** `instruction`, `prompt` (signature + docstring), `declaration`, `buggy_solution` (the function body to repair).
- **Held out from the model:** `canonical_solution`, `test` (ground-truth assertions), `bug_type`, `failure_symptoms`.
- **Test format:** a `check(<entry_point>)` function with bare `assert`s; invoked as `exec(test)` after defining the candidate. `example_test` exists for every task (an easier visible example).
- Tests are **published, not hidden** — but our harness must still withhold `test` from the model prompt and keep it non-writable inside the sandbox (the eventual evaluator reads the oracle; the candidate code never touches it).

## Reference-test verification (executed)

Script: `scripts/validate_dataset.py`. Method: for each of the 164 tasks, run `declaration + buggy_solution` and `declaration + canonical_solution` in a fresh `python3 -I` subprocess with a 10 s timeout, then `exec(test)`; exit code 0 = pass.

| Check | Result |
|---|---|
| Buggy solution fails its test | **164 / 164** |
| Canonical solution passes its test | **164 / 164** |
| Both conditions hold | **164 / 164, zero anomalies** |

Notes on non-zero buggy exit codes (all count as "fails", as intended): `rc=1` = assertion failure (most tasks), `rc=2` = runtime error raised by the bug, `rc=-9` = 10 s timeout (non-terminating buggy loop, e.g. `Python/160`), `rc=3/4` = import/entry errors (none observed). Full per-task records: `results/dataset_validation.json`.

Caveat: this validation ran on the host, not in the sandbox, because it executes **dataset-published** code (trusted oracle), not model-generated code. Model-generated code will only run inside the validated Bubblewrap sandbox (Stage 5). The identical harness will be reused inside the sandbox for the pilot.

## Execution plan for the evaluator (Stage 5/7 design)

1. Ground-truth `test` field is read by the evaluator on the host and written into the sandbox **read-only** (or passed via stdin), never into a model-writable directory.
2. Candidate code goes to a per-attempt writable tmpfs/tmpdir inside the sandbox; each attempt runs in a fresh sandbox instance with network disabled and a wall-clock timeout.
3. Dependencies: stdlib only (verified) → sandbox needs only `/usr/bin/python3` + minimal `/usr` read view.
4. Timeouts: 10 s per test run (measured: canonical runs all complete well under 1 s; one buggy task legitimately hangs and must be killed).

## Licensing / reuse

MIT — reuse permitted with attribution (keep the dataset card notice in the report). No gating on this dataset (`gated: false`).

## Conclusion

The specification's "HumanEvalFix, 164 Python tasks" matches the official `python`/`test` configuration of `bigcode/humanevalpack`. The test oracle is available, self-contained (stdlib), and verified to discriminate buggy from canonical implementations on all 164 tasks. **No substitution or correction to the benchmark specification is required.** Full 164-run not started (per rules).
