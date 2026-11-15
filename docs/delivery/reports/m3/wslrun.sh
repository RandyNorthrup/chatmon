#!/bin/bash
# Scope revision 3's Linux runs: a command in the worktree under WSL, with the throwaway venv (/var/tmp/wayland-venv,
# from packaging/requirements-test.txt) first on PATH, its output in the log named first, after a header with the
# versions, the worktree's HEAD (the caller writes it to /var/tmp/wayland-head: WSL's git can't read a worktree whose
# .git names a Windows path) and the command.
#   bash docs/delivery/reports/m3/wslrun.sh LOG CMD...
log=$1; shift
cd /mnt/c/Users/Randy/Coding/chatmon-wt/wayland || exit 1
export PATH=/var/tmp/wayland-venv/bin:$PATH
{
  echo "\$ $*"
  echo "# WSL $(. /etc/os-release; echo "$NAME"), $(uname -r); sway $(sway --version | awk '{print $3}'); $(python -c 'import sys, PyQt6.QtCore as q; print("Python", sys.version.split()[0], "PyQt6", q.PYQT_VERSION_STR, "Qt", q.qVersion())'); worktree HEAD $(cat /var/tmp/wayland-head 2>/dev/null)"
  "$@"
  echo "exit=$?"
} > "$log" 2>&1
tail -n 3 "$log"
