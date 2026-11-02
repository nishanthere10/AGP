# Stage 5 — Bubblewrap Sandbox Validation

Date: 2026-10-10
Status: **READY for controlled coding experiments, with documented limitations** (13/13 probes passed)
This does **not** constitute an absolute security guarantee (see Limitations).

## Environment

| Item | Value |
|---|---|
| Bubblewrap | `0.11.1` (`0.11.1-1ubuntu0.3`) |
| Distribution | Ubuntu 26.04.1 LTS |
| Kernel | `6.6.87.2-microsoft-standard-WSL2` |
| Namespaces | `unshare -Ur`, `-Un`, `-rm` all rc=0 (Stage 0); `max_user_namespaces=14965` |
| AppArmor userns restriction | not present on this kernel |
| Setuid mode | not used (removed upstream); pure user-namespace mode |

## Official position (from containers/bubblewrap README, fetched 2026-10-10)

- "bubblewrap is not a complete, ready-made sandbox with a specific security policy… the level of protection … is entirely determined by the arguments passed to bubblewrap."
- Mitigations bwrap provides: `PR_SET_NO_NEW_PRIVS`, own mount/user/pid/ipc/uts/net namespaces.
- Requirement noted: without seccomp filtering of `TIOCSTI`, `--new-session` is required (CVE-2017-5226) → **our wrapper passes `--new-session`**.

## Sandbox configuration

Wrapper: `scripts/sandbox.sh <host_writable_dir> <cmd…>`

Policy implemented by the wrapper (not by bwrap itself):

- `--unshare-all` → user, mount, pid, ipc, uts, **net** namespaces (net = fresh namespace, loopback only, no external connectivity)
- Root = empty tmpfs; `/usr`, `/bin`, `/sbin`, `/lib`, `/lib64` **read-only** binds
- `/proc` fresh; minimal `/dev`; selected `/etc` files ro (`ld.so.cache`, `ld.so.conf*`, `alternatives`, `python3`)
- **Only one writable host-backed path**: caller-provided dir → `/tmp/work` (also `$HOME`)
- Oracle/evaluator paths are **never mounted** (they don't appear in the argument list at all)
- `--new-session`, `--die-with-parent`, `--hostname sandbox`, `--chdir /tmp/work`, `PATH=/usr/local/bin:/usr/bin:/bin`

Probe suite: `scripts/sandbox_test.sh` (harmless commands only; disposable files).

## Test results (all executed; raw output observed in session)

| # | Check | Result | Evidence |
|---|---|---|---|
| T1 | Permitted Python command executes | **PASS** | `python3 -c 'print(2+2)'` → `PY_OK 4` |
| T2 | Filesystem visibility restricted | **PASS** | `/home` does not exist inside; host secret file unreadable (`No such file`); root listing = `bin dev etc lib lib64 proc sbin tmp usr` |
| T3a | Write to ro path `/usr` rejected | **PASS** | `cannot create /usr/truth.txt: Read-only file system`, rc=2 |
| T3b | Write to oracle path rejected | **PASS** | oracle dir not mounted: `Directory nonexistent`, rc=2; probe executed (bwrap rc=0), not a false pass |
| T4 | Designated writable tmp works | **PASS** | write `/tmp/work/x.txt` → `sandbox-data`, persisted to host dir |
| T5a | Outbound TCP blocked | **PASS** | `connect 1.1.1.1:80` → `NET_BLOCKED: OSError` |
| T5b | DNS/HTTPS blocked | **PASS** | `urlopen(https://example.com)` → `NET_BLOCKED: URLError` |
| T6 | Parent timeout kills long command | **PASS** | `timeout 3 sandbox sleep 30` → rc=124 at 3 s, no leftover `sleep 30` process |
| T7 | No files outside workspace | **PASS** | write landed in designated dir; `find` found no leaked `x.txt`/`result.txt` outside probe dirs |
| T8 | Oracle integrity on host | **PASS** | `truth.txt` content unchanged after all probes |
| T9 | Inspect effective sandbox view | done | mountinfo, pid list, id, netdevs, hostname captured (see below) |

First run of the suite **failed** (`bwrap: Can't make symlink at /bin`) because the wrapper both bound `/bin` and tried to create a symlink there; the redundant symlinks were removed (Ubuntu is merged-usr: `/bin`→`usr/bin`) and `/lib`,`/lib64` are now explicit ro-binds. A false-pass weakness in T3 (empty output counted as rejection) was also fixed so the probe must prove it executed. Re-run: 13/13 PASS.

## Effective sandbox view (T9 observations)

- Root: `tmpfs rw` (empty, invisible to host, auto-cleaned on exit).
- `/usr` ro-bind; `/bin`,`/sbin`,`/lib`,`/lib64` ro-binds of the host usr tree.
- `/tmp/work` = rw-bind of the caller dir; everything else under `/tmp` is tmpfs.
- Only sandbox-local PIDs visible (1, 2, 5, 6).
- `uid=1000` with no name (no `/etc/passwd` mounted — expected).
- `ls /sys/class/net` → **empty**: no interfaces in the new net namespace (loopback exists but is down/unconfigured).
- `hostname` → `sandbox`.

## Known limitations

1. **Not a security policy by itself** — protection is exactly what `scripts/sandbox.sh` declares. It must be reviewed whenever changed.
2. **No seccomp filter** — `--new-session` mitigates TIOCSTI, but syscall-level filtering is absent. Kernel exploit surface (the WSL kernel itself) is out of our control.
3. **WSL driver mounts visible**: `/usr/lib/wsl/drivers` and `/usr/lib/wsl/lib` (Microsoft GPU/driver 9p/overlay mounts) are inherited under the ro `/usr` bind (visible in mountinfo). They are **read-only** and 9p/overlay, not host-writable data, but a strict policy would mask them (e.g. `--tmpfs /usr/lib/wsl`). Not done yet — noted as hardening TODO.
4. **Same uid inside and out** — code runs as uid 1000; any host path accidentally bind-mounted rw would be writable with the user's full permissions. Mitigation: never pass other host dirs as the writable arg; keep the oracle unmounted (tested).
5. **No resource limits yet** — memory/CPU/pids limits (cgroup v2 delegation availability in WSL not verified) are not applied; timeouts are enforced by the parent (`timeout`), tested in T6. A fork-bomb inside the sandbox could still pressure the 3.7 GiB WSL RAM. Hardening TODO: `ulimit` wrapper or cgroup.
6. **File descriptors / proc trickery / DoS** not tested. Tests not completed: seccomp enforcement, cgroup limits, `/proc` masking beyond default, multi-process persistence attempts.
7. **Model-generated code has not been executed yet** — correct per rules; this stage used harmless probes only.

## Verdict

Namespace, filesystem, write-restriction, network and timeout behavior were demonstrated with executed probes, including the specific invariant the benchmark needs: **the ground-truth oracle is not reachable (not mounted) and not writable from inside the sandbox, while the candidate workspace is writable and single-hop.**

Sandbox: **READY** for controlled coding experiments, subject to the limitations above. Ready does not mean absolutely secure.
