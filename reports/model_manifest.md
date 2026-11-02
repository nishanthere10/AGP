# Stage 3 — Model Manifest

Date: 2026-10-10
Verification status: **PASSED** (byte-exact SHA-256 match against Hugging Face LFS metadata)

## Source

| Field | Value |
|---|---|
| Official repository | `https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF` |
| Publisher | Qwen (Alibaba Cloud) |
| Base model | `Qwen/Qwen2.5-Coder-1.5B-Instruct` |
| Repository revision used for download | `f86cb2c1fa58255f8052cc32aeede1b7482d4361` (HEAD of `main` at audit time, `lastModified` 2024-11-12) |
| File's last commit | `2ab9f8f42af02fc212effaef7c4850c885e965f4` ("upload weights", 2024-09-18) |
| License | **Apache-2.0** (`LICENSE` file present in repo; `cardData.license: apache-2.0`) |
| GGUF architecture | `qwen2`, native context length 32768 |

## File

| Field | Value |
|---|---|
| File name | `qwen2.5-coder-1.5b-instruct-q4_k_m.gguf` |
| Pinned download URL | `https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/f86cb2c1fa58255f8052cc32aeede1b7482d4361/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf` |
| Local path | `~/projects/LocalAgentBench/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf` |
| Published size (HF API `lfs.size`) | 1,117,320,768 bytes (~1.04 GiB) |
| Actual local size (`ls -la`) | **1,117,320,768 bytes — matches** |
| Published SHA-256 (HF API `lfs.oid`) | `cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046` |
| Expected SHA-256 (task brief) | `cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046` |
| Computed SHA-256 (`sha256sum`) | **`cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046` — MATCH** |

## Verification result

- Metadata was fetched live from `https://huggingface.co/api/models/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF` and the file-tree API before downloading; the current published LFS oid equals the expected hash in the task brief. The repository had not changed.
- Download performed with `curl -L -C - --fail --retry 3` (resumable) pinned to the revision SHA above.
- Post-download `sha256sum` was executed and inspected; output shown above.
- File size matches the published size exactly (no truncation).
- **Integrity: VERIFIED. No mirror used. No redownload needed.**

## Storage

- Location: WSL ext4 filesystem (`~/projects/LocalAgentBench/models/`), not under `/mnt/c`.
- Excluded from Git via `.gitignore` rule `models/` and `*.gguf`.
- Only one model downloaded, per operating rules.

## Commands used

```bash
curl -L -C - --fail --retry 3 --retry-delay 5 -o qwen2.5-coder-1.5b-instruct-q4_k_m.gguf \
  'https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/f86cb2c1fa58255f8052cc32aeede1b7482d4361/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf'
ls -la qwen2.5-coder-1.5b-instruct-q4_k_m.gguf   # -> 1117320768 bytes
sha256sum qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
```
