#!/usr/bin/env bash
# sandbox.sh — Bubblewrap wrapper for LocalAgentBench controlled code execution.
#
# Isolation policy (what THIS wrapper implements — bwrap itself has no policy):
#   - New user, mount, pid, ipc, uts, net namespaces (network: loopback only, down)
#   - Root fs is an empty tmpfs; only /usr, /bin, /sbin, /lib* ro-bound from host
#   - /proc (fresh), /dev (minimal) provided
#   - Host /home, /mnt (incl. /mnt/c), /etc (not needed) NOT visible
#   - One writable dir: /tmp/work, bind-mounted to the caller-provided host dir
#     (first argument must be the host workspace dir to expose as /tmp/work)
#   - PR_SET_NO_NEW_PRIVS on; --new-session (TIOCSTI/CVE-2017-5226 mitigation)
#   - Oracle/evaluator paths are never mounted.
#
# Usage: sandbox.sh <host_writable_dir> <command> [args...]
set -eu

HOST_WORK="$1"; shift
[ -d "$HOST_WORK" ] || { echo "sandbox.sh: not a dir: $HOST_WORK" >&2; exit 64; }

exec bwrap \
  --ro-bind /usr /usr \
  --ro-bind /bin /bin \
  --ro-bind /sbin /sbin \
  --ro-bind /lib /lib \
  --ro-bind /lib64 /lib64 \
  --proc /proc \
  --dev /dev \
  --tmpfs /tmp \
  --dir /tmp/work \
  --bind "$HOST_WORK" /tmp/work \
  --dir /etc \
  --ro-bind /etc/alternatives /etc/alternatives \
  --ro-bind /etc/ld.so.cache /etc/ld.so.cache \
  --ro-bind /etc/ld.so.conf /etc/ld.so.conf \
  --ro-bind /etc/ld.so.conf.d /etc/ld.so.conf.d \
  --ro-bind /etc/python3 /etc/python3 \
  --ro-bind /etc/localtime /etc/localtime \
  --setenv PATH /usr/local/bin:/usr/bin:/bin \
  --setenv HOME /tmp/work \
  --unshare-all \
  --new-session \
  --die-with-parent \
  --hostname sandbox \
  --chdir /tmp/work \
  "$@"
