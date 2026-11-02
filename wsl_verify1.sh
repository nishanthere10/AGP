#!/usr/bin/env bash
set -u
echo "== versions after install =="
gcc --version | head -1
g++ --version | head -1
make --version | head -1
cmake --version | head -1
pkg-config --version
echo "== dpkg state =="
dpkg-query -W -f='${Package} ${Version} ${Status}\n' build-essential cmake python3.14-venv pkg-config 2>&1
echo "== venv test =="
T=$(mktemp -d)
python3 -m venv "$T/venv" && echo "venv create: OK" || echo "venv create: FAILED"
"$T/venv/bin/python" --version
"$T/venv/bin/pip" --version | head -1
rm -rf "$T"
