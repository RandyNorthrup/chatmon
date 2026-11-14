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
    if notifications_on():
        # Windows may not say whether this app ID's notifications are on (none, for one without a Start menu
        # shortcut, on CI's runners): that's no reason not to try.
        assert tag is not None and toaster.why_not is None, f"declined: setting {toaster.setting()}, {toaster.why_not}"
        assert wait_for(qapp, lambda: tag in toaster.in_action_center()), "Windows never had the toast"
        assert toaster.hide(tag)
    else:
        assert tag is None and toaster.why_not == wintoast.WHY_NOT[wintoast.OFF_FOR_USER]
        assert toaster.setting() == wintoast.OFF_FOR_USER and toaster.listening == []


@windows
def test_only_a_real_no_keeps_a_toast_from_being_tried(qapp, monkeypatch):
    """Windows' answer decides, not its silence: on CI's runners it gave none for an app ID without a Start menu
    shortcut, yet showed the toast. Only notifications turned off (for the app, the user or by policy) mean the
    balloon instead. Windows' own handing over is stood in for here: the decision is what's tested."""
    toaster = wintoast.Toaster("RandyNorthrup.Chatmon.Test")
    handed = []

    def post(xml, tag, suppress_popup=False):
        handed.append(tag)
        toaster._shown[tag] = wintoast._Shown(toast=0)
        return True

    monkeypatch.setattr(toaster, "_post", post)
    for answer in (wintoast.ENABLED, None, wintoast.OFF_BY_MANIFEST):
        monkeypatch.setattr(toaster, "setting", lambda answer=answer: answer)
        assert toaster.show("Chatmon test") is not None and toaster.why_not is None, answer
    for answer in (wintoast.OFF_FOR_APP, wintoast.OFF_FOR_USER, wintoast.OFF_BY_POLICY):
        monkeypatch.setattr(toaster, "setting", lambda answer=answer: answer)
        assert toaster.show("Chatmon test") is None and toaster.why_not == wintoast.WHY_NOT[answer]
    assert len(handed) == 3
    toaster._shown.clear()
    toaster.close()


@windows
def test_what_windows_says_of_a_toast_comes_back_on_the_qt_thread(toaster, qapp):
    """Posted straight to Action Center. Where notifications are off Windows refuses it (Failed); where they're on
    it's there until Chatmon hides it (Dismissed). Either way Windows calls back on a thread of its own. Sent
    straight to Action Center, a toast may also count as timed out (CI's runners say so); hidden is the last word."""
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
        hidden = ("dismissed", tag, wintoast.HIDDEN_BY_CHATMON, True)
        assert wait_for(qapp, lambda: hidden in heard), heard
        wait_for(qapp, lambda: False, 0.5)  # whatever Windows says after: nothing more is reported
        assert heard[-1] == hidden and all(h == ("dismissed", tag, wintoast.TIMED_OUT, True) for h in heard[:-1]), heard
    else:
        assert wait_for(qapp, lambda: heard)
        WPN_E_NOTIFICATION_TYPE_DISABLED = -0x7FC1FEEC  # 0x803E0114
        assert heard == [("failed", tag, WPN_E_NOTIFICATION_TYPE_DISABLED, True)]
    assert toaster.listening == []  # its handlers removed, the toast let go of


class _FakeArgs:
    """An event's arguments as far as Chatmon reads them: a COM object whose one property (vtable slot 6) is
    `text` (ToastActivatedEventArgs' Arguments) or `number` (ToastDismissedEventArgs' Reason). Only Windows can
    click a toast, or say twice what became of one; this stands in for what it hands the handlers."""

    def __init__(self, text: str = "", number: int = 0):
        from chatmon import winrt

        FN = ctypes.WINFUNCTYPE
        self._text, self._number = text, number
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

        if not self._text:
            ctypes.cast(out, ctypes.POINTER(ctypes.c_int))[0] = self._number
            return 0
        return winrt.combase().WindowsCreateString(self._text, len(self._text), out)


@windows
def test_a_pressed_button_is_reported_and_its_action_runs_on_the_qt_thread(qapp):
    toaster = wintoast.Toaster("RandyNorthrup.Chatmon.Test")
    main = threading.get_ident()
    pressed, ran = [], []
    toaster.activated.connect(lambda tag, button: pressed.append((tag, button, threading.get_ident() == main)))
    tag = "00ff"
    toaster._shown[tag] = wintoast._Shown(toast=0, actions=[None, lambda: ran.append(threading.get_ident() == main)])
    clicks = [_FakeArgs("chatmon:00ff:1"), _FakeArgs("chatmon:00ff:-1")]
    worker = threading.Thread(target=lambda: toaster._on_activated(tag, clicks[0].pointer))  # as Windows would: another thread
    worker.start()
    worker.join()
    assert wait_for(qapp, lambda: pressed)
    assert pressed == [(tag, 1, True)] and ran == [True] and toaster.listening == []
    toaster._shown["beef"] = wintoast._Shown(toast=0)
    toaster._on_activated("beef", clicks[1].pointer)  # another toast's arguments: the toast itself, not a button
    assert wait_for(qapp, lambda: len(pressed) == 2) and pressed[1][:2] == ("beef", wintoast.BODY)
    toaster._on_activated("beef", clicks[0].pointer)  # settled already: not news
    toaster._on_activated("dead", clicks[0].pointer)  # never listened to
    wait_for(qapp, lambda: False, 0.3)
    assert len(pressed) == 2
    toaster.close()


@windows
def test_what_windows_says_after_a_toast_is_settled_is_not_news(qapp):
    """Windows can raise Dismissed more than once for one toast (CI's runners: hidden, then timed out). Timed out,
    it's still in Action Center and listened to; hidden, it's settled, and nothing more is reported for it."""
    toaster = wintoast.Toaster("RandyNorthrup.Chatmon.Test")
    heard = []
    main = threading.get_ident()
    toaster.dismissed.connect(lambda tag, why: heard.append((tag, why, threading.get_ident() == main)))
    toaster._shown["0a"] = wintoast._Shown(toast=0)
    reasons = [_FakeArgs(number=n) for n in (wintoast.TIMED_OUT, wintoast.HIDDEN_BY_CHATMON, wintoast.TIMED_OUT, wintoast.DISMISSED_BY_YOU)]
    for args in reasons:  # each from a thread of Windows' own, in turn
        worker = threading.Thread(target=lambda a=args: toaster._on_dismissed("0a", a.pointer))
        worker.start()
        worker.join()
    assert wait_for(qapp, lambda: len(heard) >= 2)
    wait_for(qapp, lambda: False, 0.3)
    assert heard == [("0a", wintoast.TIMED_OUT, True), ("0a", wintoast.HIDDEN_BY_CHATMON, True)] and toaster.listening == []
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
