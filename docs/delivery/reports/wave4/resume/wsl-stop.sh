#!/bin/bash
# Only this worker's processes: its batch script, its drill tool, and pytest runs from its venvs or its drill copies.
pats='run-wsl-batch.sh|wave4/wsl_drills.py|chatmon-wsl-drill-|/var/tmp/plans-venv/bin/python|/var/tmp/m4a-venv/bin/python|distro_drill.sh|chatmon-distro-drill-'
echo "before:"; pgrep -af "$pats" | grep -v pgrep || echo "  none"
pkill -f "$pats"; sleep 2; pkill -9 -f "$pats" 2>/dev/null
echo "after:"; pgrep -af "$pats" | grep -v pgrep || echo "  none"
ls -d /var/tmp/chatmon-wsl-drill-* /var/tmp/chatmon-distro-drill-* 2>/dev/null
