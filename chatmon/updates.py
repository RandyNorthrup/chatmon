"""Updating Chatmon: finding a newer release, downloading the installer for how this Chatmon was installed,
making sure it's the real one, and installing it when you say so.

What's sent: the request for the latest release (to api.github.com, as "Chatmon/<version>"), and the
downloads. What makes a download the real one, on every platform (releasecheck.py): the release's list of
checksums, SHA256SUMS.txt, must be signed by Chatmon's release key (Ed25519; only its public half is here), and
the download must match the checksum that list gives it. On Windows the installer must also be signed by Randy
Northrup's own certificate from Microsoft's identity-verified code signing, which Windows checks again as it
runs it. Everything is checked again just before it's installed. On macOS and Linux root does that itself, on
copies only root can change, with the check and the release key of the Chatmon installed (never code you could
change), and installs only a newer Chatmon: what it's handed is the download and the signed list, never a
checksum to take on trust. Where Chatmon can't install an update itself (run from a source checkout, or a pip
install of your own), it only says one is out, and how to get it.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shlex
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PyQt6 import sip
from PyQt6.QtCore import QObject, QProcess, QProcessEnvironment, QUrl, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from . import __version__, changelog, paths, releasecheck
from .releasecheck import DEB, MACOS, MANUAL, PIPX, RPM, SUMS, SUMS_SIG, WINDOWS, sha256, signed_sums

REPO = "RandyNorthrup/chatmon"
LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
PAGE = f"https://github.com/{REPO}/releases/latest"
DOWNLOADS = f"https://github.com/{REPO}/releases/download/"
RELEASE_KEYS = releasecheck.RELEASE_KEYS  # the keys a release's list of checksums may be signed with
SECURE = "https://"  # where every download must come from, after any redirect
MAX_DOWNLOAD = 400 * 2**20  # bytes: far past any installer, short of filling a disk
MAX_REPLY = 1 * 2**20  # bytes of GitHub's answer about a release, or of its checksums
# Who must have signed a Windows installer: Randy Northrup's own certificate, from Microsoft's identity-
# verified code signing (Azure Artifact Signing). The name, its organization and its issuer, and above all
# the extended key usage Microsoft gives his verified identity alone (the city and state may change with
# a new address; that OID doesn't, across certificates renewed each day).
SIGNER = re.compile(r"CN=Randy Northrup, O=Randy Northrup, (?:L=[^,]+, )?(?:S=[^,]+, )?C=US")
ISSUER = re.compile(r"CN=Microsoft ID Verified CS [AE]OC CA \d{2}, O=Microsoft Corporation, C=US")
IDENTITY = "1.3.6.1.4.1.311.97.15158122.532186155.467764996.339863661"
CHECK_EVERY = 20 * 3600  # seconds between automatic checks: about once a day, whenever Chatmon runs
HELPER = "/usr/lib/chatmon/install-update"  # the .deb's and .rpm's own: root's side of installing an update
PKEXEC = "/usr/bin/pkexec"
SYSTEM_PACKAGE = Path("/usr/lib/chatmon")  # where the .deb and .rpm put Chatmon's package
# Asking the system's package manager whether it installed Chatmon: the first that says yes is how.
PACKAGE_QUERIES = ((DEB, ["/usr/bin/dpkg-query", "-W", "chatmon"]), (RPM, ["/usr/bin/rpm", "-q", "chatmon"]))
MAC_APP = Path("/Applications/Chatmon.app")  # where the .pkg installs it


def newer(version: str, than: str = __version__) -> bool:
    return changelog.version_key(version) > changelog.version_key(than)


def _editable() -> bool:
    """Installed from a folder you can edit (pip install -e, pipx install -e): yours to update."""
    try:
        from importlib.metadata import PackageNotFoundError, distribution

        info = json.loads(distribution("chatmon").read_text("direct_url.json") or "{}")
    except (PackageNotFoundError, ValueError, OSError):
        return False
    return bool(isinstance(info, dict) and (info.get("dir_info") or {}).get("editable"))


def install_kind() -> str:
    """WINDOWS, MACOS, DEB, RPM, PIPX or MANUAL. May run the package manager: off the screen's thread."""
    if paths.frozen():
        if sys.platform == "win32" and (Path(sys.executable).parent / "unins000.exe").exists():
            return WINDOWS
        # Only the one in Applications, where the .pkg installs it (a copy run from elsewhere would get a
        # second Chatmon in Applications, and not be updated itself), and only as the .pkg left it, the
        # system's: root checks an update with the app's own code, and an app you could change can't vouch.
        if sys.platform == "darwin" and Path(sys.executable).resolve().is_relative_to(MAC_APP) and root_owned(MAC_APP):
            return MACOS
        return MANUAL
    package = Path(__file__).resolve().parent
    if sys.platform.startswith("linux") and package.parent == SYSTEM_PACKAGE:
        for kind, query in PACKAGE_QUERIES:
            if os.path.exists(query[0]):
                try:
                    if subprocess.run(query, capture_output=True, timeout=10).returncode == 0:
                        return kind
                except (OSError, subprocess.SubprocessError):
                    pass
        return MANUAL
    if _editable():
        return MANUAL
    prefix = Path(sys.prefix).parts
    # Not on Windows: there pipx can't replace chatmon.exe while it runs.
    if "pipx" in prefix and "venvs" in prefix and sys.platform != "win32":
        return PIPX
    return MANUAL


def root_owned(app: Path) -> bool:
    """macOS: a Chatmon.app as its .pkg leaves it, root's and writable by root alone, at its top. (Root's side
    checks every file of its own copy of it before trusting any.)"""
    try:
        for folder in (app, app / "Contents", app / "Contents" / "MacOS", app / "Contents" / "Resources"):
            info = os.lstat(folder)
            if info.st_uid != 0 or not stat.S_ISDIR(info.st_mode) or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                return False
    except OSError:
        return False
    return True


def asset_name(kind: str, version: str, machine: str | None = None) -> str | None:
    """The release file that updates this kind of install."""
    return releasecheck.asset_name(kind, version, machine or platform.machine())


def how_to_update(kind: str, version: str) -> str:
    """For a Chatmon that can't update itself: how to get the new one."""
    if kind != MANUAL or paths.frozen():
        return "Download its installer from the release page, and run it."
    if _editable():
        return "This Chatmon runs from a folder you installed it from: `git pull` there to update."
    if "pipx" in Path(sys.prefix).parts:
        return f"Quit Chatmon, then run `pipx install --force git+https://github.com/{REPO}@v{version}`."
    return f"Update with `pip install --upgrade git+https://github.com/{REPO}@v{version}`, or download an installer from the release page."


@dataclass
class Release:
    version: str
    notes: str  # the release's own notes (Markdown)
    page: str
    assets: dict[str, str] = field(default_factory=dict)  # file name: download URL


def parse_release(data: object) -> Release | None:
    """The latest release, from GitHub's reply; None for one that isn't a published, final release."""
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        return None
    tag = str(data.get("tag_name") or "")
    if not re.fullmatch(r"v\d+(\.\d+){1,3}", tag):
        return None
    assets = {}
    for asset in data.get("assets") or []:
        if isinstance(asset, dict):
            name, url = str(asset.get("name") or ""), str(asset.get("browser_download_url") or "")
            if name and url.startswith(DOWNLOADS + tag + "/"):  # this repository's own release files, nowhere else
                assets[name] = url
    page = str(data.get("html_url") or "")
    return Release(tag[1:], str(data.get("body") or ""), page if page.startswith(f"https://github.com/{REPO}/") else PAGE, assets)


def sums_for(download: Path) -> tuple[Path, Path]:
    """Where the signed list of checksums that vouched for a download, and its signature, wait beside it: what
    root checks again, itself, before installing it."""
    return download.with_name(f"{download.name}.{SUMS}"), download.with_name(f"{download.name}.{SUMS_SIG}")


def windows_signer(path: Path) -> tuple[str, str, str, list[str]]:
    """(status, signer, issuer, extended key usages) of a file's own Authenticode signature, as Windows'
    WinVerifyTrust sees it (wintrust.py): nothing has to start, PowerShell or anything else. Can take a while
    (Windows may fetch what the certificate chain needs): off the screen's thread."""
    try:
        from . import wintrust

        return wintrust.signer(path)
    except (ImportError, OSError, AttributeError, ValueError) as exc:  # not Windows, or a library without what's asked
        return "Unknown", str(exc)[:200], "", []


def verify(path: Path, expected: str, kind: str) -> str | None:
    """Why this download mustn't be installed, or None: it's the one the release's signed list gives (and,
    on Windows, signed by Randy Northrup). Slow: off the screen's thread."""
    if sha256(path) != expected:
        return "the download doesn't match the release's checksum"
    if kind == WINDOWS:
        status, signer, issuer, usages = windows_signer(path)
        if status != "Valid" or not SIGNER.fullmatch(signer) or not ISSUER.fullmatch(issuer) or IDENTITY not in usages:
            return f"its signature isn't Randy Northrup's ({status}{', ' + signer if signer else ''})"
    return None


def folder() -> Path:
    """Where downloads wait to be installed: a cache of this computer's own (on Windows, never the roaming
    profile, which can follow you to other PCs)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / paths.APP
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches" / paths.APP
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / paths.APP
    path = base / "updates"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        os.chmod(path, 0o700)
    return path


# macOS: root's side of installing an update (macOS asks for your password first). The AppleScript only hands
# _MACOS_ROOT, and the paths of the download and its signed list, to a shell as data (quoted form): none of it
# is ever part of the script itself.
_MACOS_SCRIPT = (
    'set c to system attribute "CHATMON_ROOT"\n'
    'set f to system attribute "CHATMON_UPDATE"\n'
    'set s to system attribute "CHATMON_SUMS"\n'
    'set g to system attribute "CHATMON_SIG"\n'
    'do shell script "/bin/sh -c " & quoted form of c & " chatmon-update " & quoted form of f & " " & quoted form of s & " " '
    '& quoted form of g with administrator privileges'
)
# What runs as root: a copy of Chatmon.app in a folder only root can write, then checked: every file of it must be
# root's and writable by root alone, as the .pkg installs it. Checking the copy leaves no moment to swap the app
# between the check and its use, and nobody but root can make a root-owned file. Only then does the copy's own
# install-update (packaging/macos/install-update) check the download, with the copy's own Python and release key
# (releasecheck.py: signed, and newer than this Chatmon), and install it.
_MACOS_ROOT = """set -eu
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
umask 077
app=/Applications/Chatmon.app
d=$(mktemp -d /private/tmp/chatmon-update.XXXXXXXX)
trap 'rm -rf "$d"' EXIT
ditto --noqtn "$app" "$d/Chatmon.app"
if [ -n "$(find "$d/Chatmon.app" \\( ! -user root -o -perm +022 \\) -print | head -n 1)" ]; then
    echo "Chatmon.app isn't the system's own (its .pkg didn't install it), so it can't check its own update: install this one from the release page." >&2
    exit 3
fi
/bin/sh "$d/Chatmon.app/Contents/Resources/install-update" "$d" "$@"
"""


def installer_command(kind: str, path: Path) -> tuple[str, list[str], dict[str, str]] | None:
    """(program, arguments, environment) that installs a verified download; None where it can't be done here.
    On macOS and Linux root gets the download and the signed list beside it (sums_for), to check itself."""
    if kind == WINDOWS:
        # Silent, as the last install was (for you, or for everyone), and Chatmon starts again afterwards.
        # An install for everyone asks Windows to elevate it, and Windows checks its signature as it does.
        return str(path), ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/relaunch=1"], {}
    sums, signature = sums_for(path)
    if kind == MACOS:
        env = {"CHATMON_ROOT": _MACOS_ROOT, "CHATMON_UPDATE": str(path), "CHATMON_SUMS": str(sums), "CHATMON_SIG": str(signature)}
        return "/usr/bin/osascript", ["-e", _MACOS_SCRIPT], env
    if kind in (DEB, RPM) and os.access(PKEXEC, os.X_OK) and os.access(HELPER, os.X_OK):
        return PKEXEC, [HELPER, str(path), str(sums), str(signature)], {}
    if kind == PIPX:
        pipx = shutil.which("pipx")  # your own tool, run as you: no more than you could do yourself
        if pipx:
            return pipx, ["install", "--force", str(path)], {}
    return None


def relaunch_command(kind: str) -> tuple[str, list[str]] | None:
    """What starts the updated Chatmon, once this one has quit (the Windows installer does it itself)."""
    if kind == MACOS:
        return "/bin/sh", ["-c", "sleep 2; exec /usr/bin/open /Applications/Chatmon.app"]
    if kind in (DEB, RPM):
        return "/bin/sh", ["-c", "sleep 2; exec /usr/bin/chatmon"]
    if kind == PIPX:
        chatmon = shutil.which("chatmon")
        if chatmon:
            return "/bin/sh", ["-c", 'sleep 2; exec "$0"', chatmon]
    return None


def metered() -> bool:
    """On a connection that's charged by the amount (a phone's hotspot, say), as far as the system says."""
    try:
        from PyQt6.QtNetwork import QNetworkInformation

        if QNetworkInformation.instance() is None and not QNetworkInformation.loadDefaultBackend():
            return False
        info = QNetworkInformation.instance()
        return bool(info is not None and info.isMetered())
    except (ImportError, AttributeError, RuntimeError):
        return False


class Updater(QObject):
    """Checks for, downloads and installs updates, one step at a time, never holding up the screen."""

    available = pyqtSignal(object)  # Release: newer, downloaded, checked, ready to install with install()
    newer_only = pyqtSignal(object, str)  # Release, why not downloaded or how to get it: newer, not downloaded
    up_to_date = pyqtSignal()
    failed = pyqtSignal(str)
    installing = pyqtSignal()  # it's installed (macOS, Linux, pipx): quit, for the new one to start
    handed_over = pyqtSignal()  # Windows' installer has it from here, and quits Chatmon when it's ready to

    def __init__(self, background, parent: QObject | None = None):
        super().__init__(parent)
        self._nam = QNetworkAccessManager(self)
        self._background = background  # runs slow work (hashing, the signature check) off the screen's thread
        self._reply: QNetworkReply | None = None
        self._file = None
        self._got = 0
        self._by_hand = False  # you asked: download even on a metered connection
        self.kind: str | None = None
        self.release: Release | None = None
        self.ready: Path | None = None  # the verified download, for self.release
        self._expected = ""  # its checksum, from the signed list: checked again just before it's installed
        self._signed: tuple[bytes, bytes] = (b"", b"")  # that list and its signature, for root to check again
        self.busy = False

    # -- checking

    def check(self, kind: str | None = None, by_hand: bool = False) -> None:
        """Look for a newer release (`kind`: how this Chatmon was installed, once known). `by_hand`: you
        asked, so it downloads on a metered connection too."""
        if self.busy:
            return
        self.busy = True
        self._by_hand = by_hand
        if kind is None and self.kind is None:
            self._background.run(install_kind, self._kind_known)
            return
        self.kind = kind or self.kind
        self._get(LATEST, self._latest)

    def _kind_known(self, kind) -> None:
        self.kind = kind if isinstance(kind, str) else MANUAL
        self._get(LATEST, self._latest)

    def _request(self, url: str) -> QNetworkRequest:
        req = QNetworkRequest(QUrl(url))
        req.setRawHeader(b"User-Agent", f"Chatmon/{__version__}".encode())
        req.setRawHeader(b"Accept", b"application/vnd.github+json")
        req.setTransferTimeout(60_000)
        return req

    def _get(self, url: str, then) -> None:
        """A small reply (MAX_REPLY at most), whole, to `then`."""
        reply = self._nam.get(self._request(url))
        self._reply = reply
        reply.downloadProgress.connect(lambda got, _total: reply.abort() if got > MAX_REPLY else None)
        reply.finished.connect(lambda: self._got_reply(reply, then))

    def _got_reply(self, reply: QNetworkReply, then) -> None:
        self._reply = None
        reply.deleteLater()
        if reply.error() != QNetworkReply.NetworkError.NoError:
            return self._fail(f"couldn't reach GitHub ({reply.errorString()})")
        raw = bytes(reply.readAll())
        if len(raw) > MAX_REPLY:
            return self._fail("GitHub's answer was far bigger than it should be")
        then(raw)

    def _latest(self, raw: bytes) -> None:
        try:
            release = parse_release(json.loads(raw))
        except (ValueError, RecursionError):
            release = None
        if release is None:
            return self._fail("GitHub's answer about the latest release wasn't readable")
        if not newer(release.version):
            self.busy = False
            self.up_to_date.emit()
            return
        self.release = release
        name = asset_name(self.kind, release.version)
        if name is None or name not in release.assets or not {SUMS, SUMS_SIG} <= set(release.assets) or installer_command(self.kind, folder() / name) is None:
            return self._only_tell(how_to_update(self.kind, release.version))
        done = folder() / name
        if self.ready == done and self._expected and all(p.exists() for p in (done, *sums_for(done))):
            self.busy = False
            self.available.emit(release)
            return
        if not self._by_hand and metered():
            return self._only_tell("You're on a metered connection, so I haven't downloaded it. **Check for updates now** in my menu downloads it anyway.")
        self._get(release.assets[SUMS_SIG], lambda sig: self._get(release.assets[SUMS], lambda text: self._sums(text, sig, name)))

    def _only_tell(self, how: str) -> None:
        self.busy = False
        self.newer_only.emit(self.release, how)

    # -- downloading

    def _sums(self, text: bytes, signature: bytes, name: str) -> None:
        sums = signed_sums(text, signature)
        if sums is None:
            return self._fail("its list of checksums isn't signed with Chatmon's release key")
        expected = sums.get(name)
        if expected is None:
            return self._fail(f"the release's signed list has no checksum for {name}")
        self._signed = (text, signature)
        part = folder() / (name + ".part")
        try:
            for old in folder().iterdir():  # last time's, of whatever version (this one's are all named after it)
                if not old.name.startswith(name) and old.is_file():
                    old.unlink()
            self._file = open(part, "wb")
        except OSError as exc:
            return self._fail(f"couldn't save the download ({exc.strerror or exc})")
        self._got = 0
        reply = self._nam.get(self._request(self.release.assets[name]))
        self._reply = reply
        reply.readyRead.connect(lambda: self._chunk(reply))
        reply.finished.connect(lambda: self._downloaded(reply, part, name, expected))

    def _chunk(self, reply: QNetworkReply) -> None:
        data = bytes(reply.readAll())
        self._got += len(data)
        if self._got > MAX_DOWNLOAD:
            reply.abort()
            return
        if self._file is not None:
            try:
                self._file.write(data)
            except OSError:
                reply.abort()

    def _downloaded(self, reply: QNetworkReply, part: Path, name: str, expected: str) -> None:
        self._chunk(reply)
        self._reply = None
        reply.deleteLater()
        if self._file is not None:
            self._file.close()
            self._file = None
        url = reply.url().toString()
        if reply.error() != QNetworkReply.NetworkError.NoError or self._got > MAX_DOWNLOAD or not url.startswith(SECURE):
            part.unlink(missing_ok=True)
            return self._fail(f"the download didn't finish ({reply.errorString()})")
        kind = self.kind
        self._background.run(lambda: verify(part, expected, kind), lambda why: self._verified(why, part, folder() / name, expected))

    def _verified(self, why, part: Path, done: Path, expected: str) -> None:
        if why is not None:
            part.unlink(missing_ok=True)
            return self._fail(str(why) if not isinstance(why, Exception) else f"couldn't check the download ({why})")
        try:
            for path, data in zip(sums_for(done), self._signed, strict=True):
                path.write_bytes(data)
            os.replace(part, done)
        except OSError as exc:
            part.unlink(missing_ok=True)
            return self._fail(f"couldn't keep the download ({exc.strerror or exc})")
        self.ready, self._expected = done, expected
        self.busy = False
        self.available.emit(self.release)

    # -- installing

    def install(self) -> None:
        """Install the verified download. Windows' installer takes over (it asks Chatmon to quit when it's
        ready, and starts it again); elsewhere the system asks for your password, then Chatmon starts again."""
        if self.ready is None or self.release is None or not self.ready.exists() or self.busy:
            return self.failed.emit("There's no update ready to install.")
        if installer_command(self.kind, self.ready) is None:
            return self.failed.emit("This Chatmon can't install updates itself.")
        self.busy = True
        # Checked again, just before: it may have waited days for you to say yes.
        ready, expected, kind = self.ready, self._expected, self.kind
        self._background.run(lambda: verify(ready, expected, kind), self._install_checked)

    def _install_checked(self, why) -> None:
        if why is not None:
            self.busy = False
            self.ready.unlink(missing_ok=True)
            self.ready = None
            return self.failed.emit(f"The update wasn't installed: {why if not isinstance(why, Exception) else 'it could not be checked'}.")
        program, args, env = installer_command(self.kind, self.ready)
        if self.kind == WINDOWS:
            # Chatmon stays: the installer asks it to quit (`chatmon quit`) once it's going ahead, and starts it
            # again after. Turned down (Windows asking to install for everyone, say), Chatmon is still here.
            self.busy = False
            if not QProcess.startDetached(program, args, str(self.ready.parent))[0]:
                return self.failed.emit("The update wasn't installed: its installer couldn't start.")
            self.handed_over.emit()
            return
        proc = QProcess(self)
        environment = QProcessEnvironment.systemEnvironment()
        for key, value in env.items():
            environment.insert(key, value)
        proc.setProcessEnvironment(environment)
        proc.finished.connect(lambda code, _status: self._installed(proc, code))
        proc.errorOccurred.connect(lambda error: self._not_started(proc, error))
        proc.start(program, args)

    def _not_started(self, proc: QProcess, error) -> None:
        if sip.isdeleted(proc):
            return
        if error == QProcess.ProcessError.FailedToStart:
            proc.deleteLater()
            self.busy = False
            self.failed.emit(f"The update wasn't installed: {Path(proc.program()).name} couldn't start.")

    def _installed(self, proc: QProcess, code: int) -> None:
        if sip.isdeleted(proc):  # Chatmon quitting while it ran
            return
        err = bytes(proc.readAllStandardError()).decode("utf-8", errors="replace").strip()
        proc.deleteLater()
        self.busy = False
        if code != 0:
            if self.kind in (DEB, RPM) and code == 126:  # pkexec: the password prompt was dismissed
                return self.failed.emit("The update wasn't installed: the password prompt was closed.")
            if self.kind in (DEB, RPM) and code == 127:  # pkexec: no prompt to ask with, or not allowed
                return self.failed.emit(
                    "The update wasn't installed: there's no password prompt running to ask you (a polkit agent). "
                    f"In a terminal: `sudo {shlex.join([HELPER, str(self.ready), *map(str, sums_for(self.ready))])}`"
                )
            detail = err.splitlines()[-1] if err else f"exit code {code}"
            return self.failed.emit(f"The update wasn't installed ({detail}).")
        relaunch = relaunch_command(self.kind)
        if relaunch is not None:
            QProcess.startDetached(*relaunch)
        self.ready.unlink(missing_ok=True)
        self.installing.emit()

    def _fail(self, why: str) -> None:
        self.busy = False
        if self._file is not None:
            self._file.close()
            self._file = None
        self.failed.emit(f"Couldn't check for updates: {why}.")

    def cancel(self) -> None:
        if self._reply is not None:
            reply, self._reply = self._reply, None
            reply.abort()
