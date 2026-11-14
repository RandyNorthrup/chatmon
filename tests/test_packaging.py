"""What packaging/ ships besides Chatmon itself: the macOS installer's postinstall (run as root, for real here as
a copy with root's uid and /usr/local/bin replaced by test values) and each release's notes."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
POSIX = pytest.mark.skipif(sys.platform == "win32", reason="an sh script run as root on macOS (and portable to Linux, for its tests)")


def build_module():
    spec = importlib.util.spec_from_file_location("chatmon_build", REPO / "packaging" / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# -- the macOS postinstall: a chatmon command, written only where root alone can write


@pytest.fixture
def postinstall(tmp_path):
    """The postinstall as shipped, for this test's uid, with /usr/local/bin a folder of the test's own."""
    local = tmp_path / "usr" / "local"
    local.mkdir(parents=True)
    local.chmod(0o755)
    bin_ = local / "bin"
    script = (REPO / "packaging" / "macos" / "scripts" / "postinstall").read_text(encoding="utf-8").replace("\r\n", "\n")
    for old in ("OWNER=0", "BIN=/usr/local/bin"):
        assert old in script
    script = script.replace("OWNER=0", f"OWNER={os.getuid()}").replace("BIN=/usr/local/bin", f"BIN='{bin_}'")
    path = tmp_path / "postinstall"
    path.write_text(script, encoding="utf-8", newline="\n")

    def run(owner: int | None = None):
        text = script if owner is None else script.replace(f"OWNER={os.getuid()}", f"OWNER={owner}")
        path.write_text(text, encoding="utf-8", newline="\n")
        return subprocess.run(["/bin/sh", str(path)], capture_output=True, text=True, timeout=30)

    return local, bin_, run


@POSIX
def test_the_command_is_written_whole_into_a_folder_root_alone_can_write(postinstall):
    _local, bin_, run = postinstall
    bin_.mkdir(mode=0o755)
    bin_.chmod(0o755)
    out = run()
    assert out.returncode == 0, out
    command = bin_ / "chatmon"
    assert command.read_text() == (
        "#!/bin/sh\n# Chatmon's command line, put here by its installer: the app's own program.\n"
        'exec "/Applications/Chatmon.app/Contents/MacOS/Chatmon" "$@"\n'
    )
    assert command.stat().st_mode & 0o777 == 0o755
    assert sorted(p.name for p in bin_.iterdir()) == ["chatmon"]  # nothing of its making left there


@POSIX
def test_a_missing_bin_folder_is_made_root_only(postinstall):
    _local, bin_, run = postinstall
    assert run().returncode == 0
    assert bin_.stat().st_mode & 0o777 == 0o755 and (bin_ / "chatmon").exists()


@POSIX
@pytest.mark.parametrize("unsafe", ["others can write", "group can write", "holder others can write", "a link", "someone else's"])
def test_a_folder_not_roots_alone_gets_nothing(postinstall, tmp_path, unsafe):
    local, bin_, run = postinstall
    bin_.mkdir(mode=0o755)
    bin_.chmod(0o755)
    owner = None
    if unsafe == "others can write":
        bin_.chmod(0o777)
    elif unsafe == "group can write":
        bin_.chmod(0o775)
    elif unsafe == "holder others can write":
        local.chmod(0o777)
    elif unsafe == "a link":
        bin_.rmdir()
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir(mode=0o755)
        bin_.symlink_to(elsewhere)
    else:
        owner = os.getuid() + 1  # "root" is someone this test isn't
    out = run(owner)
    assert out.returncode == 0 and "isn't root's alone" in out.stderr, out
    assert not (bin_ / "chatmon").exists() and not (tmp_path / "elsewhere" / "chatmon").exists()
    assert not bin_.exists() or bin_.is_symlink() or list(bin_.iterdir()) == []


@POSIX
def test_a_link_or_someone_elses_command_is_left_alone(postinstall, tmp_path):
    _local, bin_, run = postinstall
    bin_.mkdir(mode=0o755)
    bin_.chmod(0o755)
    target = tmp_path / "target"
    target.write_text("precious")
    (bin_ / "chatmon").symlink_to(target)
    assert run().returncode == 0 and target.read_text() == "precious" and (bin_ / "chatmon").is_symlink()
    (bin_ / "chatmon").unlink()
    (bin_ / "chatmon").write_text("#!/bin/sh\nexec pipx-chatmon\n")
    assert run().returncode == 0 and (bin_ / "chatmon").read_text() == "#!/bin/sh\nexec pipx-chatmon\n"
    (bin_ / "chatmon").write_text("#!/bin/sh\nexec /Applications/Chatmon.app/old\n")  # an older installer's own: replaced
    assert run().returncode == 0 and "Contents/MacOS/Chatmon" in (bin_ / "chatmon").read_text()


# -- release notes


def test_release_notes_pin_the_pipx_install_to_the_release():
    from chatmon import __version__

    notes = build_module().notes(__version__)
    assert f"pipx install --force git+https://github.com/RandyNorthrup/chatmon@v{__version__}\n" in notes
    assert "chatmon\n```" not in notes  # never main
