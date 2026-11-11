"""Chatmon's place in a Linux desktop: its .desktop file, and the desktop's notifications."""

import configparser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_the_desktop_file_offers_bring_out_and_quit():
    entry = configparser.ConfigParser(interpolation=None)
    entry.optionxform = str
    entry.read(ROOT / "packaging" / "linux" / "io.github.RandyNorthrup.chatmon.desktop", encoding="utf-8")
    assert entry["Desktop Entry"]["Actions"] == "show;quit;"
    assert entry["Desktop Action show"]["Exec"] == "chatmon"  # a running Chatmon comes out when started again
    assert entry["Desktop Action quit"]["Exec"] == "chatmon quit"


def test_a_notification_is_the_specs_eight_arguments(qapp):
    from chatmon import sysnotify

    message = sysnotify.message("Reminder", "Chatmon has something for you.")
    args = message.arguments()
    assert (message.service(), message.path(), message.member()) == (sysnotify.SERVICE, sysnotify.PATH, "Notify")
    assert len(args) == 8 and args[0] == "Chatmon" and args[2] == sysnotify.APP_ID
    assert args[3:5] == ["Reminder", "Chatmon has something for you."] and args[7] == -1  # the server's own timeout
    assert args[5] == [] and args[6] == {"desktop-entry": sysnotify.APP_ID}
