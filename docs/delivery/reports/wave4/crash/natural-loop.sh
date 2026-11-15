#!/bin/sh
# Run the suite's first files (to test_app_smoke, where CI crashed) again and again, as CI runs them, and say how each run ended.
# $1: runs, $2: a log folder; the rest: extra python options (such as -X faulthandler)
runs=$1; logs=$2; shift 2
mkdir -p "$logs"
cd /home/chatmon-tests/chatmon
files=$(ls tests/test_*.py | sort | awk '{print} /test_app_smoke.py/{exit}')
for i in $(seq 1 "$runs"); do
    start=$(date +%s)
    python3 -X faulthandler "$@" -m pytest -q -p no:cacheprovider -x $files > "$logs/run-$i.txt" 2>&1
    rc=$?
    echo "run $i: rc=$rc $(( $(date +%s) - start ))s $(grep -c 'Fatal Python error' "$logs/run-$i.txt") fatal; $(tail -1 "$logs/run-$i.txt")"
done
