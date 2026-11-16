#!/bin/bash
# The plans round for v0.10.0 (7816159): the whole suite in WSL failed tests/test_app_smoke.py's test_a_hook_reaches_it
# in its first run (under load) and test_hide_menu_and_reload in its second (quiet), each passing elsewhere. Here the
# file runs five times on its own, verbose, nothing else running, to say how often each of its tests fails in WSL.
#   MSYS_NO_PATHCONV=1 wsl.exe -d archlinux -- nice -n 10 bash /mnt/c/Users/Randy/Coding/chatmon-wt/measure/docs/delivery/reports/wave5/run-wsl-smoke.sh
R=/mnt/c/Users/Randy/Coding/chatmon-wt/measure
D=$R/docs/delivery/reports
PY=/var/tmp/plans-venv/bin/python
PROG=$D/wave5/wsl-progress.txt
export QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1
unset WAYLAND_DISPLAY
start=$(date -u +%H:%M:%S)
(cd "$R" && {
  echo "# WSL $(. /etc/os-release; echo "$NAME"), $(uname -r); $PY: $("$PY" -c 'import sys, PyQt6.QtCore as q; print(sys.version.split()[0], "PyQt6", q.PYQT_VERSION_STR, "Qt", q.qVersion())'); 7816159's files; nice $(nice); load $(cut -d' ' -f1-3 /proc/loadavg)"
  for i in 1 2 3 4 5; do
    export CHATMON_INSTANCE="plans5-wsl-smoke-$i-$$"
    echo; echo "\$ $PY -m pytest -p no:cacheprovider -v tests/test_app_smoke.py   (run $i, CHATMON_INSTANCE=$CHATMON_INSTANCE)"
    "$PY" -m pytest -p no:cacheprovider -v tests/test_app_smoke.py 2>&1 | grep -E "FAILED|ERROR|^E  |passed|failed"; echo "# exit ${PIPESTATUS[0]}"
  done
} > $D/wave5/smoke-wsl-5-runs.log 2>&1)
echo "smoke-wsl-5-runs.log $(grep -c '^# exit 0' $D/wave5/smoke-wsl-5-runs.log) of 5 exit 0 $start-$(date -u +%H:%M:%S)" >> "$PROG"
echo DONE-SMOKE >> "$PROG"
