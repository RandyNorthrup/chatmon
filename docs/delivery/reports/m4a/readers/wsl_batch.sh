#!/bin/bash
# M4A's screen-reader task: every Linux check, in WSL (Arch), on the a11y worktree's files. Leaves nothing running.
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
drills() {  # spec log
    xvfb-run -a "$PY" "$T" "$W" "$1" "$2" "$L" > "${2%.log}-run.txt" 2>&1
    echo "$(basename "$1") exit $?"
}
drills $R/readers/drill-spec-linux.json $R/readers/drills-linux.log
drills $R/wave4/drill-spec-linux.json $R/readers/drills-w4-linux.log
drills $R/wave4/drill-spec-linux-qt612.json $R/readers/drills-w4-linux-qt612.log
TESTS="tests/test_screen_readers.py tests/test_a11y.py tests/test_presence.py tests/test_linuxsession.py tests/test_heads_up.py tests/test_platform_events.py tests/test_portal_bus.py tests/test_winlock.py tests/test_macnative.py"
(cd "$W" && { echo "# M4A's tests in WSL (Arch, $(pacman -Q at-spi2-core orca | tr '\n' ' ')), $(uname -r), /var/tmp/m4a-venv: $(version $PY), under xvfb-run -a"; echo "\$ xvfb-run -a /var/tmp/m4a-venv/bin/python -m pytest -q -p no:cacheprovider -rA $TESTS"; xvfb-run -a $PY -m pytest -q -p no:cacheprovider -rA $TESTS 2>&1; echo "# exit $?"; } > $R/readers/suite-linux.log)
echo "suite-linux exit: $(tail -1 $R/readers/suite-linux.log)"
(cd "$W" && { echo "# The screen-reader sway tests in WSL (real sway, at-spi2-core 2.62, Orca 51), /var/tmp/wayland-venv: $(version $WPY)"; echo '$ /var/tmp/wayland-venv/bin/python -m pytest -q -p no:cacheprovider -rA tests/test_sway.py -k "screen_reader or orca or window_of_its_own or reaches_atspi"'; timeout 1500 $WPY -m pytest -q -p no:cacheprovider -rA tests/test_sway.py -k "screen_reader or orca or window_of_its_own or reaches_atspi" 2>&1; echo "# exit $?"; } > $R/readers/sway-readers.log)
echo "sway exit: $(tail -1 $R/readers/sway-readers.log)"
echo "left running: $(ps -eo user,args | grep -E '^randy .*(pytest-of-randy|odilia|fake_a11y|fake_orca|chatmon-wsl-drill|/var/tmp/m4a-venv|wayland-venv)' | grep -v grep | wc -l)"
echo DONE
