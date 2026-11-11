"""Updating Chatmon: finding a newer release, downloading the installer for how this Chatmon was installed,
making sure it's the real one, and installing it when you say so.

What's sent: the request for the latest release (to api.github.com, as "Chatmon/<version>"), and the
downloads. What makes a download the real one, on every platform: the release's list of checksums,
SHA256SUMS.txt, must be signed by Chatmon's release key (Ed25519; only its public half is here), and the
download must match the checksum that list gives it. On Windows the installer must also be signed by Randy
Northrup's own certificate from Microsoft's identity-verified code signing, which Windows checks again as it
runs it. Everything is checked again just before it's installed; on macOS and Linux, that's done as root on
a copy only root can change. Where Chatmon can't install an update itself (run from a source checkout, or a
pip install of your own), it only says one is out, and how to get it.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PyQt6 import sip
from PyQt6.QtCore import QObject, QProcess, QProcessEnvironment, QUrl, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from . import __version__, changelog, ed25519, paths

REPO = "RandyNorthrup/chatmon"
LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
PAGE = f"https://github.com/{REPO}/releases/latest"
DOWNLOADS = f"https://github.com/{REPO}/releases/download/"
SUMS = "SHA256SUMS.txt"
SUMS_SIG = "SHA256SUMS.txt.sig"  # its Ed25519 signature: 64 bytes
# Chatmon's release key, whose private half is a secret of the repository's `release` environment: the
# Packages workflow signs each release's SHA256SUMS.txt with it. More than one: a new key goes in here, in
# a release the old one signs, before releases are signed with it.
RELEASE_KEYS = ("bbd18835445b00c2582eb08bf1954af37966075ab3a0afdb4a32612e9a6090cf",)
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

# How this Chatmon was installed, which decides how it updates.
WINDOWS, MACOS, DEB, RPM, PIPX, MANUAL = "windows", "macos", "deb", "rpm", "pipx", "manual"


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
        # second Chatmon in Applications, and not be updated itself).
        if sys.platform == "darwin" and Path(sys.executable).resolve().is_relative_to("/Applications/Chatmon.app"):
            return MACOS
        return MANUAL
    package = Path(__file__).resolve().parent
    if sys.platform.startswith("linux") and package.parent == Path("/usr/lib/chatmon"):
        for kind, query in ((DEB, ["/usr/bin/dpkg-query", "-W", "chatmon"]), (RPM, ["/usr/bin/rpm", "-q", "chatmon"])):
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


def asset_name(kind: str, version: str, machine: str | None = None) -> str | None:
    """The release file that updates this kind of install."""
    machine = (machine or platform.machine()).lower()
    if kind == WINDOWS:
        return f"Chatmon-{version}-windows-x64-setup.exe"
    if kind == MACOS:
        return f"Chatmon-{version}-macos-{'arm64' if machine in ('arm64', 'aarch64') else 'intel'}.pkg"
    if kind == DEB:
        return f"chatmon_{version}-1_all.deb"
    if kind == RPM:
        return f"chatmon-{version}-1.noarch.rpm"
    if kind == PIPX:
        return f"chatmon-{version}-py3-none-any.whl"
    return None


def how_to_update(kind: str, version: str) -> str:
    """For a Chatmon that can't update itself: how to get the new one."""
    if kind != MANUAL:
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


def signed_sums(text: bytes, signature: bytes, keys=RELEASE_KEYS) -> dict[str, str] | None:
    """The checksums in a release's SHA256SUMS.txt, if Chatmon's release key signed it; None if it didn't."""
    if not any(ed25519.verify(bytes.fromhex(key), text, signature) for key in keys):
        return None
    return parse_sums(text.decode("utf-8", errors="replace"))


def parse_sums(text: str) -> dict[str, str]:
    """SHA256SUMS.txt: "<hex>  <name>" a line (sha256sum's own format; "*" marks binary mode)."""
    out = {}
    for line in text.splitlines():
        m = re.fullmatch(r"([0-9a-fA-F]{64}) [ *](.+)", line.strip())
        if m:
            out[m.group(2).strip()] = m.group(1).lower()
    return out


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def windows_signer(path: Path) -> tuple[str, str, str, list[str]]:
    """(status, signer, issuer, extended key usages) of a file's Authenticode signature, as Windows sees it.
    Slow (PowerShell starts): off the screen's thread."""
    script = (
        "$ErrorActionPreference = 'Stop'; $s = Get-AuthenticodeSignature -LiteralPath $env:CHATMON_UPDATE; $c = $s.SignerCertificate;"
        "[Console]::Out.Write(\"$($s.Status)|$($c.Subject)|$($c.Issuer)|$(($c.EnhancedKeyUsageList.ObjectId) -join ';')\")"
    )
    try:
        out = subprocess.run(
            paths.powershell(script),
            env={**os.environ, "CHATMON_UPDATE": str(path)},  # the path as data, never as part of the script
            capture_output=True, text=True, timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return "Unknown", str(exc), "", []
    status, signer, issuer, usages = (out.stdout.strip().split("|") + ["", "", ""])[:4]
    if not status:  # no answer: PowerShell's reason, said once, in place of a signer
        return "Unknown", next((line.strip() for line in out.stderr.splitlines() if line.strip()), "")[:200], "", []
    return status, signer, issuer, [u for u in usages.split(";") if u]


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


# macOS: run as root (macOS asks for your password), on a copy in a folder only root can change, checked
# again there. The path and checksum come in as data (quoted form), never as part of the script itself.
_MACOS_SCRIPT = (
    'set f to system attribute "CHATMON_UPDATE"\n'
    'set h to system attribute "CHATMON_SHA256"\n'
    'do shell script "d=$(/usr/bin/mktemp -d /private/tmp/chatmon-update.XXXXXXXX) && trap \'/bin/rm -rf \\"$d\\"\' EXIT && '
    '/bin/cp -- " & quoted form of f & " \\"$d/update.pkg\\" && '
    '[ \\"$(/usr/bin/shasum -a 256 \\"$d/update.pkg\\" | /usr/bin/cut -d\' \' -f1)\\" = " & quoted form of h & " ] && '
    '/usr/sbin/installer -pkg \\"$d/update.pkg\\" -target /" with administrator privileges'
)


def installer_command(kind: str, path: Path, expected: str = "") -> tuple[str, list[str], dict[str, str]] | None:
    """(program, arguments, environment) that installs a verified download; None where it can't be done here."""
    if kind == WINDOWS:
        # Silent, as the last install was (for you, or for everyone), and Chatmon starts again afterwards.
        # An install for everyone asks Windows to elevate it, and Windows checks its signature as it does.
        return str(path), ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/relaunch=1"], {}
    if kind == MACOS:
        return "/usr/bin/osascript", ["-e", _MACOS_SCRIPT], {"CHATMON_UPDATE": str(path), "CHATMON_SHA256": expected}
    if kind in (DEB, RPM) and os.access(PKEXEC, os.X_OK) and os.access(HELPER, os.X_OK):
        return PKEXEC, [HELPER, str(path), expected], {}
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
        if self.ready == done and done.exists() and self._expected:
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
        part = folder() / (name + ".part")
        try:
            for old in folder().iterdir():  # last time's, of whatever version
                if old.name != name and old.is_file():
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
        if installer_command(self.kind, self.ready, self._expected) is None:
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
        program, args, env = installer_command(self.kind, self.ready, self._expected)
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
                    f"In a terminal: `sudo {HELPER} '{self.ready}' {self._expected}`"
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
