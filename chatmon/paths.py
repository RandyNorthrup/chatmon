"""Where the companion keeps its settings and state, and how others reach it,
on Linux, macOS and Windows.

On Windows that's %LOCALAPPDATA%\\chatmon, this computer's own: never the roaming
profile, which can follow you to other PCs (and your chats with it). Versions
before 0.10 kept it all in %APPDATA%\\chatmon; `migrate()` moves it, once."""

from __future__ import annotations

import getpass
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

APP = "chatmon"
LEGACY_APP = "penguin-companion"  # its name before 0.3.0
RENAMED = ".renamed"  # left in the state folder by `migrate()`, until the app has started once since
# A Chatmon of its own, apart from the one you use: another address (pipe or socket) for the app, its command
# line and hooks alike. The tests and `packaging/build.py smoke` set it; nobody else needs to. The address is
# still yours alone, and checked as yours, whatever it's called.
INSTANCE_ENV = "CHATMON_INSTANCE"


def _roaming() -> Path:
    """Windows: the roaming profile, where Chatmon kept everything before 0.10."""
    return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")


def _local() -> Path:
    """Windows: this computer's own application data."""
    return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")


def _base(xdg_var: str, xdg_default: Path) -> Path:
    if sys.platform == "win32":
        return _local()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    value = os.environ.get(xdg_var)
    return Path(value) if value else xdg_default


def _roots(app: str) -> list[Path]:
    """The folders an app of this name keeps its settings and state in (one folder on Windows and macOS)."""
    roots = [_base("XDG_CONFIG_HOME", Path.home() / ".config") / app, _base("XDG_STATE_HOME", Path.home() / ".local" / "state") / app]
    return list(dict.fromkeys(roots))


def migrate() -> list[tuple[Path, Path]]:
    """Move the settings and state of the old name, penguin-companion, to Chatmon's folders: once, on the
    first run after the rename, and only where Chatmon has none of its own yet. Returns what it moved. On
    Windows, then, what's in the roaming profile moves to this computer's own folder (_move_to_local)."""
    moved = []
    # On Windows the old name's folder is in the roaming profile, where Chatmon's was too, so it goes there first.
    news = [_roaming() / APP] if sys.platform == "win32" else _roots(APP)
    for new in news:
        old = new.with_name(LEGACY_APP)
        if old.is_dir() and not new.exists() and not (sys.platform == "win32" and _has_own(_local() / APP)):
            try:
                os.replace(old, new)  # the same parent folder, so the same disk: a rename
            except OSError as exc:
                print(f"{APP}: couldn't move {old} to {new}: {exc}", file=sys.stderr)
                continue
            moved.append((old, new))
    if moved:  # whichever command ran first (a hook's notify, likely), the app hears of it when it starts
        try:
            state_dir().mkdir(parents=True, exist_ok=True)
            (state_dir() / RENAMED).touch()
        except OSError:
            pass
    if sys.platform == "win32":
        _move_to_local()
    return moved


def _has_own(folder: Path) -> bool:
    """Chatmon's settings or state are in `folder` (not just its downloaded updates)."""
    return (folder / "config.toml").exists() or (folder / "state").exists()


def _move_to_local() -> None:
    """Windows: everything in %APPDATA%\\chatmon (where versions before 0.10 kept settings and chats) into
    %LOCALAPPDATA%\\chatmon, once, leaving nothing in the roaming profile. A rename when it can be; else (another
    volume, as for a profile redirected to a server, or a folder that's there already) each file is moved,
    keeping the newer of one found in both. Anything in use is finished the next time Chatmon starts."""
    old, new = _roaming() / APP, _local() / APP
    if not old.is_dir() or old.resolve() == new.resolve():
        return
    try:
        new.parent.mkdir(parents=True, exist_ok=True)
        if not new.exists():
            try:
                os.replace(old, new)
                return
            except OSError:
                pass  # moved file by file
        _merge(old, new)
    except OSError as exc:
        print(f"{APP}: couldn't move {old} to {new} yet: {exc}", file=sys.stderr)


def _merge(old: Path, new: Path) -> None:
    new.mkdir(exist_ok=True)
    for item in list(old.iterdir()):
        target = new / item.name
        try:
            if item.is_dir() and not item.is_symlink():
                if target.exists() and not target.is_dir():
                    continue  # a file there by that name: left as it is, and this one too
                if not target.exists():
                    try:
                        os.replace(item, target)
                        continue
                    except OSError:
                        pass
                _merge(item, target)
                continue
            if target.is_dir():
                continue
            if target.exists() and target.stat().st_mtime >= item.stat().st_mtime:
                item.unlink()  # the one already here is as new or newer
                continue
            try:
                os.replace(item, target)
            except OSError:  # another volume
                shutil.copy2(item, target)
                item.unlink()
        except OSError as exc:
            print(f"{APP}: couldn't move {item} yet: {exc}", file=sys.stderr)
    try:
        old.rmdir()
    except OSError:
        pass  # something's still in it: next time


def first_run_since_rename() -> bool:
    """True once: the first time the app starts after `migrate()` moved the old name's folders."""
    mark = state_dir() / RENAMED
    try:
        mark.unlink()
    except FileNotFoundError:
        return False
    except OSError:
        pass
    return True


def config_dir() -> Path:
    return _base("XDG_CONFIG_HOME", Path.home() / ".config") / APP


def config_file() -> Path:
    return config_dir() / "config.toml"


def state_dir() -> Path:
    path = _base("XDG_STATE_HOME", Path.home() / ".local" / "state") / APP
    return path / "state" if sys.platform in ("win32", "darwin") else path


def state_file() -> Path:
    return state_dir() / "state.json"


def work_dir() -> Path:
    """An empty folder that command-line AI brains run in, away from your files."""
    path = state_dir() / "work"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


SOCKET_PATH_MAX = 103  # bytes in a Unix socket's address on macOS (sun_path), less its terminating NUL
_CS_DARWIN_USER_TEMP_DIR = 65537  # confstr: your own temporary folder, /var/folders/…/T/, yours alone (0700)


def instance() -> str:
    """The name of a Chatmon of its own (INSTANCE_ENV), or "" for yours: letters, digits, - and _ only."""
    value = os.environ.get(INSTANCE_ENV, "")
    return value if re.fullmatch(r"[A-Za-z0-9_-]{1,40}", value) else ""


def socket_path() -> Path:
    name = f"{APP}-{instance()}.sock" if instance() else f"{APP}.sock"
    run = os.environ.get("XDG_RUNTIME_DIR")
    if run:
        return Path(run) / name
    # No runtime folder (macOS, an ssh session, a container): a folder of our own, not the shared /tmp, where
    # another user could take the name first and hear every agent's events.
    folder = state_dir() / "run"
    path = folder / name
    if sys.platform == "darwin" and len(os.fsencode(path)) > SOCKET_PATH_MAX:
        # A user name of more than about 37 characters makes it too long to be a socket's address. macOS keeps
        # a temporary folder for each user, open to them alone: the same for the app, the CLI and every hook.
        try:
            return Path(os.confstr(_CS_DARWIN_USER_TEMP_DIR)) / name
        except (OSError, ValueError, TypeError):
            pass
    try:
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(folder, 0o700)
    except OSError:
        pass
    return path


def server_name() -> str:
    """The local server's name: a socket path on Linux and macOS, a named
    pipe on Windows."""
    if sys.platform == "win32":
        from . import winpipe

        identity = winpipe.my_identity()  # your SID and this session's number (see there why)
        name = f"{APP}-{identity}" if identity else f"{APP}-{getpass.getuser()}"
        return f"{name}-{instance()}" if instance() else name
    return str(socket_path())


def anim_dir() -> Path:
    return Path(__file__).resolve().parent / "anim"


def bubbles_dir() -> Path:
    return Path(__file__).resolve().parent / "bubbles"


FOUND_FOR = 30  # seconds `which` remembers where a program is
_found: dict[tuple, tuple[float, str | None]] = {}


def which(name: str) -> str | None:
    """shutil.which, remembered for half a minute, for the menu: on Windows each look tries every PATHEXT
    ending in every PATH folder (a few ms each), and the menu asks after a dozen programs every time it
    opens. Asked again as soon as PATH, or the lookup itself (tests replace it), changes."""
    key = (name, os.environ.get("PATH", ""), shutil.which)
    seen = _found.get(key)
    now = time.monotonic()
    if seen and now - seen[0] < FOUND_FOR:
        return seen[1]
    found = shutil.which(name)
    _found[key] = (now, found)
    return found


# Variables a login shell sets that are its own, or this moment's, not the environment a program should get.
_SHELL_ONLY = {"PWD", "OLDPWD", "SHLVL", "_", "PS1", "PS2", "PROMPT", "RPROMPT", "TERM", "TERM_PROGRAM", "TERM_SESSION_ID", "COLUMNS", "LINES", "TMPDIR"}
# Nor what would change how Chatmon itself runs: its libraries, its Python, Qt, where its socket goes.
_NOT_ADOPTED = ("DYLD_", "LD_", "PYTHON", "QT_", "XDG_", "QML", "__CF", "SSH_AUTH_SOCK")
_SENTINEL = b"--chatmon-environment--"


def login_environment(timeout: float = 4.0) -> list[str]:
    """macOS: an app started from Finder, the Dock or at login gets launchd's bare PATH (/usr/bin:/bin:...) and
    none of what your shell sets, so AI tools in /opt/homebrew/bin, ~/.local/bin or npm's folder aren't found,
    and API keys set in ~/.zshrc aren't seen. Take your login shell's environment, as a terminal would have
    it, without changing anything already set; failing that, the usual folders on PATH. Returns the names set."""
    if sys.platform != "darwin":
        return []
    shell = os.environ.get("SHELL") or "/bin/zsh"
    found: dict[str, str] = {}
    if os.path.isabs(shell) and os.access(shell, os.X_OK):
        # Its own process group, all of it ended if it doesn't answer in time; whatever the shell's startup files
        # print comes before the marker, and only what follows it is read.
        proc = None
        try:
            proc = subprocess.Popen(
                [shell, "-l", "-i", "-c", f"printf '%s\\0' {_SENTINEL.decode()}; /usr/bin/env -0"],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True,
            )
            out, _ = proc.communicate(timeout=timeout)
            if _SENTINEL + b"\0" in out:
                for item in out.split(_SENTINEL + b"\0", 1)[1].split(b"\0"):
                    name, eq, value = item.partition(b"=")
                    if eq and re.fullmatch(rb"[A-Za-z_][A-Za-z0-9_]*", name):
                        found[name.decode()] = value.decode("utf-8", "replace")
        except (OSError, subprocess.SubprocessError):
            if proc is not None:
                try:
                    os.killpg(proc.pid, 9)
                except OSError:
                    pass
                proc.wait()
    usual = ["/opt/homebrew/bin", "/usr/local/bin", str(Path.home() / ".local" / "bin"), str(Path.home() / ".npm-global" / "bin")]
    path = found.get("PATH") or os.pathsep.join([*usual, os.environ.get("PATH", "")])
    adopted = []
    if path != os.environ.get("PATH"):
        os.environ["PATH"] = os.pathsep.join(dict.fromkeys(p for p in path.split(os.pathsep) + os.environ.get("PATH", "").split(os.pathsep) if p))
        adopted.append("PATH")
    for name, value in found.items():
        if name not in os.environ and name not in _SHELL_ONLY and not name.startswith(_NOT_ADOPTED):
            os.environ[name] = value
            adopted.append(name)
    return adopted


_MACHINE_ENVIRONMENT = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"


def windows_path_with(current: str, folders: list[str]) -> str:
    """A Windows PATH: `current` as it is, then each of `folders` it doesn't have yet (in any case, with or
    without a backslash on the end)."""

    def key(folder: str) -> str:
        return folder.strip().rstrip("\\/").casefold()

    have = {key(p) for p in current.split(";") if p.strip()}
    added = []
    for folder in folders:
        if folder.strip() and key(folder) not in have:
            have.add(key(folder))
            added.append(folder.strip())
    return ";".join([p for p in current.split(";") if p] + added) if added else current


def windows_environment() -> bool:
    """Windows: the folders Windows keeps on PATH now, the computer's and yours, after those this process
    started with. A program gets its environment from whatever started it, and one an installer starts gets
    the installer's, from before it put chatmon on PATH: Chatmon started by its own installer ("Start Chatmon
    now", an update), or connecting agents from it, wouldn't find chatmon on PATH, so hooks would get a full
    path, and Claude Code's plugin, which runs chatmon by name, couldn't be connected at all. Nothing already
    on PATH moves. Returns whether anything was added."""
    if sys.platform != "win32":
        return False
    import winreg

    folders: list[str] = []
    for root, key in ((winreg.HKEY_LOCAL_MACHINE, _MACHINE_ENVIRONMENT), (winreg.HKEY_CURRENT_USER, "Environment")):
        try:
            with winreg.OpenKey(root, key) as handle:
                value, _ = winreg.QueryValueEx(handle, "Path")
        except OSError:
            continue
        if isinstance(value, str):
            folders += winreg.ExpandEnvironmentStrings(value).split(";")
    current = os.environ.get("PATH", "")
    path = windows_path_with(current, folders)
    if path == current:
        return False
    os.environ["PATH"] = path
    return True


# Windows PowerShell's own modules first. Started from PowerShell 7 (a terminal, a script), Chatmon passes on
# PowerShell 7's module path, and Windows PowerShell would load PowerShell 7's modules, which it can't:
# Get-AuthenticodeSignature and every other module command fail. Set before the script, it's what they load.
_OWN_MODULES = "$env:PSModulePath = \"$PSHOME\\Modules;\" + [Environment]::GetEnvironmentVariable('PSModulePath', 'Machine');"


def powershell(script: str) -> list[str]:
    """Windows PowerShell running `script` with its own modules, as one argument nothing can garble:
    -EncodedCommand (UTF-16LE, base64). Passed as -Command, a script's double quotes are stripped on the way in
    by Windows PowerShell's own reading of its command line, and the script never runs as written."""
    import base64

    system = Path(os.environ.get("SystemRoot") or r"C:\Windows") / "System32"
    encoded = base64.b64encode((_OWN_MODULES + "\n" + script).encode("utf-16-le")).decode("ascii")
    return [str(system / "WindowsPowerShell" / "v1.0" / "powershell.exe"), "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]


def frozen() -> bool:
    """Running from an installer's build, with no Python of its own to run it with: compiled by Nuitka
    (Windows), which gives each module it compiles a __compiled__, or frozen by PyInstaller (macOS)."""
    compiled = globals().get("__compiled__")
    return bool(getattr(compiled, "standalone", False) or getattr(sys, "frozen", False))


def command_line(windowless: bool = False) -> list[str]:
    """How to run this companion from a hook, a shortcut or autostart. `windowless`: on Windows, with
    no console window (for autostart): `chatmonw`, or pythonw, never chatmon.exe, which opens one."""
    if frozen():  # installed from a package: its own programs, whatever else is on PATH
        exe = Path(sys.executable)
        if sys.platform == "win32":
            return [str(exe.with_name(f"{APP}w.exe" if windowless else f"{APP}.exe"))]
        return [str(exe)]
    if windowless and sys.platform == "win32":
        installed = shutil.which(APP + "w")  # the GUI launcher that installing makes alongside chatmon.exe
    else:
        installed = shutil.which(APP)
    if installed:
        return [installed]
    python = sys.executable
    if windowless and sys.platform == "win32":
        pythonw = Path(python).with_name("pythonw.exe")
        python = str(pythonw) if pythonw.exists() else python
    launcher = Path(__file__).resolve().parent.parent / "bin" / APP
    if launcher.exists():
        return [python, str(launcher)]
    return [python, "-m", "chatmon"]
