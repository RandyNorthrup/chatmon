"""Start the companion when you log in: a .desktop file on Linux, a Run key in the registry on Windows. On
macOS, Chatmon.app is a login item of its own (SMAppService, macnative.py), listed by name in System Settings ›
General › Login Items and turned off there or here alike; run from source or pip, a LaunchAgent starts it."""

from __future__ import annotations

import os
import plistlib
import re
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


APP_ID = "io.github.RandyNorthrup.chatmon"  # the desktop entry's name, as the packages install it


def _desktop_file(app: str = APP_ID) -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart" / f"{app}.desktop"


def exec_line(command: list[str]) -> str:
    """A desktop entry's Exec=, quoted as the spec says: an argument with a space or a reserved character in
    double quotes, `"`, `` ` ``, `$` and `\\` escaped there, every % doubled, and then every backslash doubled
    (the rule for all string values).
    https://specifications.freedesktop.org/desktop-entry/latest/exec-variables.html"""
    out = []
    for arg in command:
        arg = arg.replace("%", "%%")
        if arg and not re.search(r"""[\s"'\\><~|&;$*?#()`]""", arg):
            out.append(arg)
        else:
            out.append('"' + re.sub(r'(["`$\\])', r"\\\1", arg) + '"')
    # Then the general rule for string values, applied before the quoting rule when it's read: each backslash
    # written twice (a literal one, in quotes, is four).
    line = " ".join(out).replace("\\", "\\\\")
    # And the string rule's escapes for what may never be in a line of the file as it is.
    return line.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")


def _launch_agent(label: str = _LABEL) -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"


def _login_item() -> int | None:
    """Chatmon.app's login item status (macnative's), when this is Chatmon.app on macOS 13 or later; else None.
    Run from source or pip, there's no app of its own to be one: the main bundle would be Python's."""
    if sys.platform != "darwin" or not paths.frozen() or ".app/Contents/MacOS/" not in sys.executable:
        return None
    from . import macnative

    return macnative.login_item()


def where() -> str:
    if sys.platform == "win32":
        return f"HKEY_CURRENT_USER\\{_RUN_KEY}\\{_NAME}"
    if _login_item() is not None:
        return "Login Items, in System Settings › General"
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
    if sys.platform == "darwin":
        from . import macnative

        return _login_item() == macnative.ENABLED or _launch_agent().exists()
    return _desktop_file().exists() or _desktop_file(paths.APP).exists()


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
        olds = [_launch_agent(_LEGACY_LABEL)] if sys.platform == "darwin" else [_desktop_file(paths.LEGACY_APP), _desktop_file(paths.APP)]
        found = [old for old in olds if old.exists()]
        if not found:
            return False
        for old in found:
            old.unlink()
    set_enabled(True)
    return True


def refresh() -> bool:
    """Bring starting at login up to date, as it starts. On Windows, autostart turned on before there was
    chatmonw runs chatmon.exe, which opens a console window at every login and keeps it open: run Chatmon
    without one instead. On macOS, Chatmon.app started by an older version's LaunchAgent becomes a login item
    of its own instead. Returns whether it changed anything."""
    if sys.platform == "darwin":
        if _login_item() is None or not _launch_agent().exists():
            return False
        set_enabled(True)
        return not _launch_agent().exists()
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
    if _login_item() is not None:  # Chatmon.app on macOS 13 or later
        from . import macnative

        if not on:
            if _login_item() in (macnative.ENABLED, macnative.REQUIRES_APPROVAL):
                macnative.set_login_item(False)
            _launch_agent().unlink(missing_ok=True)
            return
        problem = macnative.set_login_item(True)
        if problem is None:
            _launch_agent().unlink(missing_ok=True)  # an older version's: starting once at login is enough
            return
        print(f"{paths.APP}: couldn't add Chatmon to Login Items ({problem}), so a LaunchAgent starts it", file=sys.stderr)
    path = _launch_agent() if sys.platform == "darwin" else _desktop_file()
    if not on:
        path.unlink(missing_ok=True)
        if sys.platform != "darwin":
            _desktop_file(paths.APP).unlink(missing_ok=True)  # its name before 0.6.0
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
        f"Exec={exec_line(command)}\n"
        f"Icon={APP_ID}\n"
        "X-GNOME-Autostart-enabled=true\n",
        encoding="utf-8",
    )
