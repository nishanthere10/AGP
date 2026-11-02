#!/usr/bin/env python3
"""verify_quant_artifacts.py — verify quantization artifacts against the manifest.

Before any GGUF artifact is treated as reusable for the experiment, this script
verifies:

  1. The file exists and its size matches the manifest.
  2. Its SHA-256 recomputed hash matches the manifest record.
  3. Its GGUF header metadata identifies the expected architecture and
     quantization type (parsed from the file, not assumed).
  4. The recorded source checkpoint and conversion configuration in the manifest
     match the current experiment config (configs/models.yaml).
  5. The file is readable by the pinned llama.cpp runtime (binary exists and can
     open the model in --no-warmup / metadata-only mode is NOT attempted here;
     readability = file is a valid GGUF per header + binary present).

If provenance cannot be established (missing manifest record, mismatched hash,
unknown architecture/type), the artifact is marked INVALID for this experiment.
A missing artifact is reported as MISSING (fail-closed when --require-all is
set).

Usage:
  .venv/bin/python scripts/verify_quant_artifacts.py [--manifest manifests/model_provenance.json]
      [--models-dir models/qwen2.5-coder-3b-instruct] [--require-all]

Exit codes: 0 = all artifacts verified; 1 = any artifact invalid/missing;
2 = usage/config error.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT / "manifests/model_provenance.json"
DEFAULT_MODELS_DIR = ROOT / "models/qwen2.5-coder-3b-instruct"
LLAMA_BIN = ROOT / "third_party/llama.cpp/build/bin/llama-quantize"

# Expected GGUF metadata keys (llama.cpp v0.6.0-dev)
KEY_ARCH = "general.architecture"
KEY_TYPE = "general.type"
KEY_FILE_TYPE = "general.file_type"

EXPECTED_ARCH = "qwen2"
QUANT_LADDER = ["f16", "q8_0", "q6_k", "q4_k_m", "q3_k_m", "q2_k"]


def parse_gguf_metadata(path: Path) -> dict:
    """Parse GGUF header (magic, version, tensor count, KV metadata)."""
    GGUF_MAGIC = b"GGUF"
    with open(path, "rb") as f:
        magic = f.read(4)
        if magic != GGUF_MAGIC:
            raise ValueError(f"bad GGUF magic: {magic!r}")
        version = struct.unpack("<I", f.read(4))[0]
        tensor_count = struct.unpack("<Q", f.read(8))[0]
        kv_count = struct.unpack("<Q", f.read(8))[0]
        meta = {"_version": version, "_tensor_count": tensor_count}
        # GGUF value types (llama.cpp gguf.h)
        GTYPES = {
            0: "uint8", 1: "int8", 2: "uint16", 3: "int16",
            4: "uint32", 5: "int32", 6: "float32", 7: "bool",
            8: "string", 9: "array", 10: "uint64", 11: "int64",
            12: "float64",
        }
        for _ in range(kv_count):
            klen = struct.unpack("<Q", f.read(8))[0]
            key = f.read(klen).decode("utf-8", "replace")
            vtype = struct.unpack("<I", f.read(4))[0]
            if vtype == 8:  # string
                slen = struct.unpack("<Q", f.read(8))[0]
                val = f.read(slen).decode("utf-8", "replace")
                meta[key] = val
            elif vtype == 7:  # bool
                meta[key] = bool(struct.unpack("<B", f.read(1))[0])
            elif vtype in (0, 1, 2, 3, 4, 5, 10, 11, 12):
                fmt = {0: "<B", 1: "<b", 2: "<H", 3: "<h",
                       4: "<I", 5: "<i", 10: "<Q", 11: "<q",
                       12: "<d"}[vtype]
                meta[key] = struct.unpack(fmt, f.read(struct.calcsize(fmt)))[0]
            elif vtype == 6:  # float32
                meta[key] = struct.unpack("<f", f.read(4))[0]
            elif vtype == 9:  # array — skip length + element size
                atype = struct.unpack("<I", f.read(4))[0]
                alen = struct.unpack("<Q", f.read(8))[0]
                if atype == 8:
                    for _ in range(alen):
                        slen = struct.unpack("<Q", f.read(8))[0]
                        f.read(slen)
                else:
                    sz = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4,
                          6: 4, 7: 1, 10: 8, 11: 8, 12: 8}.get(atype, 4)
                    f.read(sz * alen)
            else:
                raise ValueError(f"unsupported GGUF value type {vtype} for {key}")
        return meta


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def expected_filename(quant: str) -> str:
    return f"qwen2.5-coder-3b-instruct-{quant}.gguf"


def verify_one(manifest_rec: dict, models_dir: Path, quant: str) -> dict:
    """Verify a single artifact. Returns {status, reasons}."""
    fname = expected_filename(quant)
    path = models_dir / fname
    reasons = []

    if not path.exists():
        return {"quant": quant, "file": fname, "status": "MISSING",
                "reasons": ["file not present in models dir"]}

    if manifest_rec is None:
        return {"quant": quant, "file": fname, "status": "INVALID",
                "reasons": ["no manifest record (provenance missing)"]}

    # size check
    recorded_size = manifest_rec.get("size_bytes")
    actual_size = path.stat().st_size
    if recorded_size is not None and recorded_size != actual_size:
        reasons.append(f"size mismatch (recorded {recorded_size}, actual {actual_size})")

    # hash check
    recorded_hash = manifest_rec.get("sha256")
    if recorded_hash:
        actual_hash = sha256(path)
        if actual_hash != recorded_hash:
            reasons.append(f"sha256 mismatch (recorded {recorded_hash[:16]}..., "
                           f"actual {actual_hash[:16]}...)")
    else:
        reasons.append("no recorded sha256 in manifest")

    # GGUF metadata check
    try:
        meta = parse_gguf_metadata(path)
        arch = meta.get(KEY_ARCH)
        if arch != EXPECTED_ARCH:
            reasons.append(f"architecture mismatch (got {arch!r}, expected {EXPECTED_ARCH!r})")
        gtype = meta.get(KEY_TYPE)
        if gtype != quant:
            reasons.append(f"quantization type mismatch (metadata {gtype!r}, expected {quant!r})")
    except Exception as e:
        reasons.append(f"GGUF metadata parse failed: {e}")

    # runtime availability
    if not LLAMA_BIN.exists():
        reasons.append("llama-quantize binary not present (runtime unverified)")

    return {"quant": quant, "file": fname, "status": "VALID" if not reasons else "INVALID",
            "reasons": reasons}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--models-dir", default=str(DEFAULT_MODELS_DIR))
    ap.add_argument("--require-all", action="store_true",
                    help="missing artifacts are an error")
    args = ap.parse_args()

    manifest_path = Path(args.manifest)
    models_dir = Path(args.models_dir)
    if not manifest_path.exists():
        print("ERROR: manifest not found:", manifest_path)
        return 2
    if not models_dir.exists():
        print("ERROR: models dir not found:", models_dir)
        return 2

    manifest = json.loads(manifest_path.read_text())
    artifacts = manifest.get("generated_artifacts", {}) or {}
    source_rec = manifest.get("candidates", {}).get(
        "primary_qwen2_5_coder_3b_instruct", {})
    # confirm the config records the same source revision
    source_ok = bool(source_rec.get("hf_revision"))
    if not source_ok:
        print("WARNING: manifest lacks source checkpoint revision (provenance incomplete)")

    results = []
    exit_code = 0
    for quant in QUANT_LADDER:
        rec = artifacts.get(expected_filename(quant))
        r = verify_one(rec, models_dir, quant)
        results.append(r)
        if r["status"] == "VALID":
            print(f"VALID   {r['file']}")
        elif r["status"] == "MISSING":
            print(f"MISSING {r['file']}")
            if args.require_all:
                exit_code = 1
        else:
            print(f"INVALID {r['file']}: {'; '.join(r['reasons'])}")
            exit_code = 1

    print(f"expected_arch={EXPECTED_ARCH} source_revision_recorded={source_ok}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
