#!/bin/bash
# M4A's screen-reader task, second pass (after the Orca start-and-stop test and the merge of the sway tests' fix):
# the new task's Linux drills, M4A's tests and the real-sway screen-reader tests, in WSL (Arch), on the a11y
# worktree's files. The wave-4 Linux drills ran in the first pass (wsl_batch.sh); their files haven't changed since.
W=/mnt/c/Users/Randy/Coding/chatmon-wt/a11y
R=$W/docs/delivery/reports/m4a
PY=/var/tmp/m4a-venv/bin/python
WPY=/var/tmp/wayland-venv/bin/python
T=$W/docs/delivery/reports/wave4/wsl_drills.py
L=$R/readers/files.lst
export QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1
unset WAYLAND_DISPLAY
cd /var/tmp || exit 2
version() { "$1" -c 'import sys, PyQt6.QtCore as q; print(sys.version.split()[0], "PyQt6", q.PYQT_VERSION_STR, "Qt", q.qVersion())'; }
xvfb-run -a "$PY" "$T" "$W" "$R/readers/drill-spec-linux.json" "$R/readers/drills-linux.log" "$L" > "$R/readers/drills-linux-run.txt" 2>&1
echo "drills exit $?"
TESTS="tests/test_screen_readers.py tests/test_a11y.py tests/test_presence.py tests/test_linuxsession.py tests/test_heads_up.py tests/test_platform_events.py tests/test_portal_bus.py tests/test_winlock.py tests/test_macnative.py"
(cd "$W" && { echo "# M4A's tests in WSL (Arch, $(pacman -Q at-spi2-core orca | tr '\n' ' ')), $(uname -r), /var/tmp/m4a-venv: $(version $PY), under xvfb-run -a"; echo "\$ xvfb-run -a /var/tmp/m4a-venv/bin/python -m pytest -q -p no:cacheprovider -rA $TESTS"; xvfb-run -a $PY -m pytest -q -p no:cacheprovider -rA $TESTS 2>&1; echo "# exit $?"; } > $R/readers/suite-linux.log)
echo "suite-linux: $(tail -1 $R/readers/suite-linux.log)"
(cd "$W" && { echo "# The screen-reader sway tests in WSL (real sway, at-spi2-core 2.62, Orca 51), /var/tmp/wayland-venv: $(version $WPY)"; echo '$ /var/tmp/wayland-venv/bin/python -m pytest -q -p no:cacheprovider -rA tests/test_sway.py -k "screen_reader or orca or window_of_its_own or reaches_atspi"'; timeout 1500 $WPY -m pytest -q -p no:cacheprovider -rA tests/test_sway.py -k "screen_reader or orca or window_of_its_own or reaches_atspi" 2>&1; echo "# exit $?"; } > $R/readers/sway-readers.log)
echo "sway: $(tail -1 $R/readers/sway-readers.log)"
echo DONE
