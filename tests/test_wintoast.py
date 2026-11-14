"""Windows' toasts (wintoast.py): their XML anywhere; on Windows, shown through WinRT for real under a throwaway app
ID, with everything they leave in Action Center and the registry removed after."""

import ctypes
import sys
import threading
import time
import uuid
import xml.etree.ElementTree as ET

import pytest

from chatmon import wintoast

windows = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


def actions(xml: str) -> list[dict]:
    return [a.attrib for a in ET.fromstring(xml).iter("action")]


# -- the toast's XML


def test_text_from_an_agent_is_text_never_markup():
    xml = wintoast.toast_xml('<b>Fish & "chips"</b>', "a\x01b <script>x</script>", tag="abc")
    texts = [t.text for t in ET.fromstring(xml).iter("text")]
    assert texts == ['<b>Fish & "chips"</b>', "ab <script>x</script>"]  # escaped, and the control character dropped
    assert "<script>" not in xml and "<b>" not in xml


def test_buttons_say_which_toast_and_which_button():
    xml = wintoast.toast_xml("Claude needs you", "Allow edits?", ["Allow", ("Deny", None)], tag="1f")
    toast = ET.fromstring(xml)
    assert toast.get("launch") == "chatmon:1f:-1" and toast.get("scenario") is None
    assert actions(xml) == [{"content": "Allow", "arguments": "chatmon:1f:0", "activationType": "foreground"},
                            {"content": "Deny", "arguments": "chatmon:1f:1", "activationType": "foreground"}]
    assert wintoast.parse_arguments("chatmon:1f:1") == ("1f", 1)
    assert wintoast.parse_arguments(toast.get("launch")) == ("1f", wintoast.BODY)


def test_a_reminder_stays_until_answered():
    with_buttons = wintoast.toast_xml("Reminder", "Stretch", ["Snooze 10 min", "Done"], "reminder", tag="9")
    assert ET.fromstring(with_buttons).get("scenario") == "reminder" and len(actions(with_buttons)) == 2
    # Windows holds a reminder on screen only when it has a button: without one, its own Dismiss.
    bare = wintoast.toast_xml("Reminder", "Stretch", (), "reminder", tag="9")
    assert actions(bare) == [{"content": "", "arguments": "dismiss", "activationType": "system"}]
    assert ET.fromstring(wintoast.toast_xml("Hi", silent=True)).find("audio").get("silent") == "true"
    assert ET.fromstring(wintoast.toast_xml("Hi")).find("actions") is None  # an ordinary toast: no actions element


def test_too_many_buttons_or_an_unknown_scenario_is_refused():
    assert len(actions(wintoast.toast_xml("t", buttons=[str(i) for i in range(5)]))) == 5
    with pytest.raises(ValueError, match="at most 5"):
        wintoast.toast_xml("t", buttons=[str(i) for i in range(6)])
    with pytest.raises(ValueError, match="scenario"):
        wintoast.toast_xml("t", scenario="incomingCall")


def test_only_chatmons_own_arguments_are_read():
    for text in ("", "dismiss", "chatmon:xyz:1", "chatmon:ab:1:2", "other:ab:1", "chatmon:ab:"):
        assert wintoast.parse_arguments(text) is None


@pytest.mark.skipif(sys.platform == "win32", reason="elsewhere than Windows")
def test_elsewhere_there_are_no_toasts_and_the_caller_falls_back(qapp):
    toaster = wintoast.Toaster("RandyNorthrup.Chatmon")
    assert toaster.show("Hi", "there", ["OK"]) is None and toaster.why_not
    assert wintoast.process_app_id() is None


# -- on Windows, for real


def notifications_on() -> bool:
    """What the user chose in Settings, read straight from the registry: the test's own word, not the module's."""
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\PushNotifications") as key:
            return winreg.QueryValueEx(key, "ToastEnabled")[0] != 0
    except FileNotFoundError:
        return True  # never turned off


def wait_for(qapp, done, seconds: float = 5.0) -> bool:
    deadline = time.monotonic() + seconds
    while not done() and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.02)
    return bool(done())


@pytest.fixture
def toaster(qapp):
    """A Toaster under a throwaway app ID, registered as a pip install would be; all of it gone after."""
    app_id = f"RandyNorthrup.Chatmon.Test{uuid.uuid4().hex[:8]}"
    wintoast.register_app_id(app_id, "Chatmon test")
    toaster = wintoast.Toaster(app_id)
    try:
        yield toaster
    finally:
        toaster.clear()
        left = toaster.in_action_center()
        toaster.close()
        wintoast.unregister_app_id(app_id)
        assert left == []


@windows
def test_a_toast_is_shown_or_the_caller_is_told_to_use_the_balloon(toaster, qapp):
    tag = toaster.show("Chatmon test", "A toast from Chatmon's tests, removed at once.", ["OK"], silent=True)
    setting = toaster.setting()
    if notifications_on() and setting == wintoast.ENABLED:
        assert tag is not None and toaster.why_not is None, toaster.why_not
        assert wait_for(qapp, lambda: tag in toaster.in_action_center()), "Windows never had the toast"
        assert toaster.hide(tag)
    elif notifications_on():  # on for you, off by Windows itself (a policy, a manifest, a CI runner's session): said so
        assert tag is None and toaster.why_not == wintoast.WHY_NOT[setting] and toaster.listening == [], (setting, toaster.why_not)
    else:
        assert tag is None and toaster.why_not == wintoast.WHY_NOT[wintoast.OFF_FOR_USER]
        assert setting == wintoast.OFF_FOR_USER and toaster.listening == []


@windows
def test_what_windows_says_of_a_toast_comes_back_on_the_qt_thread(toaster, qapp):
    """Posted straight to Action Center. Where notifications are off Windows refuses it (Failed); where they're on
    it's there until Chatmon hides it (Dismissed). Either way Windows calls back on a thread of its own."""
    heard = []
    main = threading.get_ident()
    toaster.failed.connect(lambda tag, code: heard.append(("failed", tag, code, threading.get_ident() == main)))
    toaster.dismissed.connect(lambda tag, why: heard.append(("dismissed", tag, why, threading.get_ident() == main)))
    tag = "a1b2c3"
    assert toaster._post(wintoast.toast_xml("Chatmon test", "Removed at once.", ["OK"], "reminder", tag, silent=True), tag, suppress_popup=True)
    assert toaster.listening == [tag]
    if notifications_on():
        assert wait_for(qapp, lambda: tag in toaster.in_action_center())
        assert toaster.hide(tag)
        assert wait_for(qapp, lambda: ("dismissed", tag, wintoast.HIDDEN_BY_CHATMON, True) in heard)
        # Windows may say first that it timed out (a CI runner's Windows expires a toast nobody can see): every report
        # comes back on the Qt thread, and Chatmon's own hiding is the last.
        assert heard[-1] == ("dismissed", tag, wintoast.HIDDEN_BY_CHATMON, True)
        assert all(h[:2] == ("dismissed", tag) and h[2] in (wintoast.TIMED_OUT, wintoast.HIDDEN_BY_CHATMON) and h[3] for h in heard), heard
    else:
        assert wait_for(qapp, lambda: heard)
        WPN_E_NOTIFICATION_TYPE_DISABLED = -0x7FC1FEEC  # 0x803E0114
        assert heard == [("failed", tag, WPN_E_NOTIFICATION_TYPE_DISABLED, True)]
    assert toaster.listening == []  # its handlers removed, the toast let go of


class _FakeActivation:
    """Windows' ToastActivatedEventArgs as far as Chatmon reads it: a COM object whose Arguments are `text`.
    Only Windows can click a toast; this stands in for what it hands the Activated handler."""

    def __init__(self, text: str):
        from chatmon import winrt

        FN = ctypes.WINFUNCTYPE
        self._text = text
        self._funcs = [
            FN(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(winrt.GUID), ctypes.POINTER(ctypes.c_void_p))(self._query),
            FN(ctypes.c_ulong, ctypes.c_void_p)(lambda this: 1),
            FN(ctypes.c_ulong, ctypes.c_void_p)(lambda this: 1),
            *[FN(ctypes.c_long, ctypes.c_void_p)(lambda this: -1) for _ in range(3)],  # IInspectable's, unused
            FN(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(self._arguments),
        ]
        self._table = (ctypes.c_void_p * len(self._funcs))(*[ctypes.cast(f, ctypes.c_void_p) for f in self._funcs])
        self._object = ctypes.c_void_p(ctypes.addressof(self._table))
        self.pointer = ctypes.addressof(self._object)

    def _query(self, this, iid, out):
        out[0] = this
        return 0

    def _arguments(self, this, out):
        from chatmon import winrt

        return winrt.combase().WindowsCreateString(self._text, len(self._text), out)


@windows
def test_a_pressed_button_is_reported_and_its_action_runs_on_the_qt_thread(qapp):
    toaster = wintoast.Toaster("RandyNorthrup.Chatmon.Test")
    main = threading.get_ident()
    pressed, ran = [], []
    toaster.activated.connect(lambda tag, button: pressed.append((tag, button, threading.get_ident() == main)))
    tag = "00ff"
    toaster._shown[tag] = wintoast._Shown(toast=0, actions=[None, lambda: ran.append(threading.get_ident() == main)])
    clicks = [_FakeActivation("chatmon:00ff:1"), _FakeActivation("chatmon:00ff:-1")]
    worker = threading.Thread(target=lambda: toaster._on_activated(tag, clicks[0].pointer))  # as Windows would: another thread
    worker.start()
    worker.join()
    assert wait_for(qapp, lambda: pressed)
    assert pressed == [(tag, 1, True)] and ran == [True] and toaster.listening == []
    toaster._on_activated("beef", clicks[1].pointer)  # another toast's arguments: the toast itself, not a button
    assert wait_for(qapp, lambda: len(pressed) == 2) and pressed[1][:2] == ("beef", wintoast.BODY)
    toaster.close()


@windows
def test_a_pip_install_tells_windows_its_name_and_icon():
    import winreg

    app_id = f"RandyNorthrup.Chatmon.Test{uuid.uuid4().hex[:8]}"
    key = rf"Software\Classes\AppUserModelId\{app_id}"
    wintoast.register_app_id(app_id, "Chatmon", r"C:\icons\chatmon.png")
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            assert winreg.QueryValueEx(k, "DisplayName")[0] == "Chatmon"
            assert winreg.QueryValueEx(k, "IconUri")[0] == r"C:\icons\chatmon.png"
    finally:
        assert wintoast.unregister_app_id(app_id)
    with pytest.raises(FileNotFoundError):
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, key)
    assert wintoast.unregister_app_id(app_id) is False
    with pytest.raises(ValueError):
        wintoast.register_app_id("..\\Run", "x")


@windows
def test_the_app_id_is_the_one_the_process_gave_itself():
    shell32 = ctypes.WinDLL("shell32")
    app_id = f"RandyNorthrup.Chatmon.Test{uuid.uuid4().hex[:8]}"
    assert shell32.SetCurrentProcessExplicitAppUserModelID(ctypes.c_wchar_p(app_id)) == 0
    assert wintoast.process_app_id() == app_id
    assert wintoast.Toaster().app_id == app_id
