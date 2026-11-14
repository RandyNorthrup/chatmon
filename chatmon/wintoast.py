"""Windows 10 and 11: notifications as Windows' own toasts rather than the tray's balloons. A toast can carry buttons,
and the reminder scenario keeps it on screen until it's answered; Action Center keeps it after, and Windows holds it
during Do Not Disturb and Focus. WinRT's ToastNotificationManager through combase with ctypes (winrt.py). Imports
anywhere; shows toasts on Windows alone, and says when it can't, so the caller can use the tray balloon instead.

A toast is shown under the app's identity: the AppUserModelID app.py gives the process, which the installer's
shortcuts carry too. Without such a shortcut (a pip install), Windows learns the name and icon to show from a
per-user registration, which register_app_id() writes.

What you do with a toast comes back through events Windows raises on threads of its own: Activated (the toast or one
of its buttons), Dismissed (closed, timed out into Action Center, or hidden by Chatmon) and Failed. They are re-emitted
on the Qt thread. They reach Chatmon while it runs; a toast clicked in Action Center after Chatmon quit goes nowhere,
so clear() removes Chatmon's toasts as it quits.
https://learn.microsoft.com/en-us/windows/apps/design/shell/tiles-and-notifications/adaptive-interactive-toasts
https://learn.microsoft.com/en-us/uwp/schemas/tiles/toastschema/element-toast
https://learn.microsoft.com/en-us/windows/apps/design/shell/tiles-and-notifications/send-local-toast-other-apps
The interfaces' IDs and method order are the Windows SDK's (winrt/windows.ui.notifications.h and
winrt/windows.data.xml.dom.h, 10.0.26100)."""

from __future__ import annotations

import ctypes
import re
import sys
import uuid
import xml.etree.ElementTree as ET
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from PyQt6.QtCore import QObject, pyqtSignal

from . import winrt
from .i18n import N_, _

GROUP = "chatmon"  # every toast Chatmon shows is in this group, so clear() takes only Chatmon's own
MAX_BUTTONS = 5  # Windows shows at most five actions
SCENARIOS = (None, "reminder", "alarm", "urgent")  # "urgent" is Windows 11's; elsewhere it's an ordinary toast
NEEDS_A_BUTTON = ("reminder", "alarm")  # Windows keeps these on screen only when they have a button
BODY = -1  # the button index for a click on the toast itself
KEEP_AT_MOST = 50  # toasts listened to at once: the oldest are let go of first
ARGUMENT = re.compile(r"chatmon:([0-9a-f]{1,32}):(-?\d+)")
# Characters XML 1.0 can't hold at all; Windows' parser refuses the whole toast for one.
NOT_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")

# NotificationSetting: whether Windows will show this app's toasts.
ENABLED, OFF_FOR_APP, OFF_FOR_USER, OFF_BY_POLICY, OFF_BY_MANIFEST = 0, 1, 2, 3, 4
WHY_NOT = {  # shown as _(WHY_NOT[setting])
    OFF_FOR_APP: N_("Notifications from Chatmon are turned off in Windows' settings."),
    OFF_FOR_USER: N_("Notifications are turned off in Windows' settings."),
    OFF_BY_POLICY: N_("Notifications are turned off by your organization."),
    OFF_BY_MANIFEST: N_("Windows doesn't allow Chatmon's notifications."),
}
# ToastDismissalReason
DISMISSED_BY_YOU, HIDDEN_BY_CHATMON, TIMED_OUT = 0, 1, 2

MANAGER = "Windows.UI.Notifications.ToastNotificationManager"
TOAST = "Windows.UI.Notifications.ToastNotification"
XML_DOCUMENT = "Windows.Data.Xml.Dom.XmlDocument"
IID_MANAGER_STATICS = "50ac103f-d235-4598-bbef-98fe4d1a3ad4"
IID_MANAGER_STATICS2 = "7ab93c52-0e48-4750-ba9d-1a4113981847"
IID_HISTORY2 = "3bc3d253-2f31-4092-9129-8ad5abf067da"
IID_TOAST_FACTORY = "04124b20-82c6-4229-b109-fd9ed4662b53"
IID_TOAST2 = "9dfb9fd1-143a-490e-90bf-b9fba7132de7"
IID_ACTIVATED_ARGS = "e3bf92f3-c197-436f-8265-0625824f8dac"
IID_XML_IO = "6cd0e74e-ee65-4489-9ebf-ca43e87ba637"
IID_XML_DOCUMENT = "f7f3a506-1e87-42d6-bcfb-b8c809fa5494"
# TypedEventHandler<ToastNotification, Object>, <ToastNotification, ToastDismissedEventArgs> and
# <ToastNotification, ToastFailedEventArgs>
IID_ON_ACTIVATED = "ab54de2d-97d9-5528-b6ad-105afe156530"
IID_ON_DISMISSED = "61c2402f-0ed0-5a18-ab69-59f4aa99a368"
IID_ON_FAILED = "95e3e803-c969-5e3a-9753-ea2ad22a9a33"

# vtable slots, IUnknown's 3 and IInspectable's 3 first
STATICS_CREATE_NOTIFIER_WITH_ID = 7
STATICS2_GET_HISTORY = 6
HISTORY_REMOVE_GROUP_WITH_ID = 7
HISTORY2_GET_HISTORY_WITH_ID = 7
VECTOR_GET_AT, VECTOR_GET_SIZE = 6, 7
NOTIFIER_SHOW, NOTIFIER_HIDE, NOTIFIER_GET_SETTING = 6, 7, 8
FACTORY_CREATE = 6
TOAST_ADD_DISMISSED, TOAST_REMOVE_DISMISSED = 9, 10
TOAST_ADD_ACTIVATED, TOAST_REMOVE_ACTIVATED = 11, 12
TOAST_ADD_FAILED, TOAST_REMOVE_FAILED = 13, 14
TOAST2_PUT_TAG, TOAST2_GET_TAG, TOAST2_PUT_GROUP, TOAST2_PUT_SUPPRESS_POPUP = 6, 7, 8, 10
XML_LOAD = 6
ARGS_GET = 6  # Arguments, Reason and ErrorCode: each event's arguments have the one property

Button = str | tuple[str, Callable[[], None] | None]

_P = ctypes.POINTER(ctypes.c_void_p)


def arguments(tag: str, index: int) -> str:
    return f"chatmon:{tag}:{index}"


def parse_arguments(text: str) -> tuple[str, int] | None:
    """(tag, button) from a toast's activation arguments; None for anything Chatmon didn't write."""
    match = ARGUMENT.fullmatch(text or "")
    return (match.group(1), int(match.group(2))) if match else None


def _clean(text: str) -> str:
    return NOT_XML.sub("", str(text))


def _label(button: Button) -> str:
    return button if isinstance(button, str) else button[0]


def toast_xml(title: str, text: str = "", buttons: Sequence[Button] = (), scenario: str | None = None, tag: str = "0",
              silent: bool = False) -> str:
    """The toast's XML. ElementTree escapes the text, which may come from an agent: it's never markup. A button's
    arguments say which toast and which button; `launch` says the toast itself was clicked."""
    if scenario not in SCENARIOS:
        raise ValueError(f"A toast's scenario is one of {', '.join(str(s) for s in SCENARIOS)}, not {scenario!r}.")
    if len(buttons) > MAX_BUTTONS:
        raise ValueError(f"A toast has at most {MAX_BUTTONS} buttons, not {len(buttons)}.")
    toast = ET.Element("toast", {"launch": arguments(tag, BODY), "activationType": "foreground"})
    if scenario:
        toast.set("scenario", scenario)
    binding = ET.SubElement(ET.SubElement(toast, "visual"), "binding", {"template": "ToastGeneric"})
    ET.SubElement(binding, "text").text = _clean(title)
    if text:
        ET.SubElement(binding, "text").text = _clean(text)
    if buttons or scenario in NEEDS_A_BUTTON:
        actions = ET.SubElement(toast, "actions")
        for index, button in enumerate(buttons):
            ET.SubElement(actions, "action", {"content": _clean(_label(button)), "arguments": arguments(tag, index),
                                              "activationType": "foreground"})
        if not buttons:  # Windows' own Dismiss, so the scenario holds
            ET.SubElement(actions, "action", {"content": "", "arguments": "dismiss", "activationType": "system"})
    if silent:
        ET.SubElement(toast, "audio", {"silent": "true"})
    return ET.tostring(toast, encoding="unicode")


def process_app_id() -> str | None:
    """The AppUserModelID this process gave itself (SetCurrentProcessExplicitAppUserModelID), or None."""
    if sys.platform != "win32":
        return None
    try:
        shell32, ole32 = ctypes.WinDLL("shell32"), ctypes.WinDLL("ole32")
        shell32.GetCurrentProcessExplicitAppUserModelID.argtypes = [ctypes.POINTER(ctypes.c_wchar_p)]
        shell32.GetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_long
        ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        out = ctypes.c_wchar_p()
        if shell32.GetCurrentProcessExplicitAppUserModelID(ctypes.byref(out)) != 0:
            return None  # E_FAIL: none was set
        try:
            return out.value or None
        finally:
            ole32.CoTaskMemFree(ctypes.cast(out, ctypes.c_void_p))
    except (AttributeError, OSError):
        return None


def _registration_key(app_id: str) -> str:
    if not app_id or "\\" in app_id or len(app_id) > 128:
        raise ValueError(f"{app_id!r} isn't an AppUserModelID.")
    return "Software\\Classes\\AppUserModelId\\" + app_id


def register_app_id(app_id: str, display_name: str, icon: str | None = None) -> None:
    """Tell Windows the name (and icon, a .png or .ico) to show on this app ID's toasts, for a Chatmon with no Start
    menu shortcut carrying the ID. Per user; OSError if it can't be written."""
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _registration_key(app_id)) as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, display_name)
        if icon:
            winreg.SetValueEx(key, "IconUri", 0, winreg.REG_SZ, icon)


def unregister_app_id(app_id: str) -> bool:
    """Remove what register_app_id wrote; False if there was nothing to remove."""
    import winreg

    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, _registration_key(app_id))
    except FileNotFoundError:
        return False
    return True


@dataclass
class _Shown:
    """A toast Windows has, the handlers listening to it, and what its buttons do."""

    toast: int
    actions: list = field(default_factory=list)
    handlers: list = field(default_factory=list)  # (remove slot, token, delegate)


class Toaster(QObject):
    """Shows toasts under one app ID and reports what became of them, on the Qt thread:
    `activated(tag, button)` (button BODY for the toast itself; a button given with an action runs it too),
    `dismissed(tag, reason)` (DISMISSED_BY_YOU, HIDDEN_BY_CHATMON, TIMED_OUT) and `failed(tag, hresult)`."""

    activated = pyqtSignal(str, int)
    dismissed = pyqtSignal(str, int)
    failed = pyqtSignal(str, int)
    _heard = pyqtSignal(str, str, int)  # (event, tag, value), from Windows' threads to this object's

    def __init__(self, app_id: str | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self.app_id = app_id if app_id is not None else process_app_id()
        self.why_not: str | None = None  # why the last show() showed nothing
        self._statics: int | None = None
        self._notifier: int | None = None
        self._shown: dict[str, _Shown] = {}
        self._heard.connect(self._hear)  # queued: emitted on Windows' threads, heard on this one

    # -- what Windows has

    def _manager(self) -> int | None:
        if self._statics is None and sys.platform == "win32" and winrt.join_com():
            self._statics = winrt.factory(MANAGER, IID_MANAGER_STATICS)
        return self._statics

    def _get_notifier(self) -> int | None:
        if self._notifier is None and self.app_id and self._manager():
            out = ctypes.c_void_p()
            with winrt.HString(self.app_id) as app:
                winrt.method(self._statics, STATICS_CREATE_NOTIFIER_WITH_ID, ctypes.c_void_p, _P)(self._statics, app.handle, ctypes.byref(out))
            self._notifier = out.value or None
        return self._notifier

    def setting(self) -> int | None:
        """Windows' NotificationSetting for this app ID (ENABLED, OFF_FOR_USER...), or None where it can't say."""
        try:
            notifier = self._get_notifier()
            if notifier is None:
                return None
            value = ctypes.c_int()
            winrt.method(notifier, NOTIFIER_GET_SETTING, ctypes.POINTER(ctypes.c_int))(notifier, ctypes.byref(value))
            return value.value
        except OSError:
            return None

    def _history(self) -> int | None:
        statics2 = winrt.query(self._statics, IID_MANAGER_STATICS2) if self._manager() else None
        if statics2 is None:
            return None
        try:
            return winrt.get_object(statics2, STATICS2_GET_HISTORY)
        finally:
            winrt.release(statics2)

    def in_action_center(self) -> list[str]:
        """The tags of this app ID's toasts Windows still has (on screen or in Action Center)."""
        tags: list[str] = []
        history = history2 = view = None
        try:
            history = self._history()
            history2 = winrt.query(history, IID_HISTORY2) if history else None
            if history2 is None or not self.app_id:
                return tags
            out = ctypes.c_void_p()
            with winrt.HString(self.app_id) as app:
                winrt.method(history2, HISTORY2_GET_HISTORY_WITH_ID, ctypes.c_void_p, _P)(history2, app.handle, ctypes.byref(out))
            view = out.value
            size = ctypes.c_uint32()
            winrt.method(view, VECTOR_GET_SIZE, ctypes.POINTER(ctypes.c_uint32))(view, ctypes.byref(size))
            for i in range(size.value):
                item = ctypes.c_void_p()
                winrt.method(view, VECTOR_GET_AT, ctypes.c_uint32, _P)(view, i, ctypes.byref(item))
                toast2 = winrt.query(item.value, IID_TOAST2) if item.value else None
                if toast2:
                    tag = ctypes.c_void_p()
                    winrt.method(toast2, TOAST2_GET_TAG, _P)(toast2, ctypes.byref(tag))
                    tags.append(winrt.take_text(tag))
                winrt.release(toast2)
                winrt.release(item.value)
        except OSError:
            pass
        finally:
            for obj in (view, history2, history):
                winrt.release(obj)
        return tags

    # -- showing

    def show(self, title: str, text: str = "", buttons: Sequence[Button] = (), scenario: str | None = None,
             silent: bool = False) -> str | None:
        """Show a toast; its tag, or None (with `why_not` saying why) where none could be shown, for the caller to
        use the tray balloon. `buttons` are labels, or (label, action) pairs whose action runs when it's pressed.
        A bad scenario or too many buttons is a ValueError."""
        tag = uuid.uuid4().hex[:16]
        xml = toast_xml(title, text, buttons, scenario, tag, silent)
        self.why_not = None
        if sys.platform != "win32":
            self.why_not = _("Toasts are Windows' own.")
            return None
        if not self.app_id:
            self.why_not = _("Chatmon has no app ID for Windows to show its notifications under.")
            return None
        setting = self.setting()
        if setting != ENABLED:
            self.why_not = _(WHY_NOT[setting]) if setting in WHY_NOT else _("Windows wouldn't say whether it shows notifications.")
            return None
        if not self._post(xml, tag):
            return None
        self._shown[tag].actions = [None if isinstance(b, str) else b[1] for b in buttons]
        return tag

    def _post(self, xml: str, tag: str, suppress_popup: bool = False) -> bool:
        """Hand Windows the toast, listening for what becomes of it. `suppress_popup` sends it straight to Action
        Center."""
        document = io = xml_document = toast_factory = toast = toast2 = None
        try:
            notifier = self._get_notifier()
            document = winrt.activate(XML_DOCUMENT)
            io = winrt.query(document, IID_XML_IO) if document else None
            toast_factory = winrt.factory(TOAST, IID_TOAST_FACTORY)
            if notifier is None or io is None or toast_factory is None:
                self.why_not = _("This Windows has no toasts.")
                return False
            with winrt.HString(xml) as text:
                winrt.method(io, XML_LOAD, ctypes.c_void_p)(io, text.handle)
            xml_document = winrt.query(document, IID_XML_DOCUMENT)
            out = ctypes.c_void_p()
            winrt.method(toast_factory, FACTORY_CREATE, ctypes.c_void_p, _P)(toast_factory, xml_document, ctypes.byref(out))
            toast = out.value
            toast2 = winrt.query(toast, IID_TOAST2)
            if toast2:
                with winrt.HString(tag) as value:
                    winrt.method(toast2, TOAST2_PUT_TAG, ctypes.c_void_p)(toast2, value.handle)
                with winrt.HString(GROUP) as value:
                    winrt.method(toast2, TOAST2_PUT_GROUP, ctypes.c_void_p)(toast2, value.handle)
                if suppress_popup:
                    winrt.method(toast2, TOAST2_PUT_SUPPRESS_POPUP, ctypes.c_ubyte)(toast2, 1)
            shown = _Shown(toast)
            self._shown[tag] = shown
            toast = None  # held by `shown` now
            for add, remove, iid, heard in ((TOAST_ADD_ACTIVATED, TOAST_REMOVE_ACTIVATED, IID_ON_ACTIVATED, self._on_activated),
                                            (TOAST_ADD_DISMISSED, TOAST_REMOVE_DISMISSED, IID_ON_DISMISSED, self._on_dismissed),
                                            (TOAST_ADD_FAILED, TOAST_REMOVE_FAILED, IID_ON_FAILED, self._on_failed)):
                delegate = winrt.Delegate(iid, lambda sender, args, heard=heard: heard(tag, args))
                token = winrt.EventToken()
                try:
                    winrt.method(shown.toast, add, ctypes.c_void_p, ctypes.POINTER(winrt.EventToken))(shown.toast, delegate.pointer, ctypes.byref(token))
                    shown.handlers.append((remove, token, delegate))
                finally:
                    delegate.release()  # Windows holds it now, or nobody does
            winrt.method(notifier, NOTIFIER_SHOW, ctypes.c_void_p)(notifier, shown.toast)
            self._keep_few()
            return True
        except OSError:
            self.why_not = _("Windows couldn't show the notification.")
            self._forget(tag)
            return False
        finally:
            for obj in (toast2, toast, toast_factory, xml_document, io, document):
                winrt.release(obj)

    def _keep_few(self) -> None:
        while len(self._shown) > KEEP_AT_MOST:
            self._forget(next(iter(self._shown)))

    # -- what became of it: on Windows' threads, then on this one

    def _on_activated(self, tag: str, args: int) -> None:
        index = BODY
        activated = winrt.query(args, IID_ACTIVATED_ARGS) if args else None
        if activated:
            try:
                text = ctypes.c_void_p()
                winrt.method(activated, ARGS_GET, _P)(activated, ctypes.byref(text))
                parsed = parse_arguments(winrt.take_text(text))
                if parsed and parsed[0] == tag:
                    index = parsed[1]
            finally:
                winrt.release(activated)
        self._heard.emit("activated", tag, index)

    def _on_dismissed(self, tag: str, args: int) -> None:
        reason = ctypes.c_int(-1)
        if args:
            winrt.method(args, ARGS_GET, ctypes.POINTER(ctypes.c_int))(args, ctypes.byref(reason))
        self._heard.emit("dismissed", tag, reason.value)

    def _on_failed(self, tag: str, args: int) -> None:
        code = ctypes.c_long(0)
        if args:
            winrt.method(args, ARGS_GET, ctypes.POINTER(ctypes.c_long))(args, ctypes.byref(code))
        self._heard.emit("failed", tag, code.value)

    def _hear(self, event: str, tag: str, value: int) -> None:
        shown = self._shown.get(tag)
        if event == "activated":
            action = shown.actions[value] if shown and 0 <= value < len(shown.actions) else None
            self._forget(tag)
            self.activated.emit(tag, value)
            if action is not None:
                action()
        elif event == "dismissed":
            if value != TIMED_OUT:  # timed out, it's in Action Center, where it can still be clicked
                self._forget(tag)
            self.dismissed.emit(tag, value)
        elif event == "failed":
            self._forget(tag)
            self.failed.emit(tag, value)

    # -- taking them back

    def hide(self, tag: str) -> bool:
        """Take a toast off the screen and out of Action Center. Dismissed follows, with HIDDEN_BY_CHATMON."""
        shown, notifier = self._shown.get(tag), self._notifier
        if shown is None or notifier is None:
            return False
        try:
            winrt.method(notifier, NOTIFIER_HIDE, ctypes.c_void_p)(notifier, shown.toast)
            return True
        except OSError:
            return False

    def clear(self) -> None:
        """Remove every toast of Chatmon's from Action Center (as it quits: nothing would hear their buttons)."""
        history = None
        try:
            history = self._history()
            if history and self.app_id:
                with winrt.HString(GROUP) as group, winrt.HString(self.app_id) as app:
                    winrt.method(history, HISTORY_REMOVE_GROUP_WITH_ID, ctypes.c_void_p, ctypes.c_void_p)(history, group.handle, app.handle)
        except OSError:
            pass
        finally:
            winrt.release(history)
        for tag in list(self._shown):
            self._forget(tag)

    def _forget(self, tag: str) -> None:
        shown = self._shown.pop(tag, None)
        if shown is None:
            return
        for remove, token, _delegate in shown.handlers:
            try:
                winrt.method(shown.toast, remove, winrt.EventToken)(shown.toast, token)
            except OSError:
                pass
        winrt.release(shown.toast)

    @property
    def listening(self) -> list[str]:
        """The tags of the toasts whose events are still heard."""
        return list(self._shown)

    def close(self) -> None:
        for tag in list(self._shown):
            self._forget(tag)
        winrt.release(self._notifier)
        winrt.release(self._statics)
        self._notifier = self._statics = None


_toaster: Toaster | None = None


def toaster() -> Toaster:
    """The app's Toaster, under the process's own app ID; made on first use, on the Qt thread."""
    global _toaster
    if _toaster is None:
        _toaster = Toaster()
    return _toaster


def show(title: str, text: str = "", buttons: Sequence[Button] = (), scenario: str | None = None) -> str | None:
    """A toast under the process's app ID; its tag, or None for the caller to use the tray balloon instead."""
    return toaster().show(title, text, buttons, scenario)
