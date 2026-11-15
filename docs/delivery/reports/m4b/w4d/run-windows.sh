#!/bin/bash
# M4B after ROADMAP.md's wave-4 round-three amendment (a rule of every plan): the Windows checks behind every
# receipt it made stale, on this worktree's files (the merge of improve/assessment-fixes at cbeed17).
#   bash docs/delivery/reports/m4b/w4d/run-windows.sh   (from the worktree's root)
cd /c/Users/Randy/Coding/chatmon-wt/mac-drills || exit 2
PY=C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe
W=docs/delivery/reports/m4b/w4d
export QT_QPA_PLATFORM=offscreen
digest() { git ls-files -s -- chatmon tests packaging pyproject.toml | sha256sum | cut -c1-64; }
toast=$(reg query 'HKCU\Software\Microsoft\Windows\CurrentVersion\PushNotifications' //v ToastEnabled 2>/dev/null | awk '/ToastEnabled/ {print $3}')
{
  echo "# Whole suite on $(git rev-parse --short HEAD), Windows 11 workstation, $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# git HEAD $(git rev-parse HEAD); git status below"
  git status --short
  echo "# source digest (sha256 of git ls-files -s for chatmon/ tests/ packaging/ pyproject.toml): $(digest)"
  echo "# ToastEnabled here: ${toast:-unset} (off: the toast tests take their declining branch)"
  echo "\$ $PY -m pytest -q -p no:cacheprovider"
  "$PY" -m pytest -q -p no:cacheprovider 2>&1
  echo "# exit $?"
  echo "# finished $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$W/suite-windows.log"
echo "suite $(tail -2 "$W/suite-windows.log" | head -1)" > "$W/windows-progress.txt"
"$PY" tests/drills/run.py docs/delivery/reports/m4b/wave4b/drill-spec.json --log "$W/drills.log" --python "$PY" > "$W/drills-run.txt" 2>&1
echo "drills exit $? $(grep -c '^PASS' "$W/drills.log") pass $(grep -c '^FAIL' "$W/drills.log") fail" >> "$W/windows-progress.txt"
echo DONE >> "$W/windows-progress.txt"
