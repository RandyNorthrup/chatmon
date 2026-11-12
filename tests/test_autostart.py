"""Starting at login: the desktop entry on Linux, written as the freedesktop spec says."""

import sys

import pytest

from chatmon import autostart, paths

linux_only = pytest.mark.skipif(sys.platform in ("win32", "darwin"), reason="the XDG autostart entry")


def test_exec_is_quoted_as_the_desktop_entry_spec_says():
    assert autostart.exec_line(["/usr/bin/chatmon"]) == "/usr/bin/chatmon"
    assert autostart.exec_line(["/home/José Q/bin/python3", "-m", "chatmon"]) == '"/home/José Q/bin/python3" -m chatmon'
    assert autostart.exec_line(["100%"]) == "100%%"
    # In quotes, " ` $ and \\ take a backslash; then every backslash is written twice (a literal one: four).
    assert autostart.exec_line(['a"b']) == '"a\\\\"b"'
    assert autostart.exec_line(["a$b"]) == '"a\\\\$b"'
    assert autostart.exec_line(["a\\b"]) == '"a\\\\\\\\b"'
    assert autostart.exec_line(["it's"]) == '"it\'s"'  # single quotes mean nothing to it: the argument is double-quoted


@linux_only
def test_the_entry_has_the_apps_own_name_and_icon_and_replaces_the_old_one(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(paths, "command_line", lambda windowless=False: ["/opt/my apps/chatmon"])
    old = tmp_path / "autostart" / "chatmon.desktop"
    old.parent.mkdir()
    old.write_text("[Desktop Entry]\nExec=chatmon\n")
    assert autostart.enabled()
    assert autostart.migrate()
    entry = tmp_path / "autostart" / "io.github.RandyNorthrup.chatmon.desktop"
    text = entry.read_text()
    assert not old.exists() and 'Exec="/opt/my apps/chatmon"' in text and "Icon=io.github.RandyNorthrup.chatmon" in text
    autostart.set_enabled(False)
    assert not entry.exists() and not autostart.enabled()


def test_a_newline_in_a_path_cant_add_a_line_to_the_entry():
    line = autostart.exec_line(["/home/me/odd\nX-Evil=1/chatmon"])
    assert "\n" not in line and "\\n" in line


class PretendLoginItems:
    """SMAppService for Chatmon.app, as macnative reports it: never the real one in a test."""

    def __init__(self, status: int, refuses: str | None = None):
        self.status, self.refuses, self.calls = status, refuses, []

    def install(self, monkeypatch, tmp_path):
        from chatmon import macnative

        monkeypatch.setattr(autostart.sys, "platform", "darwin")
        monkeypatch.setattr(autostart.Path, "home", lambda: tmp_path)
        monkeypatch.setattr(paths, "command_line", lambda windowless=False: ["/Applications/Chatmon.app/Contents/MacOS/Chatmon"])
        monkeypatch.setattr(autostart, "_login_item", lambda: self.status)
        monkeypatch.setattr(macnative, "set_login_item", self.set)
        return tmp_path / "Library" / "LaunchAgents" / "io.github.chatmon.plist"

    def set(self, on: bool) -> str | None:
        from chatmon import macnative

        self.calls.append(on)
        if self.refuses:
            return self.refuses
        self.status = macnative.ENABLED if on else macnative.NOT_REGISTERED
        return None


def test_chatmon_app_is_a_login_item_of_its_own_on_macos(tmp_path, monkeypatch):
    """Listed by name in System Settings › General › Login Items, not as an unattributed LaunchAgent."""
    from chatmon import macnative

    items = PretendLoginItems(macnative.NOT_FOUND)
    agent = items.install(monkeypatch, tmp_path)
    assert not autostart.enabled() and "Login Items" in autostart.where()
    autostart.set_enabled(True)
    assert autostart.enabled() and items.calls == [True] and not agent.exists()
    items.status = macnative.NOT_REGISTERED  # turned off in System Settings: the menu says so too
    assert not autostart.enabled()
    autostart.set_enabled(False)
    assert items.calls == [True]  # nothing to take back


def test_an_older_launch_agent_becomes_the_login_item(tmp_path, monkeypatch):
    from chatmon import macnative

    items = PretendLoginItems(macnative.NOT_FOUND)
    agent = items.install(monkeypatch, tmp_path)
    agent.parent.mkdir(parents=True)
    agent.write_bytes(autostart.plistlib.dumps({"Label": "io.github.chatmon", "ProgramArguments": ["/x"], "RunAtLoad": True}))
    assert autostart.enabled()  # it does start at login, before the move as after
    assert autostart.refresh() and not agent.exists() and items.status == macnative.ENABLED
    assert not autostart.refresh()  # once


def test_a_login_item_macos_turns_down_falls_back_to_a_launch_agent(tmp_path, monkeypatch, capsys):
    from chatmon import macnative

    items = PretendLoginItems(macnative.NOT_FOUND, refuses="Operation not permitted")
    agent = items.install(monkeypatch, tmp_path)
    autostart.set_enabled(True)
    assert agent.exists() and autostart.enabled() and "Operation not permitted" in capsys.readouterr().err
    assert autostart.plistlib.loads(agent.read_bytes())["ProgramArguments"] == ["/Applications/Chatmon.app/Contents/MacOS/Chatmon"]
    items.refuses, items.status = None, macnative.ENABLED
    autostart.set_enabled(False)
    assert not agent.exists() and items.calls[-1] is False


def test_run_from_source_or_pip_it_is_no_login_item(monkeypatch):
    """There's no Chatmon.app then: the main bundle would be Python's own, which mustn't start at login."""
    monkeypatch.setattr(autostart.sys, "platform", "darwin")
    monkeypatch.delattr(autostart.sys, "frozen", raising=False)
    assert autostart._login_item() is None
