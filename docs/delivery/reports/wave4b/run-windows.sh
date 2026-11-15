#!/bin/bash
cd /c/Users/Randy/Coding/chatmon-wt/plans2 || exit 2
PY=C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe
W=C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad
PROG="$W/win-r2-progress.txt"
R=docs/delivery/reports
export QT_QPA_PLATFORM=offscreen
for spec in $R/m0/wave4b/drill-spec.json $R/m0/wave4b/drill-spec-new.json $R/m0/wave4b/drill-spec-new2.json \
            $R/m1a/wave4b/drill-spec.json $R/m1b/wave4b/drill-spec.json $R/m1b/wave4b/drill-spec-new.json \
            $R/m2/wave4b/drill-spec.json $R/m3/wave4b/drill-spec-r3.json $R/m3/wave4b/drill-spec-wayland.json \
            $R/m4a/wave4b/w4-drill-spec.json $R/m4a/wave4b/readers-drill-spec.json $R/m4b/wave4b/drill-spec.json \
            $R/m5/wave4b/drill-spec.json $R/m5/wave4b/drill-spec-new.json $R/m6a/wave4b/drill-spec.json \
            $R/m6b/wave4b/drill-spec.json $R/m6b/wave4b/drill-spec-b.json $R/m7/wave4b/drill-spec.json $R/m7/wave4b/drill-spec-new.json \
            $R/m8/wave4b/drill-spec.json $R/m8/wave4b/drill-spec-b.json $R/m8/wave4b/drill-spec-c.json $R/m8/wave4b/drill-spec-english.json; do
  dir=$(dirname "$spec"); base=$(basename "$spec" .json); log="$dir/${base/drill-spec/drills}.log"
  start=$(date -u +%H:%M:%S)
  $PY tests/drills/run.py "$spec" --log "$log" --python "$PY" > "$dir/${base/drill-spec/drills}-run.txt" 2>&1
  echo "$spec exit $? $start-$(date -u +%H:%M:%S) $(grep -c '^PASS' "$log" 2>/dev/null) pass $(grep -c '^FAIL' "$log" 2>/dev/null) fail" >> "$PROG"
done
mkdir -p build/wave4b-coverage
{ echo "# CI run 43701523023's coverage data (bf9d8ac): coverage-windows-latest-3.14, coverage-macos-latest-3.14 and coverage-ubuntu-24.04-arm-3.14, from gh run download 43701523023 -p 'coverage-*', combined here as CI's coverage job combines them"; echo '$ python -m coverage combine --keep --data-file build/wave4b-coverage/.coverage.combined <the data files>'; $PY -m coverage combine --keep --data-file build/wave4b-coverage/.coverage.combined $(find "$W/covart2" -type f -name ".coverage.*"); echo "# exit $?"; echo '$ python -m coverage report --data-file build/wave4b-coverage/.coverage.combined (pyproject.toml: fail_under = 84)'; $PY -m coverage report --data-file build/wave4b-coverage/.coverage.combined | tail -3; echo "# exit $?"; } > $R/m6a/wave4b/coverage-combined.log 2>&1
start=$(date -u +%H:%M:%S)
$PY $R/m6a/wave4b/gate_drills.py --coverage-data build/wave4b-coverage/.coverage.combined --build-python "$W/buildvenv/Scripts/python.exe" > $R/m6a/wave4b/gate-drills-run.txt 2>&1
echo "m6a gate drills exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
start=$(date -u +%H:%M:%S)
$PY $R/m6b/wave4b/gate_drills.py > $R/m6b/wave4b/gate-drills-run.txt 2>&1
echo "m6b gate drills exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
$W/buildvenv/Scripts/python.exe $R/m6a/wave4b/sde_check.py "$W/buildvenv/Scripts/python.exe" $R/m6a/wave4b/source-date-epoch.log > /dev/null 2>&1
echo "m6a sde exit $?" >> "$PROG"
{ echo "# M6A-11 on Windows 11, Python 3.14.10, $(date -u +%Y-%m-%dT%H:%M:%SZ), $(git rev-parse --short HEAD)"; echo '$ python -m pytest -v -rs -p no:cacheprovider tests/test_windows.py -k windows_update_check'; $PY -m pytest -v -rs -p no:cacheprovider tests/test_windows.py -k windows_update_check 2>&1 | grep -v "^$"; echo "exit ${PIPESTATUS[0]}"; echo; echo '$ CHATMON_TEST_WINDOWS_UPDATE=1 python -m pytest -v -rs -p no:cacheprovider --durations=1 tests/test_windows.py -k windows_update_check'; CHATMON_TEST_WINDOWS_UPDATE=1 $PY -m pytest -v -rs -p no:cacheprovider --durations=1 tests/test_windows.py -k windows_update_check 2>&1 | grep -v "^$"; echo "exit ${PIPESTATUS[0]}"; } > $R/m6a/wave4b/windows-update-optin.log
echo "m6a windows update exit $?" >> "$PROG"
{ echo "# .github/dependabot.yml at $(git rev-parse --short HEAD) against SchemaStore's Dependabot schema (check-jsonschema's built-in copy), $(date -u +%Y-%m-%dT%H:%M:%SZ)"; echo "$ check-jsonschema --version"; $W/jsonschema-venv/Scripts/check-jsonschema.exe --version; echo '$ check-jsonschema --builtin-schema vendor.dependabot .github/dependabot.yml'; $W/jsonschema-venv/Scripts/check-jsonschema.exe --builtin-schema vendor.dependabot .github/dependabot.yml; echo "exit $?"; } > $R/m6a/wave4b/dependabot-schema.log 2>&1
{ echo "# packaging/extract_strings.py --check at $(git rev-parse HEAD), $(date -u +%Y-%m-%dT%H:%M:%SZ), Windows 11, Python 3.14.10"; echo '$ C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe packaging/extract_strings.py --check'; $PY packaging/extract_strings.py --check; echo "exit $?"; } > $R/wave4b/extract-strings-check.log 2>&1
echo DONE >> "$PROG"
