#!/usr/bin/env bash
# quantize_gguf.sh — convert the pinned source checkpoint to F16 + five GGUF
# quantizations from the SAME source, using ONE pinned llama.cpp build.
# Records sha256 of every artifact into manifests/model_provenance.json.
# Run on Kaggle (CUDA llama.cpp) or locally after model acquisition.
set -Eeuo pipefail

_log() { echo "[quant $(date -u +%FT%TZ)] $*"; }
_err() { echo "[quant $(date -u +%FT%TZ)] ERROR: $*" >&2; }
_trap() {
    local rc=$?
    _err "command failed at line $1 (rc=$rc)"
    exit "$rc"
}
trap '_trap $LINENO' ERR

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${1:-}"
QUANT="${2:-Q8_0 Q6_K Q4_K_M Q3_K_M Q2_K}"

if [ -z "$SRC" ]; then
    _err "usage: quantize_gguf.sh <source_model_dir> [Q list]"
    exit 2
fi
if [ ! -d "$SRC" ]; then
    _err "source model dir not found: $SRC"
    exit 2
fi

LLAMA="$ROOT/third_party/llama.cpp"
CONVERT="$LLAMA/convert_hf_to_gguf.py"
QUANTIZE="$LLAMA/build/bin/llama-quantize"
OUT_DIR="$ROOT/models/qwen2.5-coder-3b-instruct"
MANIFEST="$ROOT/manifests/model_provenance.json"

for tool in "$CONVERT" "$QUANTIZE"; do
    if [ ! -e "$tool" ]; then
        _err "required tool missing: $tool (run setup_kaggle.sh first)"
        exit 1
    fi
done

mkdir -p "$OUT_DIR"
_log "output dir: $OUT_DIR"

F16="$OUT_DIR/qwen2.5-coder-3b-instruct-f16.gguf"
if [ -f "$F16" ]; then
    _log "F16 exists, skipping conversion: $F16"
else
    _log "F16 conversion from $SRC"
    python3 "$CONVERT" "$SRC" --outtype f16 --outfile "$F16"
fi

for Q in $QUANT; do
    out="$OUT_DIR/qwen2.5-coder-3b-instruct-$Q.gguf"
    if [ -f "$out" ]; then
        _log "$Q exists, skipping: $out"
        continue
    fi
    _log "quantizing $Q"
    "$QUANTIZE" "$F16" "$out" "$Q" || { _err "quantize $Q failed"; exit 1; }
done

_log "hashing artifacts"
python3 - "$OUT_DIR" "$MANIFEST" <<'PY'
import hashlib, json, pathlib, sys
d = pathlib.Path(sys.argv[1]); mf = pathlib.Path(sys.argv[2])
recs = {}
for p in sorted(d.glob("*.gguf")):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    recs[p.name] = {"size_bytes": p.stat().st_size, "sha256": h.hexdigest()}
    print(p.name, recs[p.name]["sha256"][:16], recs[p.name]["size_bytes"])
data = json.loads(mf.read_text()) if mf.exists() else {}
data.setdefault("generated_artifacts", {}).update(recs)
mf.write_text(json.dumps(data, indent=1))
print("manifest updated:", mf)
PY

_log "DONE"
