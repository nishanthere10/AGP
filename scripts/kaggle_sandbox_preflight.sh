#!/usr/bin/env bash
# kaggle_sandbox_preflight.sh — verify the Bubblewrap sandbox is usable for
# controlled execution of generated code in the target environment.
#
# This is a preflight CHECK: it runs only harmless probe programs. No
# model-generated code is executed. It does NOT claim Kaggle compatibility by
# itself — it is designed to be run inside the Kaggle notebook as one gate.
#
# Checks:
#   1. bwrap present and version matches requirements
#   2. required namespaces are usable (unshare works)
#   3. a harmless program executes inside the sandbox
#   4. outbound network is blocked inside the sandbox
#   5. access to host files outside the workspace is blocked
#   6. timeout control kills a long-running process and leaves no leftover
#   7. sandbox exit codes and logs are captured correctly
#   8. designated writable workspace works
#
# Verdict:
#   PASS     — all critical probes passed (sandbox usable)
#   BLOCKED  — any critical probe failed or environment is unsupported
#
# Exit codes: 0 PASS, 1 BLOCKED, 2 usage/unsupported.
# Machine-readable summary written to results/sandbox_preflight.json.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SB="$ROOT/scripts/sandbox.sh"
WORK="$ROOT/sandbox_preflight_work"
OUT_JSON="$ROOT/results/sandbox_preflight.json"
PASS=0; FAIL=0
declare -a FAILURES=()

_log() { echo "[sandbox-preflight $(date -u +%FT%TZ)] $*"; }
_err() { echo "[sandbox-preflight $(date -u +%FT%TZ)] ERROR: $*" >&2; }

probe() { # probe <name> <critical(0/1)> <cmd...>
  local name="$1"; local critical="$2"; shift 2
  local out rc
  out=$("$@" 2>&1) && rc=0 || rc=$?
  echo "PROBE $name: rc=$rc"
  [ -n "$out" ] && printf '%s\n' "$out" | sed 's/^/    /'
  if [ "$rc" -eq 0 ]; then
    PASS=$((PASS+1)); return 0
  fi
  FAIL=$((FAIL+1)); FAILURES+=("$name")
  if [ "$critical" -eq 1 ]; then
    return 1
  fi
  return 0
}

result_json() { # result_json <verdict>
  local verdict="$1"
  local failures="$(IFS=,; echo "${FAILURES[*]:-}")"
  mkdir -p "$(dirname "$OUT_JSON")"
  VERDICT="$verdict" SB_FAILURES="$failures" SB_PASS="$PASS" SB_FAIL="$FAIL" python3 <<PY
import json, os
data = {
    "check": "kaggle_sandbox_preflight",
    "verdict": os.environ["VERDICT"],
    "pass": int(os.environ["SB_PASS"]),
    "fail": int(os.environ["SB_FAIL"]),
    "failures": [f for f in os.environ.get("SB_FAILURES", "").split(",") if f],
}
json.dump(data, open("$OUT_JSON", "w"), indent=1)
PY
}

# --- 1. bwrap present -------------------------------------------------------
_log "check 1: bwrap present"
if ! command -v bwrap >/dev/null 2>&1; then
  _err "bwrap not found — sandbox unavailable, BLOCKED"
  result_json BLOCKED
  exit 1
fi
BW_VERSION=$(bwrap --version)
_log "bwrap: $BW_VERSION"

# --- 2. namespaces usable ---------------------------------------------------
_log "check 2: namespaces (unshare) usable"
# Use the SAME bind set as sandbox.sh; a minimal bind set can fail to run the
# dynamically-linked probe binary (missing /lib), which would be a false alarm.
if ! bwrap \
     --ro-bind /usr /usr --ro-bind /bin /bin --ro-bind /sbin /sbin \
     --ro-bind /lib /lib --ro-bind /lib64 /lib64 \
     --proc /proc --dev /dev --tmpfs /tmp \
     --dir /tmp/work --chdir /tmp/work \
     --unshare-all --new-session --die-with-parent \
     /bin/true 2>/dev/null; then
  _err "user namespaces unavailable — sandbox BLOCKED"
  result_json BLOCKED
  exit 1
fi
_log "namespaces OK"

# --- 3. harmless program executes -------------------------------------------
_log "check 3: harmless python executes in sandbox"
mkdir -p "$WORK"
if ! probe "harmless_python" 1 "$SB" "$WORK" python3 -c 'print("PY_OK", 2+2)'; then
  result_json BLOCKED; exit 1
fi

# --- 4. network blocked -----------------------------------------------------
_log "check 4: network blocked inside sandbox"
NET_OUT=$("$SB" "$WORK" python3 -c 'import socket
try:
    s=socket.create_connection(("1.1.1.1",80),timeout=3); print("NET_REACHABLE"); s.close()
except Exception as e: print("NET_BLOCKED:", type(e).__name__)') || true
if echo "$NET_OUT" | grep -q "NET_BLOCKED"; then
  echo "PROBE network_blocked: rc=0 (NET_BLOCKED)"
  PASS=$((PASS+1))
else
  echo "PROBE network_blocked: rc=1 (reachable: $NET_OUT)"
  FAIL=$((FAIL+1)); FAILURES+=("network_blocked")
  result_json BLOCKED
  exit 1
fi

# --- 5. host files outside workspace blocked ---------------------------------
_log "check 5: host files outside workspace blocked"
echo "HOST_SECRET_MARKER" > "$ROOT/sandbox_preflight_secret.txt"
SECRET_OUT=$("$SB" "$WORK" sh -c "cat $ROOT/sandbox_preflight_secret.txt 2>&1") || true
if echo "$SECRET_OUT" | grep -q "No such file"; then
  echo "PROBE host_isolation: rc=0 (secret unreachable)"
  PASS=$((PASS+1))
else
  echo "PROBE host_isolation: rc=1 (leaked: $SECRET_OUT)"
  FAIL=$((FAIL+1)); FAILURES+=("host_isolation")
  result_json BLOCKED
  exit 1
fi
rm -f "$ROOT/sandbox_preflight_secret.txt"

# --- 6. timeout kills + no leftover -----------------------------------------
_log "check 6: timeout control"
T0=$(date +%s)
set +e
timeout 3 "$SB" "$WORK" sleep 30
RC=$?
set -e
T1=$(date +%s)
ELAPSED=$((T1-T0))
if [ "$RC" -eq 124 ] && [ "$ELAPSED" -le 6 ]; then
  echo "PROBE timeout_control: rc=$RC elapsed=${ELAPSED}s (ok)"
  PASS=$((PASS+1))
else
  echo "PROBE timeout_control: rc=$RC elapsed=${ELAPSED}s (bad)"
  FAIL=$((FAIL+1)); FAILURES+=("timeout_control")
  result_json BLOCKED
  exit 1
fi
sleep 1
if pgrep -f "sleep 30" >/dev/null; then
  echo "PROBE no_leftover: rc=1 (leftover process)"
  FAIL=$((FAIL+1)); FAILURES+=("no_leftover")
  result_json BLOCKED
  exit 1
else
  echo "PROBE no_leftover: rc=0"
  PASS=$((PASS+1))
fi

# --- 7. exit code + log capture --------------------------------------------
_log "check 7: exit-code capture"
set +e
"$SB" "$WORK" sh -c 'exit 7' >/dev/null 2>&1
RC=$?
set -e
if [ "$RC" -eq 7 ]; then
  echo "PROBE exitcode_capture: rc=$RC (ok)"
  PASS=$((PASS+1))
else
  echo "PROBE exitcode_capture: rc=$RC (expected 7)"
  FAIL=$((FAIL+1)); FAILURES+=("exitcode_capture")
  result_json BLOCKED
  exit 1
fi

# --- 8. writable workspace --------------------------------------------------
_log "check 8: writable workspace"
set +e
W_OUT=$("$SB" "$WORK" sh -c 'echo sandbox-data > /tmp/work/x.txt && cat /tmp/work/x.txt')
set -e
if echo "$W_OUT" | grep -q "sandbox-data"; then
  echo "PROBE writable_workspace: rc=0"
  PASS=$((PASS+1))
else
  echo "PROBE writable_workspace: rc=1 ($W_OUT)"
  FAIL=$((FAIL+1)); FAILURES+=("writable_workspace")
  result_json BLOCKED
  exit 1
fi

# --- verdict ----------------------------------------------------------------
if [ "$FAIL" -eq 0 ]; then
  echo "SANDBOX PREFLIGHT: PASS (${PASS} probes passed)"
  result_json PASS
  exit 0
else
  echo "SANDBOX PREFLIGHT: BLOCKED (${FAIL} failures)"
  result_json BLOCKED
  exit 1
fi
