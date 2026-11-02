#!/usr/bin/env bash
set -u
echo "== python3-venv dpkg state =="
dpkg -l python3-venv python3.14-venv python3-full 2>&1 | tail -10
echo "== venv creation test =="
T=$(mktemp -d)
python3 -m venv "$T/venv" 2>&1 && echo "venv create: OK" || echo "venv create: FAILED rc=$?"
"$T/venv/bin/python" --version 2>&1
"$T/venv/bin/pip" --version 2>&1 | head -1
rm -rf "$T"
echo "== sudo =="
sudo -n true 2>&1 && echo "passwordless sudo: OK" || echo "passwordless sudo: unavailable (rc=$?)"
echo "== avx =="
grep -m1 -o -E 'avx512f|avx2' /proc/cpuinfo | head -1
grep -m1 flags /proc/cpuinfo | tr ' ' '\n' | grep -E '^avx' | tr '\n' ' '; echo
echo "== wsl mem limit file =="
cat /mnt/c/Users/kirti/.wslconfig 2>&1 | head -20
echo "== time binary =="
/usr/bin/time --version 2>&1 | head -1 || echo "/usr/bin/time MISSING"
