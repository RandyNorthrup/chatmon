#!/bin/bash
# The final round's Windows checks on 45a17b3, one at a time: the suite, the stale plans' drill specs (M0, M3, M6B,
# M7, M8, M10) and the crash fix's, M6B's and M10's gate drills, M10's mypy runs, and the template check.
# Each run gets its own CHATMON_INSTANCE, so no two runs, nor anyone's running Chatmon, share an address.
cd /c/Users/Randy/Coding/chatmon-wt/plans-final || exit 2
PY=C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe
NEXT=C:/Users/Randy/AppData/Local/Temp/m10-qt6121/Scripts/python.exe     # PyQt6 6.12.1 and mypy 2.4.1 (M10's venv)
R=docs/delivery/reports
PROG=$R/wave4e/windows-progress.txt
export QT_QPA_PLATFORM=offscreen
n=0
inst() { n=$((n + 1)); export CHATMON_INSTANCE="plansfinal-win-$n-$$"; }
inst; { echo "\$ python -m pytest --collect-only -q -p no:cacheprovider   (CHATMON_INSTANCE=$CHATMON_INSTANCE)"; $PY -m pytest --collect-only -q -p no:cacheprovider; } > $R/wave4e/collect-45a17b3.txt 2>&1
inst; start=$(date -u +%H:%M:%S); { echo "# 45a17b3, Windows 11, $($PY --version), CHATMON_INSTANCE=$CHATMON_INSTANCE"; echo "\$ python -m pytest -q -p no:cacheprovider"; $PY -m pytest -q -p no:cacheprovider 2>&1; echo "# exit $?"; } > $R/wave4e/suite-windows.log
echo "suite-windows.log $(grep -E 'passed|failed' $R/wave4e/suite-windows.log | tail -1) $(tail -1 $R/wave4e/suite-windows.log) $start-$(date -u +%H:%M:%S)" >> "$PROG"
drill() {  # spec python
  inst; dir=$(dirname "$1"); base=$(basename "$1" .json); log="$dir/${base/drill-spec/drills}.log"; start=$(date -u +%H:%M:%S)
  "$2" tests/drills/run.py "$1" --log "$log" --python "$2" > "$dir/${base/drill-spec/drills}-run.txt" 2>&1
  echo "$1 exit $? $start-$(date -u +%H:%M:%S) $(grep -c '^PASS' "$log" 2>/dev/null) pass $(grep -c '^FAIL' "$log" 2>/dev/null) fail" >> "$PROG"
}
for spec in $R/m0/wave4e/drill-spec.json $R/m0/wave4e/drill-spec-new.json $R/m0/wave4e/drill-spec-new2.json \
            $R/m3/wave4e/drill-spec-r3.json $R/m3/wave4e/drill-spec-wayland.json \
            $R/m6b/wave4e/drill-spec.json $R/m6b/wave4e/drill-spec-b.json \
            $R/m7/wave4e/drill-spec.json $R/m7/wave4e/drill-spec-new.json $R/m7/wave4e/drill-spec-v3.json \
            $R/m8/wave4e/drill-spec.json $R/m8/wave4e/drill-spec-b.json $R/m8/wave4e/drill-spec-c.json $R/m8/wave4e/drill-spec-english.json \
            $R/m10/wave4e/drill-spec.json $R/wave4e/crash/drill-spec.json $R/wave4e/crash/drill-spec-new.json; do
  drill "$spec" "$PY"
done
inst; start=$(date -u +%H:%M:%S); $PY $R/m6b/wave4e/gate_drills.py > $R/m6b/wave4e/gate-drills-run.txt 2>&1; echo "m6b gate drills exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
inst; start=$(date -u +%H:%M:%S); $PY $R/m10/wave4e/gate_drills.py "$NEXT" > $R/m10/wave4e/gate-drills-run.txt 2>&1; echo "m10 gate drills exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
$PY $R/m10/mypy_runs.py "$PY" $R/m10/wave4e/mypy-611.log > /dev/null 2>&1; echo "m10 mypy 6.11 exit $?" >> "$PROG"
$PY $R/m10/mypy_runs.py "$NEXT" $R/m10/wave4e/mypy-6121.log > /dev/null 2>&1; echo "m10 mypy 6.12.1 exit $?" >> "$PROG"
{ echo "# packaging/extract_strings.py --check at $(git rev-parse HEAD), $(date -u +%Y-%m-%dT%H:%M:%SZ), Windows 11, Python 3.14.10"; echo '$ C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe packaging/extract_strings.py --check'; $PY packaging/extract_strings.py --check; echo "exit $?"; } > $R/wave4e/extract-strings-check.log 2>&1
echo "template exit $(tail -1 $R/wave4e/extract-strings-check.log)" >> "$PROG"
echo DONE >> "$PROG"
