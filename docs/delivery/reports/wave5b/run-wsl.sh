#!/bin/bash
# The plans round for v0.10.0, bound again at 56caddd: the Linux checks of the seven plans df3e93c and 56caddd staled,
# in WSL (Arch), on the measure worktree's files, each run with its own CHATMON_INSTANCE, the whole script under nice 10.
# The checks that failed at 7816159 run first (mypy with 6.12.1's stubs, the how-to's replay), then the drills, the real
# sway, the memory check, the coordinator's drill of 56caddd's test fix and the distro drill. The whole suite is retried
# apart, on a quiet machine (run-wsl-suite.sh), once the Windows runner is done.
#   MSYS_NO_PATHCONV=1 wsl.exe -d archlinux -- nice -n 10 bash /mnt/c/Users/Randy/Coding/chatmon-wt/measure/docs/delivery/reports/wave5b/run-wsl.sh
R=/mnt/c/Users/Randy/Coding/chatmon-wt/measure
D=$R/docs/delivery/reports
PY=/var/tmp/plans-venv/bin/python      # packaging/requirements-test.txt: PyQt6 6.11.0, as CI
PY612=/var/tmp/m4a-venv/bin/python     # PyQt6 6.12.1 and mypy 2.4.1
L=$D/wave5b/files-56caddd.lst
T=$D/wave4/wsl_drills.py
PROG=$D/wave5b/wsl-progress.txt
export QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1
unset WAYLAND_DISPLAY
cd /var/tmp || exit 2
n=0
inst() { n=$((n + 1)); export CHATMON_INSTANCE="plans5b-wsl-$n-$$"; }
version() { "$1" -c 'import sys, PyQt6.QtCore as q; print(sys.version.split()[0], "PyQt6", q.PYQT_VERSION_STR, "Qt", q.qVersion())'; }
header() { echo "# WSL $(. /etc/os-release; echo "$NAME"), $(uname -r); sway $(sway --version | awk '{print $3}'); $(pacman -Q at-spi2-core orca upower kwin hyprland 2>&1 | tr '\n' ' '); system bus: $(busctl --system list --no-legend 2>/dev/null | awk '{print $1}' | grep -E 'UPower|login1' | tr '\n' ' '); $1: $(version "$1"); 56caddd's files; nice $(nice); load $(cut -d' ' -f1-3 /proc/loadavg); CHATMON_INSTANCE=$CHATMON_INSTANCE"; }
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
for p in linux win32 darwin; do run $D/m6a/wave5b/mypy-pyqt6-6.12.1-$p.log $PY612 -m mypy --platform $p --no-incremental --cache-dir /var/tmp/plans5b-mypy-$p; done
rm -rf /var/tmp/plans5b-mypy-linux /var/tmp/plans5b-mypy-win32 /var/tmp/plans5b-mypy-darwin
start=$(date -u +%H:%M:%S)
rm -rf /var/tmp/plans5b-howto && mkdir -p /var/tmp/plans5b-howto && (cd "$R" && tr '\0' '\n' < "$L" | grep -v -e "^art/" -e "^docs/" | while IFS= read -r f; do [ -f "$f" ] && mkdir -p "/var/tmp/plans5b-howto/$(dirname "$f")" && cp -p "$f" "/var/tmp/plans5b-howto/$f"; done)
(cd /var/tmp && PATH="$HOME/.local/bin:$PATH" sh $D/m10/wave5b/howto-replay.sh /var/tmp/plans5b-howto > $D/m10/wave5b/howto-replay.log 2>&1)
code=$?; rm -rf /var/tmp/plans5b-howto /tmp/qt-next /tmp/qt-next.in /tmp/qt-next.txt; (exit $code)
echo "m10 howto replay exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
drills $D/m0/wave5b/drill-spec-linux.json $D/m0/wave5b/drills-linux.log $PY
drills $D/m6b/wave5b/drill-spec-linux.json $D/m6b/wave5b/drills-linux.log $PY
drills $D/m3/wave5b/drill-spec-linux-r3.json $D/m3/wave5b/drills-linux-r3.log $PY
drills $D/m3/wave5b/drill-spec-wayland-linux.json $D/m3/wave5b/drills-wayland-linux.log $PY
run $D/m3/wave5b/sway-tests-linux.log $PY -m pytest -p no:cacheprovider -v -rs tests/test_sway.py tests/test_wayland.py
M3="tests/test_wayland.py tests/test_xkb.py tests/test_overlay_stage.py tests/test_clickthrough.py tests/test_stage_timer.py tests/test_behavior.py tests/test_sprites.py tests/test_stagemenu.py tests/test_stage_features.py tests/test_sway.py"
run $D/m3/wave5b/m3-tests-linux.log $PY -m pytest -q -p no:cacheprovider -rs $M3
inst; start=$(date -u +%H:%M:%S)
(cd /var/tmp && $PY $D/m3/memory.py "$R" --window > $D/m3/wave5b/memory-after--window.json 2> $D/m3/wave5b/memory-after--window.err)
echo "m3 memory exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
rm -rf /var/tmp/plans5b-flaky && mkdir -p /var/tmp/plans5b-flaky && cp $D/wave5/flaky-hide-menu/drill.py.txt /var/tmp/plans5b-flaky/test_flaky_hide_menu_drill.py
run $D/wave5b/flaky-hide-menu-drill-wsl.log $PY -m pytest -p no:cacheprovider -v /var/tmp/plans5b-flaky/test_flaky_hide_menu_drill.py --rootdir .
rm -rf /var/tmp/plans5b-flaky
inst; start=$(date -u +%H:%M:%S)
bash $D/m6a/wave5b/distro_drill.sh "$R" "$L" $D/m6a/wave5b
echo "m6a distro drill exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
echo "left running: $(pgrep -u "$USER" -f 'chatmon-wsl-drill|plans5b|plans-venv/bin/python|m4a-venv/bin/python|chatmon-distro-drill|sway -d' | grep -vw $$ | wc -l)" >> "$PROG"
echo DONE >> "$PROG"
