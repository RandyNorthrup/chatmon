#!/bin/sh
# CONTRIBUTING.md's how-to for the next stubs, run as written (each line echoed), in WSL Arch, on a copy of the tree.
# Round three (3586a0d), the final round (45a17b3) and the plans round for v0.10.0 (7816159): the tree already has wayland-files-qt6121.diff's changes (the wayland merge made them), so the copy is the tree as it is.
set -eu
TREE=$1
rm -rf /tmp/qt-next /tmp/qt-next.in /tmp/qt-next.txt
cd "$TREE"
echo "tree: $TREE (a copy of the worktree's tracked files at 7816159 but art/ and docs/, nothing applied)"
echo "$ uname -sr; python --version; uv --version"; uname -sr; python --version; uv --version
run() { echo "$ $*"; "$@"; }
echo "$ printf 'PyQt6==6.12.1\npsutil==7.2.2\nmypy==2.4.1\n' > /tmp/qt-next.in"
printf 'PyQt6==6.12.1\npsutil==7.2.2\nmypy==2.4.1\n' > /tmp/qt-next.in
run uv pip compile /tmp/qt-next.in -o /tmp/qt-next.txt --generate-hashes
grep -E '^[a-z]' /tmp/qt-next.txt
run python -m venv /tmp/qt-next
run /tmp/qt-next/bin/python -m pip install --require-hashes -r /tmp/qt-next.txt
for p in linux win32 darwin; do
  echo "$ /tmp/qt-next/bin/python -m mypy --platform $p"
  /tmp/qt-next/bin/python -m mypy --platform $p && echo "exit 0"
done
