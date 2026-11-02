# Local Preparation Report — LocalAgentBench (Kaggle GPU migration)

**Date:** 2026-11-01
**Status:** PASS (preparation complete; execution gated)
**Canonical location:** `~/projects/LocalAgentBench` (WSL); mirrored to host `AGP/`.

---

## 1. What was implemented

| Item | File | Status |
|---|---|---|
| Model selection | `reports/model_selection.md` | ✅ |
| Model migration plan | `reports/model_migration_plan.md` | ✅ |
| Model config (primary/backup, quantization ladder, pipeline) | `configs/models.yaml` | ✅ |
| Experiment v1 config (matrix, output contract, metrics, canary gate) | `configs/experiment_v1.yaml` | ✅ |
| Provenance skeleton (sha256 slots pending download) | `manifests/model_provenance.json` | ✅ |
| Dataset pairing validator | `scripts/validate_pairing_164.py` | ✅ ran, PASS |
| Dataset pairing report | `reports/dataset_pairing_validation.md` | ✅ |
| Kaggle CUDA setup script | `scripts/setup_kaggle.sh` | ✅ (syntax-valid) |
| Kaggle preflight script | `scripts/run_kaggle_preflight.sh` | ✅ (syntax-valid) |
| Quantization script (F16 + 5 quant levels, hashing) | `scripts/quantize_gguf.sh` | ✅ (syntax-valid) |
| Canary runner (12 dev tasks, thresholds) | `scripts/run_canary.py` | ✅ (syntax-valid) |
| Kaggle setup + preflight notebook | `notebooks/kaggle_setup_and_preflight.ipynb` | ✅ (valid JSON) |
| Kaggle exploratory experiment notebook | `notebooks/kaggle_exploratory_experiment.ipynb` | ✅ (valid JSON; guarded) |

## 2. What was reused (unchanged)

- Evaluator: `scripts/evaluate_candidate.py` (v3.1+) — reused as-is.
- Sandbox: `scripts/sandbox.sh` (Bubblewrap) — reused as-is.
- Dataset: `third_party/dataset/humanevalpack_python_test.parquet` (164 tasks).
- llama.cpp pinned commit `aa94f2086147cd4bfbcff818ce998dffce5fcb39`.
- Oracle validation: `scripts/validate_dataset.py` (164/164 both directions).

## 3. What was changed / added

- **No historical results or pilot directories were modified.**
- Added `configs/`, `manifests/`, `notebooks/`, new `scripts/`, new `reports/`.
- Updated `configs/experiment_v1.yaml` canary thresholds per approved decision
  (9/12 extractable, 8/12 syntax-valid, 3/12 functional, EACH mode).

## 4. Test results

| Gate | Result |
|---|---|
| A. Repository integrity | ✅ read-only inspection; no destructive changes |
| B. Dataset integrity | ✅ 164/164 pairs; 164/164 canonical pass; 164/164 buggy fail; 0 leaks |
| C. Evaluator integrity | ✅ existing regression suite (reports/evaluator_validation.md); not re-run in this phase |
| D. Configuration integrity | ✅ six precision conditions; single source; pipeline pinned |
| E. Kaggle readiness | ✅ scripts/notebooks syntactically valid; **execution NOT run** (no Kaggle session here) |

## 5. Unexecuted tests (explicitly NOT RUN)

- Model download / hash verification (Kaggle step).
- Quantization (Kaggle step).
- Canary execution (gated on Kaggle preflight + approval).
- 1,968-generation matrix (strictly gated).

## 6. Known blockers

- GitHub username/repo not yet provided (push deferred by user decision).
- Kaggle session not launched (preparation only).
- Qwen 3B license = Qwen Research (non-commercial): no weight redistribution.

## 7. Current Git state

- Branch `master`, 2 commits, no remote configured.
- New files untracked: `configs/`, `manifests/`, `notebooks/`, new `scripts/`,
  new `reports/` (model_selection, model_migration_plan, dataset_pairing_validation).
- Existing tracked modifications remain as found (`pilot_protocol.md`,
  `evaluate_candidate.py`, `pilot_runner.py`) — left uncommitted per "do not
  commit unrelated existing work".
