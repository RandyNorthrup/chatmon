"""Start the companion when you log in: a .desktop file on Linux, a
LaunchAgent on macOS, a Run key in the registry on Windows."""

from __future__ import annotations

import os
import plistlib
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from . import paths

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_NAME = "Chatmon"
_LABEL = "io.github.chatmon"
# What it was called before the rename to Chatmon.
_LEGACY_NAME = "PenguinCompanion"
_LEGACY_LABEL = "io.github.penguin-companion"


def _desktop_file(app: str = paths.APP) -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart" / f"{app}.desktop"


def _launch_agent(label: str = _LABEL) -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"


def where() -> str:
    if sys.platform == "win32":
        return f"HKEY_CURRENT_USER\\{_RUN_KEY}\\{_NAME}"
    return str(_launch_agent() if sys.platform == "darwin" else _desktop_file())


def enabled() -> bool:
    if sys.platform == "win32":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
                winreg.QueryValueEx(key, _NAME)
            return True
        except OSError:
            return False
    return (_launch_agent() if sys.platform == "darwin" else _desktop_file()).exists()


def migrate() -> bool:
    """If it started at login under the old name, start Chatmon instead. Returns whether it did that."""
    if sys.platform == "win32":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as key:
                winreg.QueryValueEx(key, _LEGACY_NAME)
                winreg.DeleteValue(key, _LEGACY_NAME)
        except OSError:
            return False
    else:
        old = _launch_agent(_LEGACY_LABEL) if sys.platform == "darwin" else _desktop_file(paths.LEGACY_APP)
        if not old.exists():
            return False
        old.unlink()
    set_enabled(True)
    return True


def refresh() -> bool:
    """On Windows, autostart turned on before there was chatmonw runs chatmon.exe, which opens a console
    window at every login and keeps it open: run Chatmon without one instead. Returns whether it did."""
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, _NAME)
    except OSError:
        return False
    value = str(value).strip()
    program = value[1:].partition('"')[0] if value.startswith('"') else value.partition(" ")[0]
    if Path(program).name.lower() != f"{paths.APP}.exe" or not shutil.which(f"{paths.APP}w"):
        return False  # already windowless, something you set up yourself, or no chatmonw to run instead
    set_enabled(True)
    return True


def set_enabled(on: bool) -> None:
    command = paths.command_line(windowless=True)
    if sys.platform == "win32":
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if on:
                winreg.SetValueEx(key, _NAME, 0, winreg.REG_SZ, subprocess.list2cmdline(command))
            else:
                try:
                    winreg.DeleteValue(key, _NAME)
                except OSError:
                    pass
        return
    path = _launch_agent() if sys.platform == "darwin" else _desktop_file()
    if not on:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "darwin":
        path.write_bytes(plistlib.dumps({"Label": _LABEL, "ProgramArguments": command, "RunAtLoad": True}))
        return
    path.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Chatmon\n"
        "Comment=A little companion that lives on your desktop and helps out\n"
        f"Exec={shlex.join(command)}\n"
        "X-GNOME-Autostart-enabled=true\n",
        encoding="utf-8",
    )
