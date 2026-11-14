"""Windows: the signature check asks whether certificates have been revoked (and says so when it can't tell), and
`hold` keeps a file exactly as it is while it's checked and run."""

import ctypes
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Authenticode and file sharing: Windows")

if sys.platform == "win32":
    from chatmon import updates, wintrust

CERT_E_REVOKED = 0x800B010C
OFFLINE = (0x80092013, 0x80092012, 0x800B010E)  # CRYPT_E_REVOCATION_OFFLINE, CRYPT_E_NO_REVOCATION_CHECK, CERT_E_REVOCATION_FAILURE


def signed_file() -> Path:
    """A program signed in itself by its maker, here: Python's own, when its installer signed it."""
    for candidate in (getattr(sys, "_base_executable", ""), sys.executable):
        if candidate and wintrust.signer(Path(candidate))[0] not in ("NotSigned", "NotSupportedFileFormat"):
            return Path(candidate)
    pytest.skip("no program signed in itself to check here")


def as_long(code: int) -> int:
    return ctypes.c_long(code).value  # WinVerifyTrust returns a LONG


# -- revocation


def test_revocation_is_asked_for_the_whole_chain(monkeypatch):
    """The real WinVerifyTrust, watched on the way in: every check asks about revocation, and a properly signed
    file still checks out (or, offline, says it couldn't tell: never just "Valid" without looking)."""
    signed, real, asked = signed_file(), wintrust._WinVerifyTrust, []

    def watched(window, action, data):
        if data._obj.dwStateAction == wintrust.WTD_STATEACTION_VERIFY:
            asked.append((data._obj.fdwRevocationChecks, data._obj.dwProvFlags))
        return real(window, action, data)

    monkeypatch.setattr(wintrust, "_WinVerifyTrust", watched)
    status = wintrust.signer(signed)[0]
    assert asked == [(wintrust.WTD_REVOKE_WHOLECHAIN, wintrust.WTD_REVOCATION_CHECK_CHAIN_EXCLUDE_ROOT)]
    assert status in ("Valid", "RevocationUnknown")


@pytest.mark.parametrize("code, status", [(CERT_E_REVOKED, "Revoked"), *((code, "RevocationUnknown") for code in OFFLINE)])
def test_what_windows_says_of_revocation_is_what_the_updater_hears(monkeypatch, tmp_path, code, status):
    """Windows' answer for a revoked certificate, and for one it couldn't look up, from WinVerifyTrust itself
    (here a stand-in that gives that answer, as the real one does for such a file)."""
    monkeypatch.setattr(wintrust, "_WinVerifyTrust", lambda window, action, data: as_long(code))
    setup = tmp_path / "setup.exe"
    setup.write_bytes(b"setup")
    assert wintrust.signer(setup)[0] == status
    why = updates.verify(setup, updates.sha256(setup), updates.WINDOWS)
    assert why is not None and "revoked" in why
    assert isinstance(why, updates.TryLater) is (status == "RevocationUnknown")


# -- holding a file


def test_a_held_file_cant_be_written_renamed_or_deleted_nor_its_folder_renamed(tmp_path):
    folder = tmp_path / "install-x"
    folder.mkdir()
    held = folder / "setup.exe"
    held.write_bytes(b"checked")
    handle = wintrust.hold(held)
    try:
        for change in (lambda: open(held, "r+b"), lambda: open(held, "wb"), lambda: os.replace(held, tmp_path / "moved"),
                       lambda: os.remove(held), lambda: os.replace(folder, tmp_path / "moved-folder")):
            with pytest.raises(PermissionError):
                change()
        assert held.read_bytes() == b"checked"  # still readable by anyone
    finally:
        wintrust.release(handle)
    held.write_bytes(b"free again")  # let go: as any file
    assert held.read_bytes() == b"free again"


def test_a_program_starts_from_a_held_copy(tmp_path):
    copy = tmp_path / "cmd.exe"
    shutil.copy(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "cmd.exe", copy)
    handle = wintrust.hold(copy)
    try:
        assert subprocess.run([str(copy), "/c", "exit 7"], capture_output=True, timeout=30).returncode == 7
    finally:
        wintrust.release(handle)


def test_holding_a_file_that_isnt_there_says_so(tmp_path):
    with pytest.raises(OSError):
        wintrust.hold(tmp_path / "gone.exe")
