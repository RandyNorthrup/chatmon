#!/bin/bash
# M1A after the owner test (3bcd857): the Linux checks behind the receipts that bind tests/test_install_update.py,
# in WSL (Arch), on this worktree's files. Leaves nothing running.
#   git ls-files -co --exclude-standard -z > docs/delivery/reports/m1a/mac-owner/files.lst   (on Windows, first)
#   MSYS_NO_PATHCONV=1 wsl.exe -d archlinux -- bash /mnt/c/Users/Randy/Coding/chatmon-wt/mac-owner/docs/delivery/reports/m1a/mac-owner/run-wsl.sh
R=/mnt/c/Users/Randy/Coding/chatmon-wt/mac-owner
D=$R/docs/delivery/reports
W=$D/m1a/mac-owner
PY=/var/tmp/plans-venv/bin/python      # packaging/requirements-test.txt: PyQt6 6.11.0, as CI
export QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1
unset WAYLAND_DISPLAY
cd /var/tmp || exit 2
version() { "$1" -c 'import sys, PyQt6.QtCore as q, pytest; print(sys.version.split()[0], "PyQt6", q.PYQT_VERSION_STR, "Qt", q.qVersion(), "pytest", pytest.__version__)'; }
header() { echo "# WSL $(. /etc/os-release; echo "$NAME"), $(uname -r); $PY: $(version "$PY"); the worktree's files at $(date -u +%Y-%m-%dT%H:%M:%SZ), uid $(id -u)"; }

# M1A's 8 Linux drills (wave4c/drill-spec-linux.json), through wsl_drills.py, which hands each to tests/drills/run.py's own drill step.
xvfb-run -a "$PY" "$D/wave4/wsl_drills.py" "$R" "$D/m1a/wave4c/drill-spec-linux.json" "$W/drills-linux.log" "$W/files.lst" > "$W/drills-linux-run.txt" 2>&1
echo "wsl drills exit $?" > "$W/wsl-progress.txt"

# What CI's Linux job showed for these criteria: root's side of an update, the postinstall, private backups, attachments.
TESTS="tests/test_install_update.py tests/test_packaging.py tests/test_agents.py tests/test_attachments.py"
(cd "$R" && { header; echo "\$ $PY -m pytest -v -rA -p no:cacheprovider $TESTS"; "$PY" -m pytest -v -rA -p no:cacheprovider $TESTS 2>&1; echo "# exit $?"; } > "$W/linux-tests.log")
echo "linux tests $(tail -1 "$W/linux-tests.log")" >> "$W/wsl-progress.txt"
echo "left running: $(ps -eo user,args | grep -E 'chatmon-wsl-drill|plans-venv/bin/python|Xvfb' | grep -v grep | wc -l)" >> "$W/wsl-progress.txt"
echo DONE >> "$W/wsl-progress.txt"
