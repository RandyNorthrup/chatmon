#!/bin/bash
# The final round, for M10: binding its round in the plan's prose stales every M10 receipt, so the three checks
# round three's other receipts rested on run again too: the red drill in the CI-shaped venv, the UI Automation test
# there, and the locks (run-windows2.sh).
cd /c/Users/Randy/Coding/chatmon-wt/plans-final || exit 2
CIVENV=C:/Users/Randy/AppData/Local/Temp/m10-ci-test/Scripts/python.exe  # packaging/requirements-test.txt: comtypes 1.4.17 (M10's venv)
R=docs/delivery/reports
PROG=$R/wave4e/windows-progress.txt
export QT_QPA_PLATFORM=offscreen
export CHATMON_INSTANCE="plansfinal-win3-ci-venv-$$"
start=$(date -u +%H:%M:%S); "$CIVENV" tests/drills/run.py $R/m10/wave4e/drill-spec-ci-venv.json --log $R/m10/wave4e/drills-ci-venv.log --python "$CIVENV" > $R/m10/wave4e/drills-ci-venv-run.txt 2>&1
echo "$R/m10/wave4e/drill-spec-ci-venv.json exit $? $start-$(date -u +%H:%M:%S) $(grep -c '^PASS' $R/m10/wave4e/drills-ci-venv.log) pass" >> "$PROG"
export CHATMON_INSTANCE="plansfinal-win3-uia-$$"
{ echo "# M10-01.A2 in a venv of packaging/requirements-test.txt (comtypes 1.4.17, as CI's Windows legs), $(date -u +%Y-%m-%dT%H:%M:%SZ), 45a17b3, CHATMON_INSTANCE=$CHATMON_INSTANCE"; echo "\$ $CIVENV -m pytest -q -p no:cacheprovider -rs tests/test_platform_events.py::test_a_ui_automation_client_hears_the_announcement"; "$CIVENV" -m pip list --disable-pip-version-check 2>/dev/null | grep -iE "^(comtypes|PyQt6|pytest) "; "$CIVENV" -m pytest -q -p no:cacheprovider -rs tests/test_platform_events.py::test_a_ui_automation_client_hears_the_announcement 2>&1; echo "exit $?"; } > $R/m10/wave4e/uia-ci-venv.log
echo "uia-ci-venv $(tail -1 $R/m10/wave4e/uia-ci-venv.log)" >> "$PROG"
export CHATMON_INSTANCE="plansfinal-win3-locks-$$"
bash $R/wave4e/run-windows2.sh
