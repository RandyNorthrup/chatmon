#!/bin/bash
# The final round, M6A's section: M6A's plan gains its final-round section, so every M6A receipt goes stale (a plan's
# prose is in each receipt's scope), and so do M6B's and M10's, which bind M6A's plan. Every check of the three runs
# again on 45a17b3 here (wave4f/), one at a time, each with its own CHATMON_INSTANCE.
cd /c/Users/Randy/Coding/chatmon-wt/plans-final || exit 2
PY=C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe
NEXT=C:/Users/Randy/AppData/Local/Temp/m10-qt6121/Scripts/python.exe     # PyQt6 6.12.1 and mypy 2.4.1 (M10's venv)
CIVENV=C:/Users/Randy/AppData/Local/Temp/m10-ci-test/Scripts/python.exe  # packaging/requirements-test.txt: comtypes 1.4.17 (M10's venv)
S=C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad
R=docs/delivery/reports
PROG=$R/wave4f/windows-progress.txt
export QT_QPA_PLATFORM=offscreen
n=0
inst() { n=$((n + 1)); export CHATMON_INSTANCE="plansfinal-4f-win-$n-$$"; }
inst; start=$(date -u +%H:%M:%S); { echo "# 45a17b3, Windows 11, $($PY --version), CHATMON_INSTANCE=$CHATMON_INSTANCE"; echo "\$ python -m pytest -q -p no:cacheprovider"; $PY -m pytest -q -p no:cacheprovider 2>&1; echo "# exit $?"; } > $R/wave4f/suite-windows.log
echo "suite-windows.log $(grep -E 'passed|failed' $R/wave4f/suite-windows.log | tail -1) $(tail -1 $R/wave4f/suite-windows.log) $start-$(date -u +%H:%M:%S)" >> "$PROG"
drill() {  # spec python
  inst; dir=$(dirname "$1"); base=$(basename "$1" .json); log="$dir/${base/drill-spec/drills}.log"; start=$(date -u +%H:%M:%S)
  "$2" tests/drills/run.py "$1" --log "$log" --python "$2" > "$dir/${base/drill-spec/drills}-run.txt" 2>&1
  echo "$1 exit $? $start-$(date -u +%H:%M:%S) $(grep -c '^PASS' "$log" 2>/dev/null) pass $(grep -c '^FAIL' "$log" 2>/dev/null) fail" >> "$PROG"
}
for spec in $R/m6a/wave4f/drill-spec.json $R/m6b/wave4f/drill-spec.json $R/m6b/wave4f/drill-spec-b.json $R/m10/wave4f/drill-spec.json; do
  drill "$spec" "$PY"
done
drill $R/m10/wave4f/drill-spec-ci-venv.json "$CIVENV"
mkdir -p build/wave4f-coverage
{ echo "# CI's coverage data for 45a17b3 (the three Python 3.14 legs' artifacts of run 43743804662, gh run download -p 'coverage-*'), combined here as CI's coverage job combines them"; echo '$ python -m coverage combine --keep --data-file build/wave4f-coverage/.coverage.combined <the data files>'; $PY -m coverage combine --keep --data-file build/wave4f-coverage/.coverage.combined $(find "$S/covart4" -type f -name ".coverage.*"); echo "# exit $?"; echo '$ python -m coverage report --data-file build/wave4f-coverage/.coverage.combined (pyproject.toml: fail_under = 84)'; $PY -m coverage report --data-file build/wave4f-coverage/.coverage.combined | tail -3; echo "# exit ${PIPESTATUS[0]}"; } > $R/m6a/wave4f/coverage-combined.log 2>&1
inst; start=$(date -u +%H:%M:%S); $PY $R/m6a/wave4f/gate_drills.py --coverage-data build/wave4f-coverage/.coverage.combined --build-python "$S/buildvenv/Scripts/python.exe" > $R/m6a/wave4f/gate-drills-run.txt 2>&1; echo "m6a gate drills exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
inst; start=$(date -u +%H:%M:%S); $PY $R/m6b/wave4f/gate_drills.py > $R/m6b/wave4f/gate-drills-run.txt 2>&1; echo "m6b gate drills exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
inst; start=$(date -u +%H:%M:%S); $PY $R/m10/wave4f/gate_drills.py "$NEXT" > $R/m10/wave4f/gate-drills-run.txt 2>&1; echo "m10 gate drills exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
$PY $R/m10/mypy_runs.py "$PY" $R/m10/wave4f/mypy-611.log > /dev/null 2>&1; echo "m10 mypy 6.11 exit $?" >> "$PROG"
$PY $R/m10/mypy_runs.py "$NEXT" $R/m10/wave4f/mypy-6121.log > /dev/null 2>&1; echo "m10 mypy 6.12.1 exit $?" >> "$PROG"
inst; { echo "# M10-01.A2 in a venv of packaging/requirements-test.txt (comtypes 1.4.17, as CI's Windows legs), $(date -u +%Y-%m-%dT%H:%M:%SZ), 45a17b3, CHATMON_INSTANCE=$CHATMON_INSTANCE"; echo "\$ $CIVENV -m pytest -q -p no:cacheprovider -rs tests/test_platform_events.py::test_a_ui_automation_client_hears_the_announcement"; "$CIVENV" -m pip list --disable-pip-version-check 2>/dev/null | grep -iE "^(comtypes|PyQt6|pytest) "; "$CIVENV" -m pytest -q -p no:cacheprovider -rs tests/test_platform_events.py::test_a_ui_automation_client_hears_the_announcement 2>&1; echo "exit $?"; } > $R/m10/wave4f/uia-ci-venv.log
echo "uia-ci-venv $(tail -1 $R/m10/wave4f/uia-ci-venv.log)" >> "$PROG"
inst; bash $R/wave4f/run-locks.sh
"$S/buildvenv/Scripts/python.exe" $R/m6a/wave4f/sde_check.py "$S/buildvenv/Scripts/python.exe" $R/m6a/wave4f/source-date-epoch.log > /dev/null 2>&1; echo "m6a sde exit $?" >> "$PROG"
inst; { echo "# M6A-11 on Windows 11, Python 3.14.10, $(date -u +%Y-%m-%dT%H:%M:%SZ), $(git rev-parse --short HEAD), CHATMON_INSTANCE=$CHATMON_INSTANCE"; echo '$ python -m pytest -v -rs -p no:cacheprovider tests/test_windows.py -k windows_update_check'; $PY -m pytest -v -rs -p no:cacheprovider tests/test_windows.py -k windows_update_check 2>&1 | grep -v "^$"; echo "exit ${PIPESTATUS[0]}"; echo; echo '$ CHATMON_TEST_WINDOWS_UPDATE=1 python -m pytest -v -rs -p no:cacheprovider --durations=1 tests/test_windows.py -k windows_update_check'; CHATMON_TEST_WINDOWS_UPDATE=1 $PY -m pytest -v -rs -p no:cacheprovider --durations=1 tests/test_windows.py -k windows_update_check 2>&1 | grep -v "^$"; echo "exit ${PIPESTATUS[0]}"; } > $R/m6a/wave4f/windows-update-optin.log
echo "m6a winupdate $(grep -c '^exit 0' $R/m6a/wave4f/windows-update-optin.log) of 2 exit 0" >> "$PROG"
{ echo "# .github/dependabot.yml at $(git rev-parse --short HEAD) against SchemaStore's Dependabot schema (check-jsonschema's built-in copy), $(date -u +%Y-%m-%dT%H:%M:%SZ)"; echo "$ check-jsonschema --version"; $S/jsonschema-venv/Scripts/check-jsonschema.exe --version; echo '$ check-jsonschema --builtin-schema vendor.dependabot .github/dependabot.yml'; $S/jsonschema-venv/Scripts/check-jsonschema.exe --builtin-schema vendor.dependabot .github/dependabot.yml; echo "exit $?"; } > $R/m6a/wave4f/dependabot-schema.log 2>&1
echo "m6a dependabot $(tail -1 $R/m6a/wave4f/dependabot-schema.log)" >> "$PROG"
{ echo "# packaging/extract_strings.py --check at $(git rev-parse HEAD), $(date -u +%Y-%m-%dT%H:%M:%SZ), Windows 11, Python 3.14.10"; echo '$ C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe packaging/extract_strings.py --check'; $PY packaging/extract_strings.py --check; echo "exit $?"; } > $R/wave4f/extract-strings-check.log 2>&1
echo "template $(tail -1 $R/wave4f/extract-strings-check.log)" >> "$PROG"
echo DONE >> "$PROG"
