#!/bin/bash
R=/mnt/c/Users/Randy/Coding/chatmon-wt/plans
S=/mnt/c/Users/Randy/Coding/chatmon-wt/plans/docs/delivery/reports/wave4/resume
PY=/var/tmp/plans-venv/bin/python
PY612=/var/tmp/m4a-venv/bin/python
L=$S/files-fb19cb9.lst
T=$R/docs/delivery/reports/wave4/wsl_drills.py
PROG=$S/wsl-progress.txt
export QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1
cd /var/tmp || exit 2
drills() {  # spec log python
    start=$(date -u +%H:%M:%S)
    xvfb-run -a "$3" "$T" "$R" "$1" "$2" "$L" > "${2%.log}-run.txt" 2>&1
    echo "$1 exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
}
D=$R/docs/delivery/reports
# done before the pause (06:05-06:06Z, all green-red-green): drills $D/m0/wave4/drill-spec-linux.json $D/m0/wave4/drills-linux.log $PY
# done before the pause (06:05-06:06Z, all green-red-green): drills $D/m1a/wave4/drill-spec-linux.json $D/m1a/wave4/drills-linux.log $PY
# done before the pause (06:05-06:06Z, all green-red-green): drills $D/m1b/wave4/drill-spec-linux.json $D/m1b/wave4/drills-linux.log $PY
drills $D/m4a/wave4/drill-spec-linux.json $D/m4a/wave4/drills-linux.log $PY
drills $D/m4b/wave4/wsl-drill-spec.json $D/m4b/wave4/wsl-drills.log $PY
drills $D/m4b/wave4/wsl-drill-spec-new.json $D/m4b/wave4/wsl-drills-new.log $PY
drills $D/m6b/wave4/drill-spec-linux.json $D/m6b/wave4/drills-linux.log $PY
drills $D/m4a/wave4/drill-spec-linux-qt612.json $D/m4a/wave4/drills-linux-qt612.log $PY612
# The one test CI's PyQt6 6.11 skips (contrastPreferenceChanged is a signal from PyQt6 6.12): its file, in WSL on 6.12.
start=$(date -u +%H:%M:%S)
(cd "$R" && { echo "# tests/test_presence.py in WSL (Arch), $(uname -r), /var/tmp/m4a-venv: $($PY612 -c 'import sys, PyQt6.QtCore as q; print(sys.version.split()[0], "PyQt6", q.PYQT_VERSION_STR, "Qt", q.qVersion())'), under xvfb-run -a, on fb19cb9's files"; echo '$ xvfb-run -a /var/tmp/m4a-venv/bin/python -m pytest -q -p no:cacheprovider -rA tests/test_presence.py'; xvfb-run -a $PY612 -m pytest -q -p no:cacheprovider -rA tests/test_presence.py 2>&1; echo "# exit $?"; } > $D/m4a/wave4/presence-linux-qt612.log)
echo "presence qt612 exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
start=$(date -u +%H:%M:%S)
bash $D/m6a/wave4/distro_drill.sh "$R" "$L" $D/m6a/wave4
echo "m6a distro drill exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
echo DONE >> "$PROG"
