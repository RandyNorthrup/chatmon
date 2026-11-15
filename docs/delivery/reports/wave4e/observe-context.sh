#!/bin/bash
# The final round: the tools each plan's context.json names, observed again on this workstation and in WSL.
cd /c/Users/Randy/Coding/chatmon-wt/plans-final || exit 2
export MSYS_NO_PATHCONV=1  # the WSL paths are passed as they are
PY=C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe
NEXT=C:/Users/Randy/AppData/Local/Temp/m10-qt6121/Scripts/python.exe
V=C:/Users/Randy/.claude/plugins/cache/high-quality-projects-skill/high-quality-projects-skill/0.7.0/scripts/verify-delivery.py
echo "# Observed $(date -u +%Y-%m-%dT%H:%M:%SZ) on the Windows 11 workstation, for wave 4's final round (45a17b3)"
echo '$ python verify-delivery.py --observe-context'; python "$V" --observe-context
echo '$ .venv python -c (test tool versions, and Qt at run time)'
"$PY" -c "
import sys
from importlib.metadata import version
print('python', sys.version.split()[0])
for d in ('pytest', 'PyQt6', 'hypothesis', 'tzdata', 'pytest-timeout', 'coverage', 'mypy', 'zizmor', 'comtypes'):
    print(d, version(d))
from PyQt6.QtCore import qVersion
print('Qt', qVersion())
"
echo '$ ruff --version'; "$PY" -m ruff --version
echo '$ actionlint -version'; actionlint -version 2>&1 | head -1
echo '$ uv --version'; uv --version
echo '$ %TEMP%\m10-qt6121 python -c (PyQt6-next, M10)'; "$NEXT" -c "import PyQt6.QtCore as q; print('PyQt6', q.PYQT_VERSION_STR, 'Qt', q.qVersion())"; "$NEXT" -m mypy --version
echo '$ wsl: shellcheck --version, podman --version, sway, orca, at-spi2-core'
wsl.exe -d archlinux -- sh -c 'shellcheck --version | sed -n 2p; podman --version; sway --version; pacman -Q orca at-spi2-core'
echo '$ wsl: /var/tmp/plans-venv and /var/tmp/m4a-venv'
for v in plans-venv m4a-venv; do wsl.exe -d archlinux -- "/var/tmp/$v/bin/python" -c "import sys, PyQt6.QtCore as q, pytest; print(sys.version.split()[0], 'PyQt6', q.PYQT_VERSION_STR, 'Qt', q.qVersion(), 'pytest', pytest.__version__)"; done
wsl.exe -d archlinux -- /var/tmp/m4a-venv/bin/python -m mypy --version; wsl.exe -d archlinux -- sh -c "~/.local/bin/uv --version"
