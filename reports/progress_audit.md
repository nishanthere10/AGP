# LocalAgentBench — Progress Audit & Technical Status Report

**Audit date:** 2026-10-15 (host 00:19 IST / 2026-10-14 18:49 UTC)
**Auditor:** AI agent (OpenCode session `ses_ec449fc3fffej6oJdq3DtTGmyk`)
**Nature of audit:** Read-only. No project code, configuration, or results were modified.
**Tests executed by the auditor** are listed explicitly in §L and marked inline as *(auditor-run)*.

> **Legend used throughout:** **[VERIFIED]** = confirmed by direct file/execution evidence during this audit.
> **[REPORTED]** = stated in an existing project report, consistent with evidence, but not re-derived here.
> **[INFERRED]** = conclusion drawn from code/inspection, not from an executed end-to-end run.
> **[UNVERIFIED]** = could not be established; method to check it later is given.

---

## A. Executive summary

LocalAgentBench has genuinely completed its environment, build, model, sandbox, and dataset stages. As of this audit:

- **Nothing is running.** No build, no inference, no llama.cpp process exists (verified via `ps`/`pgrep`). The old "71% build progress" lead is fully outdated: the build **completed on 2026-10-10 at 16:01 UTC** (100%, 115 build targets, 21 m 19 s wall), and all three key binaries execute today.
- **Inference is real and measured.** `llama-bench` ran two complete thread sweeps (t=4, t=8; prompt-processing at 512/2048/4096 tokens + 128-token generation, 3 repetitions each, exit 0) with peak-RSS capture and a 30-minute 1 Hz memory sampler showing **zero swap usage**. Two single-run generations through `llama-completion` (one of them grammar-constrained) produced output with full timing lines.
- **The sandbox is validated (13/13 probes as reported), and the dataset oracle is validated (164/164 checks) — both re-confirmed at the artifact level; the evaluator path was re-executed successfully today.**
- **The experimental harness is written but has never been executed end-to-end.** Zero pilot tasks have run: `results/pilot/` contains only the frozen `task_selection.json`.
- **A critical bug was found in the harness during this audit:** the output extractor matches the *echoed prompt* inside llama.cpp's conversation transcript before the model's actual answer. Demonstrated against a real captured artifact, it extracts the literal placeholder `<the complete corrected function body>` (or `...`) instead of the model's fix. If the pilot were run as written, **all three configurations would fail every task for a non-model reason**, producing a false floor effect.
- Two required reports are **missing**: `reports/inference_baseline.md` (Stage 4 — measurements exist but the report was never written) and `reports/pilot_results.md` (no pilot has run).

**Project stage: late pilot-readiness.** Environment ✔, build ✔, model ✔, inference measurements ✔ (report missing), sandbox ✔, dataset ✔, harness code written ✔ but **untested end-to-end and currently incorrect**. The single most important blocker is the extraction/output-contract bug (§I-1). The project is **not ready** to start the 10-task pilot until items I-1 and I-3 are fixed and one canary task has run successfully.

---

## B. Current status dashboard

| Stage | Expected deliverable | Actual status | Verification evidence | Blockers |
|---|---|---|---|---|
| Environment setup (Stage 0/1) | Toolchain installed, venv working, audit report | **COMPLETE.** Report exists; its "Gate 1 NOT PASSED" conclusion is outdated | `reports/environment_audit.md`; dpkg today: `build-essential 12.12`, `cmake 4.2.3`, `make 4.4.1`, `pkg-config 2.5.1`, `python3.14-venv` all "install ok"; `.venv/bin/python` 3.14.4 + pyarrow 26.0.0 *(auditor-run)* | Report text not updated post-install (cosmetic) |
| llama.cpp build (Stage 2) | CPU-only build, binaries run | **COMPLETE / SUCCESS** (no build running; "71%" claim obsolete) | Commit `aa94f2086147cd4bfbcff818ce998dffce5fcb39`; build log ends `[100%] Built target test-chat` + `real 21m19.508s`; `llama-cli`, `llama-server`, `llama-bench --version` → `0.6.0-dev (build 1, commit aa94f20)` *(auditor-run)* | Report `llama_cpp_build.md` exists only in the Windows copy; raw logs exist only in the WSL copy (split-brain, §I-6) |
| Model (Stage 3) | Downloaded, hash-verified, loadable | **COMPLETE / VERIFIED** | Size `1,117,320,768` B = published; SHA-256 recomputed today = `cc324af0…b046` = HF LFS oid *(auditor-run)*; model loaded and generated in `comp1`, `grammar1`, and both bench sweeps | None |
| Inference / Stage 4 measurements | Smoke test, pp/tg speed, peak RSS, memory pressure | **MEASUREMENTS COMPLETE, REPORT MISSING** | `bench_t4.json`/`bench_t8.json` (rc=0, 3 reps each), `bench_t4.time`/`bench_t8.time` (GNU time, Exit status 0), `mem_sampler.log` (1780 samples, max swap 0), `comp1.*`, `grammar1.*` with `common_perf_print` lines | `reports/inference_baseline.md` does not exist though two scripts reference it; `run_inference_smoke.sh` never executed; `stage4_bench_console.log` truncated before end markers; `smoke_test.sh` failed silently (0-byte outputs) |
| Sandbox (Stage 5) | Bubblewrap policy + probe suite | **COMPLETE (13/13 as reported), with documented limitations** | `reports/sandbox_validation.md`; probe artifacts intact on disk (`x.txt`=`sandbox-data`, oracle `truth.txt` unchanged, etc.); 2 sandbox executions re-run today via `test_eval.py` *(auditor-run)* | Raw probe console output not preserved in any file; suite itself not re-run today |
| Dataset (Stage 6) | 164 tasks, oracle checks executed | **COMPLETE / VERIFIED** | `results/dataset_validation.json`: 164 records, summary `{total:164, buggy_fails:164, canonical_passes:164, both_ok:164}`; parquet 191,279 B present; Python/0 re-checked today: canonical rc=0, buggy rc=1 *(auditor-run)* | Validation ran host-side (documented, intentional); raw console of that run not preserved |
| Harness (Stage 7 code) | orchestrator, client, evaluator, grammar, retry policy | **WRITTEN, NEVER RUN END-TO-END; one critical bug found** | `scripts/pilot_runner.py` (236 lines), `scripts/evaluate_candidate.py`, `scripts/response.gbnf`; `--dry-run` passes *(auditor-run)*; evaluator verified end-to-end *(auditor-run)*; extraction bug demonstrated *(auditor-run)* | Extraction bug (§I-1); empty feedback note (§I-3); no end-to-end generation run |
| Pilot (10 tasks × A/B/C) | Traces + results for 30 task-config runs | **NOT STARTED (0/30)** | `results/pilot/` contains only `task_selection.json`; no `summary.json`, no task dirs | Blocked by harness bug; Gate 2 report missing |
| Statistical analysis & final reporting | `pilot_results.md`, full-benchmark analysis | **NOT STARTED** | No analysis scripts, no `pilot_results.md` anywhere | Depends on pilot |

---

## C. Environment and dependency inventory

All values re-verified today unless marked otherwise.

| Item | Value | Evidence |
|---|---|---|
| Host OS | Windows 11/10 build `10.0.26200.9550` **[REPORTED — brief, not re-verified]** | brief |
| WSL | `WSL version: 2.6.3.0`, kernel `6.6.87.2` | `wsl --version` *(auditor-run)* |
| Distro | Ubuntu 26.04.1 LTS **[REPORTED — Stage 0]**; kernel matches Stage 0 | `reports/environment_audit.md` |
| WSL state | Freshly restarted today 18:39 UTC; project files date 2026-10-10 (~4.5 days old); no processes running | `ps aux`, file mtimes |
| CPU | 12th Gen Intel Core i5-1235U; AVX/AVX2/AVX-VNNI, no AVX-512 | Stage 0 report + `cpu_info` field in `bench_t*.json` |
| RAM (WSL) | total 3.7 GiB, swap 1.0 GiB, today idle: 458 MiB used / 3.2 GiB available, 0 B swap used | `free -h` *(auditor-run)* |
| `.wslconfig` | Does not exist → default WSL2 allocation (≈50% of 7.68 GB host RAM) | re-checked today *(auditor-run)* |
| Disk | WSL root `/`: 951 G free. **Windows `C:\`: 49 G free (90% used)** — was 67 G at Stage 0 | `df -h / /mnt/c` *(auditor-run)* |
| Windows Python | 3.13.3 | `python --version` *(auditor-run)* |
| Windows Git | 2.50.0.windows.1 | `git --version` *(auditor-run)* |
| Ubuntu Python | 3.14.4 (`.venv/bin/python`, pip 25.1.1) | *(auditor-run)* |
| Ubuntu Git | 2.53.0 | *(auditor-run)* |
| Toolchain | gcc/g++ 15.2.0, cmake 4.2.3, make 4.4.1, pkg-config 2.5.1, bubblewrap 0.11.1 — all installed | dpkg-query *(auditor-run)* |
| Python dependencies | **Only `pyarrow 26.0.0`** (installed in `.venv`). **No dependency manifest exists anywhere** (no `requirements.txt`, `pyproject.toml`, or lockfile) | `find` over both copies *(auditor-run)*, `pip list` |
| Project root (canonical) | `/home/aaksh/projects/LocalAgentBench` (WSL ext4, git repo) | git log/status |
| Project root (host mirror) | `C:\Users\kirti\coding\AGP` (NOT a git repo) | `git status` fails *(auditor-run)* |

**Two-copy split (important):** the two project copies are *mostly* mirrored but diverge:

- Identical (SHA-256 matched): all 5 shared reports; all 10 shared scripts; `README.md`; `.gitignore`.
- Host-only: `wsl_audit.sh`, `wsl_audit2.sh`, `wsl_audit3.sh`, `wsl_verify1.sh`, **`reports/llama_cpp_build.md`**.
- WSL-only: **`reports/llama_cpp_build.log`**, **`reports/llama_cpp_cmake_configure.log`**, **`reports/stage4_bench_console.log`**, plus `models/`, `third_party/`, `.venv/`, `results/`, `pilot_workdir/`, `sandbox_probe*/`, `pilot_workdir`.

Consequence: neither copy alone contains the full evidence chain (report without logs, logs without report). All scripts hard-code `ROOT = /home/aaksh/projects/LocalAgentBench`, so the host copies of the scripts are inert text there.

**Git (WSL repo):** `git log` → 2 commits (`f23de3b` skeleton; `d849f9d` "Stages 0-6…"), `git status --short` → **clean**. `.gitignore` correctly excludes `models/`, `*.gguf`, `third_party/`, `build/`, `results/**` (except `.gitkeep`), `.venv/`, `*.log`. → Model and raw results are never committed (good), but that also means **raw results exist only as local files with no versioned backup** (see §I-6).

---

## D. llama.cpp build and model status

### Build

| Field | Value | Status |
|---|---|---|
| Repository | `https://github.com/ggml-org/llama.cpp`, `--depth 1` clone | [REPORTED] |
| Commit SHA | `aa94f2086147cd4bfbcff818ce998dffce5fcb39` (2026-10-10, "args: add LLAMA_ARG_SLOT_SAVE_PATH…") | **[VERIFIED]** `git rev-parse HEAD` *(auditor-run)* |
| Working tree | clean (no modified/added files) | **[VERIFIED]** *(auditor-run)* |
| Configure | `cmake -B build -DCMAKE_BUILD_TYPE=Release` → rc=0; CPU backend only; `-march=native`; OpenMP 4.5; no CUDA/Vulkan/SYCL | [REPORTED] + raw `llama_cpp_cmake_configure.log` exists (WSL) |
| Build | `cmake --build build --config Release -j 2` → rc=0, 21 m 19.5 s; log ends `[100%] Built target test-chat` with timing footer; 115 "Built target" lines | **[VERIFIED]** `reports/llama_cpp_build.log` (WSL) *(auditor-run)* |
| "71% progress" claim | **Outdated.** No partial state exists; build finished 2026-10-10 16:01 UTC | **[VERIFIED]** |
| Build process running now? | **No** — no `cmake`, `make`, `cc1plus` process | **[VERIFIED]** `pgrep` *(auditor-run)* |
| GPU offload | Disabled: bench JSON shows `backends: "CPU"`, `gpu_info: ""`, `n_gpu_layers: 0`; pilot code passes `-ngl 0` | **[VERIFIED]** |
| Binaries present | `llama-cli` (1,324,640 B), `llama-server` (17,872 B stub + `libllama-server-impl.so` 7,331,312 B), `llama-bench` (17,872 B stub + impl), `llama-completion`, `llama-quantize`, tests, etc. | **[VERIFIED]** `ls build/bin` *(auditor-run)* |
| Binaries execute | All three `--version` → `version: 0.6.0-dev (build 1, commit aa94f20) / built with GNU 15.2.0 for Linux x86_64` | **[VERIFIED]** *(auditor-run)* |
| `llama-server` used for inference? | **No evidence it was ever used** (harness uses `llama-completion`; no server logs) — it is built and version-verified only | [INFERRED] |

**Build verdict: complete, correct, CPU-only, reproducible from the recorded commands.**

### Model

| Field | Value | Status |
|---|---|---|
| File | `models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf` | [VERIFIED] |
| Size | 1,117,320,768 bytes = published `lfs.size` exactly | [VERIFIED] *(auditor-run)* |
| Source | `Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF` @ revision `f86cb2c1fa58255f8052cc32aeede1b7482d4361`, Apache-2.0 | [REPORTED — consistent with manifest] |
| Expected SHA-256 | `cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046` (HF LFS oid) | [REPORTED] |
| Actual SHA-256 (recomputed today) | `cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046` — **MATCH** | **[VERIFIED]** `sha256sum` *(auditor-run)* |
| Quantization | Q4_K_M (`qwen2 1.5B Q4_K - Medium` in bench JSON) | [VERIFIED] |
| Model actually loaded + inferred? | **Yes** — bench sweeps loaded it (11 runs), `comp1` generated 63 tokens, `grammar1` generated 21 tokens, all with perf lines | [VERIFIED] |

Three distinct claims are often conflated; here all three hold: **downloaded** (size match), **hash-verified** (recomputed today), **completed inference** (generation outputs with timings).

### Inference evidence (Stage 4)

**What has actually been measured** (`llama-bench`, 3 reps each, `-ngl 0`, rc=0 for both sweeps; `results/inference_smoke/bench_t{4,8}.json` + `.time`):

| Threads | Test | avg tokens/s (stddev) |
|---|---|---|
| 4 | pp 512 | 27.98 (6.59) |
| 4 | tg 128 (fresh ctx) | 9.21 (1.29) |
| 4 | pp 2048 + tg 128 | 29.68 (2.98) |
| 4 | pp 4096 + tg 128 | 30.83 (3.23) |
| 8 | pp 512 | 54.28 (3.91) |
| 8 | tg 128 (fresh ctx) | 16.10 (0.69) |
| 8 | pp 2048 + tg 128 | 36.91 (5.49) |
| 8 | pp 4096 + tg 128 | 32.55 (5.89) |

- **Context lengths exercised:** prompt processing at 512, 2048, 4096 tokens (pilot ctx = 4096 is covered); single runs used ctx 2048.
- **Peak process memory:** llama-bench max RSS = 1,955,940 kB (t4) / 1,957,584 kB (t8) ≈ **1.87 GiB**; `Swaps: 0`.
- **WSL-wide memory pressure:** `mem_sampler.log`, 1 Hz, 1780 samples ≈ 30 min: max used 1,392 MiB, min available 2,359 MiB, **max swap used = 0 MiB** *(auditor-run awk)*.
- **Single-run generation speeds (llama-completion, t4, ctx 2048):**
  - `comp1` (no grammar): prompt eval 56.52 t/s (19 tokens), generation 15.90 t/s (63 tokens), model load 2,119 ms.
  - `grammar1` (GBNF on): prompt eval 7.64 t/s (39 tokens), generation 2.70 t/s (21 tokens), load 10,434 ms. **Anomalous ~7× slowdown vs `comp1` — unexplained [UNVERIFIED]; likely background load at 16:25 UTC, but nothing was captured to confirm.**
- **OOM / timeouts / swap events:** none observed in any captured artifact. No OOM anywhere.
- **Repetition:** bench = 3 reps each (with stddev); single runs = 1 each (not repeated).
- **Reproducibility:** bench commands recorded verbatim in `bench_t*.time` files; single-run commands recorded inside the debug scripts.

**What was attempted and failed (honestly recorded):**
- `smoke_test.sh` → `smoke1.out/err` **0 bytes** (llama-cli with closed stdin produced nothing; return code was printed to a console and not preserved).
- `debug4/5` llama-cli with `/dev/null` or piped stdin → `cli_null.*`, `cli_pipe.*`, `cli1.*` all **0 bytes**.
- Resolution path taken by the project: switch to **`llama-completion`**, which produced working output (`comp1`, `grammar1`). This history is only partially documented (console outputs of most debug scripts were not saved to files).

**What was never measured:**
- Peak RSS of a *single generation* via `/usr/bin/time -v` — `run_inference_smoke.sh` (the script designed for it) **was never executed** (no `*.meta`/`*.time` files for any of its labels) *(auditor-run: file search)*.
- Generation speed at pilot settings (ctx 4096, n_predict 512) — only extrapolation from bench is available. **No estimate is presented here as a measurement.**
- **`reports/inference_baseline.md` does not exist**, despite being referenced by `pilot_runner.py` and `run_inference_smoke.sh`.
- `stage4_bench_console.log` ends after the t8 JSON + final `free -h`; the script's own end markers (`benchmark end`, `sampler peak`) are **absent** → either console capture stopped early or the script was interrupted after its last measurement. Measurements themselves are intact (rc=0 embedded in time files); script completion is [UNVERIFIED].

---

## E. Sandbox validation

**Status: as reported — 13/13 probes passed on 2026-10-10; probe artifacts still on disk; sandbox shell path re-executed twice today.** Raw console output of the probe run was **not preserved in any file** — the report's table plus the surviving artifacts are the evidence.

Wrapper: `scripts/sandbox.sh <host_writable_dir> <cmd…>` → `exec bwrap` with: `--unshare-all` (user/mount/pid/ipc/uts/**net**), empty tmpfs root, ro-binds of `/usr /bin /sbin /lib /lib64`, fresh `/proc`, minimal `/dev`, selected `/etc` files ro, **one** rw host bind `→ /tmp/work` (=`$HOME`), `--new-session`, `--die-with-parent`, `--hostname sandbox`, `--chdir /tmp/work`. **[VERIFIED by reading the script]**

Probe suite `scripts/sandbox_test.sh` — the 13 counted probes:

| # | Probe | Purpose | Result (Oct 10) | Auditor's re-verification today |
|---|---|---|---|---|
| 1 | T1 python runs | permitted command executes in sandbox | PASS | Sandbox invoked 2× via `test_eval.py`, both worked *(auditor-run)* |
| 2 | T2a `/home` invisible | host home not mounted | PASS | — |
| 3 | T2b host secret unreadable | non-mounted host file unreachable | PASS | — |
| 4 | T3a write `/usr` rejected | read-only bind enforced | PASS | — |
| 5 | T3b write oracle path rejected | oracle dir not mounted at all (probe must execute first) | PASS | — |
| 6 | T4 writable tmp works | designated workspace writable | PASS | — |
| 7 | T5a outbound TCP blocked | net namespace isolation | PASS | — |
| 8 | T5b DNS/HTTPS blocked | net namespace isolation | PASS | — |
| 9 | T6 parent timeout kills | `timeout 3` → rc=124, no leftover process | PASS | — |
| 10 | T7a workspace write persists | rw bind works to designated dir | PASS | Artifact `x.txt`=`sandbox-data`, `result.txt`=`model-output` still present **[VERIFIED]** |
| 11 | T7b no files leaked outside | `find` for leaked names | PASS | — |
| 12 | T8 oracle integrity | `truth.txt` unchanged on host | PASS | `truth.txt` still = `ORACLE_DATA_DO_NOT_MODIFY` **[VERIFIED]** |
| 13 | T9 inspect effective view | mounts/pids/uid/netdevs/hostname dump | done (observational) | — |
| — | T0 bwrap version | informational (not counted) | 0.11.1 | 0.11.1 *(auditor-run)* |

**Not tested / limitations (from the report, confirmed by reading the scripts):**
1. It is a **policy-in-wrapper, not a security product** (bubblewrap's own README position) — protection equals exactly what `sandbox.sh` declares.
2. **No seccomp filtering**; `--new-session` only mitigates TIOCSTI (CVE-2017-5226).
3. **No resource limits** (no cgroup/ulimit): a fork bomb or memory hog inside can pressure the 3.7 GiB WSL RAM; only wall-clock timeouts are enforced (`subprocess` timeout + `--die-with-parent`).
4. **WSL driver mounts visible** (`/usr/lib/wsl/...`) under the ro `/usr` bind — read-only, but a strict policy would mask them (hardening TODO).
5. Same uid (1000) inside and outside — any accidentally-mounted rw host path would be fully writable.
6. Probes are **behavioral, not adversarial**: they show that specific commands behave as designed; they are **not proof of filesystem security or resistance to a malicious program** (no escape attempts, no fd/proc trickery, no symlink races tested).
7. Untrusted code has **not yet been run** in the sandbox (correct per rules so far — only harmless probes and, today, dataset-published reference solutions).

---

## F. Dataset verification

| Field | Value | Status |
|---|---|---|
| Source | `bigcode/humanevalpack`, config `python`, split `test`, revision pinned `9a41762f…cf378`, MIT | [REPORTED] |
| Local file | `third_party/dataset/humanevalpack_python_test.parquet`, 191,279 bytes = published download size | **[VERIFIED]** *(auditor-run)* |
| Task count | **164**, IDs `Python/0`…`Python/163`, all unique | **[VERIFIED]** — `results/dataset_validation.json` has exactly 164 records with 164 unique IDs *(auditor-run)* |
| Schema | `task_id, prompt, declaration, canonical_solution, buggy_solution, bug_type, failure_symptoms, entry_point, import, test_setup, test, example_test, signature, docstring, instruction` | [REPORTED; consistent with all scripts' field usage] |
| Oracle representation | `test` field = `check(<entry_point>)` with bare `assert`s; run via `exec(test, ns)` after defining the candidate | **[VERIFIED]** in both harnesses' code |
| Model-visible vs held-out | Model sees `instruction`, `prompt`, `declaration`, `buggy_solution`; held out: `canonical_solution`, `test`, `bug_type`, `failure_symptoms` | **[VERIFIED]** in `pilot_runner.PROMPT_TEMPLATE` |
| Original buggy solutions tested | **164/164 fail their own test** | **[VERIFIED]** summary in JSON: `buggy_fails: 164`; sample record `Python/0` buggy rc=1 `ASSERT_FAILED` |
| Reference solutions pass | **164/164 pass** | **[VERIFIED]** `canonical_passes: 164`; `Python/0` canonical rc=0 `PASSED`; Python/0 re-executed today *(auditor-run)* |
| Did all 164 oracle checks actually run? | **Yes** — the JSON contains per-task `rc`, `output`, `wall_s` for both variants (e.g. timeouts recorded as rc=-9) | **[VERIFIED]** structurally + spot re-execution |
| Where stored | `results/dataset_validation.json` (41,860 B) — **git-ignored** (raw results excluded from VCS) | [VERIFIED] |
| Can candidate code modify tasks/tests? | **No**: parquet lives at `third_party/dataset/` which is **not mounted** in the sandbox; oracle test string is delivered via **stdin** at evaluation time; the candidate only ever runs inside bwrap | **[VERIFIED]** by code reading + T3b probe |

**Distinctions kept honest:**
- Dataset *downloaded* ✔ (size matches).
- Oracle-validation script *written* ✔ (`validate_dataset.py`).
- Oracle checks *executed* ✔ (164 detailed records exist; auditor re-ran 1 of 164 today with identical outcome).
- **Not done:** oracle validation inside the sandbox (deliberate — trusted dataset code, documented), and any execution of *model-generated* code (not yet possible — no generations from the harness exist).

**Limitations:** tests are public (no hidden holdout); `import`/`test_setup` empty for all Python tasks (pure stdlib — good for sandboxing); HumanEval is heavily public → memorization risk for a model trained on it (research-design caveat, §I/§G).

---

## G. Implementation audit

### Files and their true status

| File | Responsibility | Internal workings | Depends on | Status |
|---|---|---|---|---|
| `scripts/pilot_runner.py` (236 lines) | A/B/C orchestrator: task selection → prompt → generate → extract → sandbox-eval → retry → serialize | Loads 10 frozen tasks from parquet; builds one shared `PROMPT_TEMPLATE`; `generate()` spawns `llama-completion` (600 s timeout, stdin=`DEVNULL`, seed 42, temp 0.0, ctx 4096, t 4, `-ngl 0`, optional `--grammar-file`); `extract_body()` regex-finds `{"fix":`, JSON-decodes, falls back to fence-strip/raw for config A; `evaluate()` writes `pilot_workdir/candidate.py` then calls `evaluate_candidate.py`; config C appends failure note + last output to the prompt, max 3 attempts; writes `result.json` per task-config + `summary.json` | pyarrow, `llama-completion`, `response.gbnf`, `sandbox.sh`, `evaluate_candidate.py`, `.venv` | **Written. Dry-run passes. CRITICAL extraction bug [VERIFIED offline]. Never executed end-to-end.** |
| `scripts/evaluate_candidate.py` | Host-side oracle runner inside the sandbox | Loads parquet row; `code = declaration + body`; builds JSON payload `{code, entry, test}`; runs `sandbox.sh <workdir> /usr/bin/python3 -I -c HARNESS` with payload on stdin; HARNESS execs code (rc 3 on exception incl. SyntaxError), checks entry (rc 4), execs test (rc 1 AssertionError / rc 2 other / rc 0 pass); maps timeouts to rc 5 | `sandbox.sh`, pyarrow | **Working — verified end-to-end today** (canonical rc=0, buggy rc=1). **Defect: never relays harness output to the caller (§I-3)** |
| `scripts/sandbox.sh` | Bubblewrap policy wrapper (see §E) | `exec bwrap …` with fixed argument list; first arg = only rw host dir | bwrap 0.11.1 | **Working, validated** |
| `scripts/sandbox_test.sh` | 13-probe validation suite | Creates disposable probe dirs, asserts 13 conditions, prints PASS/FAIL counts | `sandbox.sh` | **Ran Oct 10 (13/13); artifacts intact; raw output not preserved** |
| `scripts/response.gbnf` | Response contract for B/C | `root ::= ws? "{" ws fix-kv …}` — exactly one `"fix"` key, JSON-escaped string; `chars ::= char*` (empty value allowed) | llama.cpp grammar engine | **Used successfully once** (`grammar1.out` produced valid `{"fix": …}`) |
| `scripts/validate_dataset.py` | Stage 6 oracle validation | Fresh `python3 -I` subprocess per solution, 10 s timeout, exit-code mapping; writes JSON summary + per-task records | pyarrow | **Executed for all 164 tasks; results verified** |
| `scripts/inspect_dataset.py` | Read-only dataset stats | Prints rows/cols/distributions | pyarrow | Written; console output not preserved; rerunnable |
| `scripts/stage4_bench.sh` | Stage 4 benchmark harness | Starts 1 Hz `free -b` sampler; `llama-bench -t {4,8} -r 3 -pg 2048,128 -pg 4096,128 -ngl 0 -o json` under `/usr/bin/time -v`; prints rc/peak lines | `llama-bench` | **Executed (Oct 10); measurements valid; final summary lines missing from captured console (§D)** |
| `scripts/run_inference_smoke.sh` | Per-run smoke measurement (time -v + mem before/after + meta) | Wraps `llama-cli` with time/meta capture | `llama-cli` | **NEVER EXECUTED** (no `*.meta`/`*.time` artifacts) — and it targets `llama-cli`, the binary that failed silently |
| `scripts/smoke_test.sh` | One short `llama-cli` generation | `-n 64 -c 2048 …` into `smoke1.*` | `llama-cli` | **Ran and FAILED silently** (0-byte outputs) — honest evidence of the CLI problem |
| `scripts/debug2-7.sh`, `debug_cli.sh`, `debug_tty.sh`, `bench_help.sh` | Troubleshooting probes for the CLI/completion/grammar behavior | Various | llama.cpp binaries | Mostly executed; only file-producing parts survive (`comp1.*`, `grammar1.*`, `cli_pty.log`) |
| `scripts/test_eval.py` | Evaluator smoke test (canonical vs buggy, Python/0) | Calls `evaluate_candidate.py` twice, prints rc | evaluator, venv | **Re-run by auditor today: canonical rc=0, buggy rc=1** |
| `wsl_audit*.sh`, `wsl_verify1.sh` (host only) | Stage 0/1 environment probes | — | — | Executed Oct 10 (outputs live in `environment_audit.md`) |
| `orchestrator.py`, `inference_client.py`, `sandbox_executor.py` | — | — | — | **Do not exist.** Their responsibilities live inside `pilot_runner.py` + `evaluate_candidate.py` (equivalent functionality, different names) |

### Are configurations A, B, C actually implemented?

**Yes, in code** (`pilot_runner.run_config`), and they **do isolate the intended variables**:

- **A vs B:** identical prompt template, seed, ctx, threads, n_predict, tasks, evaluator — the **only** difference is `grammar = config in ("B","C")` → `--grammar-file response.gbnf`. ✔ (Protocol §3's "byte-identical prompt A/B" holds.)
- **C vs B:** same grammar; adds sandbox test execution after each attempt, appends failure feedback, loops to `MAX_ATTEMPTS = 3` (initial + 2 repairs), stops early on pass. Attempt budget matches the protocol (A:1, B:1, C:≤3). ✔
- **Same tasks and oracle for all three:** all configs draw from the frozen 10-task selection and the same `evaluate_candidate.py`. ✔
- **Metrics:** `initial_success` (attempt 1) and `final_success` (within budget) are recorded separately. **`pass@1` appears nowhere in the codebase** (grep over all project files excluding `third_party` found zero matches) → **the specific risk of mislabelling C's retried metric as pass@1 is NOT present today.** The protocol also separates `initial_success` (A vs B headline) from `final_success` (C headline). Keep this discipline in `pilot_results.md` when it is eventually written. **[VERIFIED]**

### Design concerns found in the harness (no changes made)

1. **[CRITICAL] Extraction matches the prompt echo first.** llama-completion defaults to `--display-prompt` and runs conversation mode; every observed stdout (`comp1.out`, `grammar1.out`) begins with `user\n<prompt>\nassistant\n…`. The pilot prompt itself contains the literal `{"fix": "<the complete corrected function body>"}`. `extract_body()` takes the **first** `{"fix":` match → JSON-decodes the *echo* → returns the placeholder as the "body". Demonstrated in §I-1.
2. **[HIGH] Feedback content is lost** (§I-3): `evaluate_candidate.py` computes the harness output but never emits it; `pilot_runner.evaluate()` therefore gets `note = ""` for every non-timeout outcome. Verified today: `test_eval.py` printed `out=''` for both pass and fail.
3. **[HIGH] Candidate timeout is misclassified** (§I-4): a hanging candidate triggers `evaluate_candidate`'s outer `subprocess` timeout → rc 5 → category **`harness_error`**, not `timeout`. Dataset validation uses a different convention (rc=-9 for timeouts), so failure categories will be inconsistent between Stage 6 and the pilot.
4. **[MEDIUM] Unbounded prompt growth in C:** each retry appends up to 1000 chars of raw generation + feedback to the *same* prompt; no total-length guard against the 4096 ctx.
5. **[MEDIUM] Post-processing is not literally "identical" for A vs B:** B/C *require* JSON (grammar path), A may fall back to raw-body extraction. Same code path, different effective contract — a deviation from the protocol's wording (see §I-7).
6. `--log-file` per attempt is passed a path inside the results dir → logs will be written alongside traces (fine; git-ignored).

### Trace / result serialization

Per task-config: directory `results/pilot/<Task>_<Config>/` with `gen_a{n}.log`, `body_a{n}.py` (extracted body), `result.json` (attempt log incl. raw `gen_stdout`, stderr tail, extract note, eval rc/category/note, settings); aggregate `results/pilot/summary.json`. Malformed outputs and failures are recorded, not silently retried (matches protocol §5). **None of these files exist yet except the frozen selection.** **[VERIFIED]**

---

## H. Experimental readiness

**Can the pilot safely and correctly begin right now? No.**

What *is* ready:
- Sandbox: yes (validated, oracle unreachable, network off, timeout works).
- Dataset/oracle: yes (164/164, evaluator path re-verified today).
- Model/build/measurements: yes (bench covers the pilot's 4096 context).
- Task selection: frozen before any generation (`task_selection.json`, 10 tasks, deterministic method) — good protocol hygiene.
- Execution safety rules (sequential, per-attempt logging, no task removal) are encoded in the runner.

What blocks a *correct* start:
1. **The extraction bug** would corrupt every attempt of every configuration (§I-1). Running now would waste the pilot (protocol forbids re-runs to flip failures; a buggy harness would force a disclosed full restart).
2. **Config C's feedback would be empty** apart from a bare category label (§I-3), violating protocol §4's "append concise test output (stdout/stderr, truncated 500 chars)" — i.e., the recovery variable would not be what the protocol specifies.
3. **Gate 2 is formally unmet**: the protocol requires "inference smoke + benchmarks must pass first" and `pilot_runner.py` itself points to `reports/inference_baseline.md`, which does not exist. The measurements exist; the gate artifact does not.
4. **The end-to-end generation path is untested**: no one has run `llama-completion` exactly as `generate()` does (stdin=`DEVNULL`, these flags) and inspected stdout. The nearest evidence (`comp1`, EOF-terminated interactive session) strongly suggests a transcript-format stdout — which is precisely what triggers the bug — but the exact DEVNULL case is [UNVERIFIED] until one canary runs.

What is *safe*: nothing about the sandbox or data handling is unsafe. The risk is to **validity**, not to the machine.

---

## I. Problems and risks (ranked)

### Critical blockers

**1. Output-extraction bug: prompt echo is parsed as the model's answer. [CRITICAL — blocks pilot]**
- *Evidence:* `extract_body()` uses `re.search(r"\{\s*\"fix\"\s*:\s*", text)` — first match wins. Every observed `llama-completion` stdout starts with the echoed user prompt (`comp1.out`, `grammar1.out`), and the pilot prompt template itself contains `{"fix": "<the complete corrected function body>"}`.
- *Auditor's offline test (real code, real artifacts, no model):*
  - On the **real** `grammar1.out`: returns body `'...'` (the placeholder from the echo), note `ok-json` — the actual answer `{"fix": "The function subtracts…"}` was ignored.
  - On a **synthetic transcript built with the actual `PROMPT_TEMPLATE`**: returns `<the complete corrected function body>` instead of `    return a + b` → `exec` of `declaration + placeholder` → SyntaxError → rc 3.
  - On completion-only stdout (echo absent): returns the correct body.
- *Impact:* if the pilot ran as written, A, B and C would all score ~0% for a mechanical reason — a false floor effect that would look like "the model can't do the task" and could wrongly trigger the protocol's "floor effect" verdict.
- *Trigger condition:* stdout contains the echo (default `--display-prompt`, conversation mode). The one path not yet executed is the exact `stdin=/dev/null` invocation (§J-1 canary).

**2. The harness has never been executed end-to-end. [CRITICAL — process risk]**
- *Evidence:* `results/pilot/` = only `task_selection.json`; no `summary.json`; no body/log/result files; no `pilot_results.md`.
- *Impact:* every claim of "pilot readiness" so far is based on component tests, not integration. Bugs like #1 are exactly what integration catches.

### High-priority issues

**3. Config C's error feedback is always empty. [HIGH]**
- *Evidence (executed):* `test_eval.py` → `canonical: rc=0 out=''`, `buggy: rc=1 out=''`. Cause: `evaluate_candidate.py` line `out = (p.stdout + p.stderr).strip()[:500]` is computed and discarded (only the TIMEOUT path prints). `pilot_runner.evaluate()` therefore records `note=""` for rc 0–4.
- *Impact:* C's repair prompt becomes "Test result: assertion_fail\n" with no detail — a protocol deviation (§4 promises truncated stdout/stderr) and a weaker recovery signal than specified. HumanEval asserts are bare, so even after a fix the relayed text would be thin (`ASSERT_FAILED`) — worth acknowledging as a *design* limit of the recovery variable itself.

**4. Candidate timeouts are recorded as `harness_error`. [HIGH]**
- *Evidence:* code path analysis — outer `subprocess.run(timeout=…)` in `evaluate_candidate.py` → rc 5 → pilot category map `{5: "harness_error"}`. Dataset validation used `-9` for the same phenomenon.
- *Impact:* failure-category statistics (a planned measurement) will mislabel hangs; C's feedback for a hang will say "harness_error".

**5. Required Stage 4 report missing (`reports/inference_baseline.md`). [HIGH]**
- Referenced by `pilot_runner.py` docstring and `run_inference_smoke.sh`; gate artifact for Gate 2; measurements exist to write it today.
- *Impact:* protocol gate unmet; another auditor/reader cannot find the documented caveats (what each measurement includes/misses).

**6. Evidence is split across two diverging copies and raw results are unversioned. [HIGH]**
- Build report on host / build logs in WSL; host scripts inert (hard-coded WSL paths); `results/**` and `*.log` git-ignored → the WSL git repo (clean, 2 commits) cannot reconstruct any experiment.
- *Impact:* reproducibility and disaster-recovery risk; a fresh checkout reproduces code only, not evidence.

### Medium-priority issues

**7. Protocol §3 vs implementation contract mismatch.** Protocol §3 describes a raw-body contract ("Return ONLY the complete corrected function body… harness strips Markdown fences"), while the implementation prompts **all** configs with the JSON `{"fix": …}` contract and B/C additionally enforce it. The A/B byte-identical-prompt invariant survives, but the *written* protocol and the *executed* prompt differ. The protocol allows appending deviations before results exist — that should be done (or the protocol §3 corrected) **before** the pilot, while selection is still pre-results.

**8. Thread choice undocumented and possibly suboptimal.** Pilot hard-codes `THREADS = 4` with comment "updated from Stage 4 measurements", but the measured tg-128 speed was 9.2 t/s (t4) vs 16.1 t/s (t8) — t8 is ~1.75× faster on generation with *lower* relative variance for tg. The protocol requires threads "recorded at run time"; no rationale is recorded. Not a correctness bug, but it inflates pilot wall-time and the deviation table should state the choice.

**9. Sandbox raw probe log not preserved; suite not re-run in this audit.** Only artifacts + report table survive. The suite is rerunnable (non-destructive to everything except its own probe dirs).

**10. `stage4_bench_console.log` truncated before end markers** — measurement files are valid, but script completion is unverified; the "sampler peak" summary line was never captured (recomputable from `mem_sampler.log`: max 1,392 MiB used / 0 swap).

**11. No dependency manifest** (pyarrow 26.0.0 exists only inside `.venv`); **all scripts hard-code** `/home/aaksh/projects/LocalAgentBench` — the project runs on exactly one machine; fresh-checkout setup steps are undocumented (README has no setup section).

**12. `run_inference_smoke.sh` is dead code** (never executed; targets the binary path that failed), and `smoke_test.sh` fails *silently* (0-byte outputs, rc not persisted) — a script whose failure mode is indistinguishable from success without extra checks.

**13. `environment_audit.md` "Gate 1 NOT PASSED" is outdated** (toolchain installed afterward) — an old summary a reader could mistake for current status.

### Optional improvements

- No unit tests for `extract_body`/prompt construction (a 10-line test would have caught #1).
- Grammar allows an empty `"fix": ""`.
- Exploratory runs used default seed 4294967295 (not 42) — irrelevant to pilot settings but worth noting when reading old logs.
- README "Stages 0–N" status line is vague; no setup/reproduction section.
- Bench stddevs are large (up to ~20%) — 3 reps are thin for the t4-vs-t8 decision.
- Research-design caveats: n=10 pilot (protocol correctly promises no significance claims); HumanEval publicity → memorization possible; config "A" is not a *pure* naive baseline (it is JSON-contract-prompted) — fine if disclosed; deterministic temp-0/seed-42 gives one draw per task, no sampling-variance estimate.

---

## J. Immediate next steps (priority order)

**1. Canary: capture the exact stdout `generate()` would produce.**
- *Objective:* settle whether `llama-completion` with `stdin=/dev/null` emits the prompt echo (bug triggers) or completion-only output (bug latent).
- *Change/command:* run one short generation exactly as `pilot_runner.generate()` does, e.g.
  `wsl -d Ubuntu -- bash -lc "cd ~/projects/LocalAgentBench && ./third_party/llama.cpp/build/bin/llama-completion -m models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf -p '<the Python/0 PROMPT_TEMPLATE text>' -n 64 -c 4096 -t 4 --temp 0.0 --seed 42 -ngl 0 </dev/null > /tmp/canary.out 2>/tmp/canary.err; echo rc=$?"`
- *Verification:* inspect `/tmp/canary.out`: does it start with `user\n…` containing `{"fix": "<the complete corrected function body>"}`?
- *Artifact:* `/tmp/canary.out` (+ decision recorded in a protocol deviation note).

**2. Fix output acquisition/extraction in `pilot_runner.py` (and add a regression test).**
- *Objective:* extraction must return the model's fix, never the echo.
- *Change:* cheapest robust options: add `--no-display-prompt` (and/or `-no-cnv`) to `generate()`'s command, or parse only text after the last `assistant` marker (or use the *last* `{"fix":` match); add an offline unit test feeding `comp1.out`/`grammar1.out`/canary.out.
- *Verification:* re-run the offline extraction check on the **real** canary stdout → body equals the model's answer; test passes for transcript and completion-only formats.
- *Artifact:* updated `scripts/pilot_runner.py` + test file; append the deviation/fix to `reports/pilot_protocol.md` §deviations.

**3. Fix feedback relay in `evaluate_candidate.py`.**
- *Objective:* config C receives actual test output (protocol §4: stdout/stderr ≤500 chars) and correct failure categories.
- *Change:* emit `out` from the HARNESS (JSON on stdout, or print + capture); map candidate timeouts to a distinct `timeout` category instead of `harness_error`.
- *Verification:* `.venv/bin/python scripts/test_eval.py` → buggy case shows `out='ASSERT_FAILED'` (non-empty); a deliberately hanging body yields category `timeout`.
- *Artifact:* updated evaluator + captured `test_eval.py` output.

**4. Write `reports/inference_baseline.md` from the existing artifacts (closes Gate 2).**
- *Objective:* document what was measured, how, and what was not (llama-cli smoke failure, `run_inference_smoke.sh` unused, no per-generation RSS, grammar1 anomaly, bench table + RSS + sampler stats from §D).
- *Verification:* every number in the report traceable to `bench_t*.json`, `bench_t*.time`, `mem_sampler.log`, `comp1/grammar1` perf lines.
- *Artifact:* `reports/inference_baseline.md` (copy to both project copies).

**5. Single-task 3-config canary, then the 10-task pilot.**
- *Objective:* prove the full loop (generate → extract → sandbox eval → retry) before committing the frozen pilot.
- *Change:* add a `--tasks Python/0` (or `--limit 1`) flag to `pilot_runner.py` (small addition), run `--configs ABC` on one task; inspect all three `result.json` files (correct bodies, non-empty C feedback, plausible categories).
- *Verification:* extraction notes are `ok-json`/`ok-raw-fallback` with *real* code bodies; C shows ≤3 attempts with feedback text; no placeholder strings anywhere.
- *Artifact:* `results/pilot/Python_0_{A,B,C}/` + a go/no-go note; then run the full frozen 10×3 pilot and write `reports/pilot_results.md`.

---

## K. Completion estimates (evidence-based, categorized — no invented percentages)

**Completed (verified by execution or artifacts):**
- Environment audit + toolchain install (dpkg-verified) · llama.cpp CPU build · model download + hash + inference capability · Stage 4 throughput/memory measurements (bench + sampler) · sandbox policy + 13-probe suite · dataset acquisition + 164/164 oracle validation · frozen pilot task selection · evaluator end-to-end path (re-verified today) · dry-run dataset loading.

**In progress / partially complete:**
- Stage 4 reporting (data exists, `inference_baseline.md` missing) · harness (code complete, integration untested, 1 critical + 2 high defects) · sandbox raw-evidence preservation (report only, console lost).

**Not started:**
- Pilot execution (0/30 task-config runs) · `pilot_results.md` · full 164-task benchmark · statistical analysis · final reporting.

**Blocked:**
- Pilot start (blocked by §I-1, §I-3, Gate-2 report).

*Counting method note:* the project's own stage list (Stages 0–7 + analysis) has **8 units**: 6 fully verified, 1 partially (Stage 4 reporting/harness integration), 1 not started (pilot) plus analysis not started. Stage-7 *code* is written but that is deliberately not counted as "complete" because completion here requires an executed end-to-end run.

---

## L. Reproduction guide (exact commands, real paths)

**Executed by the auditor during this audit (safe, read-only or non-destructive):**

```bash
# From PowerShell on the host:
wsl.exe -d Ubuntu -- bash -lc "cd ~/projects/LocalAgentBench && git log --oneline && git status --short"
wsl.exe -d Ubuntu -- bash -lc "cd ~/projects/LocalAgentBench && sha256sum models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
#   -> cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046
wsl.exe -d Ubuntu -- bash -lc "cd ~/projects/LocalAgentBench && ./third_party/llama.cpp/build/bin/llama-cli --version"
#   -> version: 0.6.0-dev (build 1, commit aa94f20)
wsl.exe -d Ubuntu -- bash -lc "cd ~/projects/LocalAgentBench && .venv/bin/python scripts/pilot_runner.py --dry-run"
#   -> would run: ['Python/0', …, 'Python/144'] configs: ABC
wsl.exe -d Ubuntu -- bash -lc "cd ~/projects/LocalAgentBench && .venv/bin/python scripts/test_eval.py"
#   -> canonical: rc=0 / buggy: rc=1   (exercises sandbox.sh + oracle-via-stdin)
# Offline extraction check (auditor-written, lives outside the project):
wsl.exe -d Ubuntu -- bash -lc "cd ~/projects/LocalAgentBench && .venv/bin/python /mnt/c/Users/kirti/AppData/Local/Temp/opencode/audit_extract.py"
#   -> Case 1 (real grammar1.out): body '...'  | Case 3 (synthetic): placeholder, MATCHES EXPECTED: False
```

**Available but NOT run by the auditor (they overwrite results or recreate probe dirs — run only with consent):**

```bash
wsl.exe -d Ubuntu -- bash -lc "cd ~/projects/LocalAgentBench && bash scripts/sandbox_test.sh"        # recreates sandbox_probe*; expect RESULT: PASS=13 FAIL=0
wsl.exe -d Ubuntu -- bash -lc "cd ~/projects/LocalAgentBench && .venv/bin/python scripts/validate_dataset.py"  # overwrites results/dataset_validation.json (~164 runs, minutes)
wsl.exe -d Ubuntu -- bash -lc "cd ~/projects/LocalAgentBench && bash scripts/stage4_bench.sh"        # overwrites bench results; ~30 min
```

**Key evidence files:**

```
WSL  ~/projects/LocalAgentBench/reports/llama_cpp_build.log          (100% + timing footer)
WSL  ~/projects/LocalAgentBench/reports/stage4_bench_console.log     (bench JSON, truncated end)
Host C:\Users\kirti\coding\AGP\reports\llama_cpp_build.md            (build report — host copy only)
WSL  ~/projects/LocalAgentBench/results/dataset_validation.json      (164 oracle records)
WSL  ~/projects/LocalAgentBench/results/inference_smoke/bench_t{4,8}.{json,time}, mem_sampler.log, comp1.*, grammar1.*
WSL  ~/projects/LocalAgentBench/results/pilot/task_selection.json    (frozen; nothing else in pilot/)
```

---

## M. Final verdict

**1. What genuinely works right now?**
The full foundation chain: environment and toolchain; a CPU-only llama.cpp build at pinned commit `aa94f20` whose binaries run today; a byte-verified model that has demonstrably completed inference; measured prompt-processing/generation throughput at the pilot's 4096 context with peak-RSS and zero-swap memory evidence; a Bubblewrap sandbox with 13/13 passing probes and an unreachable oracle; a 164-task dataset whose oracle discriminates buggy from canonical on all 164 tasks; and a working evaluator path (sandbox + stdin-delivered oracle) re-proven today.

**2. What has been verified but not yet integrated?**
- The evaluator works, but its output never reaches config C's feedback loop (empty notes).
- Extraction works on completion-only stdout but fails on the transcript-format stdout that every observed `llama-completion` run produces — and `pilot_runner` has never been run against real model output.
- Stage 4 measurements exist but are not integrated into the required `inference_baseline.md` (Gate 2 artifact).
- The 13-probe suite and 164 oracle checks are verified at report/artifact level but their raw console outputs were not preserved.

**3. The single biggest current blocker?**
**The output-extraction prompt-echo bug in `pilot_runner.py`, compounded by the fact that the pilot has never run end-to-end.** Everything else is fixable in minutes; this one silently invalidates the experiment's results if the pilot starts before it is caught.

**4. What should we do next?**
Run the one-command canary (§J-1) to capture real `stdin=/dev/null` stdout, fix extraction (§J-2) and the feedback relay (§J-3) with offline tests, write `inference_baseline.md` (§J-4), then a single-task 3-config canary before the frozen 10-task pilot (§J-5).

**5. Is the project ready for the 10-task pilot?**
**No — not yet.** It is *close*: safety and data validity are genuinely ready, but correctness of measurement is not. Realistic estimate: items §J-1…§J-5 are one focused working session (roughly hours, not days), after which the pilot itself should take well under two hours at measured throughput (t4, ≤50 generations of ≤512 tokens, sequential, plus sandbox evals) — order-of-magnitude only, based on measured token speeds, not a promised figure. Against the December 31, 2026 deadline, the schedule is comfortable; the risk is validity, not time.

---

*Rules honored: no code or configuration changes; no builds/inference/full-benchmark runs started; no files deleted; no packages installed; all failures (CLI silent failures, truncated logs, missing reports, split copies) recorded above; unverified facts labeled as such.*
