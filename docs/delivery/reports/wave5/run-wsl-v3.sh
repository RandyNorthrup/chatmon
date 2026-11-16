#!/bin/bash
# The plans round for v0.10.0 (7816159): M3-RC-clipboard-v3, after -v2 left the real sway's clipboard test green
# (m3/wave5/drills-left-out.txt), run in WSL as run-wsl.sh runs every Linux drill.
#   MSYS_NO_PATHCONV=1 wsl.exe -d archlinux -- nice -n 10 bash /mnt/c/Users/Randy/Coding/chatmon-wt/measure/docs/delivery/reports/wave5/run-wsl-v3.sh
R=/mnt/c/Users/Randy/Coding/chatmon-wt/measure
D=$R/docs/delivery/reports
PY=/var/tmp/plans-venv/bin/python
export QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 CHATMON_INSTANCE="plans5-wsl-v3-$$"
unset WAYLAND_DISPLAY
cd /var/tmp || exit 2
start=$(date -u +%H:%M:%S)
xvfb-run -a "$PY" $D/wave4/wsl_drills.py "$R" $D/m3/wave5/drill-spec-wayland-linux-v3.json $D/m3/wave5/drills-wayland-linux-v3.log $D/wave5/files-7816159.lst > $D/m3/wave5/drills-wayland-linux-v3-run.txt 2>&1
echo "m3/drill-spec-wayland-linux-v3.json exit $? $start-$(date -u +%H:%M:%S)" >> $D/wave5/wsl-progress.txt
