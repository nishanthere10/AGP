# Stage 2 — llama.cpp Build Report

Date: 2026-10-10
Status: **SUCCESS**

## Repository

| Field | Value |
|---|---|
| URL | `https://github.com/ggml-org/llama.cpp` (official; task-specified) |
| Clone method | `git clone --depth 1` into `third_party/llama.cpp` |
| Commit SHA | **`aa94f2086147cd4bfbcff818ce998dffce5fcb39`** (2026-10-10, "args: add LLAMA_ARG_SLOT_SAVE_PATH env for --slot-save-path (#30272)") |
| ggml version | `0.26.0` |
| Prior presence | None — no existing checkout found anywhere under `/home/aaksh` (Stage 0 `find`); fresh clone |

## Toolchain

| Tool | Version |
|---|---|
| Compiler | `gcc (Ubuntu 15.2.0-16ubuntu1) 15.2.0`, `g++ 15.2.0` |
| CMake | `4.2.3` |
| Make | `4.4.1` (generator: Unix Makefiles) |
| OpenMP | found, 4.5 |
| Build host | Ubuntu 26.04.1 LTS / WSL2, x86_64, i5-1235U (AVX2/AVX-VNNI, no AVX-512) |

## Build configuration (from configure log)

Docs consulted: `docs/build.md` at the cloned commit (CPU Build section: `cmake -B build` + `cmake --build build --config Release`).

```
cmake -B build -DCMAKE_BUILD_TYPE=Release      # configure: rc=0, 13.1s
cmake --build build --config Release -j 2      # build: rc=0
```

Observed configure facts (raw log: `reports/llama_cpp_cmake_configure.log`):

- `Including CPU backend` → **CPU only; no CUDA/Vulkan/SYCL/Metal targets configured**
- `Adding CPU backend variant ggml-cpu: -march=native` (AVX2-family code paths)
- `Found OpenMP: TRUE (found version 4.5)`
- Warning only: OpenSSL not found → server HTTPS disabled (HTTP fine; irrelevant for localhost benchmark)
- Warning only: ccache not found (no effect on correctness)

## Result

- **Build: SUCCESS**, `BUILD_RC=0`.
- Build time: **21 m 19.5 s wall**, 36 m 39.9 s user, 4 m 28.7 s sys (`time` output at end of `reports/llama_cpp_build.log`).
- Memory: no OOM, no swap-out events observed; WSL stayed ≥2.6 GiB available during build (spot-checked `free -h` at 70 %: 1.0 GiB used / 2.6 GiB available). `-j2` was sufficient and safe.

## Binaries (all under `third_party/llama.cpp/build/bin/`)

| Binary | Status | Verification |
|---|---|---|
| `llama-cli` | built (1,324,640 B) | `--version` → `version: 0.6.0-dev (build 1, commit aa94f20)`, GNU 15.2.0 |
| `llama-server` | built (17,872 B stub + `libllama-server-impl.so`) | `--version` → same version line |
| `llama-bench` | built (17,872 B stub + `libllama-bench-impl.so`) | `--version` → same version line |
| `llama-quantize`, tests | built | `[100%] Built target …` in log |

The small size of `llama-server`/`llama-bench` is expected at this commit: the main code lives in `libllama-*-impl.so` loaded at runtime (confirmed via `file` + `--version` output).

## Raw logs

- `reports/llama_cpp_cmake_configure.log` (configure output)
- `reports/llama_cpp_build.log` (full build output, 100 %, timing footer)

## Issues encountered

- First `apt-get install` attempt failed with `404 Not Found` for `libarchive13t64` (stale apt index). Fixed with `apt-get update` (index refresh only, not a system upgrade) and retried — success. Recorded here because it was a real failure, not skipped.
- No build failures, no retries, no reduced-job rebuilds needed.
