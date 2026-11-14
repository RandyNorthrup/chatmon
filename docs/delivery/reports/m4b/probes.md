# M4B probes, 2026-11-14

Short experiments run before the design was settled. The scripts were throwaway, in the session's scratch folder;
the output below is what they printed.

## 1. RegisterHotKey on a message-only window, heard by a Qt native event filter

Windows 11 26200, Python 3.14.10, PyQt6 6.11.0. A `STATIC`-class window with `HWND_MESSAGE` as its parent,
`RegisterHotKey(hwnd, 7, MOD_ALT|MOD_CONTROL|MOD_SHIFT|MOD_NOREPEAT, VK_F24)`, then a raw
`RegisterHotKey(NULL, 8, ...)` of the same combination, then `WM_HOTKEY` posted to the window and Qt's event loop run
until a `QAbstractNativeEventFilter` saw it. Run with `QT_QPA_PLATFORM=offscreen` and `QT_QPA_PLATFORM=windows`:

```
platform offscreen
hwnd 63377724 1400
register 1 1400
second register 0 1409
seen [(7, 8847367)]
unregister 1
again by other 1 1
destroy 1
platform windows
hwnd 33559752 1400
register 1 1400
second register 0 1409
seen [(7, 8847367)]
unregister 1
again by other 1 1
destroy 1
```

Findings: the filter hears the message-only window's messages on both platforms; a second registration of a held
combination fails with `ERROR_HOTKEY_ALREADY_REGISTERED` (1409); after `UnregisterHotKey` anyone can register it.

## 2. A WinRT toast through combase, its events, and the history

The same machine, through `chatmon/winrt.py`: `ToastNotificationManager` statics, `CreateToastNotifierWithId`,
`XmlDocument.LoadXml`, `ToastNotification` factory, tag and group, `SuppressPopup`, Dismissed and Failed delegates,
`Show`, `GetHistoryWithId`, `Hide`, `ClearWithId`. Once with a throwaway app ID unregistered, once with it registered
under `HKCU\Software\Classes\AppUserModelId` (deleted after):

```
== noreg
setting 2
refs after add 2 2
shown
history [] events [('failed', '0x803e0114')]
after hide events [('failed', '0x803e0114'), ('dismissed', 1)] history []
after clear []
refs after remove 0 0
== reg
setting 2
refs after add 2 2
shown
history [] events [('failed', '0x803e0114')]
after hide events [('failed', '0x803e0114'), ('dismissed', 1)] history []
after clear []
refs after remove 0 0
key removed
```

Findings:

- `get_Setting` is 2, `NotificationSetting_DisabledForUser`: this user has notifications turned off
  (`HKCU\Software\Microsoft\Windows\CurrentVersion\PushNotifications\ToastEnabled = 0`, read only). Windows refuses
  the toast with Failed `0x803E0114` (`WPN_E_NOTIFICATION_TYPE_DISABLED`), so the history stays empty here.
- The delegates work as agile objects: Windows calls Failed and Dismissed (reason 1, `ApplicationHidden`, after
  `Hide`) from its own thread, and releases them when the handlers are removed (reference counts back to 0).
- Whether a toast lands in the history can only be seen where notifications are on: CI's Windows runner.

## 3. QtDBus and arrays of structs (WSL, Arch Linux, PyQt6 6.12.1)

`BindShortcuts(o, a(sa{sv}), s, a{sv})` needs an array of structs. Sending one built with
`QDBusArgument.beginArray(QMetaType(QVariantMap))` and `beginStructure()` inside, watched with `dbus-monitor` on a
`dbus-run-session` bus:

```
connected True
dbus[314]: Writing an element of type struct, but the expected type here is array
The overall signature expected here was 'aa{sv}' and we are on byte 1 of that signature.
  D-Bus not built with -rdynamic so unable to print a backtrace
```

libdbus aborted the process. `beginArray` takes only an element type registered with QtDBus, and from Python no
struct type can be registered.

Receiving such a call with a `QDBusAbstractAdaptor` slot taking a `QDBusArgument`, called with
`gdbus call ... BindShortcuts /org/s "[(\"a\", {\"description\": <\"d\">})]" "" "{\"handle_token\": <\"t\">}"`:

```
True True
Skipped method "BindShortcuts" : Type not registered with QtDBus in parameter list: QDBusArgument
qt.dbus.integration: QDBusConnection: couldn't handle call to BindShortcuts: Type not registered with QtDBus in parameter list: QDBusArgument
Error: GDBus.Error:org.freedesktop.DBus.Error.UnknownMethod: No such method 'BindShortcuts' in interface 'org.freedesktop.portal.GlobalShortcuts' at object path '/org/freedesktop/portal/desktop' (signature 'sa(sa{sv})sa{sv}')
```

Finding: the GlobalShortcuts portal can't be reached through QtDBus from PyQt6, in either direction. Chatmon reaches it
through libdbus with ctypes instead (`chatmon/libdbus.py`), and the pretend portal in the tests uses it too, with
`dbus-monitor` as the independent check of what went over the wire.

## 4. The XDG shortcuts format

From https://specifications.freedesktop.org/shortcuts/latest/ (the GlobalShortcuts portal's `preferred_trigger`
refers to it): modifiers `CTRL`, `ALT`, `SHIFT`, `NUM`, `LOGO`, joined to the key by `+`; the key is an xkbcommon
keysym name without `XKB_KEY_`. Examples there: `a`, `CTRL+a`, `CTRL+SHIFT+a`, `CTRL+ALT+Return`.
