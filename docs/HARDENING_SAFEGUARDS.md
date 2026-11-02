# Hardening & Safeguards — LocalAgentBench

This document details the safety gates, error-handling rules, test suites, and
local validation procedure that protect the experiment's validity and the host
environment. Master readiness verdict: `reports/pre_kaggle_readiness.md` (**PASS**).

---

## 1. Guardrail philosophy

1. **Never count a harness error as a model failure.**
2. **Fail closed:** missing oracle, unverified artifact, unexplained infra error, or incomplete run ⇒ nonzero exit / BLOCKED.
3. **Never execute model-generated code without the validated sandbox.**
4. **Preserve raw outputs** so every score is reproducible.
5. **Do not run a large experiment merely because infrastructure is ready** — gates decide.

---

## 2. Sandbox model

```mermaid
flowchart LR
    subgraph Host["Host"]
        ORC[oracle test — stdin only]
        E[evaluate_candidate.py]
        W[pilot_workdir — only rw bind]
    end
    subgraph Box["Bubblewrap sandbox"]
        subgraph NS["Namespaces: user/mount/pid/ipc/uts/net (unshared)"]
            RUN[candidate code]
        end
        RO[/usr /bin /sbin /lib /lib64 — ro bind/]
        WR[/tmp/work — writable/]
        PROC[/proc fresh · /dev minimal/]
    end
    E --> Box
    RUN -->|stdin| ORC
    W -->|bind| WR
    RO -.- Box
    PROC -.- Box
```

### Sandbox preflight (`kaggle_sandbox_preflight.sh`)

```mermaid
flowchart TD
    A[bwrap present] --> B[namespaces usable]
    B --> C[harmless program executes]
    C --> D[network blocked inside]
    D --> E[host files outside workspace blocked]
    E --> F[timeout kills; no leftover]
    F --> G[exit code captured]
    G --> H[writable workspace works]
    H --> I{any probe failed?}
    I -->|yes| BL[BLOCKED — stop before generated code]
    I -->|no| P[PASS]
```

- Local verdict: **PASS (7/7 probes)** on WSL Ubuntu.
- Kaggle result is **pending** until run in the real GPU notebook — local PASS is not claimed as Kaggle compatibility.
- There is **no unsandboxed fallback**; a BLOCKED sandbox stops the run.

---

## 3. Verdict logic (canary)

```mermaid
stateDiagram-v2
    [*] --> Running
    Running --> BLOCKED: any infra outcome (gen_failure / eval_timeout / harness_error / infra_error)
    Running --> BLOCKED: run incomplete (fewer cells than planned)
    Running --> FAIL: complete, no infra, thresholds not met
    Running --> PASS: complete, no infra, F16 thresholds met in both modes
    FAIL --> [*]
    PASS --> [*]
    BLOCKED --> [*]
```

### Outcome classification

| Stage | Outcome possibilities |
|---|---|
| generate | `pass` path → gen records; rc ≠ 0 → `gen_failure`; exception → `infra_error` |
| extract | `ok-def` → evaluate; else `extraction_rejected` (kind recorded); exception → `infra_error` |
| evaluate | rc 0–4 → model outcomes; rc 5 + TIMEOUT → `eval_timeout`; rc 5 else → `harness_error`; exception → `infra_error` |

### Thresholds (F16, per mode)

| Metric | Threshold |
|---|---|
| Extractable | ≥ 9/12 |
| Syntax-valid | ≥ 8/12 |
| Functional | ≥ 3/12 |

---

## 4. Test suites

All suites run under `.venv/bin/python scripts/validate_prep_artifacts.py` (master gate), which runs:

```mermaid
flowchart TD
    G[validate_prep_artifacts.py] --> B[bash -n on 4 shell scripts]
    G --> P[py_compile on all python]
    G --> T1[test_validate_pairing.py]
    G --> T2[test_canary_smoke.py]
    G --> T3[test_canary_gates.py]
    G --> T4[test_task_split.py]
    G --> T5[test_verify_quant_artifacts.py]
    G --> N[notebook JSON validity]
    T1 --> R{all green?}
    T2 --> R
    T3 --> R
    T4 --> R
    T5 --> R
    R -->|yes| OK["0 failures"]
    R -->|no| BAD["nonzero exit — stop"]
```

### What the suites assert (acceptance criteria)

| Requirement | Coverage |
|---|---|
| Harness error ⇒ BLOCKED, not a model failure | `test_canary_gates.py` |
| Incomplete canary cannot pass | `test_canary_gates.py` |
| Missing oracle ⇒ validation failure | `test_validate_pairing.py` (with `--require-oracle`) |
| Duplicate / unknown / non-12 dev task IDs rejected | `test_canary_smoke.py`, `test_pre_kaggle_acceptance.py` |
| Development task cannot enter confirmatory set | `test_task_split.py` |
| Invalid / unverified quantization artifact not reused | `test_verify_quant_artifacts.py` |
| Sandbox failure prevents generated-code execution | `kaggle_sandbox_preflight.sh` (BLOCKED exits) |
| Prompt/generation token counts recorded | `run_canary.py` records; tested via generate/records shape |
| Existing regression suites still pass | master gate + legacy suites |

---

## 5. Provenance & artifact verification

```mermaid
flowchart LR
    M[model_provenance.json] --> S[source repo + revision + license]
    M --> A[planned artifacts]
    A --> V[verify_quant_artifacts.py]
    V --> C1{file exists?}
    C1 -->|no| MISS[MISSING]
    C1 -->|yes| C2{manifest record?}
    C2 -->|no| INV[INVALID — no provenance]
    C2 -->|yes| C3{size matches?}
    C3 -->|no| INV
    C3 -->|yes| C4{sha256 matches?}
    C4 -->|no| INV
    C4 -->|yes| C5{GGUF arch + type match?}
    C5 -->|no| INV
    C5 -->|yes| OK[VALID]
```

- `quantize_gguf.sh` is idempotent (skips existing outputs) but the **verifier always runs independently** — existence never substitutes for verification.
- No model has been downloaded or quantized during preparation; all artifacts are `MISSING` until the approved Kaggle phase.

---

## 6. Kaggle readiness gates

```mermaid
flowchart LR
    A[Local PASS] --> B[kaggle_setup_and_preflight.ipynb]
    B --> C[setup_kaggle.sh — CUDA llama.cpp]
    C --> D[run_kaggle_preflight.sh — GPU/VRAM/CUDA]
    D --> E[kaggle_sandbox_preflight.sh]
    E -->|BLOCKED| S[STOP]
    E -->|PASS| F[acquire pinned checkpoint]
    F --> G[verify_quant_artifacts.py --require-all]
    G --> H[canary — 12 dev tasks F16+Q8]
    H -->|not PASS| S
    H -->|PASS| I[1,968-gen matrix]
```

- GPU/VRAM are detected dynamically; two GPUs are never assumed to pool memory.
- Model acquisition is restartable; state persists under `/kaggle/working` and is exported to `/kaggle/output`.
- No credentials are stored in the repo; the repo URL is public-facing.

---

## 7. Local validation output (executed 2026-11-01)

| Gate | Result |
|---|---|
| bash -n (setup/preflight/quantize/sandbox-preflight) | PASS |
| py_compile (all modules + suites) | PASS |
| test_validate_pairing | PASS (incl. missing-oracle fail-closed) |
| test_canary_smoke | PASS |
| test_canary_gates | PASS |
| test_task_split | PASS |
| test_verify_quant_artifacts | PASS |
| validate_pairing_164 --require-oracle | PASS (164/164, 0 leaks, 0 anomalies) |
| kaggle_sandbox_preflight | PASS (7/7 local) |
| verify_quant_artifacts --require-all | all MISSING ⇒ nonzero (correct) |
| Master gate | **0 failures** |

---

## 8. Remaining blockers / decisions

1. **No GitHub remote** — push commands ready; awaiting user repo decision.
2. **Kaggle GPU session** — the only *unexecuted* gate (build, acquire, canary, matrix).
3. **Qwen 3B license** — Qwen Research (non-commercial); no weight redistribution; review before public release.
