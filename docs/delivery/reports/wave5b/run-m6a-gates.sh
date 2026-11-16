#!/bin/bash
# The plans round for v0.10.0, bound again at 56caddd: M6A's gate drills, after run-windows.sh, on CI's own coverage
# data for 56caddd (the three Python 3.14 legs' artifacts of PR #24's run 43794815103, gh run download -p 'coverage-*'),
# combined here as CI's coverage job combines them. BelowNormal priority, a CHATMON_INSTANCE of its own.
#   cmd //c start "" //belownormal //b //wait "C:/Program Files/Git/usr/bin/bash.exe" docs/delivery/reports/wave5b/run-m6a-gates.sh
cd /c/Users/Randy/Coding/chatmon-wt/measure || exit 2
PY=C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe
S=C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad
R=docs/delivery/reports
PROG=$R/wave5b/windows-progress.txt
export QT_QPA_PLATFORM=offscreen CHATMON_INSTANCE="plans5b-win-m6a-gates-$$"
mkdir -p build/wave5b-coverage
{ echo "# CI's coverage data for 56caddd (the three Python 3.14 legs' artifacts of PR #24's run 43794815103, gh run download -p 'coverage-*'), combined here as CI's coverage job combines them"; echo '$ python -m coverage combine --keep --data-file build/wave5b-coverage/.coverage.combined <the data files>'; $PY -m coverage combine --keep --data-file build/wave5b-coverage/.coverage.combined $(find "$S/covart5b" -type f -name ".coverage.*"); echo "# exit $?"; echo '$ python -m coverage report --data-file build/wave5b-coverage/.coverage.combined (pyproject.toml: fail_under = 84)'; $PY -m coverage report --data-file build/wave5b-coverage/.coverage.combined | tail -3; echo "# exit ${PIPESTATUS[0]}"; } > $R/m6a/wave5b/coverage-combined.log 2>&1
start=$(date -u +%H:%M:%S); $PY $R/m6a/wave5b/gate_drills.py --coverage-data build/wave5b-coverage/.coverage.combined --build-python "$S/buildvenv/Scripts/python.exe" > $R/m6a/wave5b/gate-drills-run.txt 2>&1; echo "m6a gate drills exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
echo DONE-M6A-GATES >> "$PROG"
