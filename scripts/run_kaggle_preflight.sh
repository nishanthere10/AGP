#!/usr/bin/env bash
# run_kaggle_preflight.sh — preflight checks for the Kaggle GPU environment.
# Reports GPU, VRAM, CUDA, llama.cpp build, python deps.
# Does NOT download models or run experiments.
set -Eeuo pipefail

_log() { echo "[preflight $(date -u +%FT%TZ)] $*"; }
_err() { echo "[preflight $(date -u +%FT%TZ)] ERROR: $*" >&2; }
_trap() {
    local rc=$?
    _err "command failed at line $1 (rc=$rc)"
    exit "$rc"
}
trap '_trap $LINENO' ERR

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$ROOT/third_party/llama.cpp"

_log "== System =="
uname -a
nproc
free -h || true

_log "== GPU detection (dynamic; never assume T4x2) =="
if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi
    GPU_COUNT="$(nvidia-smi -L | wc -l)"
    _log "GPU COUNT: $GPU_COUNT"
    _log "VRAM per GPU:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || true
    if [ "$GPU_COUNT" -lt 1 ]; then
        _err "no GPU detected via nvidia-smi"
        exit 1
    fi
else
    _err "nvidia-smi not found — no NVIDIA GPU."
    exit 1
fi

_log "== CUDA =="
if command -v nvcc >/dev/null 2>&1; then
    nvcc --version
else
    _err "nvcc not found (CUDA toolkit missing)."
    exit 1
fi

_log "== llama.cpp build =="
if [ -x "$BUILD_DIR/build/bin/llama-cli" ]; then
    "$BUILD_DIR/build/bin/llama-cli" --version
    _log "llama-cli: OK"
else
    _err "llama-cli NOT built — run setup_kaggle.sh first."
    exit 1
fi

_log "== Python =="
python --version || python3 --version
if ! python -c "import pyarrow; print('pyarrow', pyarrow.__version__)"; then
    _err "pyarrow not importable — run setup_kaggle.sh first."
    exit 1
fi

_log "== Model source (not downloaded by preflight) =="
_log "pinned: Qwen/Qwen2.5-Coder-3B-Instruct @ 488639f1ff808d1d3d0ba301aef8c11461451ec5"
_log "license: qwen-research (non-commercial); no redistribution of weights."

_log "== PREFLIGHT DONE =="
