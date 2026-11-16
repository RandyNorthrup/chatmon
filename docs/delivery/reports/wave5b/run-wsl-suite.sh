#!/bin/bash
# The plans round for v0.10.0, bound again at 56caddd: the whole suite in WSL, retried at the new head with nothing else
# running on the machine (both runners done), after 56caddd's fix to test_hide_menu_and_reload. Under nice 10, with a
# CHATMON_INSTANCE of its own.
#   MSYS_NO_PATHCONV=1 wsl.exe -d archlinux -- nice -n 10 bash /mnt/c/Users/Randy/Coding/chatmon-wt/measure/docs/delivery/reports/wave5b/run-wsl-suite.sh
R=/mnt/c/Users/Randy/Coding/chatmon-wt/measure
D=$R/docs/delivery/reports
PY=/var/tmp/plans-venv/bin/python
PROG=$D/wave5b/wsl-progress.txt
export QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 CHATMON_INSTANCE="plans5b-wsl-suite-$$"
unset WAYLAND_DISPLAY
version() { "$1" -c 'import sys, PyQt6.QtCore as q; print(sys.version.split()[0], "PyQt6", q.PYQT_VERSION_STR, "Qt", q.qVersion())'; }
start=$(date -u +%H:%M:%S)
(cd "$R" && {
  echo "# WSL $(. /etc/os-release; echo "$NAME"), $(uname -r); sway $(sway --version | awk '{print $3}'); $(pacman -Q at-spi2-core orca upower kwin hyprland 2>&1 | tr '\n' ' '); system bus: $(busctl --system list --no-legend 2>/dev/null | awk '{print $1}' | grep -E 'UPower|login1' | tr '\n' ' '); $PY: $(version "$PY"); 56caddd's files; nice $(nice); load $(cut -d' ' -f1-3 /proc/loadavg); CHATMON_INSTANCE=$CHATMON_INSTANCE"
  echo "\$ $PY -m pytest -q -p no:cacheprovider   (quiet machine: both runners done)"
  "$PY" -m pytest -q -p no:cacheprovider 2>&1; echo "# exit $?"
} > $D/wave5b/suite-linux.log)
echo "suite-linux.log $(grep -E 'passed|failed' $D/wave5b/suite-linux.log | tail -1) $(tail -1 $D/wave5b/suite-linux.log) $start-$(date -u +%H:%M:%S)" >> "$PROG"
echo "left running: $(pgrep -u "$USER" -f 'plans5b|plans-venv/bin/python|fake_a11y_bus|sway -d' | grep -vw $$ | wc -l)" >> "$PROG"
echo DONE-SUITE >> "$PROG"
