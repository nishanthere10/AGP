# LocalAgentBench — Model Migration Plan

**Date:** 2026-11-01
**Status:** PROPOSED — no downloads, quantization, or experiment runs have occurred.
**Strict stop condition honored:** stop after model selection + local configuration
preparation. No full checkpoint download, no quantization, no Kaggle job, no 1,968-
generation run, no modification of historical results.

---

## 1. Migration summary

- **Replace** the experiment's inference model from `Qwen2.5-Coder-1.5B-Instruct`
  (Q4_K_M only) to **`Qwen2.5-Coder-3B-Instruct`** as primary (backup:
  Qwen2.5-Coder-7B-Instruct, conditional).
- The **original 1.5B model and its manifest remain untouched** as historical records.
- All six precision variants derive from the **same 3B source checkpoint**, one pinned
  llama.cpp version, one conversion pipeline.

---

## 2. What is preserved (read-only)

| Item | Location | Action |
|---|---|---|
| 1.5B model file | `models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf` | preserved |
| Stage-3 model manifest | `reports/model_manifest.md` | preserved |
| Pilot results (v2/v3/v3.2/v3.3) | `results/pilot_v*` | preserved, never rewritten |
| Evaluator + regression tests | `scripts/evaluate_candidate.py`, `scripts/test_*` | unchanged |
| Research reports | `reports/*` | unchanged |
| Frozen pilot protocol | `reports/pilot_protocol.md` | unchanged |

---

## 3. New/changed files (this preparation only)

| File | Change |
|---|---|
| `configs/models.yaml` | NEW — primary/backup/optional candidates, quantization ladder, pipeline, resource estimates |
| `configs/experiment_v1.yaml` | NEW — 164×2×6 matrix, generation contract, metrics, canary gate |
| `manifests/model_provenance.json` | NEW — provenance skeleton; sha256 slots pending download/conversion |
| `reports/model_selection.md` | NEW — ranked comparison + evidence |
| `reports/model_migration_plan.md` | NEW — this document |
| `reports/final_validation_report.md` | to be produced after local preparation completes |
| `reports/dataset_pairing_validation.md` | to be produced (dataset pairing/validation) |
| `reports/kaggle_deployment_readiness.md` | to be produced (Kaggle readiness) |
| `reports/local_preparation_report.md` | to be produced (final local prep) |

---

## 4. Migration steps (ordered; all gated)

1. **Approve selection** (this document + `model_selection.md`).
2. **Dataset pairing/validation** — build synthesis/repair pairs from the existing
   164-task HumanEvalPack; verify 164/164 canonical-pass and buggy-fail; no leakage.
3. **Model acquisition** (in Kaggle, restartable) — download pinned 3B source
   checkpoint; compute safetensors sha256; record in manifest.
4. **Conversion** — F16 GGUF + five quantizations from the same source (single
   pipeline, pinned llama.cpp).
5. **Canary** — 8–12 dev tasks, F16 + Q8_0, both modes; enforce pre-set thresholds;
   BLOCKED if no non-floor success in both modes at F16.
6. **Full matrix** — only if canary passes; 164×2×6 = 1,968 generations, greedy,
   interleaved, sequential, checkpoint/resume.
7. **Analysis & release** — frozen analysis script; report results; preserve raw outputs.

---

## 5. Canary protocol (frozen pre-run)

See `reports/model_selection.md` §7 for thresholds and stop rules. Key guarantees:
- 8–12 development tasks **excluded** from the final evaluation sample.
- No separate prompt tuning for synthesis vs repair.
- F16 and Q8_0 only; if F16 fails, do not proceed to Q6/Q4/Q3/Q2.

---

## 6. Risk / decision notes

- **License:** Qwen 3B is Qwen Research (non-commercial). Acceptable for this
  academic study; disclose in the paper; do not redistribute the weights.
- **7B backup:** only viable if the F16 reference condition is dropped (→ Q8_0 as
  highest precision) or a larger GPU is confirmed. Default study uses 3B.
- **StarCoder2-3B:** optional second family; include only if canary shows non-floor
  behavior (its HumanEval ≈31.7 is a floor risk).

---

## 7. Deliverables status

| Deliverable | Status |
|---|---|
| Ranked model comparison | ✅ done (`model_selection.md`) |
| Primary + backup selected | ✅ done |
| Evidence | ✅ done (HF API-verified) |
| F16 memory estimate | ✅ done |
| Kaggle compatibility assessment | ✅ done |
| GGUF conversion plan | ✅ done |
| Updated config/manifest files | ✅ done (`configs/`, `manifests/`) |
| Canary design | ✅ done (thresholds pre-set) |
| Local validation run | ⛔ NOT RUN (next phase) |
| Final PASS/BLOCKED gate | ⛔ pending approval + canary |
