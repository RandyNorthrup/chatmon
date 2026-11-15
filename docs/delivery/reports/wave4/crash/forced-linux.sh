#!/bin/sh
# forced_repro.py five times on the base checkout and five on the fixed one, in the fedora:44 container
for which in base fixed; do
    if [ $which = base ]; then root=/home/chatmon-tests/base; rev="bf9d8ac (base)"; else root=/home/chatmon-tests/chatmon; rev="bf9d8ac + this commit's harness and app.py"; fi
    out=/home/chatmon-tests/forced-linux-$which.log
    {
        echo "# forced_repro.py in a fedora:44 container ($(python3 -c 'import sys; from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR; print(f"Python {sys.version.split()[0]}, PyQt6 {PYQT_VERSION_STR}, Qt {QT_VERSION_STR}")'), CI's packages), offscreen, as CI's user; source: $rev"
        for i in 1 2 3 4 5; do
            echo "## run $i"
            (cd $root && python3 -X faulthandler /home/chatmon-tests/chatmon/docs/delivery/reports/wave4/crash/forced_repro.py $root 2>&1)
            echo "# exit $?"
        done
    } > $out
    echo "$which: exits $(grep '^# exit' $out | sed 's/# exit //' | tr '\n' ' ')| freed inside: $(grep -o 'freed inside them: [0-9]*' $out | sed 's/.*: //' | tr '\n' ' ')| segfaults: $(grep -c 'Fatal Python error: Segmentation fault' $out)"
done
