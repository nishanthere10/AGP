# Stage 0 — Environment Audit

Date: 2026-10-10
Auditor: AI agent (OpenCode session `ses_ed99914b2ffeeag1bU7SpIK1Eh`)
Execution context: Windows PowerShell (host) invoking `wsl.exe -d Ubuntu -- bash -lc "<script>"`.
Audit scripts: `wsl_audit.sh`, `wsl_audit2.sh`, `wsl_audit3.sh` (run from `/mnt/c/Users/kirti/coding/AGP/`).

All statements below are taken from observed command output. Tests that did not run are marked as such.

## 1. Verified hardware and OS

| Item | Observed value | Source |
|---|---|---|
| Host OS (reported) | Windows `10.0.26200.9550` (from task brief; not re-verified by agent) | brief |
| WSL distro | `Ubuntu`, WSL version 2, state `Stopped` before first command | `wsl.exe -l -v` |
| WSL default distro | `Ubuntu` (also `docker-desktop` present, version 2, stopped) | `wsl.exe -l -v` |
| Distro release | **Ubuntu 26.04.1 LTS (Resolute Raccoon)** | `/etc/os-release` |
| Kernel | `6.6.87.2-microsoft-standard-WSL2 #1 SMP PREEMPT_DYNAMIC Thu Jun 5 18:30:46 UTC 2025 x86_64` | `uname -a` |
| CPU | 12th Gen Intel Core i5-1235U, 1 socket, 6 cores / 12 threads (12 logical CPUs online) | `lscpu` |
| Relevant CPU features | `avx avx2 avx_vnni` present; `avx512f` **not** present in flags list | `/proc/cpuinfo` |
| Virtualization | Hypervisor: Microsoft, VT-x | `lscpu` |
| Physical RAM (Windows, brief) | 7.68 GB | brief |
| WSL visible RAM | total **3.7 GiB**, available 3.2 GiB at audit time | `free -h` |
| WSL swap | **1.0 GiB**, 0 B used at audit time | `free -h` |
| WSL RAM limit source | No `.wslconfig` found at `/mnt/c/Users/kirti/.wslconfig` (`cat: No such file or directory`) → default WSL2 memory allocation is in effect. Not modified. | `cat /mnt/c/Users/kirti/.wslconfig` |
| Root filesystem (`/dev/sdd`) | 1007 G total, **954 G available** | `df -h /` |
| Windows C: via `/mnt/c` | 476 G total, 67 G available (87% used) | `df -h /mnt/c` |

Notes:
- The i5-1235U has 2 P-cores + 8 E-cores (lscpu reports 6 "cores" with HT; the model line is authoritative for the SKU). For build parallelism we use `-j2` per brief, and for inference we will measure thread settings explicitly.
- WSL sees only 3.7 GiB RAM despite 7.68 GiB physical: WSL2 default is ~50% of host memory. This is the binding constraint for model loading.

## 2. Build tools and package state

| Tool | Status | Version / evidence |
|---|---|---|
| `python3` | present | `Python 3.14.4` (`/usr/bin/python3`) |
| `python3 -m venv` module | **BROKEN** | venv creation fails: `ensurepip is not available ... apt install python3.14-venv`. dpkg: `python3-venv` and `python3.14-venv` are `un` (uninstalled). |
| `pip3` | MISSING | `command -v pip3` → not found |
| `git` | present | `2.53.0` |
| `cmake` | **MISSING** | `command not found`; dpkg: no package |
| `gcc` / `g++` / `make` | **MISSING** | `command not found`; dpkg `build-essential`: no package found |
| `pkg-config` | MISSING | not found (needed by some llama.cpp build paths; will verify at build time) |
| `curl` | present | `curl 8.18.0`, OpenSSL 3.5.5 |
| `sha256sum` | present | `/usr/bin/sha256sum` |
| `bwrap` | present | **bubblewrap 0.11.1** (`0.11.1-1ubuntu0.3` per dpkg) |
| `unshare` | present | `/usr/bin/unshare` |
| GNU `/usr/bin/time` | present | `time (GNU Time) UNKNOWN` (package-provided binary exists at `/usr/bin/time`) |
| `ca-certificates` | present | `20260601~26.04.1` |

`dpkg-query` results: `bubblewrap`, `ca-certificates`, `curl`, `git` INSTALLED; `build-essential`, `cmake`, `python3-venv` NOT installed.

## 3. Python and virtual-environment status

- System Python: **3.14.4** (Ubuntu 26.04 default).
- `python3 -m venv /tmp/.../venv` **failed** with `ensurepip is not available`; recommended fix is `apt install python3.14-venv`.
- Consequence: a project virtual environment cannot be created until `python3.14-venv` is installed. System Python must not be modified (per operating rules).
- Windows Python 3.13.3 / Windows Git 2.50.0 are host-side and were not used for any Linux work.

## 4. Memory and disk limits

- WSL total RAM: 3.7 GiB; available: 3.2 GiB at idle; swap 1 GiB (0 used).
- Root FS: 954 G free → disk is not a constraint for the 1.12 GB model + llama.cpp build.
- `/mnt/c`: 67 G free; avoid using it for build/model work per operating rules.
- No `.wslconfig` present → allocation is stock. **No memory changes will be made without explicit approval.**

## 5. Namespace / sandbox prerequisites

| Test | Result |
|---|---|
| `cat /proc/sys/user/max_user_namespaces` | `14965` (non-zero → namespaces enabled) |
| `unshare -Ur true` | **OK (rc=0)** |
| `unshare -Un true` | **OK (rc=0)** |
| `unshare -rm true` | **OK (rc=0)** |
| `apparmor_restrict_unprivileged_userns` | file not present (n/a on this kernel/config) → no AppArmor userns restriction observed |
| `bwrap --version` | `0.11.1` |

Conclusion: unprivileged user + mount + pid namespaces work in this WSL2 instance, and Bubblewrap is installed. Full sandbox validation (mounts, network, write restrictions, timeout) deferred to Stage 5.

## 6. Other observations

- User `aaksh` (uid 1000) is in group `sudo`, but `sudo -n true` requires interactive authentication → **system package installation will need the user's password / interactive approval** (requested separately; not attempted).
- Network: `https://github.com` → HTTP 200; `https://huggingface.co` → HTTP 200 (from inside Ubuntu). Model download and clone are feasible.
- `~/projects/LocalAgentBench` did **not** exist before this session (`ls: cannot access`). No pre-existing work was overwritten.
- No pre-existing `llama.cpp` checkout or `*.gguf` files found under `/home/aaksh` (maxdepth 4).
- Docker Desktop WSL distro exists but is stopped; not used (Docker infrastructure out of scope).

## 7. Missing dependencies (must be resolved in Stage 1)

1. `build-essential` (gcc, g++, make) — required to compile llama.cpp.
2. `cmake` — required by llama.cpp build system.
3. `python3.14-venv` — required for isolated project virtualenv.
4. Possibly `pkg-config` — verify at build time.
5. `bubblewrap` already present → no install needed.

All four missing items require `sudo apt install`, which needs interactive approval (Stage 1 gate).

## 8. Identified risks

1. **Memory (highest risk):** 3.7 GiB WSL RAM / 1 GiB swap vs 1.12 GB model file → GGUF q4_k_m weights ≈ 1.1 GB resident + KV cache + compute buffers at 2k–4k context. Tight but plausible; must measure, not assume. OOM during build (`-j` too high) or inference is likely if careless — use `-j2` build and start inference at small context.
2. **Python 3.14 bleeding-edge:** some PyPI packages may lack cp314 wheels. Mitigation: stdlib-first scripts; if a dependency is incompatible, use an isolated alternative Python (uv-managed) inside the project only.
3. **CPU heterogeneity (P/E cores):** thread placement can distort benchmark variance; record `-t` settings and repeat ≥3 times.
4. **Sandbox is not a security policy:** Bubblewrap validates namespace/mount behavior only; test oracle must live outside the writable sandbox view (Stage 5/7 design constraint).
5. **Host filesystem exposure:** WSL can see `/mnt/c`; the sandbox must not expose it.
6. **No `.wslconfig`:** if OOM occurs we must stop and present options rather than editing it.

## 9. Exact commands used

Executed from PowerShell on the host (each line is a full host command):

```powershell
wsl.exe -l -v
wsl.exe --status
wsl.exe -d Ubuntu -- bash -lc "cat /etc/os-release; uname -a"
wsl.exe -d Ubuntu -- bash -lc "lscpu; echo ---; free -h; echo ---; df -h / /mnt/c"
wsl.exe -d Ubuntu -- bash -lc "bash /mnt/c/Users/kirti/coding/AGP/wsl_audit.sh 2>&1"
wsl.exe -d Ubuntu -- bash -lc "bash /mnt/c/Users/kirti/coding/AGP/wsl_audit2.sh 2>&1"
wsl.exe -d Ubuntu -- bash -lc "bash /mnt/c/Users/kirti/coding/AGP/wsl_audit3.sh 2>&1"
wsl.exe -d Ubuntu -- bash -lc "mkdir -p ~/projects/LocalAgentBench/{models,third_party,scripts,reports,results} && cd ~/projects/LocalAgentBench && git init"
```

The three audit scripts contain, respectively: os-release/uname/lscpu/free/df/tool inventory/versions/venv test/namespace tests/dpkg state; python3-venv dpkg detail + live venv creation test + sudo test + AVX flags + `.wslconfig` check + GNU time check; uid/groups/project-dir check + pre-existing llama.cpp/model search + network reachability check.

## 10. Gate 1 status

**Gate 1 (Environment): NOT YET PASSED.** The audit is complete, the project workspace exists, but the build toolchain (`build-essential`, `cmake`) and `python3.14-venv` are missing and require `sudo` with interactive approval. Gate 1 passes once those are installed and verified (Stage 1).
