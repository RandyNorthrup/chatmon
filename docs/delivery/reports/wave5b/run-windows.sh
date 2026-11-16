#!/bin/bash
# The plans round for v0.10.0, bound again at 56caddd (df3e93c: layer.py's two instance() calls typed, CONTRIBUTING.md's
# opt-in table; 56caddd: test_hide_menu_and_reload waits for the greeting): every Windows check of the seven plans they
# staled (M0, M3, M6A, M6B, M7, M8, M10), one at a time, each with its own CHATMON_INSTANCE, at BelowNormal priority.
# The checks that failed at 7816159 run first. M6A's gate drills wait for CI's coverage data of 56caddd and run apart.
#   cmd //c start "" //belownormal //b //wait "C:/Program Files/Git/usr/bin/bash.exe" docs/delivery/reports/wave5b/run-windows.sh
cd /c/Users/Randy/Coding/chatmon-wt/measure || exit 2
PY=C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe
NEXT=C:/Users/Randy/AppData/Local/Temp/m10-qt6121/Scripts/python.exe     # PyQt6 6.12.1 and mypy 2.4.1 (M10's venv)
CIVENV=C:/Users/Randy/AppData/Local/Temp/m10-ci-test/Scripts/python.exe  # packaging/requirements-test.txt: comtypes 1.4.17 (M10's venv)
S=C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad
R=docs/delivery/reports
W=$R/wave5b
PROG=$W/windows-progress.txt
export QT_QPA_PLATFORM=offscreen
n=0
inst() { n=$((n + 1)); export CHATMON_INSTANCE="plans5b-win-$n-$$"; }
# The checks that failed at 7816159 on layer.py: M10's 6.12.1 gate drills and mypy runs.
inst; start=$(date -u +%H:%M:%S); $PY $R/m10/wave5b/gate_drills.py "$NEXT" > $R/m10/wave5b/gate-drills-run.txt 2>&1; echo "m10 gate drills exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
$PY $R/m10/mypy_runs.py "$PY" $R/m10/wave5b/mypy-611.log > /dev/null 2>&1; echo "m10 mypy 6.11 exit $?" >> "$PROG"
$PY $R/m10/mypy_runs.py "$NEXT" $R/m10/wave5b/mypy-6121.log > /dev/null 2>&1; echo "m10 mypy 6.12.1 exit $?" >> "$PROG"
# The coordinator's drill of 56caddd's test fix, run as a .py copy (it stays .txt in the repository).
mkdir -p "$S/flaky5b" && cp docs/delivery/reports/wave5/flaky-hide-menu/drill.py.txt "$S/flaky5b/test_flaky_hide_menu_drill.py"
inst; { echo "# The coordinator's drill for test_hide_menu_and_reload (wave5/flaky-hide-menu/drill.py.txt, run as a .py copy), $(git rev-parse --short HEAD), $(date -u +%Y-%m-%dT%H:%M:%SZ), Windows 11, $($PY --version), CHATMON_INSTANCE=$CHATMON_INSTANCE"; echo "\$ python -m pytest -p no:cacheprovider -v <copy>/test_flaky_hide_menu_drill.py --rootdir .   (expected: the old body fails, 1; the new body passes, 4)"; $PY -m pytest -p no:cacheprovider -v "$S/flaky5b/test_flaky_hide_menu_drill.py" --rootdir . 2>&1 | grep -v "^$"; echo "# exit ${PIPESTATUS[0]}"; } > $W/flaky-hide-menu-drill-windows.log
echo "flaky drill $(grep -E 'passed|failed' $W/flaky-hide-menu-drill-windows.log | tail -1)" >> "$PROG"
inst; { echo "\$ python -m pytest --collect-only -q -p no:cacheprovider   (CHATMON_INSTANCE=$CHATMON_INSTANCE)"; $PY -m pytest --collect-only -q -p no:cacheprovider; } > $W/collect-56caddd.txt 2>&1
$PY -m pytest --collect-only -q -p no:cacheprovider tests/test_presence.py -k gnome > $W/collect-56caddd-gnome.txt 2>&1
$PY -m pytest --collect-only -q -p no:cacheprovider tests/test_macnative.py > $W/collect-56caddd-macnative.txt 2>&1
$PY -m pytest --collect-only -q -p no:cacheprovider tests/test_windows.py -k "tells_the_display or drop_target or zip or paste" > $W/collect-56caddd-windows-real.txt 2>&1
$PY -m pytest --collect-only -q -p no:cacheprovider tests/test_sway.py tests/test_wayland.py > $W/collect-56caddd-sway.txt 2>&1
echo "collections $(tail -1 $W/collect-56caddd.txt)" >> "$PROG"
inst; start=$(date -u +%H:%M:%S); { echo "# 56caddd, Windows 11, $($PY --version), BelowNormal priority, CHATMON_INSTANCE=$CHATMON_INSTANCE"; echo "\$ python -m pytest -q -p no:cacheprovider"; $PY -m pytest -q -p no:cacheprovider 2>&1; echo "# exit $?"; } > $W/suite-windows.log
echo "suite-windows.log $(grep -E 'passed|failed' $W/suite-windows.log | tail -1) $(tail -1 $W/suite-windows.log) $start-$(date -u +%H:%M:%S)" >> "$PROG"
drill() {  # spec python
  inst; dir=$(dirname "$1"); base=$(basename "$1" .json); log="$dir/${base/drill-spec/drills}.log"; start=$(date -u +%H:%M:%S)
  "$2" tests/drills/run.py "$1" --log "$log" --python "$2" > "$dir/${base/drill-spec/drills}-run.txt" 2>&1
  echo "$1 exit $? $start-$(date -u +%H:%M:%S) $(grep -c '^PASS' "$log" 2>/dev/null) pass $(grep -c '^FAIL' "$log" 2>/dev/null) fail" >> "$PROG"
}
for spec in $R/m6a/wave5b/drill-spec.json $R/m6a/wave5b/drill-spec-pins.json \
            $R/m10/wave5b/drill-spec.json \
            $R/m0/wave5b/drill-spec.json $R/m0/wave5b/drill-spec-new.json $R/m0/wave5b/drill-spec-new2.json \
            $R/m3/wave5b/drill-spec-r3.json $R/m3/wave5b/drill-spec-wayland.json \
            $R/m8/wave5b/drill-spec.json $R/m8/wave5b/drill-spec-b.json $R/m8/wave5b/drill-spec-c.json $R/m8/wave5b/drill-spec-english.json \
            $R/m6b/wave5b/drill-spec.json $R/m6b/wave5b/drill-spec-b.json \
            $R/m7/wave5b/drill-spec.json $R/m7/wave5b/drill-spec-new.json $R/m7/wave5b/drill-spec-v3.json; do
  drill "$spec" "$PY"
done
drill $R/m10/wave5b/drill-spec-ci-venv.json "$CIVENV"
inst; start=$(date -u +%H:%M:%S); $PY $R/m6b/wave5b/gate_drills.py > $R/m6b/wave5b/gate-drills-run.txt 2>&1; echo "m6b gate drills exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
inst; { echo "# M10-01.A2 in a venv of packaging/requirements-test.txt (comtypes 1.4.17, as CI's Windows legs), $(date -u +%Y-%m-%dT%H:%M:%SZ), $(git rev-parse --short HEAD), CHATMON_INSTANCE=$CHATMON_INSTANCE"; echo "\$ $CIVENV -m pytest -q -p no:cacheprovider -rs tests/test_platform_events.py::test_a_ui_automation_client_hears_the_announcement"; "$CIVENV" -m pip list --disable-pip-version-check 2>/dev/null | grep -iE "^(comtypes|PyQt6|pytest) "; "$CIVENV" -m pytest -q -p no:cacheprovider -rs tests/test_platform_events.py::test_a_ui_automation_client_hears_the_announcement 2>&1; echo "exit $?"; } > $R/m10/wave5b/uia-ci-venv.log
echo "uia-ci-venv $(tail -1 $R/m10/wave5b/uia-ci-venv.log)" >> "$PROG"
inst; bash $W/run-locks.sh
"$S/buildvenv/Scripts/python.exe" $R/m6a/wave5b/sde_check.py "$S/buildvenv/Scripts/python.exe" $R/m6a/wave5b/source-date-epoch.log > /dev/null 2>&1; echo "m6a sde exit $?" >> "$PROG"
inst; { echo "# M6A-11 on Windows 11, Python 3.14.10, $(date -u +%Y-%m-%dT%H:%M:%SZ), $(git rev-parse --short HEAD), CHATMON_INSTANCE=$CHATMON_INSTANCE"; echo '$ python -m pytest -v -rs -p no:cacheprovider tests/test_windows.py -k windows_update_check'; $PY -m pytest -v -rs -p no:cacheprovider tests/test_windows.py -k windows_update_check 2>&1 | grep -v "^$"; echo "exit ${PIPESTATUS[0]}"; echo; echo '$ CHATMON_TEST_WINDOWS_UPDATE=1 python -m pytest -v -rs -p no:cacheprovider --durations=1 tests/test_windows.py -k windows_update_check'; CHATMON_TEST_WINDOWS_UPDATE=1 $PY -m pytest -v -rs -p no:cacheprovider --durations=1 tests/test_windows.py -k windows_update_check 2>&1 | grep -v "^$"; echo "exit ${PIPESTATUS[0]}"; } > $R/m6a/wave5b/windows-update-optin.log
echo "m6a winupdate $(grep -c '^exit 0' $R/m6a/wave5b/windows-update-optin.log) of 2 exit 0" >> "$PROG"
CJ=$S/jsonschema-venv/Scripts/check-jsonschema.exe
{ echo "# .github/dependabot.yml and .github/workflows/pins.yml at $(git rev-parse --short HEAD) against SchemaStore's schemas (check-jsonschema's built-in copies), $(date -u +%Y-%m-%dT%H:%M:%SZ)"; echo "$ check-jsonschema --version"; $CJ --version; echo '$ check-jsonschema --builtin-schema vendor.dependabot .github/dependabot.yml'; $CJ --builtin-schema vendor.dependabot .github/dependabot.yml; echo "exit $?"; echo '$ check-jsonschema --builtin-schema vendor.github-workflows .github/workflows/pins.yml'; $CJ --builtin-schema vendor.github-workflows .github/workflows/pins.yml; echo "exit $?"; } > $R/m6a/wave5b/dependabot-schema.log 2>&1
echo "m6a dependabot $(grep -c '^exit 0' $R/m6a/wave5b/dependabot-schema.log) of 2 exit 0" >> "$PROG"
inst; { echo "# M6A-02B: the pins check's own steps, as pins.yml's types job runs them, at $(git rev-parse --short HEAD), $(date -u +%Y-%m-%dT%H:%M:%SZ), Windows 11, $($PY --version), CHATMON_INSTANCE=$CHATMON_INSTANCE"; for p in linux win32 darwin; do echo "\$ python -m mypy --strict --platform $p --no-incremental packaging/pins.py"; $PY -m mypy --strict --platform $p --no-incremental packaging/pins.py 2>&1; echo "exit $?"; done; echo '$ python -m pytest -p no:cacheprovider -v -rs tests/test_pins.py tests/test_requirements.py'; $PY -m pytest -p no:cacheprovider -v -rs tests/test_pins.py tests/test_requirements.py 2>&1; echo "exit $?"; } > $R/m6a/wave5b/pins-tests.log
echo "m6a pins tests $(grep -c '^exit 0' $R/m6a/wave5b/pins-tests.log) of 4 exit 0" >> "$PROG"
{ echo "# packaging/extract_strings.py --check at $(git rev-parse HEAD), $(date -u +%Y-%m-%dT%H:%M:%SZ), Windows 11, Python 3.14.10"; echo '$ C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe packaging/extract_strings.py --check'; $PY packaging/extract_strings.py --check; echo "exit $?"; } > $W/extract-strings-check.log 2>&1
echo "template $(tail -1 $W/extract-strings-check.log)" >> "$PROG"
echo DONE >> "$PROG"
