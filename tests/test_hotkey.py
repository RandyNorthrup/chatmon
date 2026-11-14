"""The global shortcut (hotkey.py): reading a shortcut anywhere, and claiming one for real on each platform with
combinations nobody uses, always given back after. No keystrokes reach your session: Windows' WM_HOTKEY is posted
to the shortcut's window, macOS's hot-key event is sent to the app, and X11's keys are pressed on a private Xvfb."""

import ctypes
import ctypes.util
import os
import shutil
import subprocess
import sys
import time

import pytest

from chatmon import hotkey

# -- reading a shortcut


@pytest.mark.parametrize("written, canonical", [
    ("Ctrl+Alt+Space", "Ctrl+Alt+Space"),
    ("alt+ctrl+space", "Ctrl+Alt+Space"),
    (" Control + Option + k ", "Ctrl+Alt+K"),
    ("meta+shift+f5", "Shift+Meta+F5"),
    ("Win+Escape", "Meta+Esc"),
    ("Super+PageDown", "Meta+PgDown"),
    ("Ctrl+Alt+/", "Ctrl+Alt+/"),
    ("Ctrl+Shift+Return", "Ctrl+Shift+Return"),
    ("Ctrl+Alt+Enter", "Ctrl+Alt+Return"),
    ("F13", "F13"),
    ("Shift+F24", "Shift+F24"),
])
def test_a_shortcut_is_read_as_qt_writes_it(written, canonical):
    assert hotkey.parse(written, "linux").text() == canonical


def test_command_is_ctrl_on_a_mac_as_in_qt():
    assert hotkey.parse("Cmd+Shift+Space", "darwin") == hotkey.Combo(frozenset({"ctrl", "shift"}), "Space")
    assert hotkey.parse("Cmd+Shift+Space", "linux") == hotkey.Combo(frozenset({"meta", "shift"}), "Space")


@pytest.mark.parametrize("written, says", [
    ("", "needs a key"),
    ("   ", "needs a key"),
    ("Ctrl+", "isn't a shortcut"),
    ("Ctrl+Alt", "needs a key as well"),
    ("Ctrl+A+B", "one key, not A and B"),
    ("Ctrl+Hyper", 'doesn\'t know the key "Hyper"'),
    ("A", "would take that key"),
    ("Shift+A", "would take that key"),
    ("F12", "would take that key"),  # F1-F12 are every app's own
    ("Shift+Space", "would take that key"),
])
def test_what_isnt_a_shortcut_says_why(written, says):
    with pytest.raises(ValueError, match=says):
        hotkey.parse(written, "linux")


def test_every_key_has_a_code_of_its_own():
    """A slip in the tables would make two keys one: each platform's codes are distinct."""
    windows = [k.windows for k in hotkey.KEYS.values()]
    mac = [k.mac for k in hotkey.KEYS.values() if k.mac is not None]
    x11 = [k.x11 for k in hotkey.KEYS.values()]
    assert len(set(windows)) == len(windows) and len(set(mac)) == len(mac) and len(set(x11)) == len(x11)
    assert hotkey.KEYS["A"].mac == 0x00 and hotkey.KEYS["Space"].mac == 0x31 and hotkey.KEYS["F19"].mac == 0x50  # Carbon's Events.h
    assert len(hotkey.KEYS) == 17 + 11 + 36 + 24


def test_each_platform_has_its_way():
    assert hotkey.backend_kind("win32", {}) == "windows"
    assert hotkey.backend_kind("darwin", {}) == "carbon"
    # A Wayland session asks the portal, even with XWayland there: an X grab hears keys only over X apps.
    assert hotkey.backend_kind("linux", {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}) == "portal"
    assert hotkey.backend_kind("linux", {"DISPLAY": ":0"}) == "x11"
    assert hotkey.backend_kind("linux", {}) is None


def test_a_bad_shortcut_is_refused_before_anything_is_claimed(qapp):
    hk = hotkey.Hotkey(kind="nowhere")
    assert "would take that key" in hk.register("Shift+A") and hk.combo is None and hk._backend is None
    assert hk.register("Ctrl+Alt+Space") == "There's no display to set a shortcut on."
    hk.close()


def wait_for(qapp, done, seconds: float = 5.0) -> bool:
    deadline = time.monotonic() + seconds
    while not done() and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    return bool(done())


# -- Windows

windows = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x4000
VK_F22, VK_F23, VK_F24 = 0x85, 0x86, 0x87
WM_HOTKEY = 0x0312
SOMEONE_ELSE = 0xBEEF  # an id for raw registrations: another app, as far as Windows can tell


def user32():
    from ctypes import wintypes

    u = ctypes.WinDLL("user32", use_last_error=True)
    u.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    u.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    u.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    u.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
    u.FindWindowExW.restype = wintypes.HWND
    return u


def held_by_someone(vk: int) -> bool:
    """Is Ctrl+Alt+Shift+vk taken? Windows' own answer: try to register it, and give it straight back."""
    u = user32()
    if u.RegisterHotKey(None, SOMEONE_ELSE, MOD_CONTROL | MOD_ALT | MOD_SHIFT | MOD_NOREPEAT, vk):
        u.UnregisterHotKey(None, SOMEONE_ELSE)
        return False
    assert ctypes.get_last_error() == 1409  # ERROR_HOTKEY_ALREADY_REGISTERED, not some other failure
    return True


@windows
def test_windows_registers_it_on_a_message_only_window_and_hears_it(qapp):
    from ctypes import wintypes

    u = user32()
    hk = hotkey.Hotkey()
    pressed = []
    hk.pressed.connect(lambda: pressed.append(True))
    try:
        assert not held_by_someone(VK_F24)
        assert hk.register("Ctrl+Alt+Shift+F24") is None and hk.combo.text() == "Ctrl+Alt+Shift+F24"
        assert held_by_someone(VK_F24)  # really claimed
        window = hk._backend.hwnd
        assert u.FindWindowExW(wintypes.HWND(-3), None, "STATIC", "Chatmon shortcut") == window  # among message-only windows
        u.PostMessageW(window, WM_HOTKEY, hk._backend.id + 1, 0)  # not its registration: ignored
        u.PostMessageW(window, WM_HOTKEY, hk._backend.id, (VK_F24 << 16) | MOD_CONTROL | MOD_ALT | MOD_SHIFT)
        assert wait_for(qapp, lambda: pressed)
        qapp.processEvents()
        assert pressed == [True]  # once
        hk.unregister()
        assert hk.combo is None and not held_by_someone(VK_F24)  # given back
    finally:
        hk.close()
    assert not u.FindWindowExW(wintypes.HWND(-3), None, "STATIC", "Chatmon shortcut")


@windows
def test_windows_reports_a_conflict_and_keeps_the_shortcut_it_had(qapp):
    u = user32()
    assert u.RegisterHotKey(None, SOMEONE_ELSE, MOD_CONTROL | MOD_ALT | MOD_SHIFT | MOD_NOREPEAT, VK_F23)  # another app's
    hk = hotkey.Hotkey()
    try:
        assert hk.register("Ctrl+Alt+Shift+F23") == "Ctrl+Alt+Shift+F23 is already used by another app. Pick another shortcut."
        assert hk.combo is None
        assert hk.register("Ctrl+Alt+Shift+F24") is None
        assert hk.register("Shift+Alt+Ctrl+F23") == hotkey.CONFLICT.format(combo="Ctrl+Alt+Shift+F23")
        assert hk.combo.text() == "Ctrl+Alt+Shift+F24" and held_by_someone(VK_F24)  # still set
    finally:
        hk.close()
        u.UnregisterHotKey(None, SOMEONE_ELSE)
    assert not held_by_someone(VK_F24) and not held_by_someone(VK_F23)


@windows
def test_the_apps_one_shortcut(qapp):
    u = user32()
    pressed = []
    try:
        assert hotkey.register("Ctrl+Alt+Shift+F22", lambda: pressed.append("ask")) is None
        assert hotkey.current() == "Ctrl+Alt+Shift+F22" and held_by_someone(VK_F22)
        backend = hotkey._hotkey._backend
        u.PostMessageW(backend.hwnd, WM_HOTKEY, backend.id, 0)
        assert wait_for(qapp, lambda: pressed) and pressed == ["ask"]
        assert "would take that key" in hotkey.register("Q", lambda: None)
        assert hotkey.current() == "Ctrl+Alt+Shift+F22"
        hotkey.unregister()
        assert hotkey.current() is None and not held_by_someone(VK_F22)
    finally:
        if hotkey._hotkey is not None:
            hotkey._hotkey.close()
            hotkey._hotkey = None


# -- macOS

mac = pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")


def carbon():
    lib = ctypes.cdll.LoadLibrary(hotkey._Carbon.CARBON)
    lib.GetApplicationEventTarget.restype = ctypes.c_void_p
    lib.CreateEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_double, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)]
    lib.CreateEvent.restype = ctypes.c_int32
    lib.SetEventParameter.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_ulong, ctypes.c_void_p]
    lib.SetEventParameter.restype = ctypes.c_int32
    lib.SendEventToEventTarget.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    lib.SendEventToEventTarget.restype = ctypes.c_int32
    lib.ReleaseEvent.argtypes = [ctypes.c_void_p]
    lib.RegisterEventHotKey.argtypes = [ctypes.c_uint32, ctypes.c_uint32, hotkey._EventHotKeyID, ctypes.c_void_p, ctypes.c_uint32,
                                        ctypes.POINTER(ctypes.c_void_p)]
    lib.RegisterEventHotKey.restype = ctypes.c_int32
    lib.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
    return lib


def send_hot_key(signature: int, number: int) -> int:
    """A hot-key-pressed event, as the window server sends one, to the app's own event target."""
    lib, event = carbon(), ctypes.c_void_p()
    assert lib.CreateEvent(None, hotkey._Carbon.KEYBOARD, hotkey._Carbon.HOT_KEY_PRESSED, 0.0, 0, ctypes.byref(event)) == 0
    try:
        hot_key = hotkey._EventHotKeyID(signature, number)
        assert lib.SetEventParameter(event, hotkey._Carbon.DIRECT_OBJECT, hotkey._Carbon.HOT_KEY_ID, ctypes.sizeof(hot_key), ctypes.byref(hot_key)) == 0
        return lib.SendEventToEventTarget(event, lib.GetApplicationEventTarget())
    finally:
        lib.ReleaseEvent(event)


@mac
def test_macos_registers_it_and_hears_it(qapp):
    hk = hotkey.Hotkey()
    pressed = []
    hk.pressed.connect(lambda: pressed.append(True))
    try:
        assert hk.register("Ctrl+Alt+Shift+F19") is None  # Command+Option+Shift+F19
        backend = hk._backend
        assert send_hot_key(backend.SIGNATURE, backend.id + 1) == backend.NOT_HANDLED  # not its own
        assert send_hot_key(backend.SIGNATURE, backend.id) == 0
        assert wait_for(qapp, lambda: pressed) and pressed == [True]
        hk.unregister()
        assert hk.combo is None and backend.id is None
    finally:
        hk.close()


@mac
def test_macos_reports_a_conflict_and_keeps_the_shortcut_it_had(qapp):
    lib, theirs = carbon(), ctypes.c_void_p()
    flags = hotkey._Carbon.FLAGS
    held = lib.RegisterEventHotKey(hotkey.KEYS["F18"].mac, flags["ctrl"] | flags["alt"] | flags["shift"], hotkey._EventHotKeyID(hotkey.fourcc("TEST"), 1),
                                   lib.GetApplicationEventTarget(), hotkey._Carbon.EXCLUSIVE, ctypes.byref(theirs))
    assert held == 0
    hk = hotkey.Hotkey()
    try:
        assert hk.register("Ctrl+Alt+Shift+F17") is None
        assert hk.register("Ctrl+Alt+Shift+F18") == hotkey.CONFLICT.format(combo="Ctrl+Alt+Shift+F18")
        assert hk.combo.text() == "Ctrl+Alt+Shift+F17"
    finally:
        hk.close()
        lib.UnregisterEventHotKey(theirs)


# -- X11, on a private Xvfb


@pytest.fixture
def xvfb(monkeypatch):
    if not sys.platform.startswith("linux") or not shutil.which("Xvfb"):
        pytest.skip("Linux with Xvfb")
    if not ctypes.util.find_library("Xtst"):
        pytest.skip("libXtst, to press keys")
    # Listening on the abstract socket alone: /tmp/.X11-unix may not be writable (WSLg mounts it read-only).
    server = subprocess.Popen(["Xvfb", "-displayfd", "1", "-nolisten", "tcp", "-nolisten", "unix", "-screen", "0", "640x480x24"], stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL)
    try:
        number = server.stdout.readline().strip().decode()  # written once it's ready
        assert number, "Xvfb didn't start"
        monkeypatch.setenv("DISPLAY", f":{number}")
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        yield f":{number}"
    finally:
        server.terminate()
        server.wait(10)
        server.stdout.close()


class Keyboard:
    """Another X client, pressing keys with XTest and grabbing as another app would."""

    def __init__(self, display: str):
        self.x = ctypes.cdll.LoadLibrary(ctypes.util.find_library("X11"))
        self.xtst = ctypes.cdll.LoadLibrary(ctypes.util.find_library("Xtst"))
        self.x.XOpenDisplay.restype = ctypes.c_void_p
        self.x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x.XStringToKeysym.restype = ctypes.c_ulong
        self.x.XStringToKeysym.argtypes = [ctypes.c_char_p]
        self.x.XKeysymToKeycode.restype = ctypes.c_ubyte
        self.x.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self.x.XDefaultRootWindow.restype = ctypes.c_ulong
        self.x.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        self.x.XGrabKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        self.x.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.x.XFlush.argtypes = [ctypes.c_void_p]
        self.x.XCloseDisplay.argtypes = [ctypes.c_void_p]
        self.xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        self.display = self.x.XOpenDisplay(display.encode())
        assert self.display

    def code(self, keysym: str) -> int:
        return self.x.XKeysymToKeycode(self.display, self.x.XStringToKeysym(keysym.encode()))

    def press(self, *keysyms: str) -> None:
        for name in keysyms:
            self.xtst.XTestFakeKeyEvent(self.display, self.code(name), 1, 0)
        for name in reversed(keysyms):
            self.xtst.XTestFakeKeyEvent(self.display, self.code(name), 0, 0)
        self.x.XSync(self.display, 0)

    def grab(self, keysym: str, modifiers: int) -> None:
        self.x.XGrabKey(self.display, self.code(keysym), modifiers, self.x.XDefaultRootWindow(self.display), 0, 1, 1)
        self.x.XSync(self.display, 0)

    def close(self) -> None:
        self.x.XCloseDisplay(self.display)


def test_x11_grabs_it_whatever_numlock_says_and_reports_a_conflict(qapp, xvfb):
    keyboard = Keyboard(xvfb)
    hk = hotkey.Hotkey(kind="x11")
    pressed = []
    hk.pressed.connect(lambda: pressed.append(True))
    try:
        assert hk.register("Ctrl+Alt+Space") is None
        keyboard.press("Control_L", "Alt_L", "space")
        assert wait_for(qapp, lambda: len(pressed) == 1)
        keyboard.press("Control_L", "space")  # not the shortcut
        keyboard.press("Num_Lock")  # NumLock on: X counts it as a modifier
        keyboard.press("Control_L", "Alt_L", "space")
        assert wait_for(qapp, lambda: len(pressed) == 2)
        keyboard.press("Num_Lock")
        qapp.processEvents()
        assert len(pressed) == 2

        keyboard.grab("F5", hotkey._X11.FLAGS["ctrl"] | hotkey._X11.FLAGS["shift"])  # another app holds Ctrl+Shift+F5
        assert hk.register("Ctrl+Shift+F5") == hotkey.CONFLICT.format(combo="Ctrl+Shift+F5")
        assert hk.combo.text() == "Ctrl+Alt+Space"
        keyboard.press("Control_L", "Alt_L", "space")  # the one it had still works
        assert wait_for(qapp, lambda: len(pressed) == 3)
        keyboard.close()  # the other app quits, and its grab goes with it
        keyboard = Keyboard(xvfb)
        assert hk.register("Ctrl+Shift+F5") is None
        keyboard.press("Control_L", "Shift_L", "F5")
        assert wait_for(qapp, lambda: len(pressed) == 4)
        keyboard.press("Control_L", "Alt_L", "space")  # the old one given back
        time.sleep(0.2)
        qapp.processEvents()
        assert len(pressed) == 4
    finally:
        hk.close()
        keyboard.close()


def test_x11_without_a_display_says_so(qapp, monkeypatch):
    if not sys.platform.startswith("linux") or not ctypes.util.find_library("X11"):
        pytest.skip("Linux with libX11")
    monkeypatch.setenv("DISPLAY", ":999")  # no server there
    hk = hotkey.Hotkey(kind="x11")
    assert hk.register("Ctrl+Alt+Space") == "There's no X display to set a shortcut on."
    hk.close()
    assert os.environ["DISPLAY"] == ":999"
