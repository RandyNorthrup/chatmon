#!/bin/bash
# The plans round for v0.10.0 (7816159): the Linux checks of the nine plans PR #22's merge staled, in WSL (Arch), on
# the measure worktree's files. Each run gets its own CHATMON_INSTANCE; the whole script runs under nice -n 10.
# Leaves nothing running.
#   MSYS_NO_PATHCONV=1 wsl.exe -d archlinux -- nice -n 10 bash /mnt/c/Users/Randy/Coding/chatmon-wt/measure/docs/delivery/reports/wave5/run-wsl.sh
#   (from Git Bash; MSYS_NO_PATHCONV keeps the /mnt path as it is)
R=/mnt/c/Users/Randy/Coding/chatmon-wt/measure
D=$R/docs/delivery/reports
PY=/var/tmp/plans-venv/bin/python      # packaging/requirements-test.txt: PyQt6 6.11.0, as CI
PY612=/var/tmp/m4a-venv/bin/python     # PyQt6 6.12.1 and mypy 2.4.1
L=$D/wave5/files-7816159.lst
T=$D/wave4/wsl_drills.py
PROG=$D/wave5/wsl-progress.txt
export QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1
unset WAYLAND_DISPLAY
cd /var/tmp || exit 2
n=0
inst() { n=$((n + 1)); export CHATMON_INSTANCE="plans5-wsl-$n-$$"; }
version() { "$1" -c 'import sys, PyQt6.QtCore as q; print(sys.version.split()[0], "PyQt6", q.PYQT_VERSION_STR, "Qt", q.qVersion())'; }
header() { echo "# WSL $(. /etc/os-release; echo "$NAME"), $(uname -r); sway $(sway --version | awk '{print $3}'); $(pacman -Q at-spi2-core orca upower | tr '\n' ' '); system bus: $(busctl --system list --no-legend 2>/dev/null | awk '{print $1}' | grep -E 'UPower|login1' | tr '\n' ' '); $1: $(version "$1"); 7816159's files; nice $(nice); CHATMON_INSTANCE=$CHATMON_INSTANCE"; }
drills() {  # spec log python
    inst; start=$(date -u +%H:%M:%S)
    xvfb-run -a "$3" "$T" "$R" "$1" "$2" "$L" > "${2%.log}-run.txt" 2>&1
    echo "$(basename "$(dirname "$(dirname "$1")")")/$(basename "$1") exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
}
run() {  # log python args...
    inst; log=$1; py=$2; shift 2; start=$(date -u +%H:%M:%S)
    (cd "$R" && { header "$py"; echo "\$ $py $*"; "$py" "$@" 2>&1; echo "# exit $?"; } > "$log")
    echo "$(basename "$log") $(grep -E 'passed|failed|Success|Found' "$log" | tail -1) $(tail -1 "$log") $start-$(date -u +%H:%M:%S)" >> "$PROG"
}
drills $D/m0/wave5/drill-spec-linux.json $D/m0/wave5/drills-linux.log $PY
drills $D/m6b/wave5/drill-spec-linux.json $D/m6b/wave5/drills-linux.log $PY
drills $D/m3/wave5/drill-spec-linux-r3.json $D/m3/wave5/drills-linux-r3.log $PY
drills $D/m3/wave5/drill-spec-wayland-linux.json $D/m3/wave5/drills-wayland-linux.log $PY
drills $D/m4a/wave5/w4-drill-spec-linux.json $D/m4a/wave5/w4-drills-linux.log $PY
drills $D/m4a/wave5/w4-drill-spec-linux-qt612.json $D/m4a/wave5/w4-drills-linux-qt612.log $PY612
drills $D/m4a/wave5/readers-drill-spec-linux.json $D/m4a/wave5/readers-drills-linux.log $PY612
run $D/m3/wave5/sway-tests-linux.log $PY -m pytest -p no:cacheprovider -v -rs tests/test_sway.py tests/test_wayland.py
M3="tests/test_wayland.py tests/test_xkb.py tests/test_overlay_stage.py tests/test_clickthrough.py tests/test_stage_timer.py tests/test_behavior.py tests/test_sprites.py tests/test_stagemenu.py tests/test_stage_features.py tests/test_sway.py"
run $D/m3/wave5/m3-tests-linux.log $PY -m pytest -q -p no:cacheprovider -rs $M3
M4A="tests/test_screen_readers.py tests/test_a11y.py tests/test_presence.py tests/test_linuxsession.py tests/test_heads_up.py tests/test_platform_events.py tests/test_portal_bus.py tests/test_winlock.py tests/test_macnative.py"
run $D/m4a/wave5/suite-linux-qt612.log $PY612 -m pytest -q -p no:cacheprovider -rA $M4A
run $D/wave5/sway-readers.log $PY -m pytest -q -p no:cacheprovider -rA tests/test_sway.py -k "screen_reader or orca or window_of_its_own or reaches_atspi"
run $D/wave5/suite-linux.log $PY -m pytest -q -p no:cacheprovider
inst; start=$(date -u +%H:%M:%S)
(cd /var/tmp && $PY $D/m3/memory.py "$R" --window > $D/m3/wave5/memory-after--window.json 2> $D/m3/wave5/memory-after--window.err)
echo "m3 memory exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
for p in linux win32 darwin; do run $D/m6a/wave5/mypy-pyqt6-6.12.1-$p.log $PY612 -m mypy --platform $p --no-incremental --cache-dir /var/tmp/plans5-mypy-$p; done
rm -rf /var/tmp/plans5-mypy-linux /var/tmp/plans5-mypy-win32 /var/tmp/plans5-mypy-darwin
start=$(date -u +%H:%M:%S)
rm -rf /var/tmp/plans5-howto && mkdir -p /var/tmp/plans5-howto && (cd "$R" && tr '\0' '\n' < "$L" | grep -v -e "^art/" -e "^docs/" | while IFS= read -r f; do [ -f "$f" ] && mkdir -p "/var/tmp/plans5-howto/$(dirname "$f")" && cp -p "$f" "/var/tmp/plans5-howto/$f"; done)
(cd /var/tmp && PATH="$HOME/.local/bin:$PATH" sh $D/m10/wave5/howto-replay.sh /var/tmp/plans5-howto > $D/m10/wave5/howto-replay.log 2>&1)
code=$?; rm -rf /var/tmp/plans5-howto /tmp/qt-next /tmp/qt-next.in /tmp/qt-next.txt; (exit $code)
echo "m10 howto replay exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
inst; start=$(date -u +%H:%M:%S)
bash $D/m6a/wave5/distro_drill.sh "$R" "$L" $D/m6a/wave5
echo "m6a distro drill exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
echo "left running: $(pgrep -u "$USER" -f 'chatmon-wsl-drill|plans5|plans-venv/bin/python|m4a-venv/bin/python|chatmon-distro-drill|sway -d' | grep -vw $$ | wc -l)" >> "$PROG"
echo DONE >> "$PROG"
