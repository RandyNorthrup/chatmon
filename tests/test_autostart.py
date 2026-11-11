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
