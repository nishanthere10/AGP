#!/usr/bin/env bash
# Stage 0 environment audit for LocalAgentBench
set -u
echo "== os-release =="
grep -E 'PRETTY_NAME|VERSION_ID' /etc/os-release
echo "== uname =="
uname -a
echo "== cpu =="
lscpu | grep -E 'Model name|CPU\(s\):|Thread|Core|Flags' | cut -c1-200
grep -o -m1 -E 'avx2|avx512f' /proc/cpuinfo | sort -u | tr '\n' ' '; echo
echo "== memory =="
free -h
echo "== disk =="
df -h / /mnt/c
echo "== tools =="
for c in python3 git cmake gcc g++ make curl sha256sum bwrap unshare pkg-config pip3 time; do
  p=$(command -v "$c" 2>/dev/null) && echo "$c: $p" || echo "$c: MISSING"
done
echo "== versions =="
python3 --version 2>&1
git --version 2>&1
cmake --version 2>&1 | head -1
gcc --version 2>&1 | head -1
g++ --version 2>&1 | head -1
make --version 2>&1 | head -1
curl --version 2>&1 | head -1
bwrap --version 2>&1
echo "== venv support =="
python3 -m venv --help >/dev/null 2>&1 && echo "venv: OK" || echo "venv: MISSING/FAIL"
python3 -c "import ensurepip; print('ensurepip: OK')" 2>&1
echo "== namespaces =="
echo "max_user_namespaces=$(cat /proc/sys/user/max_user_namespaces 2>/dev/null)"
unshare -Ur true 2>&1 && echo "unshare -Ur: OK (rc=0)" || echo "unshare -Ur: FAILED rc=$?"
unshare -Un true 2>&1 && echo "unshare -Un: OK (rc=0)" || echo "unshare -Un: FAILED rc=$?"
unshare -rm true 2>&1 && echo "unshare -rm: OK (rc=0)" || echo "unshare -rm: FAILED rc=$?"
echo "== apparmor userns restriction =="
cat /proc/sys/kernel/apparmor_restrict_unprivileged_userns 2>/dev/null || echo "apparmor_restrict_unprivileged_userns: n/a"
echo "== project dir =="
ls -la ~/projects/LocalAgentBench 2>&1 | head -30
echo "== apt package state (build-relevant) =="
dpkg-query -W -f='${Package} ${Version} ${Status}\n' build-essential cmake git curl ca-certificates python3-venv bubblewrap 2>&1 | sed 's/install ok installed/INSTALLED/;s/not-installed/MISSING/'
