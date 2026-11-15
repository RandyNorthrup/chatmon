#!/bin/bash
# Round three's Linux checks, in WSL (Arch), on the plans3 worktree's files (3586a0d). Leaves nothing running.
#   bash /mnt/c/Users/Randy/Coding/chatmon-wt/plans3/docs/delivery/reports/wave4c/run-wsl.sh
R=/mnt/c/Users/Randy/Coding/chatmon-wt/plans3
D=$R/docs/delivery/reports
PY=/var/tmp/plans-venv/bin/python      # packaging/requirements-test.txt: PyQt6 6.11.0, as CI
PY612=/var/tmp/m4a-venv/bin/python     # PyQt6 6.12.1: the tests and drills that need Qt 6.10's contrast signal
L=$D/wave4c/files-3586a0d.lst
T=$D/wave4/wsl_drills.py
PROG=$D/wave4c/wsl-progress.txt
export QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1
unset WAYLAND_DISPLAY
cd /var/tmp || exit 2
version() { "$1" -c 'import sys, PyQt6.QtCore as q; print(sys.version.split()[0], "PyQt6", q.PYQT_VERSION_STR, "Qt", q.qVersion())'; }
header() { echo "# WSL $(. /etc/os-release; echo "$NAME"), $(uname -r); sway $(sway --version | awk '{print $3}'); $(pacman -Q at-spi2-core orca | tr '\n' ' '); $1: $(version "$1"); 3586a0d's files"; }
drills() {  # spec log python
    start=$(date -u +%H:%M:%S)
    xvfb-run -a "$3" "$T" "$R" "$1" "$2" "$L" > "${2%.log}-run.txt" 2>&1
    echo "$(basename "$(dirname "$(dirname "$1")")")/$(basename "$1") exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
}
run() {  # log python args...
    log=$1; py=$2; shift 2; start=$(date -u +%H:%M:%S)
    (cd "$R" && { header "$py"; echo "\$ $py $*"; "$py" "$@" 2>&1; echo "# exit $?"; } > "$log")
    echo "$(basename "$log") $(tail -1 "$log") $start-$(date -u +%H:%M:%S)" >> "$PROG"
}
drills $D/m0/wave4c/drill-spec-linux.json $D/m0/wave4c/drills-linux.log $PY
drills $D/m1a/wave4c/drill-spec-linux.json $D/m1a/wave4c/drills-linux.log $PY
drills $D/m1b/wave4c/drill-spec-linux.json $D/m1b/wave4c/drills-linux.log $PY
drills $D/m4a/wave4c/w4-drill-spec-linux.json $D/m4a/wave4c/w4-drills-linux.log $PY
drills $D/m4a/wave4c/w4-drill-spec-linux-qt612.json $D/m4a/wave4c/w4-drills-linux-qt612.log $PY612
drills $D/m4a/wave4c/readers-drill-spec-linux.json $D/m4a/wave4c/readers-drills-linux.log $PY612
drills $D/m4b/wave4c/wsl-drill-spec.json $D/m4b/wave4c/wsl-drills.log $PY
drills $D/m4b/wave4c/wsl-drill-spec-new.json $D/m4b/wave4c/wsl-drills-new.log $PY
drills $D/m6b/wave4c/drill-spec-linux.json $D/m6b/wave4c/drills-linux.log $PY
drills $D/m3/wave4c/drill-spec-linux-r3.json $D/m3/wave4c/drills-linux-r3.log $PY
drills $D/m3/wave4c/drill-spec-wayland-linux.json $D/m3/wave4c/drills-wayland-linux.log $PY
TESTS="tests/test_screen_readers.py tests/test_a11y.py tests/test_presence.py tests/test_linuxsession.py tests/test_heads_up.py tests/test_platform_events.py tests/test_portal_bus.py tests/test_winlock.py tests/test_macnative.py"
run $D/m4a/wave4c/suite-linux-qt612.log $PY612 -m pytest -q -p no:cacheprovider -rA $TESTS
run $D/wave4c/sway-readers.log $PY -m pytest -q -p no:cacheprovider -rA tests/test_sway.py -k "screen_reader or orca or window_of_its_own or reaches_atspi"
run $D/m3/wave4c/sway-tests-linux.log $PY -m pytest -p no:cacheprovider -v -rs tests/test_sway.py tests/test_wayland.py
run $D/wave4c/suite-linux.log $PY -m pytest -q -p no:cacheprovider
start=$(date -u +%H:%M:%S)
(cd /var/tmp && $PY $D/m3/memory.py "$R" --window > $D/m3/wave4c/memory-after--window.json 2> $D/m3/wave4c/memory-after--window.err)
echo "m3 memory exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
for p in linux win32 darwin; do run $D/m6a/wave4c/mypy-pyqt6-6.12.1-$p.log $PY612 -m mypy --platform $p --no-incremental --cache-dir /var/tmp/plans3-mypy-$p; done
start=$(date -u +%H:%M:%S)
rm -rf /var/tmp/plans3-howto && mkdir -p /var/tmp/plans3-howto && (cd "$R" && tr '\0' '\n' < "$L" | grep -v -e "^art/" -e "^docs/" | while IFS= read -r f; do [ -f "$f" ] && mkdir -p "/var/tmp/plans3-howto/$(dirname "$f")" && cp -p "$f" "/var/tmp/plans3-howto/$f"; done)
(cd /var/tmp && PATH="$HOME/.local/bin:$PATH" sh $D/m10/wave4c/howto-replay.sh /var/tmp/plans3-howto > $D/m10/wave4c/howto-replay.log 2>&1)
code=$?; rm -rf /var/tmp/plans3-howto /tmp/qt-next /tmp/qt-next.in /tmp/qt-next.txt; (exit $code)
echo "m10 howto replay exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
start=$(date -u +%H:%M:%S)
bash $D/m6a/wave4c/distro_drill.sh "$R" "$L" $D/m6a/wave4c
echo "m6a distro drill exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
echo "left running: $(ps -eo user,args | grep -E '^randy .*(chatmon-wsl-drill|plans-venv|m4a-venv/bin/python|chatmon-distro-drill|sway -d)' | grep -v grep | wc -l)" >> "$PROG"
echo DONE >> "$PROG"
