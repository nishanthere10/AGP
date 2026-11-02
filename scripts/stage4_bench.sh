#!/usr/bin/env bash
# Stage 4: controlled CPU inference benchmark.
# - llama-bench for pp/tg throughput at 2048/4096-token contexts, 3 reps each
# - thread settings t=4 and t=8 (recorded; not tuned for favorable results)
# - /usr/bin/time -v for peak RSS per invocation
# - background 1 Hz sampler for WSL memory/swap pressure
# - -ngl 0 forced: GPU offload explicitly disabled
set -u
ROOT=/home/aaksh/projects/LocalAgentBench
BIN=$ROOT/third_party/llama.cpp/build/bin
MODEL=$ROOT/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
OUT=$ROOT/results/inference_smoke
mkdir -p "$OUT"

# --- memory sampler (1 Hz) ---
SAMPLER_LOG=$OUT/mem_sampler.log
( while true; do
    free -b | awk -v ts="$(date +%s)" '/^Mem:/{printf "%s mem_used=%s mem_avail=%s ", ts, $3, $7}/^Swap:/{printf "swap_used=%s\n", $3}'
    sleep 1
  done ) > "$SAMPLER_LOG" 2>&1 &
SAMPLER_PID=$!
trap 'kill $SAMPLER_PID 2>/dev/null' EXIT

echo "=== stage4 benchmark start $(date -Is) ==="
free -h

# --- Thread sweep + contexts: pp/tg ---
# -pg PP,TG: prompt-processing PP tokens then TG tokens.
# Conditions: {t=4,t=8} x {pp=2048,pp=4096} tg=128, reps=3
for T in 4 8; do
  echo "=== llama-bench threads=$T reps=3 pg=2048,128 pg=4096,128 ngl=0 ==="
  /usr/bin/time -v -o "$OUT/bench_t${T}.time" \
    "$BIN/llama-bench" -m "$MODEL" -t "$T" -ngl 0 -r 3 \
      -pg 2048,128 -pg 4096,128 \
      -o json > "$OUT/bench_t${T}.json" 2> "$OUT/bench_t${T}.err"
  echo "bench_t${T}_rc=$?"
  grep -E 'Maximum resident set size|Elapsed \(wall' "$OUT/bench_t${T}.time"
  cat "$OUT/bench_t${T}.json"
  free -h
done

kill $SAMPLER_PID 2>/dev/null
trap - EXIT
echo "=== stage4 benchmark end $(date -Is) ==="
echo "sampler peak:"
awk '{for(i=1;i<=NF;i++){if($i~/mem_used=/){split($i,a,"=");if(a[2]>m)m=a[2]}if($i~/swap_used=/){split($i,b,"=");if(b[2]>s)s=b[2]}}}END{printf "max_mem_used=%d MiB max_swap_used=%d MiB\n", m/1048576, s/1048576}' "$SAMPLER_LOG"
echo "sampler lines: $(wc -l < "$SAMPLER_LOG")"
