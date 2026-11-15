#!/bin/bash
# M4B after ROADMAP.md's round-three amendment: the Linux checks behind every receipt it made stale, in WSL (Arch),
# on this worktree's files. As m4b/w4c/run-wsl.sh, with all seven Linux drills. Leaves nothing running.
#   git ls-files -co --exclude-standard -z > docs/delivery/reports/m4b/w4d/files.lst   (on Windows, first)
#   wsl.exe -d archlinux -- bash /mnt/c/Users/Randy/Coding/chatmon-wt/mac-drills/docs/delivery/reports/m4b/w4d/run-wsl.sh
R=/mnt/c/Users/Randy/Coding/chatmon-wt/mac-drills
D=$R/docs/delivery/reports
W=$D/m4b/w4d
PY=/var/tmp/plans-venv/bin/python      # packaging/requirements-test.txt: PyQt6 6.11.0, as CI
export QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1
unset WAYLAND_DISPLAY
cd /var/tmp || exit 2
version() { "$1" -c 'import sys, PyQt6.QtCore as q, pytest; print(sys.version.split()[0], "PyQt6", q.PYQT_VERSION_STR, "Qt", q.qVersion(), "pytest", pytest.__version__)'; }
header() { echo "# WSL $(. /etc/os-release; echo "$NAME"), $(uname -r); $(pacman -Q xorg-server-xvfb dbus 2>/dev/null | tr '\n' ' '); $PY: $(version "$PY"); the worktree's files at $(date -u +%Y-%m-%dT%H:%M:%SZ)"; }

# The six drills of wave4b/wsl-drill-spec.json and the one of wave4b/wsl-drill-spec-new.json, through
# wsl_drills.py, which hands each to tests/drills/run.py's own drill step.
xvfb-run -a "$PY" "$D/wave4/wsl_drills.py" "$R" "$D/m4b/wave4b/wsl-drill-spec.json" "$W/wsl-drills.log" "$W/files.lst" > "$W/wsl-drills-run.txt" 2>&1
echo "wsl drills exit $?" > "$W/wsl-progress.txt"
xvfb-run -a "$PY" "$D/wave4/wsl_drills.py" "$R" "$D/m4b/wave4b/wsl-drill-spec-new.json" "$W/wsl-drills-new.log" "$W/files.lst" > "$W/wsl-drills-new-run.txt" 2>&1
echo "wsl drills (new) exit $?" >> "$W/wsl-progress.txt"

# What CI's Linux job showed for this plan: the imports, the X11 grab, the GlobalShortcuts portal, the Linux players.
TESTS="tests/test_m4b_imports.py tests/test_hotkey.py tests/test_hotkey_portal.py tests/test_sound.py"
(cd "$R" && { header; echo "\$ $PY -m pytest -v -rA -p no:cacheprovider $TESTS"; "$PY" -m pytest -v -rA -p no:cacheprovider $TESTS 2>&1; echo "# exit $?"; } > "$W/linux-tests.log")
echo "linux tests $(tail -1 "$W/linux-tests.log")" >> "$W/wsl-progress.txt"
echo "left running: $(ps -eo user,args | grep -E 'chatmon-wsl-drill|plans-venv/bin/python|Xvfb' | grep -v grep | wc -l)" >> "$W/wsl-progress.txt"
echo DONE >> "$W/wsl-progress.txt"
