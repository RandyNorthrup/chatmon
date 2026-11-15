#!/bin/bash
# The compositor checks' runs in WSL (Arch): a command in the worktree, at nice 10, with a throwaway venv first on PATH
# (VENV, default /var/tmp/plans-venv: packaging/requirements-test.txt), a Chatmon instance of the run's own, and its
# output in the log named first, after a header with the versions, the worktree's HEAD and the command.
#   bash docs/delivery/reports/release/compositors/run.sh LOG CMD...
# The caller writes the HEAD to /var/tmp/compositors-head (WSL's git can't read a worktree whose .git names a
# Windows path).
log=$1; shift
cd /mnt/c/Users/Randy/Coding/chatmon-wt/compositors || exit 1
venv=${VENV:-/var/tmp/plans-venv}
export PATH=$venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 QT_QPA_PLATFORM=offscreen
export CHATMON_INSTANCE="compositors-$$-$(date +%s)"
{
  echo "\$ $*"
  echo "# WSL $(. /etc/os-release; echo "$NAME"), kernel $(uname -r); worktree HEAD $(cat /var/tmp/compositors-head 2>/dev/null); CHATMON_INSTANCE=$CHATMON_INSTANCE"
  echo "# $(kwin_wayland --version 2>&1 | head -1); $(Hyprland --version 2>/dev/null | head -1 | cut -d' ' -f1-2); sway $(sway --version | awk '{print $3}')"
  echo "# packages: $(pacman -Q kwin hyprland aquamarine sway wlroots0.20 grim wl-clipboard orca at-spi2-core mesa qt6-base qt6-wayland 2>&1 | tr '\n' ' ')"
  echo "# $(python -c 'import sys, PyQt6.QtCore as q; print("venv", sys.prefix, "Python", sys.version.split()[0], "PyQt6", q.PYQT_VERSION_STR, "Qt", q.qVersion())')"
  nice -n 10 "$@"
  echo "exit=$?"
} > "$log" 2>&1
tail -n 3 "$log"
