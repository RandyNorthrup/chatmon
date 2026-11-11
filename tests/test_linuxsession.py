"""What Chatmon hears from a Linux system over D-Bus (the parts that take no running service)."""

import pytest

pytest.importorskip("PyQt6.QtDBus")  # not in PyQt's Windows build


def test_the_power_saver_profile_is_heard_as_it_changes(qapp):
    from PyQt6.QtDBus import QDBusMessage

    from chatmon import linuxsession

    heard = []
    watcher = linuxsession.PowerProfile(heard.append)  # whatever this machine's profile is now
    heard.clear()
    for profile in ("power-saver", "balanced"):
        signal = QDBusMessage.createSignal("/org/freedesktop/UPower/PowerProfiles", "org.freedesktop.DBus.Properties", "PropertiesChanged")
        signal.setArguments(["org.freedesktop.UPower.PowerProfiles", {"ActiveProfile": profile}, []])
        watcher._changed(signal)
    watcher._changed(QDBusMessage.createSignal("/", "org.freedesktop.DBus.Properties", "PropertiesChanged"))  # nothing in it
    assert heard == [True, False]
