# LocalAgentBench — Model Selection Report

**Date:** 2026-11-01
**Status:** Selection PROPOSED. No download/quantization/experiment performed.
**Purpose:** Rank candidate base models for the Kaggle GPU migration of the
quantization × synthesis-vs-repair study.

---

## 1. Requirement summary (from the brief)

- Research question: does quantization affect functional correctness **differently**
  for synthesis vs repair, on the same underlying tasks, scored by the same tests?
- Six precision conditions from **one source checkpoint**: F16, Q8_0, Q6_K,
  Q4_K_M, Q3_K_M, Q2_K.
- Runtime: llama.cpp with CUDA on Kaggle (prefer T4, 16 GB VRAM each; GPUs not pooled).
- F16 reference must fit comfortably on **one** T4.
- Prefer a **general code-instruction model**, not a repair-specialized fine-tune
  (would bias the synthesis-vs-repair comparison).
- Must have verifiable original checkpoint, suitable license, GGUF/llama.cpp support.

---

## 2. Candidates investigated

| # | Model | Params | License | F16 size | Fits T4 F16? | Code benchmark (published) | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | **Qwen2.5-Coder-3B-Instruct** | 3.09B | **Qwen Research (non-commercial)** | ~6.17 GB | ✅ comfortable | HumanEval ~45 (OpenCompass, protocol-dependent) | **PRIMARY — best 3B general code model, clean F16 fit** |
| 2 | Qwen2.5-Coder-7B-Instruct | 7.61B | Apache-2.0 | ~15.2 GB | ❌ no headroom | HumanEval ~85 (vendor-reported) | Backup only (F16 not viable on T4) |
| 3 | NextCoder-3B | — | — | — | — | — | **Does not exist as a 3B checkpoint** (family is 7B/14B/32B; Microsoft). Also repair-specialized → disfavored by brief |
| 4 | StarCoder2-3B | 3.03B | BigCode OpenRAIL-M | ~6.1 GB | ✅ | HumanEval 31.7 (official model-index) | Optional second family; weaker → floor risk |
| 5 | Granite-3b-code-instruct | ~3B | Apache-2.0 | ~6 GB | ✅ | ~35–40 (legacy eval) | Weaker than Qwen 3B; not selected |
| 6 | Qwen3-Coder-Next | 80B MoE (3B active) | Apache-2.0 | n/a (MoE) | ❌ | strong | Too large for T4/GGUF study; out of scope |

**Key verified facts:**
- `Qwen/Qwen2.5-Coder-3B-Instruct` revision `488639f1…ec5`; 3.09B params, 36 layers,
  GQA 16Q/2KV, ctx 32K, BF16, F16 weights = 6,171,927,000 B (HF API).
- `Qwen/Qwen2.5-Coder-7B-Instruct` revision `c03e6d35…e242`; 7.61B params, 28 layers,
  ctx 128K, F16 weights = 15,231,271,864 B (HF API). Apache-2.0.
- **3B license caveat:** HF card lists `qwen-research` (Qwen Research License,
  non-commercial). Suitable for an academic study; weight redistribution restricted;
  must be disclosed. 7B is Apache-2.0.
- NextCoder-3B: no such HF checkpoint found. NextCoder 7B/14B/32B are **code-editing
  fine-tunes** (task-mode bias) → rejected per brief even ignoring availability.

---

## 3. Selected primary and backup

### Primary: Qwen2.5-Coder-3B-Instruct
Why it is best suited vs the original 1.5B model:
- **3.09B params vs 1.54B** → roughly 2× capacity; the 1.5B hit a hard **floor
  effect** (0/10 functional passes in v2/v3.2; 0/90 extractable definitions in
  v3.3). A bigger, general code-instruct model is the minimal change that can
  plausibly clear the floor.
- **General code-instruction model** (synthesis + repair + reasoning), not a
  repair-specialized fine-tune → clean for the paired synthesis-vs-repair question.
- **F16 fits one T4** with comfortable headroom (~6.7 GiB total vs 16 GB).
- **llama.cpp support confirmed** (Qwen2 architecture; same family as the existing
  1.5B GGUF, which already runs in this project).
- Verifiable checkpoint: pinned revision SHA recorded; source safetensors hash to be
  computed at download.

### Backup: Qwen2.5-Coder-7B-Instruct
- Apache-2.0 and notably stronger, but **F16 (15.2 GB) cannot fit a single 16 GB T4**
  with headroom. Use ONLY if the F16 reference is dropped (highest precision Q8_0)
  or a 24 GB+ GPU is confirmed. Kept as fallback if the 3B canary floors.

---

## 4. F16 GPU memory estimate (T4, 16 GB)

| Model | Weights (F16) | KV + activations (est.) | Total est. | Fits 16 GB T4? |
|---|---|---|---|---|
| Qwen 3B | 6.17 GB | ~0.5 GB | ~6.7 GiB | ✅ |
| Qwen 7B | 15.23 GB | ~1.0 GB | ~16.2 GiB | ❌ |

---

## 5. Kaggle compatibility assessment

- **GPU detection:** notebooks/scripts will detect actual GPU + VRAM dynamically;
  never assume T4×2 or pooled memory.
- **Backend:** llama.cpp CUDA build at the pinned commit; identical backend across
  all six quant variants. No vLLM.
- **Conversion:** `convert_hf_to_gguf.py` (F16) → `llama-quantize` for Q8_0/Q6_K/
  Q4_K_M/Q3_K_M/Q2_K, all from the same source checkpoint.
- **Model acquisition:** restartable (resumable download stuck to the pinned revision).

---

## 6. GGUF conversion plan

```
python3 convert_hf_to_gguf.py <hf_dir> --outtype f16 --outfile qwen2.5-coder-3b-instruct-f16.gguf
llama-quantize qwen2.5-coder-3b-instruct-f16.gguf qwen2.5-coder-3b-instruct-Q8_0.gguf  Q8_0
llama-quantize qwen2.5-coder-3b-instruct-f16.gguf qwen2.5-coder-3b-instruct-Q6_K.gguf   Q6_K
llama-quantize qwen2.5-coder-3b-instruct-f16.gguf qwen2.5-coder-3b-instruct-Q4_K_M.gguf Q4_K_M
llama-quantize qwen2.5-coder-3b-instruct-f16.gguf qwen2.5-coder-3b-instruct-Q3_K_M.gguf Q3_K_M
llama-quantize qwen2.5-coder-3b-instruct-f16.gguf qwen2.5-coder-3b-instruct-Q2_K.gguf  Q2_K
```
- Same source checkpoint, same llama.cpp version, one pipeline.
- Record sha256 of every artifact in `manifests/model_provenance.json`.
- **Q8_0 is quantized, never called full precision.**

---

## 7. Canary experiment design (gate before full matrix)

- **8–12 paired development tasks**, excluded from the final evaluation set.
- Conditions: **F16 + Q8_0**, both synthesis and repair modes.
- Metrics: extractable %, syntax-valid %, functional pass rate, termination reason,
  generated tokens, latency, peak VRAM, repetition/incomplete flag.
- **Thresholds (set before running):**
  - extractable ≥ 70%
  - syntax-valid ≥ 60%
  - functional pass ≥ 20% in at least one mode at F16
- **Stop rules:** if F16 does not show non-floor functional success in BOTH modes →
  BLOCKED; do NOT proceed to Q6/Q4/Q3/Q2; investigate prompt/model/evaluation; then
  decide whether to fall back to the 7B (with F16 caveat) — or revisit prompting.

---

## 8. Recommendation

**Select Qwen2.5-Coder-3B-Instruct as the primary model** (backup:
Qwen2.5-Coder-7B-Instruct, conditional on F16-gate change).

| Item | Verdict |
|---|---|
| Ranked comparison | ✅ provided |
| Primary selected | ✅ Qwen2.5-Coder-3B-Instruct |
| Backup selected | ✅ Qwen2.5-Coder-7B-Instruct (conditional) |
| Evidence | ✅ HF API-verified params/revisions/licenses/sizes |
| F16 GPU estimate | ✅ ~6.7 GiB total, fits T4 |
| Kaggle compatibility | ✅ CUDA llama.cpp + dynamic GPU detection |
| GGUF conversion plan | ✅ pinned single-pipeline |
| Canary design | ✅ thresholds pre-set |
| **Overall status** | **PASS (proposal) — awaiting approval before any download/quantization** |
