#!/usr/bin/env bash
# setup_kaggle.sh — Kaggle GPU environment setup for LocalAgentBench.
# Run from the repository root inside a Kaggle notebook / terminal cell.
# Idempotent; restartable. Does NOT acquire models or run the experiment.
set -Eeuo pipefail

# --- logging helpers --------------------------------------------------------
_log() { echo "[setup $(date -u +%FT%TZ)] $*"; }
_err() { echo "[setup $(date -u +%FT%TZ)] ERROR: $*" >&2; }
_trap() {
    local rc=$?
    _err "command failed at line $1 (rc=$rc)"
    exit "$rc"
}
trap '_trap $LINENO' ERR

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LLAMA_COMMIT="${LLAMA_COMMIT:-aa94f2086147cd4bfbcff818ce998dffce5fcb39}"
BUILD_DIR="$ROOT/third_party/llama.cpp"
NPROC="$(nproc)"

_log "root=$ROOT"
_log "llama.cpp commit=$LLAMA_COMMIT"

# --- 1. Python deps (light; evaluator = stdlib + pyarrow) ------------------
_log "installing python deps"
if ! pip install --quiet --upgrade pip; then
    _err "pip self-upgrade failed (non-fatal, continuing)"
fi
if ! pip install --quiet 'pyarrow==26.0.0' 'PyYAML>=6.0'; then
    _err "pyarrow/PyYAML install failed"
    exit 1
fi

# --- 2. Build CUDA-enabled llama.cpp at the pinned commit (restartable) ----
if [ ! -d "$BUILD_DIR/.git" ]; then
    _log "cloning llama.cpp"
    if ! git clone https://github.com/ggml-org/llama.cpp.git "$BUILD_DIR"; then
        _err "clone failed"
        exit 1
    fi
fi

(
    cd "$BUILD_DIR"
    _log "fetching + checking out $LLAMA_COMMIT"
    if ! git fetch --quiet origin; then
        _err "git fetch failed"
        exit 1
    fi
    if ! git checkout --quiet "$LLAMA_COMMIT"; then
        _err "git checkout $LLAMA_COMMIT failed (commit reachable?)"
        exit 1
    fi

    # Detect GPU arch from nvidia-smi, else fall back to a broad set.
    ARCH="${GGUF_CUDA_ARCH:-}"
    if [ -z "$ARCH" ]; then
        if command -v nvidia-smi >/dev/null 2>&1; then
            ARCH="$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader \
                    | head -n1 | tr -d ' ')"
            [ -n "$ARCH" ] && ARCH="$(printf '%s' "$ARCH" | sed 's/\.//')"
        fi
        [ -z "$ARCH" ] && ARCH="75;80;86;89"
        _log "detected CUDA compute capability: $ARCH"
    fi

    _log "cmake configure (CUDA arch=$ARCH)"
    if ! cmake -B build -DCMAKE_BUILD_TYPE=Release \
            -DGGML_CUDA=ON \
            -DCMAKE_CUDA_ARCHITECTURES="$ARCH" \
            -DGGML_NATIVE=OFF; then
        _err "cmake configure failed"
        exit 1
    fi

    _log "building ($NPROC jobs)"
    if ! cmake --build build --config Release -j "$NPROC"; then
        _err "build failed"
        exit 1
    fi
)

_log "verifying binaries"
for b in llama-cli llama-completion llama-quantize llama-bench; do
    if [ ! -x "$BUILD_DIR/build/bin/$b" ]; then
        _err "MISSING binary: $b"
        exit 1
    fi
done
"$BUILD_DIR/build/bin/llama-cli" --version

_log "DONE"
