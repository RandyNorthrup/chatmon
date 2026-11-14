"""Run Python in the Arch WSL test venv as if it were a local interpreter, for tests/drills/run.py --python:
the current directory and PYTHONPATH become their /mnt/c paths there, and /mnt/c/ paths in the output come back as
C:/ ones (the harness checks which chatmon was imported). The exit code is the WSL run's."""

import os
import subprocess
import sys

VENV_PYTHON = "~/venv-chatmon-m3/bin/python"


def to_wsl(path: str) -> str:
    drive, rest = os.path.splitdrive(os.path.abspath(path))
    return f"/mnt/{drive[0].lower()}{rest.replace(os.sep, '/')}"


def main() -> int:
    cwd = to_wsl(os.getcwd())
    args = " ".join("'" + a.replace("'", "'\\''") + "'" for a in sys.argv[1:])
    script = f"cd '{cwd}' && PYTHONPATH='{cwd}' QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 {VENV_PYTHON} {args}"
    done = subprocess.run(["wsl.exe", "-d", "archlinux", "--", "sh", "-c", script], capture_output=True)
    for stream, data in ((sys.stdout, done.stdout), (sys.stderr, done.stderr)):
        stream.write(data.decode("utf-8", errors="replace").replace("/mnt/c/", "C:/"))
        stream.flush()
    return done.returncode


if __name__ == "__main__":
    sys.exit(main())
