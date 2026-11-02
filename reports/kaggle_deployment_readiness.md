# Kaggle Deployment Readiness — LocalAgentBench

**Date:** 2026-11-01
**Status:** READY (files prepared & validated); EXECUTION NOT RUN (no Kaggle session here).

---

## 1. Target environment

- Kaggle GPU (dynamic detection; do not assume T4×2 or pooled memory).
- 16 GB VRAM per GPU is the planning assumption for the primary model F16 fit.
- Internet access required to clone repo and download pinned checkpoint.

## 2. What ships to Kaggle

| File | Purpose |
|---|---|
| `notebooks/kaggle_setup_and_preflight.ipynb` | clone at pinned commit → GPU/CUDA check → build CUDA llama.cpp → preflight → download source checkpoint → hash → persist to output |
| `notebooks/kaggle_exploratory_experiment.ipynb` | matrix harness; guarded by env var; requires canary approval |
| `scripts/setup_kaggle.sh` | build CUDA llama.cpp at pinned commit; install pyarrow |
| `scripts/run_kaggle_preflight.sh` | report GPU, VRAM, CUDA, build, python deps |
| `scripts/quantize_gguf.sh` | F16 + Q8_0/Q6_K/Q4_K_M/Q3_K_M/Q2_K from same source; hash artifacts |
| `scripts/run_canary.py` | 12 dev-task canary with frozen thresholds |
| `configs/models.yaml`, `configs/experiment_v1.yaml` | experiment definition |
| `manifests/model_provenance.json` | provenance (sha256 slots) |

## 3. Key design points

- **Checkpoint/resume:** state lives in files under `/kaggle/working` and is copied
  to `/kaggle/output`; notebook variables are not relied upon for persistence.
- **Restartable acquisition:** pinned revision download can be resumed.
- **Identical backend:** the same llama.cpp build serves all six quantization variants.
- **No vLLM:** llama.cpp (GGUF) is the designated runtime.
- **No credentials:** public repo URL only; no tokens in git.
- **Safety guard:** the experiment notebook refuses to run unless
  `LOCAL_AGENTBENCH_RUN_MATRIX=1` and the canary passed.

## 4. Dependency path

```
Kaggle notebook (GPU)
  └─ git clone {PUBLIC_REPO_URL} @ {PINNED_COMMIT}
       └─ bash scripts/setup_kaggle.sh        (pip pyarrow; build CUDA llama.cpp)
       └─ bash scripts/run_kaggle_preflight.sh (verify GPU/VRAM/CUDA/build)
       └─ snapshot_download(Qwen/Qwen2.5-Coder-3B-Instruct @ 488639f1...)
       └─ sha256 → manifests/model_provenance_kaggle.json
       └─ bash scripts/quantize_gguf.sh <src> (F16 → 5 quant levels)
       └─ python scripts/run_canary.py (12 dev tasks @ F16+Q8) → thresholds
       └─ [approved] python scripts/run_matrix.py (1,968 gens) → results
```

## 5. Go/no-go for experiment start

- CANARY must pass: extractable ≥9/12, syntax-valid ≥8/12, functional ≥3/12
  in EACH mode at F16.
- Only after canary approval is the matrix enabled.

## 6. Not-yet-executed (explicit)

- CUDA build, GPU verify, model download, quantization, canary, matrix — all
  pending a real Kaggle session and the user's go-ahead.
