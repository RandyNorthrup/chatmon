"""Chatmon was penguin-companion before 0.3.0: its settings, state and login entry come along."""

import sys

import pytest

from chatmon import autostart, paths


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / ".state"))
    monkeypatch.setattr(paths.Path, "home", lambda: tmp_path)
    return tmp_path


def _old(new):
    """The old name's folder: beside Chatmon's, except on Windows, where it was in the roaming profile (as
    Chatmon's own was before 0.10)."""
    if sys.platform == "win32" and new == paths.config_dir():
        return paths._roaming() / paths.LEGACY_APP
    return new.with_name(paths.LEGACY_APP)


def test_settings_and_state_move_to_the_new_name(home):
    old_config = _old(paths.config_dir())
    if sys.platform in ("win32", "darwin"):  # one folder for both, with the state in a folder inside it
        old_state = old_config / "state"
    else:
        old_state = _old(paths.state_dir())
    old_config.mkdir(parents=True)
    old_state.mkdir(parents=True, exist_ok=True)
    (old_config / "config.toml").write_text('name = "Starry"\n')
    (old_state / "state.json").write_text('{"x": 630}')

    moved = paths.migrate()
    assert moved and not old_config.exists()
    assert paths.config_file().read_text() == 'name = "Starry"\n'
    assert paths.state_file().read_text() == '{"x": 630}'
    assert paths.migrate() == []  # once
    assert paths.first_run_since_rename() and not paths.first_run_since_rename()  # the app hears of it once


def test_existing_chatmon_settings_are_never_overwritten(home):
    old = _old(paths.config_dir())
    old.mkdir(parents=True)
    (old / "config.toml").write_text("old\n")
    paths.config_dir().mkdir(parents=True)
    paths.config_file().write_text("new\n")
    paths.migrate()
    assert paths.config_file().read_text() == "new\n" and (old / "config.toml").read_text() == "old\n"


def test_nothing_old_moves_nothing(home):
    assert paths.migrate() == [] and not paths.first_run_since_rename()


@pytest.mark.skipif(sys.platform == "win32", reason="Windows keeps it in the registry")
def test_login_entry_moves_to_the_new_name(home, monkeypatch):
    monkeypatch.setattr(paths, "command_line", lambda windowless=False: ["/usr/bin/chatmon"])
    old = autostart._launch_agent(autostart._LEGACY_LABEL) if sys.platform == "darwin" else autostart._desktop_file(paths.LEGACY_APP)
    old.parent.mkdir(parents=True)
    old.write_text("old entry")
    assert autostart.migrate()
    assert not old.exists() and autostart.enabled()
    assert "/usr/bin/chatmon" in autostart._launch_agent().read_bytes().decode() if sys.platform == "darwin" else "Exec=/usr/bin/chatmon" in autostart._desktop_file().read_text()
    assert not autostart.migrate()  # once


@pytest.mark.skipif(sys.platform == "win32", reason="Windows keeps it in the registry")
def test_no_old_login_entry_adds_none(home):
    assert not autostart.migrate() and not autostart.enabled()
