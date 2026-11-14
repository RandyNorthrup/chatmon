"""Root's side of installing an update, run for real as a script: Linux's install-update and verify-update, and
macOS's root code (updates._MACOS_ROOT) with the copy of Chatmon.app it checks and runs.

They run as root for real, so here a copy of each is made with root's uid, its fixed paths and the package
manager (apt-get, installer) replaced by test values; everything else is the script as shipped. What they
check with is Chatmon's own release check, from a copy of the package with a release key of the test's own.
POSIX only: these are sh scripts, run on Linux and macOS (CI) and skipped on Windows."""

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ed25519_sign  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="root's side is sh, on Linux and macOS")

REPO = Path(__file__).resolve().parent.parent
MODULES = ("__init__", "releasecheck", "ed25519", "changelog")
INSTALLED = "0.9.2"


def text(path: Path) -> str:
    """A script as shipped, with Unix line endings whatever this checkout has."""
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def write(path: Path, content: str, mode: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    path.chmod(mode)
    return path


def substituted(content: str, **changes: str) -> str:
    for old, new in changes.items():
        assert content.count(old) >= 1, f"{old!r} isn't in the script any more"
        content = content.replace(old, new)
    return content


def package_copy(folder: Path, public_key: str, installed: str = INSTALLED) -> Path:
    """Chatmon's release check as installed: its modules, root-only modes, a release key of the test's own."""
    package = folder / "chatmon"
    for name in MODULES:
        content = text(REPO / "chatmon" / f"{name}.py")
        if name == "releasecheck":
            content = substituted(content, **{'RELEASE_KEYS = ("bbd18835445b00c2582eb08bf1954af37966075ab3a0afdb4a32612e9a6090cf",)': f'RELEASE_KEYS = ("{public_key}",)'})
        if name == "__init__":
            content = f'__version__ = "{installed}"\n'
        write(package / f"{name}.py", content, 0o644)
    for path in (folder, package):
        path.chmod(0o755)
    return package


class Release:
    """A package, the release's SHA256SUMS.txt and its signature, signed with a throwaway key."""

    def __init__(self, folder: Path, name: str, data: bytes = b"the new package"):
        self.secret, self.public = ed25519_sign.new_key()
        folder.mkdir(parents=True, exist_ok=True)
        self.package = folder / name
        self.package.write_bytes(data)
        self.sums = folder / "SHA256SUMS.txt"
        self.sums.write_bytes(f"{'2' * 64}  other.txt\n{hashlib.sha256(data).hexdigest()}  {name}\n".encode())
        self.sig = folder / "SHA256SUMS.txt.sig"
        self.sign()

    def sign(self) -> None:
        self.sig.write_bytes(ed25519_sign.sign(self.secret, self.sums.read_bytes()))


RECORDER = """#!/bin/sh
# Stands in for the package manager: notes what it was asked, a copy of the package, and its folder's modes.
for arg; do [ -f "$arg" ] && package=$arg; done
printf '%s\\n' "$*" > "{record}/args"
ls -ldn "$(dirname "$package")" > "{record}/folder"
cp "$package" "{record}/installed"
"""


# -- Linux: install-update and verify-update


@pytest.fixture
def linux(tmp_path):
    """install-update and verify-update as the package installs them, under this test's own uid and folder."""
    release = Release(tmp_path / "downloads", "chatmon_9.0.0-1_all.deb")
    home = tmp_path / "usr-lib-chatmon"
    package_copy(home, release.public)
    record = tmp_path / "record"
    record.mkdir()
    uid = str(os.getuid())
    verify = write(tmp_path / "verify-update", substituted(text(REPO / "packaging" / "linux" / "verify-update"), **{
        'HOME = "/usr/lib/chatmon"': f'HOME = "{home}"', "OWNER = 0  # root": f"OWNER = {uid}",
    }), 0o755)
    apt = write(tmp_path / "apt-get", RECORDER.format(record=record), 0o755)
    dpkg = write(tmp_path / "dpkg-deb", "#!/bin/sh\necho chatmon\n", 0o755)
    temp = tmp_path / "tmp"
    temp.mkdir()
    script = write(tmp_path / "install-update", substituted(text(REPO / "packaging" / "linux" / "install-update"), **{
        '[ "$(id -u)" = 0 ]': f'[ "$(id -u)" = {uid} ]',
        "/usr/bin/python3 -I -S /usr/lib/chatmon/verify-update": f"{sys.executable} -I -S {verify}",
        "dpkg-deb --field": str(dpkg),
        "apt-get install": f"{apt} install",
        "mktemp -d /tmp/chatmon-update.": f"mktemp -d {temp}/chatmon-update.",
    }), 0o755)

    def run(*args):
        return subprocess.run(["/bin/sh", str(script), *map(str, args)], capture_output=True, text=True, timeout=60)

    return release, home, record, temp, run


def test_a_signed_newer_package_is_installed_from_roots_own_copy(linux):
    release, _home, record, temp, run = linux
    out = run(release.package, release.sums, release.sig)
    assert out.returncode == 0, out
    assert (record / "installed").read_bytes() == release.package.read_bytes()
    args = (record / "args").read_text().split()
    assert args[:2] == ["install", "-y"] and Path(args[-1]).name == "update.deb" and Path(args[-1]).parent.parent == temp
    assert (record / "folder").read_text().startswith("drwx------")  # a folder only its owner (root) can use
    assert list(temp.iterdir()) == []  # and gone afterwards


def test_a_tampered_list_is_refused_by_root(linux):
    release, _home, record, _temp, run = linux
    release.sums.write_bytes(release.sums.read_bytes() + b"# changed after signing\n")
    out = run(release.package, release.sums, release.sig)
    assert out.returncode == 3 and "isn't signed with Chatmon's release key" in out.stderr, out
    assert not (record / "args").exists()


def test_a_bad_signature_is_refused_by_root(linux):
    release, _home, record, _temp, run = linux
    release.sig.write_bytes(bytes(64))
    out = run(release.package, release.sums, release.sig)
    assert out.returncode == 3 and "isn't signed" in out.stderr, out
    assert not (record / "args").exists()


def test_an_older_release_is_refused_by_root(linux, tmp_path):
    """A real, signed release, but not newer than the one installed: rolling back is refused."""
    _release, home, record, _temp, run = linux
    old = Release(tmp_path / "old", "chatmon_0.9.1-1_all.deb", b"an older package")
    package_copy(home, old.public)
    out = run(old.package, old.sums, old.sig)
    assert out.returncode == 3 and "isn't newer than the 0.9.2 installed" in out.stderr, out
    assert not (record / "args").exists()


def test_a_package_that_changed_since_it_was_listed_is_refused_by_root(linux):
    release, _home, record, _temp, run = linux
    release.package.write_bytes(b"something else")
    out = run(release.package, release.sums, release.sig)
    assert out.returncode == 3 and "isn't in the release's signed list" in out.stderr, out
    assert not (record / "args").exists()


def test_a_checksum_from_the_caller_is_never_taken(linux):
    """The old call, FILE SHA256: refused before anything is looked at."""
    release, _home, record, _temp, run = linux
    out = run(release.package, hashlib.sha256(release.package.read_bytes()).hexdigest())
    assert out.returncode == 2 and "usage" in out.stderr
    assert not (record / "args").exists()


@pytest.mark.parametrize("change", ["group-writable module", "others-writable folder", "module is a link", "compiled copy writable"])
def test_the_check_isnt_loaded_from_anything_but_roots_own(linux, change, tmp_path):
    release, home, record, _temp, run = linux
    module = home / "chatmon" / "ed25519.py"
    if change == "group-writable module":
        module.chmod(0o664)
    elif change == "others-writable folder":
        (home / "chatmon").chmod(0o757)
    elif change == "module is a link":
        elsewhere = tmp_path / "ed25519.py"
        shutil.copy(module, elsewhere)
        module.unlink()
        module.symlink_to(elsewhere)
    else:
        compiled = home / "chatmon" / "__pycache__"
        compiled.mkdir(mode=0o755)
        write(compiled / "releasecheck.cpython-399.pyc", "", 0o666)
    out = run(release.package, release.sums, release.sig)
    assert out.returncode == 3 and "isn't root's alone" in out.stderr, out
    assert not (record / "args").exists()


def test_only_root_runs_it(linux, tmp_path):
    release, _home, record, _temp, _run = linux
    if os.getuid() == 0:
        pytest.skip("this test itself runs as root")
    original = text(REPO / "packaging" / "linux" / "install-update")
    out = subprocess.run(["/bin/sh", "-c", original, "install-update", str(release.package), str(release.sums), str(release.sig)],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 1 and "run as root" in out.stderr and not (record / "args").exists()


def test_the_package_installs_the_check_where_install_update_runs_it():
    nfpm = text(REPO / "packaging" / "linux" / "nfpm.yaml")
    assert "src: ./packaging/linux/verify-update" in nfpm and "dst: /usr/lib/chatmon/verify-update" in nfpm
    script = text(REPO / "packaging" / "linux" / "install-update")
    assert "/usr/bin/python3 -I -S /usr/lib/chatmon/verify-update " in script
    assert 'HOME = "/usr/lib/chatmon"' in text(REPO / "packaging" / "linux" / "verify-update")


# -- macOS: the root code, and the checked copy of Chatmon.app it runs


FAKE_APP = """#!/bin/sh
# Stands in for the frozen Chatmon: `Chatmon verify-update ...` runs Chatmon's release check from inside this app.
touch "{ran}"
[ "$1" = verify-update ] || exit 64
shift
here=$(cd "$(dirname "$0")/../Resources" && pwd)
exec "{python}" -I -S -c 'import sys; sys.path.append(sys.argv[1]); from chatmon.releasecheck import main; raise SystemExit(main(sys.argv[2:]))' "$here" "$@"
"""


@pytest.fixture
def mac(tmp_path):
    if sys.platform != "darwin":
        pytest.skip("macOS's root code: ditto, BSD find, osascript")
    from chatmon import updates  # Qt, which macOS CI has

    release = Release(tmp_path / "downloads", "Chatmon-9.0.0-macos-arm64.pkg")
    record = tmp_path / "record"
    record.mkdir()
    app = tmp_path / "Applications" / "Chatmon.app"
    uid = str(os.getuid())
    resources = app / "Contents" / "Resources"
    package_copy(resources, release.public)
    write(app / "Contents" / "MacOS" / "Chatmon", FAKE_APP.format(ran=tmp_path / "app-ran", python=sys.executable), 0o755)
    installer = write(tmp_path / "installer", RECORDER.format(record=record), 0o755)
    write(resources / "install-update", substituted(text(REPO / "packaging" / "macos" / "install-update"), **{
        '[ "$(id -u)" = 0 ]': f'[ "$(id -u)" = {uid} ]', "installer -pkg": f"{installer} -pkg",
    }), 0o755)
    for folder in (app, app / "Contents", app / "Contents" / "MacOS", resources):
        folder.chmod(0o755)
    root = substituted(updates._MACOS_ROOT, **{"app=/Applications/Chatmon.app": f"app='{app}'", "! -user root": f"! -user {uid}"})

    def run(*args):
        return subprocess.run(["/bin/sh", "-c", root, "chatmon-update", *map(str, args)], capture_output=True, text=True, timeout=120)

    return release, app, record, run, root


def test_mac_a_signed_newer_package_is_installed_from_a_checked_copy(mac, tmp_path):
    release, app, record, run, _root = mac
    out = run(release.package, release.sums, release.sig)
    assert out.returncode == 0, out
    assert (record / "installed").read_bytes() == release.package.read_bytes()
    installed_from = Path((record / "args").read_text().split()[1])
    assert installed_from.name == "update.pkg" and (installed_from.parent / "Chatmon.app").name == "Chatmon.app"
    assert not installed_from.parent.exists()  # the root-only folder, gone afterwards
    assert (record / "folder").read_text().startswith("drwx------")


@pytest.mark.parametrize("tamper", ["list", "signature", "older"])
def test_mac_what_isnt_a_signed_newer_release_is_refused(mac, tmp_path, tamper):
    release, app, record, run, _root = mac
    if tamper == "list":
        release.sums.write_bytes(release.sums.read_bytes() + b"\n")
    elif tamper == "signature":
        release.sig.write_bytes(bytes(64))
    else:
        package_copy(app / "Contents" / "Resources", release.public, installed="9.0.0")
    out = run(release.package, release.sums, release.sig)
    assert out.returncode == 3, out
    assert ("isn't newer" if tamper == "older" else "isn't signed") in out.stderr
    assert not (record / "args").exists()


def test_mac_an_app_others_could_change_is_never_run_as_root(mac, tmp_path):
    """One file in Chatmon.app that isn't root's alone (here, writable by its group): nothing of the app runs."""
    release, app, record, run, _root = mac
    (app / "Contents" / "Resources" / "chatmon" / "ed25519.py").chmod(0o664)
    out = run(release.package, release.sums, release.sig)
    assert out.returncode == 3 and "isn't the system's own" in out.stderr, out
    assert not (tmp_path / "app-ran").exists() and not (record / "args").exists()


def test_mac_the_applescript_hands_paths_over_as_data(mac, tmp_path):
    """The AppleScript as the updater runs it, without asking for a password: a download whose name is made to
    break out of quotes is still just a name, and the update still goes through the checked copy."""
    from chatmon import updates

    release, _app, record, _run, root = mac
    hostile = release.package.with_name("it's a \"pkg\" $(touch pwned).pkg")
    release.package.rename(hostile)
    script = updates._MACOS_SCRIPT.replace(" with administrator privileges", "")
    env = {**os.environ, "CHATMON_ROOT": root, "CHATMON_UPDATE": str(hostile), "CHATMON_SUMS": str(release.sums), "CHATMON_SIG": str(release.sig)}
    out = subprocess.run(["/usr/bin/osascript", "-e", script], env=env, capture_output=True, text=True, cwd=tmp_path, timeout=120)
    # Renamed, it isn't under its release name, but the list is checked by checksum: still the signed package.
    assert out.returncode == 0, out
    assert (record / "installed").read_bytes() == hostile.read_bytes()
    assert not (tmp_path / "pwned").exists()
