"""Attaching a file: looked at before it's opened (a folder, a device or a pipe is never opened), checked again by
what was opened (a file swapped in between is refused), and never one on another computer, on any system.

The network cases stand in for the system's own answer about a drive or mount (GetDriveTypeW, statfs) at that
boundary, since a test can't count on a network share; each also runs the real call on a local folder."""

import os
import stat
import sys
from pathlib import Path

import pytest

from chatmon import attachments

POSIX = pytest.mark.skipif(sys.platform == "win32", reason="POSIX file types")


@pytest.fixture
def opened(monkeypatch):
    """Every path os.open is asked to open, while it still opens it."""
    real, seen = os.open, []

    def watching(path, *args, **kwargs):
        seen.append(str(path))
        return real(path, *args, **kwargs)

    monkeypatch.setattr(attachments.os, "open", watching)
    return seen


def test_a_local_file_still_attaches(tmp_path, opened):
    f = tmp_path / "notes.txt"
    f.write_text("hello", encoding="utf-8")
    assert attachments.from_path(f).text == "hello" and opened == [str(f)]


# -- looked at before it's opened, and checked after (AC-09-ORDER)


def test_a_folder_is_refused_without_being_opened(tmp_path, opened):
    with pytest.raises(attachments.AttachError, match="isn't a file"):
        attachments.from_path(tmp_path)
    assert opened == []


@POSIX
def test_a_pipe_or_a_device_is_refused_without_being_opened(tmp_path, opened):
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)
    for path in (fifo, Path("/dev/zero"), Path("/dev/null")):
        with pytest.raises(attachments.AttachError, match="isn't a file"):
            attachments.from_path(path)
    assert opened == []


def test_a_file_swapped_between_the_look_and_the_open_is_refused(tmp_path, monkeypatch):
    f = tmp_path / "report.txt"
    f.write_text("what was looked at", encoding="utf-8")
    other = tmp_path / "other.txt"
    other.write_text("what was swapped in", encoding="utf-8")
    real = os.open

    def swap_then_open(path, *args, **kwargs):
        os.replace(other, f)  # another file at the same name, between os.stat and os.open
        return real(path, *args, **kwargs)

    monkeypatch.setattr(attachments.os, "open", swap_then_open)
    with pytest.raises(attachments.AttachError, match="changed as it was opened"):
        attachments.from_path(f)


@POSIX
def test_a_file_swapped_for_a_pipe_is_refused_after_the_open(tmp_path, monkeypatch):
    f = tmp_path / "report.txt"
    f.write_text("looked at", encoding="utf-8")
    real = os.open

    def swap_then_open(path, *args, **kwargs):
        os.unlink(f)
        os.mkfifo(f)
        return real(path, *args, **kwargs)

    monkeypatch.setattr(attachments.os, "open", swap_then_open)
    with pytest.raises(attachments.AttachError, match="changed as it was opened"):
        attachments.from_path(f)


def test_a_file_too_big_is_refused_before_its_opened(tmp_path, opened):
    big = tmp_path / "big.txt"
    with open(big, "wb") as out:
        out.truncate(attachments.MAX_FILE + 1)
    with pytest.raises(attachments.AttachError, match="too big"):
        attachments.from_path(big)
    assert opened == []


# -- never on another computer (AC-09-REMOTE)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows paths and drives")
def test_windows_shares_are_refused_untouched(monkeypatch, opened):
    looked = []
    monkeypatch.setattr(attachments.os, "stat", lambda path, *a, **k: looked.append(path) or os.stat(path))
    for path in (r"\\server\share\notes.txt", "//server/share/notes.txt", r"\\?\UNC\server\share\notes.txt", r"\\?\unc\server\share\x.txt"):
        with pytest.raises(attachments.AttachError, match="network share"):
            attachments.from_path(Path(path))
    assert opened == [] and looked == []


@pytest.mark.skipif(sys.platform != "win32", reason="Windows paths and drives")
def test_windows_mapped_drives_are_refused_and_local_ones_taken(monkeypatch, tmp_path, opened):
    f = tmp_path / "notes.txt"
    f.write_text("local", encoding="utf-8")
    assert attachments._drive_type(os.path.splitdrive(str(f))[0] + "\\") != attachments.DRIVE_REMOTE  # the real answer, here
    assert attachments.from_path(Path("\\\\?\\" + str(f))).text == "local"  # a local path, spelled the long way
    remote = os.path.splitdrive(str(f))[0].upper()
    monkeypatch.setattr(attachments, "_drive_type", lambda root: attachments.DRIVE_REMOTE if root.upper().startswith(remote) else 3)
    opened.clear()
    with pytest.raises(attachments.AttachError, match="network drive"):
        attachments.from_path(f)
    assert opened == []


@pytest.mark.skipif(sys.platform != "win32", reason="Windows links")
def test_windows_a_link_to_a_share_is_the_share(tmp_path, opened):
    link = tmp_path / "shortcut.txt"
    try:
        os.symlink(r"\\server\share\notes.txt", link)
    except OSError:
        pytest.skip("making links needs Developer Mode or an administrator here")
    with pytest.raises(attachments.AttachError, match="network share"):
        attachments.from_path(link)
    assert opened == []


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux statfs and mountinfo")
def test_linux_network_and_fuse_mounts_are_refused_but_not_fuseblk(monkeypatch, tmp_path, opened):
    f = tmp_path / "notes.txt"
    f.write_text("local", encoding="utf-8")
    assert attachments._statfs_type(f) not in attachments.LINUX_REMOTE  # the real answer, here
    assert attachments.from_path(f).text == "local"
    for magic, says in ((0x6969, "NFS"), (0xFF534D42, "CIFS"), (0xFE534D42, "SMB"), (attachments.FUSE, "FUSE")):
        monkeypatch.setattr(attachments, "_statfs_type", lambda path, m=magic: m)
        monkeypatch.setattr(attachments, "_mount_type", lambda path: "fuse.gvfsd-fuse")
        opened.clear()
        with pytest.raises(attachments.AttachError, match=says):
            attachments.from_path(f)
        assert opened == []
    monkeypatch.setattr(attachments, "_mount_type", lambda path: "fuseblk")  # an NTFS disk here, through ntfs-3g
    assert attachments.from_path(f).text == "local"


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux paths, resolved as Linux does")
def test_linux_mountinfo_names_the_mount_a_path_is_on(tmp_path):
    mountinfo = (
        "22 1 8:2 / / rw,relatime shared:1 - ext4 /dev/sda2 rw\n"
        "40 22 0:45 / /run/user/1000/gvfs rw,nosuid shared:20 - fuse.gvfsd-fuse gvfsd-fuse rw,user_id=1000\n"
        "41 22 8:17 / /media/me/USB\\040Disk rw shared:21 - fuseblk /dev/sdb1 rw,user_id=0\n"
        "42 22 0:50 / /mnt/nas rw shared:22 - nfs4 nas:/export rw\n"
    )
    assert attachments._mount_type(Path("/media/me/USB Disk/photo.png"), mountinfo) == "fuseblk"
    assert attachments._mount_type(Path("/run/user/1000/gvfs/smb-share:server=x/a.txt"), mountinfo) == "fuse.gvfsd-fuse"
    assert attachments._mount_type(Path("/mnt/nas/a.txt"), mountinfo) == "nfs4"
    assert attachments._mount_type(Path("/mnt/nasty/a.txt"), mountinfo) == "ext4"  # a name that only starts the same
    assert attachments._mount_type(Path("/home/me/a.txt"), mountinfo) == "ext4"


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS statfs")
def test_mac_mounts_not_stored_here_are_refused(monkeypatch, tmp_path, opened):
    f = tmp_path / "notes.txt"
    f.write_text("local", encoding="utf-8")
    flags, kind = attachments._mac_statfs(f)  # the real answer: read with the right layout, so a real type
    assert flags & attachments.MNT_LOCAL and kind in ("apfs", "hfs")
    assert attachments.from_path(f).text == "local"
    monkeypatch.setattr(attachments, "_mac_statfs", lambda path: (0, "smbfs"))
    opened.clear()
    with pytest.raises(attachments.AttachError, match="network drive"):
        attachments.from_path(f)
    assert opened == []


def test_where_the_system_cant_say_the_file_itself_decides(tmp_path):
    assert attachments.network_location(tmp_path / "missing.txt") is None
    with pytest.raises(attachments.AttachError, match="couldn't open"):
        attachments.from_path(tmp_path / "missing.txt")
    assert stat.S_ISDIR(os.stat(tmp_path).st_mode)
