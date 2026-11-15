#!/bin/bash
# M4B, after tests/test_wintoast.py's change: the Linux checks whose receipts it made stale, in WSL (Arch), on this
# worktree's files. Leaves nothing running.
#   wsl.exe -d archlinux -- bash /mnt/c/Users/Randy/Coding/chatmon-wt/m4b-toast/docs/delivery/reports/m4b/w4c/run-wsl.sh
R=/mnt/c/Users/Randy/Coding/chatmon-wt/m4b-toast
D=$R/docs/delivery/reports
W=$D/m4b/w4c
PY=/var/tmp/plans-venv/bin/python      # packaging/requirements-test.txt: PyQt6 6.11.0, as CI
export QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1
unset WAYLAND_DISPLAY
cd /var/tmp || exit 2
version() { "$1" -c 'import sys, PyQt6.QtCore as q, pytest; print(sys.version.split()[0], "PyQt6", q.PYQT_VERSION_STR, "Qt", q.qVersion(), "pytest", pytest.__version__)'; }
header() { echo "# WSL $(. /etc/os-release; echo "$NAME"), $(uname -r); $(pacman -Q xorg-server-xvfb dbus 2>/dev/null | tr '\n' ' '); $PY: $(version "$PY"); the worktree's files at $(date -u +%Y-%m-%dT%H:%M:%SZ)"; }

# L-00B-eager-objc, as round two ran it: wsl_drills.py hands it to tests/drills/run.py's own drill step.
xvfb-run -a "$PY" "$D/wave4/wsl_drills.py" "$R" "$W/wsl-drill-spec.json" "$W/wsl-drills.log" "$W/files.lst" > "$W/wsl-drills-run.txt" 2>&1
echo "wsl drills exit $?" > "$W/wsl-progress.txt"

# What CI's Linux job showed for this plan: the imports, the X11 grab, the GlobalShortcuts portal, the Linux players.
TESTS="tests/test_m4b_imports.py tests/test_hotkey.py tests/test_hotkey_portal.py tests/test_sound.py"
(cd "$R" && { header; echo "\$ $PY -m pytest -v -rA -p no:cacheprovider $TESTS"; "$PY" -m pytest -v -rA -p no:cacheprovider $TESTS 2>&1; echo "# exit $?"; } > "$W/linux-tests.log")
echo "linux tests $(tail -1 "$W/linux-tests.log")" >> "$W/wsl-progress.txt"
echo "left running: $(ps -eo user,args | grep -E 'chatmon-wsl-drill|plans-venv/bin/python|Xvfb' | grep -v grep | wc -l)" >> "$W/wsl-progress.txt"
echo DONE >> "$W/wsl-progress.txt"
