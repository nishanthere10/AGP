# Final Validation Report — LocalAgentBench (Kaggle GPU migration)

**Date:** 2026-11-01
**Status:** PREPARATION PASS — experiment NOT run (correctly gated).

---

## 1. Verdict summary

| Area | Status |
|---|---|
| Local preparation | ✅ PASS |
| Dataset | ✅ PASS (164/164 pairs; 164/164 canonical pass; 164/164 buggy fail; 0 leaks) |
| Evaluator | ✅ PASS (existing regression suite; reused unchanged) |
| Model configuration | ✅ PASS (primary Qwen2.5-Coder-3B-Instruct; backup 7B; six precision conditions) |
| Kaggle notebook | ✅ PASS (files prepared & syntax-valid; execution NOT run) |
| GitHub readiness | ⛔ BLOCKED (no remote configured; username/repo pending user decision) |

## 2. Provenance

- **Primary model:** Qwen/Qwen2.5-Coder-3B-Instruct @ revision
  `488639f1ff808d1d3d0ba301aef8c11461451ec5`, Qwen Research license, 3.09B
  params, F16 weights ≈ 6.17 GB.
- **Dataset:** HumanEvalPack Python, 164 tasks, parquet
  `third_party/dataset/humanevalpack_python_test.parquet`.
- **Backend:** llama.cpp @ `aa94f2086147cd4bfbcff818ce998dffce5fcb39`.
- **Conversion:** single pipeline (`convert_hf_to_gguf.py` F16 → `llama-quantize`
  for Q8_0/Q6_K/Q4_K_M/Q3_K_M/Q2_K) from the same source; sha256 recorded per artifact.

## 3. Test results

| Test | Result |
|---|---|
| Oracle: canonical passes | 164/164 |
| Oracle: buggy fails | 164/164 |
| Pairing: 164 tasks, unique, both modes buildable | PASS |
| Leak check (hidden tests + canonical outside buggy) | 0 leaks |
| Bash syntax (setup/preflight/quantize) | PASS |
| Python syntax (canary, pairing validator) | PASS |
| Notebook JSON validity | PASS |

## 4. Unexecuted tests (explicitly NOT RUN)

- Model download + hash verification (Kaggle step).
- Quantization (Kaggle step).
- Canary execution (gated on preflight + approval).
- 1,968-generation matrix (strictly gated).

## 5. Known blockers / notes

- GitHub remote not configured (blocked on user decision).
- Qwen 3B non-commercial license: no weight redistribution.
- 7B backup conditional on GPU or F16-reference change.
- StarCoder2-3B excluded (not an instruction model).

## 6. Clean deployment commands (when authorized)

```bash
# After repo is pushed (user supplies remote):
#   git remote add origin <URL>; git push -u origin master
# Clone + pin on Kaggle:
#   git clone <URL>
#   cd LocalAgentBench && git checkout <commit-sha>
#   bash scripts/setup_kaggle.sh
#   bash scripts/run_kaggle_preflight.sh
#   (acquire model, quantize, canary — then matrix)
```
