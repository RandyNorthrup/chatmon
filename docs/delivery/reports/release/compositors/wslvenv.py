"""Run Python in the WSL (Arch) venv the compositor checks use, as if it were a local interpreter, for
tests/drills/run.py --python (through wslvenv.bat): the current directory and PYTHONPATH become their /mnt/c paths
there, and /mnt/c/ paths in the output come back as C:/ ones (the harness checks which chatmon was imported). The
exit code is the WSL run's. As docs/delivery/reports/m3/wslvenv.py, for /var/tmp/plans-venv
(packaging/requirements-test.txt), at nice 10."""

import os
import subprocess
import sys

VENV_PYTHON = "/var/tmp/plans-venv/bin/python"  # noqa: S108 - the venv in WSL, a fixed path, no temporary file


def to_wsl(path: str) -> str:
    drive, rest = os.path.splitdrive(os.path.abspath(path))
    return f"/mnt/{drive[0].lower()}{rest.replace(os.sep, '/')}"


def main() -> int:
    cwd = to_wsl(os.getcwd())
    args = " ".join("'" + a.replace("'", "'\\''") + "'" for a in sys.argv[1:])
    script = (f"cd '{cwd}' && PYTHONPATH='{cwd}' QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 "
              f"CHATMON_INSTANCE=drill-$$ nice -n 10 {VENV_PYTHON} {args}")
    done = subprocess.run(["wsl.exe", "-d", "archlinux", "--", "sh", "-c", script], capture_output=True, check=False)  # noqa: S603, S607 - wsl.exe, fixed, with the drill runner's own arguments
    for stream, data in ((sys.stdout, done.stdout), (sys.stderr, done.stderr)):
        stream.write(data.decode("utf-8", errors="replace").replace("/mnt/c/", "C:/"))
        stream.flush()
    return done.returncode


if __name__ == "__main__":
    sys.exit(main())
