"""Where Chatmon keeps things on Windows: %LOCALAPPDATA%\\chatmon, this computer's own, moved there once from the
roaming profile (%APPDATA%), where versions before 0.10 kept settings and chats; and a Chatmon of its own, apart
from yours, for tests. Runs everywhere: off Windows, paths is told it's on Windows."""

import os
import sys
import time

import pytest

from chatmon import paths


@pytest.fixture
def windows(tmp_path, monkeypatch):
    """Roaming and Local folders of the test's own, and paths answering as on Windows."""
    roaming, local = tmp_path / "Roaming", tmp_path / "Local"
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setattr(paths.sys, "platform", "win32")
    return roaming, local


def fill(folder, files):
    for rel, text in files.items():
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        (folder / rel).write_text(text, encoding="utf-8")


def contents(folder):
    return {p.relative_to(folder).as_posix(): p.read_text(encoding="utf-8") for p in folder.rglob("*") if p.is_file()}


BEFORE_0_10 = {"config.toml": 'name = "Starry"\n', "state/state.json": '{"x": 630}', "state/chats/a.json": '{"title": "Hi"}',
               "state/memory.json": "{}"}


def test_on_windows_everything_lives_on_this_computer(windows):
    roaming, local = windows
    assert paths.config_file() == local / "chatmon" / "config.toml"
    assert paths.state_file() == local / "chatmon" / "state" / "state.json"
    assert paths.work_dir().parent == local / "chatmon" / "state"
    assert not roaming.exists()


def test_settings_and_chats_move_off_the_roaming_profile_once(windows):
    roaming, local = windows
    fill(roaming / "chatmon", BEFORE_0_10)
    assert paths.migrate() == []  # not a rename: nothing to tell
    assert contents(local / "chatmon") == BEFORE_0_10
    assert not (roaming / "chatmon").exists()  # nothing left behind
    assert paths.state_file().read_text(encoding="utf-8") == '{"x": 630}'
    paths.migrate()  # again: nothing to do
    assert contents(local / "chatmon") == BEFORE_0_10


def test_they_join_whats_on_this_computer_already_the_newer_file_winning(windows):
    roaming, local = windows
    fill(local / "chatmon", {"updates/chatmon-9.exe": "a download", "state/chats/b.json": "newer here", "state/state.json": "older here"})
    fill(roaming / "chatmon", {**BEFORE_0_10, "state/chats/b.json": "older there"})
    now = time.time()
    os.utime(local / "chatmon" / "state" / "state.json", (now - 100, now - 100))
    os.utime(roaming / "chatmon" / "state" / "chats" / "b.json", (now - 100, now - 100))
    paths.migrate()
    assert contents(local / "chatmon") == {**BEFORE_0_10, "updates/chatmon-9.exe": "a download", "state/chats/b.json": "newer here"}
    assert not (roaming / "chatmon").exists()


def test_across_volumes_each_file_is_copied_then_removed(windows, monkeypatch):
    """A roaming profile redirected to a server: no rename reaches it, so each file is copied, then removed."""
    roaming, local = windows
    fill(roaming / "chatmon", BEFORE_0_10)

    def other_volume(src, dst):
        raise OSError(18, "Invalid cross-device link")

    monkeypatch.setattr(paths.os, "replace", other_volume)
    paths.migrate()
    assert contents(local / "chatmon") == BEFORE_0_10 and not (roaming / "chatmon").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="a file in use can't be moved: Windows")
def test_a_file_in_use_is_finished_next_time(windows):
    roaming, local = windows
    fill(roaming / "chatmon", BEFORE_0_10)
    with open(roaming / "chatmon" / "state" / "memory.json", "rb"):  # open, as an older Chatmon still running might
        paths.migrate()
        assert (roaming / "chatmon" / "state" / "memory.json").exists()
        assert contents(local / "chatmon")["state/chats/a.json"] == '{"title": "Hi"}'
    paths.migrate()
    assert contents(local / "chatmon") == BEFORE_0_10 and not (roaming / "chatmon").exists()


def test_the_old_name_from_the_roaming_profile_comes_along_too(windows):
    roaming, local = windows
    fill(roaming / paths.LEGACY_APP, BEFORE_0_10)
    moved = paths.migrate()
    assert moved == [(roaming / paths.LEGACY_APP, roaming / "chatmon")]
    assert contents(local / "chatmon") == {**BEFORE_0_10, f"state/{paths.RENAMED}": ""}
    assert not (roaming / paths.LEGACY_APP).exists() and not (roaming / "chatmon").exists()
    assert paths.first_run_since_rename() and not paths.first_run_since_rename()


def test_the_old_name_never_overwrites_chatmons_own_on_this_computer(windows):
    roaming, local = windows
    fill(roaming / paths.LEGACY_APP, {"config.toml": "old\n"})
    fill(local / "chatmon", {"config.toml": "new\n"})
    assert paths.migrate() == []
    assert paths.config_file().read_text(encoding="utf-8") == "new\n"
    assert (roaming / paths.LEGACY_APP / "config.toml").read_text(encoding="utf-8") == "old\n"


# -- a Chatmon of its own


def test_a_chatmon_of_its_own_has_an_address_of_its_own(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv(paths.INSTANCE_ENV, raising=False)
    yours = paths.server_name()
    monkeypatch.setenv(paths.INSTANCE_ENV, "test-42")
    assert paths.instance() == "test-42" and paths.server_name() != yours and paths.server_name().endswith("test-42" if sys.platform == "win32" else "test-42.sock")
    for odd in ("../elsewhere", "a b", "x" * 41, ""):
        monkeypatch.setenv(paths.INSTANCE_ENV, odd)
        assert paths.instance() == "" and paths.server_name() == yours
