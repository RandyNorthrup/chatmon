"""Run mypy for linux, win32 and darwin with one interpreter's PyQt6 stubs, and keep the output as a log.

usage (from the worktree root):
    python docs/delivery/reports/m10/mypy_runs.py PYTHON LOG [--root DIR]

PYTHON is the interpreter whose mypy and PyQt6 are used: the shared venv's (PyQt6 6.11, the lock's) or a throwaway
venv's (PyQt6 6.12.1). LOG is written whole: the interpreter, PyQt6's and mypy's versions, then each platform's
command, exit code and output. --root checks another copy of the tree (a scratch copy) instead of this one. Exit 0
only when all three platforms pass.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PLATFORMS = ("linux", "win32", "darwin")


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    done = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)  # noqa: S603 - mypy, fixed
    return done.returncode, (done.stdout + done.stderr).rstrip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("python")
    parser.add_argument("log")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    _, versions = run([args.python, "-c", "import sys, PyQt6.QtCore as q; print(sys.version.split()[0], 'PyQt6', q.PYQT_VERSION_STR, 'Qt', q.QT_VERSION_STR)"], root)
    _, mypy = run([args.python, "-m", "mypy", "--version"], root)
    lines = [f"interpreter: {args.python}", f"python {versions}", mypy, f"tree: {root}"]
    failed = 0
    for platform in PLATFORMS:
        cmd = [args.python, "-m", "mypy", "--platform", platform, "--no-incremental"]
        code, out = run(cmd, root)
        failed += code != 0
        lines += ["", f"$ {' '.join(cmd)}", out, f"exit {code}"]
    Path(args.log).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"{args.log}: {len(PLATFORMS) - failed} of {len(PLATFORMS)} platforms pass")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
