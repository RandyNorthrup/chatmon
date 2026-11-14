"""Whether a downloaded update is a real Chatmon release, and newer than the Chatmon checking it: the check both
sides of an update make.

Chatmon makes it as you, once the download is in. On macOS and Linux root makes it again, on its own copies,
just before installing (packaging/linux/install-update and packaging/macos/install-update), with this module as
the installed Chatmon has it: from /usr/lib/chatmon, which only root can change, or from inside a Chatmon.app
root owns. So whatever runs as you, and anything that could change your files, never decides what root
installs: only Chatmon's release key does.

A release's SHA256SUMS.txt lists each of its files' SHA-256, and SHA256SUMS.txt.sig is the list's Ed25519
signature by Chatmon's release key (its private half is a secret of the repository's `release` environment). A
package passes only if its SHA-256 is in a list that key signed, under a release file name of its kind; the
version is read from that name (which the signature covers too), and it must be newer than this Chatmon.

Only the standard library and Chatmon's own Ed25519 check: no Qt, nothing from outside the package. As a
command (what root runs):

    verify-update KIND PACKAGE SHA256SUMS.txt SHA256SUMS.txt.sig

prints the version and exits 0, or says why not and exits 3 (2 for a wrong call).
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

from . import __version__, ed25519
from .changelog import version_key

SUMS = "SHA256SUMS.txt"
SUMS_SIG = "SHA256SUMS.txt.sig"  # its Ed25519 signature: 64 bytes
# Chatmon's release key, whose private half is a secret of the repository's `release` environment: the Packages
# workflow signs each release's SHA256SUMS.txt with it. More than one: a new key goes in here, in a release the
# old one signs, before releases are signed with it.
RELEASE_KEYS = ("bbd18835445b00c2582eb08bf1954af37966075ab3a0afdb4a32612e9a6090cf",)
MAX_SUMS = 1 * 2**20  # bytes of a list of checksums: far past any release's
SIGNATURE_SIZE = 64

# How this Chatmon was installed, which decides how it updates.
WINDOWS, MACOS, DEB, RPM, PIPX, MANUAL = "windows", "macos", "deb", "rpm", "pipx", "manual"

_VERSION = r"(?P<version>\d+(?:\.\d+){1,3})"
# Each kind's release file, by name: what packaging/build.py and the Packages workflow make.
NAMES = {
    WINDOWS: re.compile(rf"Chatmon-{_VERSION}-windows-x64-setup\.exe"),
    MACOS: re.compile(rf"Chatmon-{_VERSION}-macos-(?:arm64|intel)\.pkg"),
    DEB: re.compile(rf"chatmon_{_VERSION}-1_all\.deb"),
    RPM: re.compile(rf"chatmon-{_VERSION}-1\.noarch\.rpm"),
    PIPX: re.compile(rf"chatmon-{_VERSION}-py3-none-any\.whl"),
}
REFUSED, WRONG_CALL = 3, 2  # exit codes


class Refused(Exception):
    """Why an update mustn't be installed."""


def asset_name(kind: str, version: str, machine: str) -> str | None:
    """The release file that updates this kind of install, on this machine (platform.machine())."""
    machine = machine.lower()
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


def parse_sums(text: str) -> dict[str, str]:
    """SHA256SUMS.txt: "<hex>  <name>" a line (sha256sum's own format; "*" marks binary mode)."""
    out = {}
    for line in text.splitlines():
        m = re.fullmatch(r"([0-9a-fA-F]{64}) [ *](.+)", line.strip())
        if m:
            out[m.group(2).strip()] = m.group(1).lower()
    return out


def signed_sums(text: bytes, signature: bytes, keys: tuple[str, ...] | None = None) -> dict[str, str] | None:
    """The checksums in a release's SHA256SUMS.txt, if Chatmon's release key signed it (or one of `keys`, hex);
    None if it didn't."""
    if not any(ed25519.verify(bytes.fromhex(key), text, signature) for key in (RELEASE_KEYS if keys is None else keys)):
        return None
    return parse_sums(text.decode("utf-8", errors="replace"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(kind: str, package: Path, sums: bytes, signature: bytes, installed: str | None = None, keys: tuple[str, ...] | None = None) -> str:
    """The version `package` is, if it may be installed over Chatmon `installed` (by default this one: on root's
    side, the Chatmon installed); Refused says why not."""
    installed = installed or __version__
    pattern = NAMES.get(kind)
    if pattern is None:
        raise Refused(f"there's no release file of the kind {kind!r}")
    listed = signed_sums(sums, signature, keys)
    if listed is None:
        raise Refused("its list of checksums isn't signed with Chatmon's release key")
    digest = sha256(package)
    versions = {m.group("version") for name, value in listed.items() if value == digest and (m := pattern.fullmatch(name))}
    if not versions:
        raise Refused("the download isn't in the release's signed list of checksums")
    if len(versions) > 1:  # one file under two versions' names: no version to trust
        raise Refused("the release's signed list gives the download more than one version")
    (version,) = versions
    if version_key(version) <= version_key(installed):
        raise Refused(f"it's Chatmon {version}, which isn't newer than the {installed} installed")
    return version


def main(argv: list[str] | None = None) -> int:
    """verify-update KIND PACKAGE SHA256SUMS.txt SHA256SUMS.txt.sig: what root runs before installing."""
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 4:
        print("usage: verify-update KIND PACKAGE SHA256SUMS.txt SHA256SUMS.txt.sig", file=sys.stderr)
        return WRONG_CALL
    kind, package, sums, signature = argv
    try:
        with open(sums, "rb") as f:
            text = f.read(MAX_SUMS + 1)
        with open(signature, "rb") as f:
            sig = f.read(SIGNATURE_SIZE + 1)
        if len(text) > MAX_SUMS:
            raise Refused("its list of checksums is far bigger than a release's")
        version = check(kind, Path(package), text, sig)
    except Refused as why:
        print(f"The update wasn't installed: {why}.", file=sys.stderr)
        return REFUSED
    except OSError as exc:
        print(f"The update wasn't installed: couldn't read {exc.filename or 'it'} ({exc.strerror or exc}).", file=sys.stderr)
        return REFUSED
    print(version)
    return 0
