"""Screen readers: is one listening, and how to have it say what a bubble says.

The chatmon and its bubbles are drawn, not widgets a screen reader can walk (and PyQt6 has none of Qt's
accessibility API to make them so, or to announce: no QAccessible, no QAccessibleAnnouncementEvent, as of PyQt6
6.12). So each platform's own way to ask the screen reader to speak is used where there is one; where there
isn't, the app sends a system notification, which screen readers read (Narrator, NVDA and JAWS read Windows'
notifications; Orca reads GNOME's). `announce()` picks.

- Linux, Orca 49 or later: its remote controller on the session bus, PresentMessage(s), which speaks (and
  brailles) whatever is in front. Named org.gnome.Orca.Service in 49 and 50, org.gnome.Orca1.Service from 51.
  https://gitlab.gnome.org/GNOME/orca/-/blob/main/docs/remote-controller.md
  Another screen reader (an older Orca, Odilia, Fenrir) is found by AT-SPI's ScreenReaderEnabled where at-spi2-core
  still keeps it (before 2.62), GNOME's screen-reader-enabled setting, or its own process, and the notification
  says it (linuxsession.ScreenReaders, which hears each without waiting).
- macOS, VoiceOver: NSAccessibilityAnnouncementRequestedNotification, posted on the app. VoiceOver speaks it for
  the app in front (with the chat open, Chatmon is); from the background it may stay silent, and it drops one
  that comes while it moves to Chatmon. So while Chatmon isn't in front, announcements wait (the last few) and are
  said a moment after you come to it; or, if you chose it (`set_speech_fallback`), macOS's own voice says them at
  once.
  https://developer.apple.com/documentation/appkit/nsaccessibility-swift.struct/notification/announcementrequested
- Windows: UI Automation's notification event (winuia.py) while Chatmon is in front; NVDA ignores those from apps
  in the background, so then the notification. https://github.com/nvaccess/nvda/blob/master/source/NVDAObjects/UIA/__init__.py
"""

from __future__ import annotations

import ctypes
import logging
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.QtCore import QCoreApplication, QObject, QProcess, Qt, QTimer

from .i18n import _, either

logger = logging.getLogger(__name__)

SPI_GETSCREENREADER = 0x0046  # set by NVDA, JAWS and others; Narrator doesn't set it
PRIORITY_MEDIUM, PRIORITY_HIGH = 50, 90  # NSAccessibilityPriorityLevel


@dataclass
class Reader:
    name: str  # "Orca", "VoiceOver", "Narrator", "a screen reader"
    speak: Callable[[str, bool], None] | None = None  # (text, important); None: a notification says it instead


def reader() -> Reader | None:
    """The screen reader running now, if there is one. On Linux, as last heard (nothing is asked and waited for):
    a Desk, made at the app's start, starts listening; the first reading otherwise starts it, and says None."""
    try:
        if sys.platform == "win32":
            return _windows()
        if sys.platform == "darwin":
            return _mac()
        return _linux()
    except (OSError, AttributeError, ImportError, ValueError) as exc:
        logger.debug("couldn't tell whether a screen reader is running: %s", exc)
        return None


def announce(found: Reader | None, words: str, important: bool = False, notify: Callable[[], None] | None = None) -> str:
    """Have the running screen reader say `words`, the best way there is now, and say how it went:
    "uia" (Windows, Chatmon in front: a UI Automation notification, which Narrator, NVDA and JAWS read),
    "spoken" (Orca's or VoiceOver's own way; VoiceOver's may wait for Chatmon to come in front),
    "notification" (`notify` was called: it sends the system notification a screen reader reads, built by the
    caller, which knows the title and buttons), or "" (no screen reader, or no way to reach it)."""
    if found is None:
        return ""
    if sys.platform == "win32" and _uia_say(words, important):
        return "uia"
    if found.speak is not None:
        found.speak(words, important)
        return "spoken"
    if notify is not None:
        notify()
        return "notification"
    return ""


def _uia_say(words: str, important: bool) -> bool:
    if sys.platform != "win32":
        return False
    try:
        from . import winuia
    except (ImportError, OSError) as exc:  # what failed, never the words
        logger.debug("couldn't load UI Automation: %s", exc)
        return False
    return winuia.in_front() and winuia.say(words, important)


def spoken(title: str, text: str = "", buttons: list[str] | None = None) -> str:
    """A bubble as it's read out: plain words, and what to type to press its buttons."""
    parts = [plain(title), plain(text)]
    if buttons:
        # Translators: a button's label, quoted, in the sentence that says what to type to press it.
        quoted = [_("“{label}”").format(label=b) for b in buttons]
        parts.append(_("To answer, type {buttons} in the chat.").format(buttons=either(quoted)))
    return " ".join(p if p.endswith((".", "!", "?", "…", ":")) else p + "." for p in parts if p)


def typed_button(labels: list[str], typed: str) -> int | None:
    """Which button was typed: its label, or the start of it if that's one label's alone (at least 3 letters)."""
    wanted = " ".join(typed.lower().split()).strip(" .!")
    exact = [i for i, label in enumerate(labels) if label.lower() == wanted]
    starting = [i for i, label in enumerate(labels) if len(wanted) >= 3 and label.lower().startswith(wanted)]
    chosen = exact or (starting if len(starting) == 1 else [])
    return chosen[0] if chosen else None


def plain(text: str) -> str:
    """Markdown as words: links by their text, no emphasis marks or code ticks, one line."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text or "")
    text = re.sub(r"(\*\*|__|\*|_|`)(?=\S)(.+?)(?<=\S)\1", r"\2", text)
    text = re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "", text, flags=re.M)
    return " ".join(text.replace("`", "").split())


# -- Linux


def _linux() -> Reader | None:
    from PyQt6.QtDBus import QDBusConnection

    from . import linuxsession

    readers = linuxsession.screen_readers()
    readers.rescan()  # its process, looked for again: a read of /proc
    found = readers.found()
    if found is None:
        return None
    name, orca = found
    if orca is None:
        return Reader(name)  # no way of its own to speak through: the notification says it
    bus: QDBusConnection = QDBusConnection.sessionBus()  # typed: PyQt6 6.12.1's stubs give static constructors an unbound Self

    def speak(text: str, important: bool, service: str = orca[0], path: str = orca[1]) -> None:
        _orca(bus, service, path, text)

    return Reader(name, speak)


def _orca(bus, service: str, path: str, text: str) -> None:
    from PyQt6.QtDBus import QDBusMessage

    message: QDBusMessage = QDBusMessage.createMethodCall(service, path, service, "PresentMessage")
    message.setArguments([text])
    bus.send(message)  # no waiting: it speaks when it can


# -- Windows


def _windows() -> Reader | None:
    if sys.platform != "win32":  # asked on Windows alone
        return None
    on = ctypes.c_int(0)
    if ctypes.windll.user32.SystemParametersInfoW(SPI_GETSCREENREADER, 0, ctypes.byref(on), 0) and on.value:
        found = Reader("a screen reader")
    elif _running("narrator.exe"):
        found = Reader("Narrator")
    else:
        return None
    from . import winuia

    winuia.prepare()  # UI Automation takes a moment to take in its window: ready before anything is to be said
    return found


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_uint32), ("cntUsage", ctypes.c_uint32), ("th32ProcessID", ctypes.c_uint32),
        ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", ctypes.c_uint32), ("cntThreads", ctypes.c_uint32),
        ("th32ParentProcessID", ctypes.c_uint32), ("pcPriClassBase", ctypes.c_long), ("dwFlags", ctypes.c_uint32),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def _running(exe: str) -> bool:
    """A program of that name is running (for Narrator, which tells Windows nothing else)."""
    if sys.platform != "win32":
        return False
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    snapshot = kernel32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if not snapshot or snapshot == ctypes.c_void_p(-1).value:
        return False
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        more = kernel32.Process32FirstW(ctypes.c_void_p(snapshot), ctypes.byref(entry))
        while more:
            if entry.szExeFile.lower() == exe:
                return True
            more = kernel32.Process32NextW(ctypes.c_void_p(snapshot), ctypes.byref(entry))
        return False
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(snapshot))


# -- macOS


def _mac() -> Reader | None:
    from . import macnative

    rt = macnative._rt()
    if rt is None:
        return None
    workspace = rt.obj(rt.cls("NSWorkspace"), rt.sel("sharedWorkspace"))
    on = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(rt.send)
    if not workspace or not rt.responds(workspace, rt.sel("respondsToSelector:"), rt.sel("isVoiceOverEnabled")):
        return None
    return Reader("VoiceOver", voiceover().say) if on(workspace, rt.sel("isVoiceOverEnabled")) else None


_speech_fallback = False


def set_speech_fallback(on: bool) -> None:
    """Whether macOS's own voice says what VoiceOver would otherwise hold while Chatmon isn't in front (a
    setting, off unless you turn it on: with it, you hear it at once, in a voice that isn't VoiceOver's)."""
    global _speech_fallback
    _speech_fallback = bool(on)


class VoiceOver(QObject):
    """Announcements for VoiceOver: posted at once while Chatmon is the active app; otherwise held (the last
    `HELD`) and posted together SETTLE_MS after it becomes active, or, with the speech fallback on, said by `say`
    at once. VoiceOver drops an announcement that comes while it moves to an app that has just become active (or
    just started): on macOS 26.7, every one posted at that moment, or a second after, went unsaid, and each posted
    2.5 s after was said. So what's held, and what's said in that first moment, waits until then.
    `post`, `active` and `speak` are AppKit's announcement, Qt's application state and macOS's `say` command."""

    HELD = 5
    # From Chatmon becoming active (or starting active) to VoiceOver taking its announcements. Measured with VoiceOver
    # itself (docs/delivery/reports/release/screen-readers): at 1 s it still dropped them, at 2.5 s and 4 s it said
    # every one. AppKit has no word for when VoiceOver has finished announcing the newly active window (no
    # counterpart of iOS's UIAccessibilityAnnouncementDidFinishNotification), so it's a time.
    SETTLE_MS = 2500

    def __init__(self, post: Callable[[str, bool], None] | None = None, active: Callable[[], bool] | None = None,
                 speak: Callable[[str], None] | None = None):
        super().__init__()
        from PyQt6.QtGui import QGuiApplication

        self._post = post or _voiceover
        self._active = active or (lambda: QGuiApplication.applicationState() == Qt.ApplicationState.ApplicationActive)
        self._speak = speak or self._say_aloud
        self.held: list[tuple[str, bool]] = []
        self._voice: QProcess | None = None
        self._to_say: list[str] = []
        self._settled_at: float | None = time.monotonic() + self.SETTLE_MS / 1000 if self._active() else None
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.timeout.connect(self._post_held)
        app: QCoreApplication | None = QGuiApplication.instance()
        if isinstance(app, QGuiApplication):  # only a GUI application has a state (and Chatmon's always is one)
            app.applicationStateChanged.connect(self.state_changed)

    def say(self, text: str, important: bool = False) -> None:
        wait = self._settling_ms()
        if self._active() and not wait:
            self._post(text, important)
        elif self._active():  # just became active: VoiceOver would drop it yet
            self.held = [*self.held, (text, important)][-self.HELD:]
            self._settle.start(wait)
        elif _speech_fallback:
            self._speak(text)
        else:
            self.held = [*self.held, (text, important)][-self.HELD:]

    def state_changed(self, state) -> None:
        if state == Qt.ApplicationState.ApplicationActive:
            self._settled_at = time.monotonic() + self.SETTLE_MS / 1000
            if self.held:
                self._settle.start(self.SETTLE_MS)
        else:
            self._settled_at = None
            self._settle.stop()

    def _settling_ms(self) -> int:
        """How long until VoiceOver takes Chatmon's announcements (0: it does now)."""
        if self._settled_at is None:
            return 0
        return max(0, round((self._settled_at - time.monotonic()) * 1000))

    def _post_held(self) -> None:
        if self.held and self._active():
            held, self.held = self.held, []
            self._post(" ".join(text for text, _ in held), any(important for _, important in held))

    def _say_aloud(self, text: str) -> None:
        """macOS's say command, one after another."""
        self._to_say.append(text)
        if self._voice is None:
            self._voice = QProcess(self)
            self._voice.finished.connect(self._next)
        if self._voice.state() == QProcess.ProcessState.NotRunning:
            self._next()

    def _next(self, *_) -> None:
        if self._to_say and self._voice is not None:
            self._voice.start("/usr/bin/say", [self._to_say.pop(0)])


_voiceover_queue: VoiceOver | None = None


def voiceover() -> VoiceOver:
    """The app's one VoiceOver queue."""
    global _voiceover_queue
    if _voiceover_queue is None:
        _voiceover_queue = VoiceOver()
    return _voiceover_queue


def _voiceover(text: str, important: bool) -> None:
    from . import macnative

    rt = macnative._rt()
    if rt is None:
        return
    appkit = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/AppKit.framework/AppKit")
    send = rt.send
    string = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)(send)
    number = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long)(send)
    dictionary = ctypes.CFUNCTYPE(
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p), ctypes.c_ulong
    )(send)
    key = ctypes.c_void_p.in_dll(appkit, "NSAccessibilityAnnouncementKey").value
    priority_key = ctypes.c_void_p.in_dll(appkit, "NSAccessibilityPriorityKey").value
    requested = ctypes.c_void_p.in_dll(appkit, "NSAccessibilityAnnouncementRequestedNotification").value
    words = string(rt.cls("NSString"), rt.sel("stringWithUTF8String:"), text.encode("utf-8"))
    level = number(rt.cls("NSNumber"), rt.sel("numberWithInteger:"), PRIORITY_HIGH if important else PRIORITY_MEDIUM)
    keys, values = (ctypes.c_void_p * 2)(key, priority_key), (ctypes.c_void_p * 2)(words, level)
    info = dictionary(rt.cls("NSDictionary"), rt.sel("dictionaryWithObjects:forKeys:count:"), values, keys, 2)
    app = rt.obj(rt.cls("NSApplication"), rt.sel("sharedApplication"))
    post = appkit.NSAccessibilityPostNotificationWithUserInfo
    post.restype, post.argtypes = None, [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    post(app, requested, info)
