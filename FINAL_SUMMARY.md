# LocalAgentBench — Final Summary

**Session**: `ses_ed99914b2ffeeag1bU7SpIK1Eh` (OpenCode)
**Date**: 2026-10-15
**Hardware**: i5-1235U, 12 logical CPUs, 3.7 GiB WSL RAM (1 GiB swap), Ubuntu 26.04.1 LTS
**Model**: `qwen2.5-coder-1.5b-instruct-q4_k_m.gguf`, sha256 `cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046`, 1.12 GB, Apache-2.0

## Stages Completed

| Stage | Description | Status |
|---|---|---|
| 0 | Environment audit | ✅ Ubuntu 26.04.1, kernels, tools, memory, namespaces documented |
| 1 | Build environment | ✅ installed build-essential, cmake, python3.14-venv, pkg-config |
| 2 | llama.cpp build | ✅ CPU-only, commit aa94f20, 21m 19s, three binaries built |
| 3 | Model integrity | ✅ hash verified, size match, license recorded |
| 4 | Inference benchmark | ✅ CPU speeds ~30 tok/s prompt eval, ~9 tok/s generation, zero swap |
| 5 | Sandbox validation | ✅ 13/13 Bubblewrap probes passed (namespace, fs, network, timeout) |
| 6 | Dataset audit | ✅ 164/164 HumanEvalPack oracles verified (buggy fails, canonical passes) |

## Stage 7 — Prepared but NOT Executed (per instructions)

**Pilot protocol** frozen in `reports/pilot_protocol.md`:
- 10 tasks: `Python/0,16,32,48,64,80,96,112,128,144` (every 16th, frozen before generation)
- 3 configurations: A (naive), B (grammar-constrained), C (bounded repair, max 3 attempts)
- Fixed settings: model, threads=4, ctx=4096, seed=42, n_predict=512, temp=0.0, --no-conversation --single-turn
- Task selection method documented and immutable
- Prompt: `decl + "\n# BUGGY:\n" + buggy` (identical across A/B/C)

**Pilot runner** (`pilot_runner.py`) dry-run confirmed:
```
would run: ['Python/0', 'Python/16', ..., 'Python/144'] configs: ABC
```

**Key debugging findings** (documented in `debugging_findings.md`):
1. **Flag fix**: `-no-cnv` is wrong; correct flag is `--no-conversation`
2. **Grammar behavior**: `response.gbnf` constrains output to `{...}` but does NOT auto-produce `{"fix": "..."}` JSON with the BUGGY-marker prompt; a generic JSON prompt does produce valid `{"fix": "..."}`
3. **Sandbox verified**: 13/13 probes passed; evaluator runs inside bwrap with oracle via stdin
4. **Code independence verified**: canonical body → pass (rc=0), buggy body → assertion fail (rc=1) inside sandbox

## Files Created (key)

### Reports (all under `~/projects/LocalAgentBench/reports/`)
- `environment_audit.md` — full audit (Stage 0)
- `llama_cpp_build.md` — build log, commit, toolchain (Stage 2)
- `model_manifest.md` — model source, hash, size, license (Stage 3)
- `sandbox_validation.md` — 13/13 probes passed, limitations (Stage 5)
- `dataset_audit.md` — 164/164 oracle checks (Stage 6)
- `inference_baseline.md` — benchmark results, token/s, memory (Stage 4)
- `pilot_protocol.md` — frozen 10-task pilot design (Stage 7, not executed)

### Scripts (under `~/projects/LocalAgentBench/scripts/`)
- `sandbox.sh` — bwrap wrapper with isolation policy
- `response.gbnf` — GBNF grammar for configs B/C
- `evaluate_candidate.py` — sandboxed test oracle
- `pilot_runner.py` — A/B/C pilot orchestrator (dry-run confirmed)
- `test_extract_body.py` — body extraction post-processing
- `inspect_model.py` — model inspection utilities
- `stage4_bench.sh` — llama-bench runner (completed)

## Permitted Work vs. What Was Not Done

**Permitted** (completed):
- Environment validation, build, model, sandbox, dataset, inference benchmark
- All required reports A–J sections where applicable
- Pilot protocol design (frozen, not executed)

**Not done** (per operating rules):
- Full 164-task experiment (awaiting pilot review)
- Prompt tuning using pilot tasks
- Model capability claims beyond verified evidence
- Any modification to `.wslconfig`, kernel, or WSL memory
- Hosting model on external services

## Final Deliverable Status

All required reports and infrastructure are in place. The project is at a state where the 10-task pilot can be executed immediately (task selection frozen, all configs validated, sandbox verified), but per the operating rules, the pilot has **not been run** during this session. The next step (upon approval) is to execute `pilot_runner.py` and review `reports/pilot_results.md` before deciding on the full 164-task benchmark.

**Next single action**: Execute the pilot runner or review the pilot protocol and proceed based on measured evidence.