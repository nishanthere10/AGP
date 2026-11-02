# Pre-Kaggle Readiness Report — LocalAgentBench

**Date:** 2026-11-01
**Status:** **PASS** (local hardening complete; Kaggle execution NOT started)
**Canonical location:** `~/projects/LocalAgentBench` (WSL)

---

## 1. Verified starting state

| Item | Verified value |
|---|---|
| Git branch / HEAD | `master` @ `d849f9d` ("Stages 0-6: …"), parent `f23de3b` |
| Remote | none configured |
| Working tree | clean of *tracked* changes except: `reports/pilot_protocol.md`, `scripts/evaluate_candidate.py`, `scripts/pilot_runner.py` (pre-existing, uncommitted work left untouched) |
| Existing frozen results | `results/pilot/`, `pilot_v2/`, `pilot_v3/`, `pilot_v3_2/`, `pilot_v3_3/` — **untouched** |
| Evaluator | `scripts/evaluate_candidate.py` revision **v3.2** (canonical path, reused unchanged) |
| Sandbox wrapper | `scripts/sandbox.sh` (bubblewrap 0.11.1, `--unshare-all`, ro `/usr /bin /sbin /lib /lib64`, one rw bind) |
| Dataset | `third_party/dataset/humanevalpack_python_test.parquet` (164 tasks) |
| Config/manifest | `configs/models.yaml`, `configs/experiment_v1.yaml`, `manifests/model_provenance.json` (from prior selection phase) |

No destructive commands were used; nothing was committed or pushed.

---

## 2. Files changed and why

| File | Change | Why |
|---|---|---|
| `scripts/run_canary.py` | Rewritten with outcome taxonomy, stage attribution, verdict logic (BLOCKED/FAIL/PASS), raw-output preservation, frozen-manifest dev-task loading | Distinguish model vs infrastructure/extraction/evaluator failures; never count `harness_error` as a model failure; partial runs cannot pass; missing/timeout/malformed outputs have explicit categories |
| `scripts/validate_pairing_164.py` | Added `--oracle <path>` (fail-closed testability), `--require-oracle` enforcement, shared-test invariant + fingerprint, empty-test anomaly | Mandatory-oracle fail-closed for the main dataset; explicit shared-test verification |
| `scripts/task_split.py` (new) | Seeded deterministic dev/eval split; writes `manifests/dev_eval_split.json` | 12-task canary must never enter the 152-task confirmatory sample |
| `manifests/dev_eval_split.json` (new) | Frozen: method, seed, rationale, dev ids (12), eval ids (152) | explicit, recorded development/evaluation split |
| `scripts/kaggle_sandbox_preflight.sh` (new) | 8-probe preflight (bwrap, namespaces, harmless exec, network block, host isolation, timeout/no-leftover, exit-code capture, writable workspace) + machine-readable verdict JSON | gate for sandbox usability in Kaggle; never fall back to unsandboxed execution |
| `scripts/verify_quant_artifacts.py` (new) | Recomputes sha256, size, GGUF header metadata (architecture + quant type) against manifest; fail-closed on missing provenance | no unverified artifact may be reused |
| `scripts/test_canary_gates.py` (new) | unit tests for verdict logic + classification | regression coverage |
| `scripts/test_task_split.py` (new) | split invariants (12/152, disjoint, union=164, deterministic) | regression coverage |
| `scripts/test_verify_quant_artifacts.py` (new) | synthetic GGUF header tests (valid, hash mismatch, provenance missing, missing file, type mismatch, arch mismatch, non-GGUF) | regression coverage |
| `scripts/test_validate_pairing.py` | extended with `--require-oracle` missing-oracle fail-closed test | regression coverage |
| `scripts/validate_prep_artifacts.py` | master gate now compiles/runs all suites | single local acceptance gate |
| `.gitignore` | ignore `sandbox_preflight_work/`, `pilot_workdir/`, `sandbox_probe*/` | keep runtime probe dirs out of VCS |
| `configs/experiment_v1.yaml` | record `split_manifest`, `dev_tasks: 12`, `eval_tasks: 152` | documented split |

---

## 3. Tests actually executed (2026-11-01)

Command: `.venv/bin/python scripts/validate_prep_artifacts.py` → **VALIDATION_FAILURES: 0**

| Suite | Result |
|---|---|
| bash -n (4 scripts: setup/preflight/quantize/sandbox-preflight) | PASS |
| py_compile (run_canary, validate_pairing, task_split, verify_quant_artifacts, 5 test suites) | PASS |
| `test_validate_pairing.py` | PASS |
| `test_canary_smoke.py` | PASS |
| `test_canary_gates.py` | PASS (harness→BLOCKED, partial→BLOCKED, complete-pass→PASS, complete-floor→FAIL, rc classification, summarize counts) |
| `test_task_split.py` | PASS (12/152, disjoint, union=164, deterministic manifest) |
| `test_verify_quant_artifacts.py` | PASS (7 synthetic artifact scenarios) |
| Notebook JSON validity (2) | PASS |

Additional executed checks:
- `scripts/validate_pairing_164.py --require-oracle` → **PASS** (164/164 unique, oracle 164/164 canonical pass + buggy fail, 0 leaks, 0 anomalies, shared-test fingerprints recorded).
- `scripts/validate_pairing_164.py --require-oracle --oracle /nonexistent/oracle.json` → fail-closed (nonzero exit).
- `scripts/kaggle_sandbox_preflight.sh` → **PASS (7 probes)** on this Ubuntu/WSL host; verdict JSON written to `results/sandbox_preflight.json`.
- `scripts/verify_quant_artifacts.py --require-all` (no artifacts present) → all 6 listed `MISSING`, exit nonzero (fail-closed, correct).

---

## 4. Dataset and oracle validation results

- 164 unique task IDs; 164/164 synthesis/repair pairs share the same underlying problem and the same hidden test (fingerprinted).
- Oracle present and discriminating for all 164 tasks (canonical pass, buggy fail).
- Synthetic + repair prompts verified leak-free (0 hidden-test leaks; 0 canonical leaks outside the buggy block).
- Missing oracle → hard failure with `--require-oracle` (not a warning) for the main dataset.

---

## 5. Sandbox checks implemented vs actually executed

| Probe | Implemented | Executed locally (WSL) |
|---|---|---|
| bwrap present | ✅ | ✅ bubblewrap 0.11.1 |
| namespaces usable | ✅ | ✅ |
| harmless program executes | ✅ | ✅ PY_OK 4 |
| network blocked inside sandbox | ✅ | ✅ NET_BLOCKED |
| host files outside workspace blocked | ✅ | ✅ (secret unreachable) |
| timeout kills + no leftover | ✅ | ✅ (rc=124, 3s, no leftover) |
| exit code captured correctly | ✅ | ✅ (rc=7 propagated) |
| writable workspace works | ✅ | ✅ |

**Local verdict: PASS.** Kaggle-specific check remains **pending** (must be executed inside the actual GPU notebook; local Ubuntu PASS is not claimed as Kaggle compatibility).

---

## 6. Artifact-provenance safeguards

- `manifests/model_provenance.json` records source repo + revision + license + planned artifacts.
- `scripts/verify_quant_artifacts.py` refuses any artifact without a matching manifest record, size, sha256, GGUF architecture (`qwen2`), and quantization type; `--require-all` makes missing artifacts an error.
- Quantization workflow (`quantize_gguf.sh`) is idempotent (skips existing outputs) but the **verifier runs independently and is never skipped** because a file exists.
- No model downloaded, no GGUF generated, no conversion performed during this task.

---

## 7. Remaining blockers

1. **No GitHub remote/URL** — user decision pending. Push commands below are ready to use once the repo is created.
2. **Kaggle GPU session not run** — CUDA build, model download, F16/Q8 canary, sandbox preflight-in-Kaggle, and the 1,968-generation matrix are all pending explicit approval.
3. **Model license** — Qwen2.5-Coder-3B-Instruct is Qwen Research (non-commercial): no weight redistribution; review before any public release.

---

## 8. Exact commands for the eventual Kaggle preflight

```bash
# In the Kaggle notebook (after cloning the repo at the pinned commit):
cd LocalAgentBench
bash scripts/setup_kaggle.sh               # builds CUDA llama.cpp, installs deps
bash scripts/run_kaggle_preflight.sh       # GPU/VRAM/CUDA/build checks
bash scripts/kaggle_sandbox_preflight.sh   # sandbox gate (BLOCKED => stop)
# Then (only after approval): acquire model, verify with
.venv/bin/python scripts/verify_quant_artifacts.py --require-all
# Then canary (only after approval):
.venv/bin/python scripts/run_canary.py --model-f16 <f16> --model-q8 <q8> --execute
```

---

## 9. Final decision

**PASS** — local hardening complete, all local gates green, existing research preserved, and all safeguards implemented. The project is ready to proceed to the Kaggle preflight phase pending user approval; no experiment, canary, download, or quantization has been started.
