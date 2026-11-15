#!/bin/bash
# Round three, after run-windows.sh: M10-01.A1's locks, locked again from the committed .in files in a scratch copy of
# packaging/ (uv 0.12.7, the command the locks' headers record), compared byte for byte, then the lock tests.
cd /c/Users/Randy/Coding/chatmon-wt/plans3 || exit 2
PY=C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe
S=C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad
LOG=docs/delivery/reports/m10/wave4c/locks.log
C=$S/m10-locks
rm -rf "$C" && mkdir -p "$C" && cp -p packaging/*.in packaging/*.txt "$C/"
{
  echo "=== 1. Locking again from the committed .in files reproduces the committed locks (a scratch copy of packaging/; $(uv --version | cut -d' ' -f1-2)), $(date -u +%Y-%m-%dT%H:%M:%SZ), $(git rev-parse --short HEAD)"
  for lock in test dev; do
    echo "\$ (cd packaging) uv pip compile requirements-$lock.in -o requirements-$lock.txt --universal --python-version 3.11 --generate-hashes --exclude-newer 2026-10-31"
    (cd "$C" && uv pip compile "requirements-$lock.in" -o "requirements-$lock.txt" --universal --python-version 3.11 --generate-hashes --exclude-newer 2026-10-31 -q 2>&1); echo "uv exit $?"
    if cmp -s "$C/requirements-$lock.txt" "packaging/requirements-$lock.txt"; then echo "requirements-$lock.txt: identical to the committed lock"; else echo "requirements-$lock.txt: DIFFERS from the committed lock"; diff "packaging/requirements-$lock.txt" "$C/requirements-$lock.txt" | head -40; fi
  done
  echo
  echo "=== 2. What changed in the locks and their inputs since round two (bf9d8ac)"
  echo "\$ git diff --stat bf9d8ac 3586a0d -- packaging/requirements-test.in packaging/requirements-test.txt packaging/requirements-dev.in packaging/requirements-dev.txt pyproject.toml"
  changed=$(git diff --stat bf9d8ac 3586a0d -- packaging/requirements-test.in packaging/requirements-test.txt packaging/requirements-dev.in packaging/requirements-dev.txt pyproject.toml)
  if [ -z "$changed" ]; then echo "(no output: all five unchanged)"; else echo "$changed"; fi
  echo
  echo "=== 3. The lock tests"
  echo "\$ $PY -m pytest -q -p no:cacheprovider -v tests/test_requirements.py"
  "$PY" -m pytest -q -p no:cacheprovider -v tests/test_requirements.py 2>&1; echo "pytest exit $?"
} > "$LOG" 2>&1
rm -rf "$C"
echo "m10 locks done" >> docs/delivery/reports/wave4c/windows-progress.txt
