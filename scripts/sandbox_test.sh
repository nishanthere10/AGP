#!/usr/bin/env bash
# Stage 5: Bubblewrap sandbox validation with harmless probes.
# All probes are harmless; nothing model-generated is executed here.
set -u

ROOT=/home/aaksh/projects/LocalAgentBench
WORK=$ROOT/sandbox_probe          # host-side workspace (model-writable equivalent)
ORACLE=$ROOT/sandbox_probe_oracle # host-side read-only oracle dir (evaluator tests)
SB="$ROOT/scripts/sandbox.sh"
W=$WORK/writable
PASS=0; FAIL=0
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
bad()  { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

rm -rf "$WORK" "$ORACLE"
mkdir -p "$W" "$ORACLE"
echo "ORACLE_DATA_DO_NOT_MODIFY" > "$ORACLE/truth.txt"
echo "host original" > "$W/candidate.txt"
echo "host-only secret" > "$WORK/host_secret.txt"

echo "=== T0: bwrap version ==="
bwrap --version

echo "=== T1: permitted python command executes ==="
if OUT=$("$SB" "$W" python3 -c 'print("PY_OK", 2+2)'); then ok "python runs in sandbox"; else bad "python runs in sandbox: $OUT"; fi
echo "  -> ${OUT:-<no output>}"

echo "=== T2: filesystem visibility restricted ==="
OUT=$("$SB" "$W" sh -c 'ls /home 2>&1; echo "rc=$?"')
echo "  ls /home -> $OUT"
if echo "$OUT" | grep -q "No such file"; then ok "/home not visible in sandbox"; else bad "/home not visible in sandbox ($OUT)"; fi
OUT=$("$SB" "$W" sh -c "cat $WORK/host_secret.txt 2>&1")
echo "  read host_secret -> $OUT"
if echo "$OUT" | grep -q "No such file"; then ok "host secret file unreachable"; else bad "host secret file unreachable ($OUT)"; fi
OUT=$("$SB" "$W" sh -c 'ls / 2>&1 | tr "\n" " "')
echo "  sandbox root listing -> $OUT"

echo "=== T3: write to read-only path rejected ==="
BWRAP_ERR=0
OUT=$("$SB" "$W" sh -c 'echo pwned > /usr/truth.txt 2>&1; echo rc=$?') || BWRAP_ERR=$?
echo "  write /usr -> (bwrap_rc=$BWRAP_ERR) $OUT"
if [ "$BWRAP_ERR" -ne 0 ] || [ -z "$OUT" ]; then bad "write to ro /usr: probe did not execute (bwrap_rc=$BWRAP_ERR)"; elif echo "$OUT" | grep -q "rc=0"; then bad "write to ro /usr succeeded"; else ok "write to ro /usr rejected ($OUT)"; fi
BWRAP_ERR=0
OUT=$("$SB" "$W" sh -c "echo pwned > $ORACLE/truth.txt 2>&1; echo rc=\$?") || BWRAP_ERR=$?
echo "  write oracle path -> (bwrap_rc=$BWRAP_ERR) $OUT"
if [ "$BWRAP_ERR" -ne 0 ] || [ -z "$OUT" ]; then bad "write to oracle: probe did not execute (bwrap_rc=$BWRAP_ERR)"; elif echo "$OUT" | grep -q "rc=0"; then bad "write to oracle path succeeded"; else ok "write to oracle path rejected ($OUT)"; fi

echo "=== T4: designated writable tmp works ==="
OUT=$("$SB" "$W" sh -c 'echo sandbox-data > /tmp/work/x.txt && cat /tmp/work/x.txt; echo rc=$?')
echo "  tmp write -> $OUT"
if echo "$OUT" | grep -q "sandbox-data"; then ok "writable tmp dir works"; else bad "writable tmp dir works ($OUT)"; fi

echo "=== T5: network isolation ==="
OUT=$("$SB" "$W" python3 -c 'import socket
try:
    s=socket.create_connection(("1.1.1.1",80),timeout=3); print("NET_REACHABLE"); s.close()
except Exception as e: print("NET_BLOCKED:", type(e).__name__)')
echo "  connect 1.1.1.1:80 -> $OUT"
if echo "$OUT" | grep -q "NET_BLOCKED"; then ok "outbound network blocked"; else bad "outbound network blocked ($OUT)"; fi
OUT=$("$SB" "$W" python3 -c 'import urllib.request
try:
    urllib.request.urlopen("https://example.com", timeout=3); print("NET_REACHABLE")
except Exception as e: print("NET_BLOCKED:", type(e).__name__)')
echo "  https example.com -> $OUT"
if echo "$OUT" | grep -q "NET_BLOCKED"; then ok "DNS/HTTPS blocked"; else bad "DNS/HTTPS blocked ($OUT)"; fi

echo "=== T6: parent timeout terminates long-running command ==="
T0=$(date +%s)
timeout 3 "$SB" "$W" sleep 30
RC=$?
T1=$(date +%s)
echo "  timeout rc=$RC elapsed=$((T1-T0))s"
if [ "$RC" -eq 124 ] && [ $((T1-T0)) -le 6 ]; then ok "timeout kills sandbox process"; else bad "timeout kills sandbox process (rc=$RC elapsed=$((T1-T0)))"; fi
sleep 1
if pgrep -f "sleep 30" >/dev/null; then bad "no leftover process"; else ok "no leftover process"; fi

echo "=== T7: no unwanted files outside workspace ==="
"$SB" "$W" sh -c 'echo model-output > /tmp/work/result.txt'
sleep 1
if [ -f "$W/result.txt" ] && [ "$(cat "$W/result.txt")" = "model-output" ]; then
  ok "workspace write persisted to designated dir"
else
  bad "workspace write persisted to designated dir"
fi
LEAK=$(find /home/aaksh -maxdepth 3 -newermt '-3 minutes' \( -name 'x.txt' -o -name 'result.txt' \) 2>/dev/null | grep -v sandbox_probe | head)
if [ -z "$LEAK" ]; then ok "no leaked files outside workspace"; else bad "leaked files: $LEAK"; fi

echo "=== T8: oracle integrity unchanged on host ==="
if [ "$(cat "$ORACLE/truth.txt")" = "ORACLE_DATA_DO_NOT_MODIFY" ]; then ok "oracle file unmodified"; else bad "oracle file unmodified"; fi

echo "=== T9: inspect sandbox view (mounts/processes/ids/net) ==="
"$SB" "$W" sh -c 'echo "-- mounts --"; cat /proc/self/mountinfo | head -25; echo "-- pids visible --"; ls /proc | grep -E "^[0-9]+$"; echo "-- id --"; id; echo "-- netdevs --"; ls /sys/class/net 2>/dev/null; echo "-- hostname --"; hostname'

echo
echo "RESULT: PASS=$PASS FAIL=$FAIL"
