"""The release check root runs before installing an update (chatmon/releasecheck.py): only a package in a list
of checksums Chatmon's release key signed, and newer than the Chatmon installed, passes. Every refusal here is
made by the check itself, against a release key of the test's own (tests/ed25519_sign.py). No Qt."""

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ed25519_sign  # noqa: E402

from chatmon import ed25519, releasecheck  # noqa: E402

DEB = "chatmon_9.0.0-1_all.deb"


@pytest.fixture
def release(tmp_path, monkeypatch):
    """A release signed with a key of this test's own, which the check is told to trust; Chatmon 0.9.2 installed."""
    secret, public = ed25519_sign.new_key()
    monkeypatch.setattr(releasecheck, "RELEASE_KEYS", (public,))
    monkeypatch.setattr(releasecheck, "__version__", "0.9.2")

    def make(name=DEB, data=b"the real package", extra=b""):
        package = tmp_path / name
        package.write_bytes(data)
        sums = f"{'1' * 64}  other-file.txt\n{hashlib.sha256(data).hexdigest()}  {name}\n".encode() + extra
        return package, sums, ed25519_sign.sign(secret, sums)

    return make


def run_main(tmp_path, kind, package, sums, signature):
    (tmp_path / "SHA256SUMS.txt").write_bytes(sums)
    (tmp_path / "SHA256SUMS.txt.sig").write_bytes(signature)
    return releasecheck.main([kind, str(package), str(tmp_path / "SHA256SUMS.txt"), str(tmp_path / "SHA256SUMS.txt.sig")])


# -- the signer the tests use is RFC 8032's Ed25519


def test_the_tests_signer_matches_rfc_8032():
    h = bytes.fromhex
    for secret, public, message, signature in (
        ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60", "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "",
         "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
        ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb", "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c", "72",
         "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
    ):
        assert ed25519_sign.public_key(h(secret)) == h(public)
        assert ed25519_sign.sign(h(secret), h(message)) == h(signature)


@pytest.mark.skipif(not shutil.which("openssl"), reason="needs OpenSSL to compare with")
def test_what_the_tests_sign_openssl_verifies(tmp_path):
    """An independent second opinion on the signer: OpenSSL checks its signature with its public key."""
    secret, public = ed25519_sign.new_key()
    message = tmp_path / "SHA256SUMS.txt"
    message.write_bytes(b"0" * 64 + b"  chatmon_9.0.0-1_all.deb\n")
    (tmp_path / "sig").write_bytes(ed25519_sign.sign(secret, message.read_bytes()))
    der = bytes.fromhex("302a300506032b6570032100") + bytes.fromhex(public)  # SubjectPublicKeyInfo, Ed25519
    (tmp_path / "pub.der").write_bytes(der)
    out = subprocess.run(
        ["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(tmp_path / "pub.der"), "-keyform", "DER", "-rawin",
         "-in", str(message), "-sigfile", str(tmp_path / "sig")],
        capture_output=True, text=True,
    )
    if "-rawin" in out.stderr or "unknown option" in out.stderr.lower():
        pytest.skip(f"this OpenSSL can't check Ed25519 signatures: {out.stderr.strip()[:200]}")
    assert out.returncode == 0 and "Success" in out.stdout, out


# -- what passes and what's refused


def test_a_signed_newer_package_passes_with_its_version(release):
    package, sums, signature = release()
    assert releasecheck.check("deb", package, sums, signature) == "9.0.0"
    for kind, name in (("rpm", "chatmon-9.0.0-1.noarch.rpm"), ("macos", "Chatmon-9.0.0-macos-arm64.pkg"), ("macos", "Chatmon-9.0.0-macos-intel.pkg")):
        package, sums, signature = release(name)
        assert releasecheck.check(kind, package, sums, signature) == "9.0.0"


def test_a_tampered_list_is_refused(release):
    """The list changed after it was signed: here, its checksum for the package swapped for another file's."""
    package, sums, signature = release(data=b"the real package")
    evil = package.with_name("evil.deb")
    evil.write_bytes(b"something else")
    tampered = sums.replace(hashlib.sha256(b"the real package").hexdigest().encode(), hashlib.sha256(b"something else").hexdigest().encode())
    assert tampered != sums
    with pytest.raises(releasecheck.Refused, match="isn't signed"):
        releasecheck.check("deb", evil, tampered, signature)
    with pytest.raises(releasecheck.Refused, match="isn't signed"):
        releasecheck.check("deb", package, sums + b"\n", signature)  # even a byte added


def test_a_bad_signature_is_refused(release):
    package, sums, signature = release()
    other_secret, _ = ed25519_sign.new_key()
    flipped = bytearray(signature)
    flipped[10] ^= 1
    for bad in (bytes(64), bytes(flipped), ed25519_sign.sign(other_secret, sums), signature[:63], b""):
        with pytest.raises(releasecheck.Refused, match="isn't signed"):
            releasecheck.check("deb", package, sums, bad)


def test_the_real_release_key_is_the_only_one_trusted_by_default(release, monkeypatch):
    package, sums, signature = release()
    monkeypatch.undo()  # the real RELEASE_KEYS again
    assert releasecheck.RELEASE_KEYS == ("bbd18835445b00c2582eb08bf1954af37966075ab3a0afdb4a32612e9a6090cf",)
    with pytest.raises(releasecheck.Refused, match="isn't signed"):
        releasecheck.check("deb", package, sums, signature, installed="0.1")


@pytest.mark.parametrize("installed", ["9.0.0", "9.0", "9.0.1", "10.0.0"])
def test_an_older_or_the_same_version_is_refused(release, installed):
    package, sums, signature = release()
    with pytest.raises(releasecheck.Refused, match="isn't newer"):
        releasecheck.check("deb", package, sums, signature, installed=installed)


def test_the_installed_version_is_the_checking_chatmons_own(release, monkeypatch):
    package, sums, signature = release()
    monkeypatch.setattr(releasecheck, "__version__", "9.0.0")
    with pytest.raises(releasecheck.Refused, match="isn't newer than the 9.0.0 installed"):
        releasecheck.check("deb", package, sums, signature)


def test_a_package_not_in_the_list_is_refused(release):
    package, sums, signature = release()
    package.write_bytes(b"changed after the list was made")
    with pytest.raises(releasecheck.Refused, match="isn't in the release's signed list"):
        releasecheck.check("deb", package, sums, signature)


def test_a_package_listed_under_another_kinds_name_is_refused(release):
    """The right bytes, but listed as the rpm (or as nothing Chatmon releases): not a .deb to install."""
    package, sums, signature = release("chatmon-9.0.0-1.noarch.rpm")
    with pytest.raises(releasecheck.Refused, match="isn't in the release's signed list"):
        releasecheck.check("deb", package, sums, signature)
    package, sums, signature = release("chatmon_9.0.0-1_all.deb.old")
    with pytest.raises(releasecheck.Refused, match="isn't in the release's signed list"):
        releasecheck.check("deb", package, sums, signature)
    with pytest.raises(releasecheck.Refused, match="no release file"):
        releasecheck.check("tarball", package, sums, signature)


def test_one_file_under_two_versions_names_is_refused(release):
    data = b"the real package"
    package, sums, signature = release(extra=f"{hashlib.sha256(data).hexdigest()}  chatmon_9.1.0-1_all.deb\n".encode())
    with pytest.raises(releasecheck.Refused, match="more than one version"):
        releasecheck.check("deb", package, sums, signature)


# -- as root runs it


def test_the_command_says_the_version_or_why_not(release, tmp_path, capsys):
    package, sums, signature = release()
    assert run_main(tmp_path, "deb", package, sums, signature) == 0
    assert capsys.readouterr().out.strip() == "9.0.0"
    assert run_main(tmp_path, "deb", package, sums + b"x", signature) == releasecheck.REFUSED
    assert "isn't signed with Chatmon's release key" in capsys.readouterr().err
    assert run_main(tmp_path, "deb", package, sums, bytes(64)) == releasecheck.REFUSED
    assert releasecheck.main(["deb", str(package), str(tmp_path / "missing"), str(tmp_path / "SHA256SUMS.txt.sig")]) == releasecheck.REFUSED
    assert "couldn't read" in capsys.readouterr().err
    assert releasecheck.main(["deb", str(package)]) == releasecheck.WRONG_CALL


def test_the_command_refuses_a_list_far_too_big(release, tmp_path, capsys):
    package, sums, signature = release(extra=b"#" * (releasecheck.MAX_SUMS + 1))
    assert run_main(tmp_path, "deb", package, sums, signature) == releasecheck.REFUSED
    assert "far bigger" in capsys.readouterr().err


def test_checksums_are_read_in_sha256sums_own_format():
    a, b = "a" * 64, "B" * 64
    text = f"{a}  Chatmon-9.0.0-windows-x64-setup.exe\n{b} *chatmon_9.0.0-1_all.deb\nnot a line\n{'c' * 63}  short\n"
    assert releasecheck.parse_sums(text) == {"Chatmon-9.0.0-windows-x64-setup.exe": a, "chatmon_9.0.0-1_all.deb": b.lower()}


def test_it_needs_nothing_but_the_standard_library():
    """Root runs it with python3 -I -S: no Qt, no site-packages. Imported fresh in such a Python, it loads no
    module from outside Chatmon's package and the standard library."""
    root = Path(releasecheck.__file__).resolve().parent.parent
    probe = (
        "import sys; sys.path.insert(0, sys.argv[1]); before = set(sys.modules); import chatmon.releasecheck; "
        "files = [getattr(sys.modules[m], '__file__', None) or '' for m in set(sys.modules) - before]; "
        "odd = [f for f in files if f and ('site-packages' in f or 'dist-packages' in f "
        "or not f.startswith((sys.base_prefix, sys.argv[1])))]; print(odd)"
    )
    out = subprocess.run([sys.executable, "-I", "-S", "-c", probe, str(root)], capture_output=True, text=True)
    assert out.returncode == 0 and out.stdout.strip() == "[]", out
    assert ed25519.verify  # the very module root checks signatures with
