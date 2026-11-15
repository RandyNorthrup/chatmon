#!/bin/bash
# The sway tests on Ubuntu 24.04's sway 1.9 (container) and on Arch's sway 1.12 (WSL), each log beside this script.
here=$(cd "$(dirname "$0")" && pwd)
src=/mnt/c/Users/Randy/Coding/chatmon-wt/sway-ci
mkdir -p "$here/logs"
{ echo "\$ CHATMON_SWAY=1 python -m pytest -p no:cacheprovider -q -rs tests/test_sway.py tests/test_wayland.py   (ubuntu:24.04 container: apt's sway, Python 3.12)"
  bash "$here/run.sh" "$src" tests/test_sway.py tests/test_wayland.py -q; echo "exit=$?"; } > "$here/logs/sway19.log" 2>&1
tail -n 4 "$here/logs/sway19.log"
cd "$src" || exit 1
{ echo "\$ CHATMON_SWAY=1 python -m pytest -p no:cacheprovider -q -rs tests/test_sway.py tests/test_wayland.py   (WSL Arch: sway $(sway --version | awk '{print $3}'), /var/tmp/wayland-venv)"
  CHATMON_SWAY=1 /var/tmp/wayland-venv/bin/python -m pytest -p no:cacheprovider -q -rs tests/test_sway.py tests/test_wayland.py; echo "exit=$?"; } > "$here/logs/sway112.log" 2>&1
tail -n 4 "$here/logs/sway112.log"
