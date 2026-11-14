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


def _properties_changed(path: str, interface: str, changed: dict):
    from PyQt6.QtDBus import QDBusMessage

    signal = QDBusMessage.createSignal(path, "org.freedesktop.DBus.Properties", "PropertiesChanged")
    signal.setArguments([interface, changed, []])
    return signal


def test_running_on_battery_saves_power_too(qapp):
    """UPower's OnBattery and the power-saver profile: saving while either is on, each change told once."""
    from chatmon import linuxsession

    heard = []
    watcher = linuxsession.PowerProfile(heard.append)
    heard.clear()
    watcher.profile_saver = watcher.on_battery = False
    watcher.told = False  # as told at start on a machine plugged in, without power-saver
    upower = ("/org/freedesktop/UPower", "org.freedesktop.UPower")
    profiles = ("/org/freedesktop/UPower/PowerProfiles", "org.freedesktop.UPower.PowerProfiles")
    watcher._changed(_properties_changed(*upower, {"OnBattery": True}))  # unplugged: on battery alone saves power
    assert heard == [True]
    watcher._changed(_properties_changed(*profiles, {"ActiveProfile": "power-saver"}))  # still saving: no news
    watcher._changed(_properties_changed(*upower, {"OnBattery": False}))  # plugged in, power-saver still on
    assert heard == [True]
    watcher._changed(_properties_changed(*profiles, {"ActiveProfile": "balanced"}))
    assert heard == [True, False]
    watcher._changed(_properties_changed(*upower, {"Percentage": 50.0}))  # another of UPower's properties
    watcher._changed(_properties_changed("/org/freedesktop/UPower/devices/battery_BAT0", "org.freedesktop.UPower.Device", {"OnBattery": True}))
    assert heard == [True, False]


def test_the_lock_is_told_once_and_stops_drawing(qapp):
    """logind's LockedHint and the screen saver both tell of a lock: told once, and nothing need be drawn."""
    from PyQt6.QtDBus import QDBusMessage

    from chatmon import linuxsession

    locked, slept, seen = [], [], []
    watcher = linuxsession.SessionWatcher(locked.append, slept.append, seen=seen.append)

    def hint(on: bool) -> QDBusMessage:
        return _properties_changed("/org/freedesktop/login1/session/_32", "org.freedesktop.login1.Session", {"LockedHint": on})

    watcher._active(True)  # the screen saver comes on
    watcher._session_changed(hint(True))  # and logind says it's locked: the same news
    watcher._session_changed(_properties_changed("/org/freedesktop/login1/session/_32", "org.freedesktop.login1.Session", {"IdleHint": True}))
    watcher._sleep(True)
    watcher._sleep(False)
    watcher._session_changed(hint(False))
    watcher._active(False)
    assert locked == [True, False] and seen == [False, True] and slept == [True, False]
    plain = linuxsession.SessionWatcher(locked.append, slept.append)  # without `seen`, as before
    plain._active(True)
    assert locked == [True, False, True]


def test_portal_settings_are_yes_no_or_unknown(qapp):
    from PyQt6.QtDBus import QDBusVariant

    from chatmon import linuxsession

    assert linuxsession.portal_flag(1) is True and linuxsession.portal_flag(0) is False
    assert linuxsession.portal_flag(QDBusVariant(QDBusVariant(1))) is True  # Read (version 1) wraps it twice
    assert linuxsession.portal_flag(2) is None and linuxsession.portal_flag("1") is None and linuxsession.portal_flag(None) is None
    told = []
    settings = linuxsession.PortalSettings(lambda: told.append(dict(settings.values)))
    settings.set("contrast", 1)
    settings.set("contrast", 1)
    settings.set("reduced-motion", 0)
    assert told == [{"contrast": True}, {"contrast": True, "reduced-motion": False}]
    settings.close()


def test_packagekit_answers_with_a_count_where_it_runs(qapp):
    from chatmon import packagekit

    if not packagekit.present():
        pytest.skip("no PackageKit here")
    from PyQt6.QtCore import QEventLoop, QTimer

    answers = []
    loop = QEventLoop()
    counter = packagekit.UpdateCount()
    counter.counted.connect(lambda n: (answers.append(n), loop.quit()))
    QTimer.singleShot(150_000, loop.quit)
    counter.start()
    loop.exec()
    assert answers and isinstance(answers[0], int)


POWER_CLIENT = r"""
import sys
sys.path.insert(0, sys.argv[1])
from PyQt6.QtCore import QCoreApplication, QTimer
app = QCoreApplication([])
from chatmon import linuxsession
told = []
watcher = linuxsession.PowerProfile(told.append)
QTimer.singleShot(1500, app.quit)
app.exec()
print("saving", told, "heard", watcher.heard, flush=True)
"""


def test_power_saving_follows_upower_on_a_bus(tmp_path):
    """Against a pretend UPower (tests/fake_upower.py) and no power-profiles-daemon: on battery at first, then
    plugged in, each told as UPower says it, without waiting."""
    import private_bus

    private_bus.needs_dbus_run_session()
    out, asked = private_bus.as_system_bus(tmp_path, "fake_upower.py", ["80", "2", "true", "false"], POWER_CLIENT)
    assert "saving [True, False] heard ['org.freedesktop.UPower']" in out, out
    assert {"path": "UPower", "method": "Get", "name": "OnBattery"} in asked
