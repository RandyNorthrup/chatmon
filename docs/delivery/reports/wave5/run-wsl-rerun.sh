#!/bin/bash
# The plans round for v0.10.0 (7816159): the whole suite in WSL failed 5 tests and errored 1 (suite-linux.log), run with
# nice 10 while the Windows runner's drills and gate drills ran beside it. Here those six run again, each alone and
# verbose, with nothing else running on the machine (both runners done), then the whole suite once more, the same way.
#   MSYS_NO_PATHCONV=1 wsl.exe -d archlinux -- nice -n 10 bash /mnt/c/Users/Randy/Coding/chatmon-wt/measure/docs/delivery/reports/wave5/run-wsl-rerun.sh
R=/mnt/c/Users/Randy/Coding/chatmon-wt/measure
D=$R/docs/delivery/reports
PY=/var/tmp/plans-venv/bin/python
PROG=$D/wave5/wsl-progress.txt
export QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1
unset WAYLAND_DISPLAY
n=0
inst() { n=$((n + 1)); export CHATMON_INSTANCE="plans5-wsl-rerun-$n-$$"; }
version() { "$1" -c 'import sys, PyQt6.QtCore as q; print(sys.version.split()[0], "PyQt6", q.PYQT_VERSION_STR, "Qt", q.qVersion())'; }
header() { echo "# WSL $(. /etc/os-release; echo "$NAME"), $(uname -r); sway $(sway --version | awk '{print $3}'); $(pacman -Q at-spi2-core orca upower kwin hyprland 2>&1 | tr '\n' ' '); system bus: $(busctl --system list --no-legend 2>/dev/null | awk '{print $1}' | grep -E 'UPower|login1' | tr '\n' ' '); $1: $(version "$1"); 7816159's files; nice $(nice); load $(cut -d' ' -f1-3 /proc/loadavg); CHATMON_INSTANCE=$CHATMON_INSTANCE"; }
FAILED="tests/test_sway.py::test_clicks_land_on_the_chatmon_and_pass_through_everywhere_else
tests/test_app_smoke.py::test_a_hook_reaches_it
tests/test_compositors.py::test_the_clipboard_goes_both_ways_between_the_overlay_other_apps_and_chatmons_own_windows[kwin]
tests/test_compositors.py::test_with_a_screen_reader_the_ask_box_is_a_window_on_screen_and_focused[hyprland]
tests/test_compositors.py::test_only_as_a_window_of_its_own_is_the_box_ever_an_active_window_to_a_screen_reader[hyprland-auto-True]
tests/test_compositors.py::test_with_orca_the_box_drawn_on_the_overlay_is_never_announced_as_a_window[kwin]"
start=$(date -u +%H:%M:%S)
(cd "$R" && {
  echo "$FAILED" | while IFS= read -r t; do
    inst; echo; header "$PY"; echo "\$ $PY -m pytest -p no:cacheprovider -v -rs '$t'"
    "$PY" -m pytest -p no:cacheprovider -v -rs "$t" 2>&1 | grep -E "PASSED|FAILED|ERROR|SKIPPED|^E  |passed|failed|error"; echo "# exit ${PIPESTATUS[0]}"
  done
} > $D/wave5/suite-linux-failures-rerun.log 2>&1)
echo "suite-linux-failures-rerun.log $(grep -c '^# exit 0' $D/wave5/suite-linux-failures-rerun.log) of 6 exit 0 $start-$(date -u +%H:%M:%S)" >> "$PROG"
inst; start=$(date -u +%H:%M:%S)
(cd "$R" && { header "$PY"; echo "\$ $PY -m pytest -q -p no:cacheprovider   (quiet machine: both runners done)"; "$PY" -m pytest -q -p no:cacheprovider 2>&1; echo "# exit $?"; } > $D/wave5/suite-linux-quiet.log)
echo "suite-linux-quiet.log $(grep -E 'passed|failed' $D/wave5/suite-linux-quiet.log | tail -1) $(tail -1 $D/wave5/suite-linux-quiet.log) $start-$(date -u +%H:%M:%S)" >> "$PROG"
echo "left running: $(pgrep -u "$USER" -f 'plans5|plans-venv/bin/python|fake_a11y_bus|sway -d' | grep -vw $$ | wc -l)" >> "$PROG"
echo DONE-RERUN >> "$PROG"
