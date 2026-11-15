#!/bin/bash
# M1A after the owner test (3bcd857): the Windows checks behind the receipts that bind tests/test_install_update.py.
#   bash docs/delivery/reports/m1a/mac-owner/run-windows.sh   (from the worktree's root)
cd /c/Users/Randy/Coding/chatmon-wt/mac-owner || exit 2
PY=C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe
W=docs/delivery/reports/m1a/mac-owner
export QT_QPA_PLATFORM=offscreen
digest() { git ls-files -s -- chatmon tests packaging pyproject.toml | sha256sum | cut -c1-64; }
{
  echo "# Whole suite on $(git rev-parse --short HEAD), Windows 11 workstation, $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# git HEAD $(git rev-parse HEAD); git status below"
  git status --short
  echo "# source digest (sha256 of git ls-files -s for chatmon/ tests/ packaging/ pyproject.toml): $(digest)"
  echo "\$ $PY -m pytest -q -p no:cacheprovider"
  "$PY" -m pytest -q -p no:cacheprovider 2>&1
  echo "# exit $?"
  echo "# finished $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$W/suite-windows.log"
echo "suite $(tail -2 "$W/suite-windows.log" | head -1)" > "$W/windows-progress.txt"
"$PY" tests/drills/run.py docs/delivery/reports/m1a/wave4c/drill-spec.json --only AC-01-USER-handoff --log "$W/drills-windows.log" --python "$PY" > "$W/drills-windows-run.txt" 2>&1
echo "drills exit $? $(grep -c '^PASS' "$W/drills-windows.log") pass $(grep -c '^FAIL' "$W/drills-windows.log") fail" >> "$W/windows-progress.txt"
echo DONE >> "$W/windows-progress.txt"
