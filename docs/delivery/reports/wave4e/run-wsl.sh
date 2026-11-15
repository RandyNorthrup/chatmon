#!/bin/bash
# The final round's Linux checks, in WSL (Arch), on the plans-final worktree's files (45a17b3). Leaves nothing running.
#   bash /mnt/c/Users/Randy/Coding/chatmon-wt/plans-final/docs/delivery/reports/wave4e/run-wsl.sh
# Each run gets its own CHATMON_INSTANCE. UPower is on WSL's system bus: the whole suite and the crash fix's quit test
# run with it there, which is the case round three found failing.
R=/mnt/c/Users/Randy/Coding/chatmon-wt/plans-final
D=$R/docs/delivery/reports
PY=/var/tmp/plans-venv/bin/python      # packaging/requirements-test.txt: PyQt6 6.11.0, as CI
PY612=/var/tmp/m4a-venv/bin/python     # PyQt6 6.12.1 and mypy 2.4.1
L=$D/wave4e/files-45a17b3.lst
T=$D/wave4/wsl_drills.py
PROG=$D/wave4e/wsl-progress.txt
export QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1
unset WAYLAND_DISPLAY
cd /var/tmp || exit 2
n=0
inst() { n=$((n + 1)); export CHATMON_INSTANCE="plansfinal-wsl-$n-$$"; }
version() { "$1" -c 'import sys, PyQt6.QtCore as q; print(sys.version.split()[0], "PyQt6", q.PYQT_VERSION_STR, "Qt", q.qVersion())'; }
header() { echo "# WSL $(. /etc/os-release; echo "$NAME"), $(uname -r); sway $(sway --version | awk '{print $3}'); $(pacman -Q at-spi2-core orca upower | tr '\n' ' '); system bus: $(busctl --system list --no-legend 2>/dev/null | awk '{print $1}' | grep -E 'UPower|login1' | tr '\n' ' '); $1: $(version "$1"); 45a17b3's files; CHATMON_INSTANCE=$CHATMON_INSTANCE"; }
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
drills $D/m0/wave4e/drill-spec-linux.json $D/m0/wave4e/drills-linux.log $PY
drills $D/m6b/wave4e/drill-spec-linux.json $D/m6b/wave4e/drills-linux.log $PY
drills $D/m3/wave4e/drill-spec-linux-r3.json $D/m3/wave4e/drills-linux-r3.log $PY
drills $D/m3/wave4e/drill-spec-wayland-linux.json $D/m3/wave4e/drills-wayland-linux.log $PY
drills $D/wave4e/crash/drill-spec-heard-linux.json $D/wave4e/crash/drills-heard-linux.log $PY
run $D/m3/wave4e/sway-tests-linux.log $PY -m pytest -p no:cacheprovider -v -rs tests/test_sway.py tests/test_wayland.py
M3="tests/test_wayland.py tests/test_xkb.py tests/test_overlay_stage.py tests/test_clickthrough.py tests/test_stage_timer.py tests/test_behavior.py tests/test_sprites.py tests/test_stagemenu.py tests/test_stage_features.py tests/test_sway.py"
run $D/m3/wave4e/m3-tests-linux.log $PY -m pytest -q -p no:cacheprovider -rs $M3
run $D/wave4e/suite-linux.log $PY -m pytest -q -p no:cacheprovider
inst; start=$(date -u +%H:%M:%S)
(cd /var/tmp && $PY $D/m3/memory.py "$R" --window > $D/m3/wave4e/memory-after--window.json 2> $D/m3/wave4e/memory-after--window.err)
echo "m3 memory exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
QT=tests/test_app_smoke.py::test_a_quit_companion_runs_nothing_it_had_waiting
inst; start=$(date -u +%H:%M:%S)
(cd "$R" && { header "$PY"
  for i in 1 2 3 4 5; do inst; echo; echo "\$ $PY -m pytest -p no:cacheprovider -v $QT   (run $i, UPower on the system bus, CHATMON_INSTANCE=$CHATMON_INSTANCE)"; $PY -m pytest -p no:cacheprovider -v "$QT" 2>&1 | grep -E "^E |passed|failed|PASSED|FAILED"; echo "# exit ${PIPESTATUS[0]}"; done
} > $D/wave4e/crash-test-wsl.log 2>&1)
echo "crash-test-wsl.log $(grep -c '^# exit 0' $D/wave4e/crash-test-wsl.log) of 5 passed $start-$(date -u +%H:%M:%S)" >> "$PROG"
for p in linux win32 darwin; do run $D/m6a/wave4e/mypy-pyqt6-6.12.1-$p.log $PY612 -m mypy --platform $p --no-incremental --cache-dir /var/tmp/plansfinal-mypy-$p; done
rm -rf /var/tmp/plansfinal-mypy-linux /var/tmp/plansfinal-mypy-win32 /var/tmp/plansfinal-mypy-darwin
start=$(date -u +%H:%M:%S)
rm -rf /var/tmp/plansfinal-howto && mkdir -p /var/tmp/plansfinal-howto && (cd "$R" && tr '\0' '\n' < "$L" | grep -v -e "^art/" -e "^docs/" | while IFS= read -r f; do [ -f "$f" ] && mkdir -p "/var/tmp/plansfinal-howto/$(dirname "$f")" && cp -p "$f" "/var/tmp/plansfinal-howto/$f"; done)
(cd /var/tmp && PATH="$HOME/.local/bin:$PATH" sh $D/m10/wave4e/howto-replay.sh /var/tmp/plansfinal-howto > $D/m10/wave4e/howto-replay.log 2>&1)
code=$?; rm -rf /var/tmp/plansfinal-howto /tmp/qt-next /tmp/qt-next.in /tmp/qt-next.txt; (exit $code)
echo "m10 howto replay exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
echo "left running: $(pgrep -u "$USER" -f 'plans-final|plansfinal|m4a-venv/bin/python|sway -d' | grep -vw $$ | wc -l)" >> "$PROG"
echo DONE >> "$PROG"
