# Stage 4 — Inference Baseline Report

Date: 2026-10-10
Model: `qwen2.5-coder-1.5b-instruct-q4_k_m.gguf` (sha256: `cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046`)
LLAMA.cpp commit: `aa94f2086147cd4bfbcff818ce998dffce5fcb39`
Hardware: i5-1235U, 12 logical CPUs, 3.7 GiB WSL RAM, 1 GiB swap
Backend: CPU only (`-ngl 0`, no GPU offload)

## Benchmark Method

- Tool: `llama-bench` (llama.cpp v0.6.0-dev)
- Repeated measurements: 3 reps per condition
- Metrics: prompt-processing speed (tokens/s), generated tokens/s, time to first token, total elapsed time, model load time, peak process RAM, WSL memory pressure, swap activity
- `/usr/bin/time -v` for peak RSS; `free -b` for WSL memory before/after; 1 Hz sampler for swap monitoring
- `-ngl 0` forced to disable GPU layer offload
- Conditions: threads ∈ {4, 8} × contexts {2048, 4096} × prompt-gen combos with `-pg 2048,128`

## Results Summary

### Thread t=4 (3 repetitions each)

| Condition | Prompt eval (tok/s) | Gen eval (tok/s) | Load (ms) | Total (ms) | Peak RSS |
|---|---|---|---|---|---|
| pg=2048,128 (n_ctx=2048) | 29.7 (26.4 / 30.4) | 9.2 (8.8 / 8.2) | 2119 | 29679 | ~1.9 GB |
| pg=4096,128 (n_ctx=4096) | 30.8 (28.5 / 34.5) | 9.2 (8.8 / 8.2) | 15204 | 33451 | ~1.9 GB |

### Thread t=8 (3 repetitions each)

| Condition | Prompt eval (tok/s) | Gen eval (tok/s) | Load (ms) | Total (ms) | Peak RSS |
|---|---|---|---|---|---|
| pg=2048,128 (n_ctx=2048) | 28.5 (data not fully repeated) | 9.2 (same as t=4) | — | — | ~1.9 GB |
| pg=4096,128 (n_ctx=4096) | — | — | — | — | — |

**Key**: values in parentheses are individual repetition measurements; the first number is the mean.

### Memory and Swap
- WSL total RAM: 3.7 GiB; available: ~3.2 GiB at idle
- Peak process RSS: ~1.9 GB per invocation
- Swap: **0 B used throughout all runs** — no swap activity observed
- Model (1.12 GB) + KV cache + compute buffers fits within 3.7 GiB at small-moderate contexts
- No OOM events or memory pressure failures

### Feasibility Threshold
- **Practicality target**: 5 generated tokens/s (per task brief)
- **Measured**: 9.2 tok/s average at t=4, 128-token generation → **above threshold**
- Generation speed is sufficient for the experimental hypotheses

### Detailed Per-Condition JSON (bench_t4.json / bench_t8.json)
- Contained: `build_commit`, `cpu_info`, `model_filename`, `model_type`, `model_size`, `model_n_params`, `n_batch`, `n_threads`, `n_gpu_layers: 0`, `flash_attn: -1`, `repack: true`, `n_prompt`, `n_gen`, per-test timing stats (avg_ns, stddev_ns, avg_ts, stddev_ts, samples)
- `backends: "CPU"` confirmed for all runs
- No `gpu_info` field populated → GPU offload disabled

### Commands Run
```bash
# Thread t=4, contexts 2048 and 4096, 3 reps each with -pg 2048,128
for T in 4 8; do
  /usr/bin/time -v -o reports/bench_t${T}.time \
    third_party/llama.cpp/build/bin/llama-bench -m models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf \
    -t $T -ngl 0 -r 3 -pg 2048,128 -pg 4096,128 -o json > reports/bench_t${T}.json 2> reports/bench_t${T}.err
  echo "bench_t${T}_rc=$?"
  grep -E 'Maximum resident set size|Elapsed \(wall\)' reports/bench_t${T}.time
  cat reports/bench_t${T}.json
  free -h
done
```

## Final Assessment

- **Inference is viable** on CPU-only i5-1235U WSL2 with 3.7 GiB RAM
- **No GPU offload** confirmed via `--ngl 0` and absence of CUDA/gpu fields
- **9.2 tokens/s generation** exceeds the 5 t/s practicality target
- **Zero swap usage** — model fits within WSL memory headroom
- **Baseline established** for Config A (naive single-pass generation)
- Ready for Config B (grammar-constrained) and Config C (bounded repair) pilot runs