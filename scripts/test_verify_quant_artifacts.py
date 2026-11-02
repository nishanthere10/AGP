#!/usr/bin/env python3
"""Regression tests for verify_quant_artifacts.py.

Uses synthetic GGUF files built in-memory (valid header + metadata) so no real
model artifacts are required.
"""
import importlib.util
import json
import struct
import sys
import tempfile
from pathlib import Path

ROOT = Path("/home/aaksh/projects/LocalAgentBench")
spec = importlib.util.spec_from_file_location("vq", ROOT / "scripts/verify_quant_artifacts.py")
vq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vq)

FAILED = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILED.append(name)


def make_gguf(path: Path, arch: str, gtype: str):
    """Write a minimal but structurally valid GGUF header."""
    def _kv(key: str, val: str) -> bytes:
        kb = key.encode()
        vb = val.encode()
        return (struct.pack("<Q", len(kb)) + kb
                + struct.pack("<I", 8)          # type string
                + struct.pack("<Q", len(vb)) + vb)
    body = b"GGUF" + struct.pack("<I", 3)        # version 3
    body += struct.pack("<Q", 1)                 # tensor count
    body += struct.pack("<Q", 2)                 # kv count
    body += _kv("general.architecture", arch)
    body += _kv("general.type", gtype)
    path.write_bytes(body)


def sha256(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()


with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    models = td / "models"
    models.mkdir()

    # VALID artifact: correct arch + type, matching manifest
    fn = "qwen2.5-coder-3b-instruct-q4_k_m.gguf"
    make_gguf(models / fn, "qwen2", "q4_k_m")
    rec = {"size_bytes": (models / fn).stat().st_size, "sha256": sha256(models / fn)}
    r = vq.verify_one(rec, models, "q4_k_m")
    check("VALID artifact accepted", r["status"] == "VALID" and not r["reasons"])

    # INVALID: hash mismatch (tamper after recording)
    tampered = models / fn
    rec2 = {"size_bytes": tampered.stat().st_size, "sha256": "0" * 64}
    r = vq.verify_one(rec2, models, "q4_k_m")
    check("hash mismatch -> INVALID", r["status"] == "INVALID")

    # INVALID: no manifest record (provenance missing)
    r = vq.verify_one(None, models, "q4_k_m")
    check("no manifest record -> INVALID", r["status"] == "INVALID")

    # MISSING: file absent
    r = vq.verify_one(rec, models, "q2_k")
    check("absent file -> MISSING", r["status"] == "MISSING")

    # INVALID: wrong quantization type in metadata
    fn2 = "qwen2.5-coder-3b-instruct-q6_k.gguf"
    make_gguf(models / fn2, "qwen2", "q4_k_m")   # metadata says q4_k_m, file name q6_k
    rec3 = {"size_bytes": (models / fn2).stat().st_size, "sha256": sha256(models / fn2)}
    r = vq.verify_one(rec3, models, "q6_k")
    check("type mismatch -> INVALID", r["status"] == "INVALID")

    # INVALID: wrong architecture
    fn3 = "qwen2.5-coder-3b-instruct-f16.gguf"
    make_gguf(models / fn3, "llama", "f16")
    rec4 = {"size_bytes": (models / fn3).stat().st_size, "sha256": sha256(models / fn3)}
    r = vq.verify_one(rec4, models, "f16")
    check("arch mismatch -> INVALID", r["status"] == "INVALID")

    # INVALID: not GGUF at all
    fn4 = "qwen2.5-coder-3b-instruct-q8_0.gguf"
    (models / fn4).write_bytes(b"not a gguf file" + b"\0" * 64)
    rec5 = {"size_bytes": (models / fn4).stat().st_size, "sha256": sha256(models / fn4)}
    r = vq.verify_one(rec5, models, "q8_0")
    check("non-GGUF -> INVALID", r["status"] == "INVALID")


def main() -> int:
    if FAILED:
        print("\n%d FAILED: %s" % (len(FAILED), FAILED))
        return 1
    print("\nALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
