"""Screen readers: is one listening, and how to have it say what a bubble says.

The chatmon and its bubbles are drawn, not widgets a screen reader can walk (and PyQt6 has none of Qt's
accessibility API to make them so, or to announce). So each platform's own way to ask the screen reader to
speak is used where there is one; where there isn't, the app sends a system notification, which screen readers
read (Narrator and NVDA read Windows' notifications; Orca reads GNOME's).

- Linux, Orca 49 or later: its remote controller on the session bus, PresentMessage(s), which speaks (and
  brailles) whatever is in front. Named org.gnome.Orca.Service in 49 and 50, org.gnome.Orca1.Service from 51.
  https://gitlab.gnome.org/GNOME/orca/-/blob/main/docs/remote-controller.md
- macOS, VoiceOver: NSAccessibilityAnnouncementRequestedNotification, posted on the app. VoiceOver speaks it for
  the app in front (with the chat open, Chatmon is); from the background it may stay silent.
  https://developer.apple.com/documentation/appkit/nsaccessibility-swift.struct/notification/announcementrequested
- Windows: a notification. A UIA notification event needs a UIA provider of the app's own, and NVDA ignores those
  from apps in the background. https://github.com/nvaccess/nvda/blob/master/source/NVDAObjects/UIA/__init__.py
"""

from __future__ import annotations

import ctypes
import re
import sys
from dataclasses import dataclass
from typing import Callable

ORCA = (("org.gnome.Orca1.Service", "/org/gnome/Orca1/Service"), ("org.gnome.Orca.Service", "/org/gnome/Orca/Service"))
SPI_GETSCREENREADER = 0x0046  # set by NVDA, JAWS and others; Narrator doesn't set it
PRIORITY_MEDIUM, PRIORITY_HIGH = 50, 90  # NSAccessibilityPriorityLevel


@dataclass
class Reader:
    name: str  # "Orca", "VoiceOver", "Narrator", "a screen reader"
    speak: Callable[[str, bool], None] | None = None  # (text, important); None: a notification says it instead


def reader() -> Reader | None:
    """The screen reader running now, if there is one."""
    try:
        if sys.platform == "win32":
            return _windows()
        if sys.platform == "darwin":
            return _mac()
        return _linux()
    except (OSError, AttributeError, ImportError, ValueError):
        return None


def spoken(title: str, text: str = "", buttons: list[str] | None = None) -> str:
    """A bubble as it's read out: plain words, and what to type to press its buttons."""
    parts = [plain(title), plain(text)]
    if buttons:
        parts.append("To answer, type " + " or ".join(f"“{b}”" for b in buttons) + " in the chat.")
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
    from PyQt6.QtDBus import QDBus, QDBusConnection, QDBusMessage

    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        return None
    interface = bus.interface()
    for service, path in ORCA:
        if interface.isServiceRegistered(service).value():
            return Reader("Orca", lambda text, important, s=service, p=path: _orca(bus, s, p, text))
    # An older Orca, or another screen reader: at-spi says one's on (where it still keeps ScreenReaderEnabled).
    message = QDBusMessage.createMethodCall("org.a11y.Bus", "/org/a11y/bus", "org.freedesktop.DBus.Properties", "Get")
    message.setArguments(["org.a11y.Status", "ScreenReaderEnabled"])
    reply = bus.call(message, QDBus.CallMode.Block, 500)
    value = reply.arguments()[0] if reply.type() == QDBusMessage.MessageType.ReplyMessage and reply.arguments() else None
    while hasattr(value, "variant"):
        value = value.variant()
    return Reader("a screen reader") if value is True else None


def _orca(bus, service: str, path: str, text: str) -> None:
    from PyQt6.QtDBus import QDBusMessage

    message = QDBusMessage.createMethodCall(service, path, service, "PresentMessage")
    message.setArguments([text])
    bus.send(message)  # no waiting: it speaks when it can


# -- Windows


def _windows() -> Reader | None:
    on = ctypes.c_int(0)
    if ctypes.windll.user32.SystemParametersInfoW(SPI_GETSCREENREADER, 0, ctypes.byref(on), 0) and on.value:
        return Reader("a screen reader")
    return Reader("Narrator") if _running("narrator.exe") else None


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_uint32), ("cntUsage", ctypes.c_uint32), ("th32ProcessID", ctypes.c_uint32),
        ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", ctypes.c_uint32), ("cntThreads", ctypes.c_uint32),
        ("th32ParentProcessID", ctypes.c_uint32), ("pcPriClassBase", ctypes.c_long), ("dwFlags", ctypes.c_uint32),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def _running(exe: str) -> bool:
    """A program of that name is running (for Narrator, which tells Windows nothing else)."""
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
    on = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(ctypes.cast(rt.lib.objc_msgSend, ctypes.c_void_p).value)
    if not workspace or not rt.responds(workspace, rt.sel("respondsToSelector:"), rt.sel("isVoiceOverEnabled")):
        return None
    return Reader("VoiceOver", _voiceover) if on(workspace, rt.sel("isVoiceOverEnabled")) else None


def _voiceover(text: str, important: bool) -> None:
    from . import macnative

    rt = macnative._rt()
    if rt is None:
        return
    appkit = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/AppKit.framework/AppKit")
    send = ctypes.cast(rt.lib.objc_msgSend, ctypes.c_void_p).value
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
