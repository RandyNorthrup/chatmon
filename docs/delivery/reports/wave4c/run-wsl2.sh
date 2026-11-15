#!/bin/bash
# Round three, after run-wsl.sh: (1) M3's own test files in WSL, the receipt the whole suite gave M3 in round two,
# since the whole suite now fails one test that is none of M3's; (2) that test, five times, verbose, to say what ran.
#   bash /mnt/c/Users/Randy/Coding/chatmon-wt/plans3/docs/delivery/reports/wave4c/run-wsl2.sh
R=/mnt/c/Users/Randy/Coding/chatmon-wt/plans3
D=$R/docs/delivery/reports
PY=/var/tmp/plans-venv/bin/python      # packaging/requirements-test.txt: PyQt6 6.11.0, as CI
PROG=$D/wave4c/wsl-progress.txt
export QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1
unset WAYLAND_DISPLAY
version() { "$1" -c 'import sys, PyQt6.QtCore as q; print(sys.version.split()[0], "PyQt6", q.PYQT_VERSION_STR, "Qt", q.qVersion())'; }
header() { echo "# WSL $(. /etc/os-release; echo "$NAME"), $(uname -r); sway $(sway --version | awk '{print $3}'); $(pacman -Q at-spi2-core orca upower power-profiles-daemon 2>&1 | tr '\n' ' '); $1: $(version "$1"); 3586a0d's files"; }
M3="tests/test_wayland.py tests/test_xkb.py tests/test_overlay_stage.py tests/test_clickthrough.py tests/test_stage_timer.py tests/test_behavior.py tests/test_sprites.py tests/test_stagemenu.py tests/test_stage_features.py tests/test_sway.py"
start=$(date -u +%H:%M:%S)
(cd "$R" && { header "$PY"; echo "\$ $PY -m pytest -q -p no:cacheprovider -rs $M3"; $PY -m pytest -q -p no:cacheprovider -rs $M3 2>&1; echo "# exit $?"; } > $D/m3/wave4c/m3-tests-linux.log)
echo "m3-tests-linux.log $(tail -1 $D/m3/wave4c/m3-tests-linux.log) $start-$(date -u +%H:%M:%S)" >> "$PROG"
T=tests/test_app_smoke.py::test_a_quit_companion_runs_nothing_it_had_waiting
start=$(date -u +%H:%M:%S)
(cd "$R" && { header "$PY"; echo "# the system bus: $(busctl --system list --no-legend 2>&1 | awk '{print $1}' | grep -E 'UPower|PowerProfiles|login1' | tr '\n' ' ')"
  for i in 1 2 3 4 5; do echo; echo "\$ $PY -m pytest -p no:cacheprovider -vv $T   (run $i)"; $PY -m pytest -p no:cacheprovider -vv "$T" 2>&1 | grep -E "^E |passed|failed|PASSED|FAILED"; echo "# exit ${PIPESTATUS[0]}"; done
  echo; echo "\$ DBUS_SYSTEM_BUS_ADDRESS=unix:path=/nonexistent $PY -m pytest -p no:cacheprovider -vv $T   (no system bus)"
  DBUS_SYSTEM_BUS_ADDRESS=unix:path=/nonexistent $PY -m pytest -p no:cacheprovider -vv "$T" 2>&1 | grep -E "^E |passed|failed|PASSED|FAILED"; echo "# exit ${PIPESTATUS[0]}"
} > $D/wave4c/crash-test-wsl.log 2>&1)
echo "crash-test-wsl.log $start-$(date -u +%H:%M:%S)" >> "$PROG"
echo "left running: $(ps -eo user,args | grep -E '^randy .*(plans-venv/bin/python)' | grep -v grep | wc -l)" >> "$PROG"
echo DONE2 >> "$PROG"
