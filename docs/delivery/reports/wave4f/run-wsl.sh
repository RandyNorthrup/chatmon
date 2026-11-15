#!/bin/bash
# The final round, M6A's section: the Linux half of M6A's, M6B's and M10's checks on 45a17b3, in WSL (Arch).
#   bash /mnt/c/Users/Randy/Coding/chatmon-wt/plans-final/docs/delivery/reports/wave4f/run-wsl.sh
R=/mnt/c/Users/Randy/Coding/chatmon-wt/plans-final
D=$R/docs/delivery/reports
PY=/var/tmp/plans-venv/bin/python      # packaging/requirements-test.txt: PyQt6 6.11.0, as CI
PY612=/var/tmp/m4a-venv/bin/python     # PyQt6 6.12.1 and mypy 2.4.1
L=$D/wave4e/files-45a17b3.lst
T=$D/wave4/wsl_drills.py
PROG=$D/wave4f/wsl-progress.txt
export QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1
unset WAYLAND_DISPLAY
cd /var/tmp || exit 2
n=0
inst() { n=$((n + 1)); export CHATMON_INSTANCE="plansfinal-4f-wsl-$n-$$"; }
version() { "$1" -c 'import sys, PyQt6.QtCore as q; print(sys.version.split()[0], "PyQt6", q.PYQT_VERSION_STR, "Qt", q.qVersion())'; }
header() { echo "# WSL $(. /etc/os-release; echo "$NAME"), $(uname -r); $1: $(version "$1"); 45a17b3's files; CHATMON_INSTANCE=$CHATMON_INSTANCE"; }
inst; start=$(date -u +%H:%M:%S)
xvfb-run -a "$PY" "$T" "$R" $D/m6b/wave4f/drill-spec-linux.json $D/m6b/wave4f/drills-linux.log "$L" > $D/m6b/wave4f/drills-linux-run.txt 2>&1
echo "m6b/drill-spec-linux.json exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
for p in linux win32 darwin; do
  inst; start=$(date -u +%H:%M:%S); log=$D/m6a/wave4f/mypy-pyqt6-6.12.1-$p.log
  (cd "$R" && { header "$PY612"; echo "\$ $PY612 -m mypy --platform $p --no-incremental --cache-dir /var/tmp/plansfinal4f-mypy-$p"; "$PY612" -m mypy --platform $p --no-incremental --cache-dir /var/tmp/plansfinal4f-mypy-$p 2>&1; echo "# exit $?"; } > "$log")
  echo "$(basename "$log") $(grep -E 'Success|Found' "$log" | tail -1) $(tail -1 "$log") $start-$(date -u +%H:%M:%S)" >> "$PROG"
done
rm -rf /var/tmp/plansfinal4f-mypy-linux /var/tmp/plansfinal4f-mypy-win32 /var/tmp/plansfinal4f-mypy-darwin
start=$(date -u +%H:%M:%S)
rm -rf /var/tmp/plansfinal4f-howto && mkdir -p /var/tmp/plansfinal4f-howto && (cd "$R" && tr '\0' '\n' < "$L" | grep -v -e "^art/" -e "^docs/" | while IFS= read -r f; do [ -f "$f" ] && mkdir -p "/var/tmp/plansfinal4f-howto/$(dirname "$f")" && cp -p "$f" "/var/tmp/plansfinal4f-howto/$f"; done)
(cd /var/tmp && PATH="$HOME/.local/bin:$PATH" sh $D/m10/wave4f/howto-replay.sh /var/tmp/plansfinal4f-howto > $D/m10/wave4f/howto-replay.log 2>&1)
code=$?; rm -rf /var/tmp/plansfinal4f-howto /tmp/qt-next /tmp/qt-next.in /tmp/qt-next.txt; (exit $code)
echo "m10 howto replay exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
inst; start=$(date -u +%H:%M:%S)
bash $D/m6a/wave4f/distro_drill.sh "$R" "$L" $D/m6a/wave4f
echo "m6a distro drill exit $? $start-$(date -u +%H:%M:%S)" >> "$PROG"
echo DONE >> "$PROG"
