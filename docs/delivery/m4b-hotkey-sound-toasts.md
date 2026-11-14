# M4B: hotkey, sound and Windows notifications

Milestone M4B of [ROADMAP.md](ROADMAP.md), covering items M4B-01 to M4B-04 of [ASSESSMENT.md](ASSESSMENT.md). Branch
`wave1/m4b`, from `improve/assessment-fixes` at `5346385`. Reports, logs and context are in
[reports/m4b/](reports/m4b/).

## Rationale

Chatmon has no global shortcut, no sound, and on Windows its notifications are tray balloons. Magnifier users lose
bubbles that appear away from where they're looking. This milestone adds the platform pieces as modules with small
APIs; wiring them into the app and the settings window is M7's (see Integration notes).

### Scope and non-goals

- In scope: new `chatmon/hotkey.py`, `chatmon/sound.py`, `chatmon/wintoast.py`, plus `chatmon/winfocus.py`, which is
  this milestone's, and new helper modules `chatmon/winrt.py`, `chatmon/wincaret.py`, `chatmon/libdbus.py` and
  `chatmon/shortcutportal.py`, with their tests.
- Not in scope: the sound files (M9 makes them in `chatmon/sounds/`; tests generate their own WAVs), settings keys
  (`settings.py` is M1B's), the settings window (M7), calling any of this from `app.py` (M0/M7), and CI workflow
  changes (M6A).

### Reuse decisions

- `winfocus.py` already reached WinRT through combase with ctypes (GUIDs, vtable slots, an activation factory). Toasts
  need the same plus HSTRINGs, instances and a callback delegate, so those helpers move into a shared
  `chatmon/winrt.py`, and `winfocus.py` uses it. Its public names (`manager`, `is_active`, `Focus`) stay as they were;
  `tests/test_presence.py` keeps covering it.
- `winlock.py`'s native event filter pattern is reused for the hotkey's `WM_HOTKEY`. The hotkey's window is a
  message-only Win32 window made with ctypes, not a `QWindow`: under the offscreen platform a `QWindow` has no real
  window handle, and a message-only window never shows anywhere. A probe confirmed Qt's event loop passes its
  messages to native event filters on both the `windows` and `offscreen` platforms
  ([reports/m4b/probes.md](reports/m4b/probes.md)).
- `portal.py` and `tests/fake_portal.py` are the pattern for the GlobalShortcuts portal and its pretend portal on a
  private bus. **QtDBus can't be used for it from Python.** `BindShortcuts` takes `a(sa{sv})`, an array of structs;
  PyQt6's `QDBusArgument.beginArray` takes only an element type registered with QtDBus, and no struct type is, so
  libdbus aborts the process ("Writing an element of type struct, but the expected type here is array"). QtDBus
  can't receive such a call either ("Type not registered with QtDBus in parameter list: QDBusArgument"). Both are
  recorded in the probes report. So `chatmon/libdbus.py` talks to the session bus through libdbus itself, with
  ctypes: the library QtDBus loads anyway, so it's present wherever QtDBus works. The portal client,
  `chatmon/shortcutportal.py`, runs on a thread of its own, so no portal call ever waits on the screen's thread.
- `macnative.py`'s Objective-C runtime helper is private to it and M4A's to change, so `sound.py` makes its few
  NSSound calls with its own exact prototypes rather than importing it.
- M4B-04 lives in a new `chatmon/wincaret.py` rather than `winfocus.py`: `winfocus.py` is about Windows 11's Focus
  sessions, and the caret is about where Magnifier looks.

### Design

**hotkey.py.** `parse(sequence)` reads a portable sequence in Qt's PortableText names, as `QKeySequenceEdit` writes
them (`Ctrl+Alt+Space`, `Meta+Shift+F5`), with aliases (`Control`, `Option`, `Win`, `Super`, `Cmd`). It follows Qt's
convention that on macOS `Ctrl` is the Command key and `Meta` the Control key. A shortcut needs Ctrl, Alt or Meta,
except F13 to F24, which no app types with. `Hotkey` (a QObject with `pressed`, `failed(str)` and `bound(str)`
signals) registers one shortcut through one backend:

- Windows: `RegisterHotKey` with `MOD_NOREPEAT` on its own message-only window, heard by a native event filter.
- macOS: Carbon's `RegisterEventHotKey`, exclusive, with an event handler on the application target.
- X11: `XGrabKey` on the root window over a connection of its own, for each NumLock and CapsLock state, watched with
  a `QSocketNotifier`. `BadAccess` (another client holds it) is caught with a temporary Xlib error handler.
- Wayland (`WAYLAND_DISPLAY` set, whatever Qt's own platform): the GlobalShortcuts portal, `CreateSession` then
  `BindShortcuts` with the preferred trigger in the XDG shortcuts format (`CTRL+ALT+space`), and `Activated`.

`register()` returns an error sentence or None. On Windows, macOS and X11 a failed change keeps the shortcut already
registered. The portal answers later, so on Wayland `register()` returns None once the request is on its way, and a
refusal, or a desktop with no portal, comes through `failed`. A desktop binds a session's shortcuts once, so a change
there closes the old session and asks again in a new one.

**sound.py.** Seven cues, named as M9's files (`needs-you`, `reminder`, `focus-done`, `done`, `success`, `error`,
`pop`). The first three are on by default, as the owner decided. `Sounds.configure(enabled, volume, cues, quiet)`
takes the one switch, a volume in percent, per-cue switches and a callable that says whether now is a quiet time;
`play(cue)` returns whether a sound started. Players, first that works: `QSoundEffect`; else on Windows `PlaySound`
from memory on a worker thread (with the samples scaled for the volume), on macOS `NSSound`, on Linux `pw-play`,
`paplay` or `canberra-gtk-play` started without waiting. None blocks the caller.

**wintoast.py.** `toast_xml()` builds the toast's XML with ElementTree, so text from agents is always escaped: title,
text, up to five buttons, the reminder (or alarm or urgent) scenario, and `launch` arguments that say which toast and
which button. `Toaster.show()` creates the toast through combase (`ToastNotificationManager`, `XmlDocument`,
`ToastNotification`) under the process's own AppUserModelID (the one `app.py:34` sets at `app.py:2580`), with a tag and
the group `chatmon`, and returns the tag, or None when it can't (not Windows, no app ID, notifications off), for the
caller to fall back to the tray balloon. Activated, Dismissed and Failed come back through agile delegates on Windows'
threads and are re-emitted on the Qt thread as `activated(tag, button)`, `dismissed(tag, reason)` and
`failed(tag, code)`. `register_app_id()` writes the per-user registration Windows reads for apps without a Start menu
shortcut (pip installs), and `unregister_app_id()` removes it.

**wincaret.py.** `place(hwnd, x, y, width, height)` creates a hidden system caret on the stage window over the new
bubble, which raises the caret location event Magnifier follows. `clear()` destroys it. `magnifier_running()` looks
for Magnifier's window, so the caret is only ever placed while it runs.

### Verification approach

- Real Qt objects and real OS calls. On Windows, the hotkey is registered for real with an unusual combination
  (Ctrl+Alt+Shift+F24) and unregistered after, and a conflict is made with a second, raw registration of the same
  combination. `WM_HOTKEY` is posted to the message-only window rather than typed, so no keystrokes reach the
  owner's session.
- Toasts on this PC: notifications are off for this user (`ToastEnabled = 0`), so `show()` must decline. The posting
  and its events are exercised with a pop-up-suppressed toast that Windows refuses (Failed) and that is then hidden
  (Dismissed). Where notifications are on (CI), the toast must also appear in the history under its tag. Everything
  shown is cleared from the history, and any registration written is deleted.
- Linux: X11 runs against Xvfb with XTest key presses; the portal against a pretend GlobalShortcuts portal on a
  private bus (`dbus-run-session`), with `dbus-monitor` independently decoding what went over the wire. Run here
  in WSL (Arch); in CI the X11 test skips unless Xvfb is installed (an Integration note for M6A).
- macOS: tests that run on macOS CI and skip elsewhere. They are pending CI.
- Each platform's behavior is its own acceptance criterion (scope revision 3), so what was verified on this PC is
  separate from what waits for CI. The ledger's profile is this PC (Windows); the WSL runs are recorded with their own
  Linux environment, and the tasks they cover stay implemented, not verified, until CI's Linux job runs them under
  the project's own profile.

### Found while delivering

- **A sound playing at quit crashed the process.** Drill D-02A-volume's red run ended with 0xC0000409 rather than
  pytest's failure: a QSoundEffect destroyed while still playing, during interpreter shutdown, is a fail-fast in Qt
  Multimedia. A plain script reproduced it every time (3 of 3), and with the fix not once (3 of 3). `QtPlayer` now
  stops every effect as the app quits and at exit; `test_quitting_while_a_sound_plays_ends_cleanly` and drill
  D-02A-stopped-at-exit guard it.
- **An equivalent mutation.** D-04A-one-pixel (dropping the caret's one-pixel minimum) survived: Windows gives a
  zero-width caret the border width, one pixel here, so the rectangle was the same. It was replaced by
  D-04A-bubble-size, which halves the width and is caught.
- **Transient failures from sharing this PC.** `test_events.py::test_send_without_a_running_companion` failed once
  while another worker's suite held this user's Chatmon pipe (passed alone, recorded in `gates-windows.txt`). One full
  run of the second commit's tree had 2 failures, one of them
  `test_brains.py::test_a_redirect_never_takes_the_key_anywhere` (the other's name was cut from the output kept);
  `test_brains.py` passed alone, and the next full run of the same tree had none. None of these tests touch this
  milestone's code.
- **The portal thread could die on a bad answer.** A Response of the wrong shape, or a refused call, ended the
  portal's thread, so no later shortcut was ever asked for. It now fails that shortcut and carries on; the pretend
  portal's `garbled` mode and drill L-01F-carries-on cover it.
- Red drills: [reports/m4b/drill-spec.json](reports/m4b/drill-spec.json) through `tests/drills/run.py` for everything
  that runs on Windows. The Linux-only drills ([reports/m4b/wsl-drill-spec.json](reports/m4b/wsl-drill-spec.json)) run
  in WSL with [reports/m4b/wsl-drills.py](reports/m4b/wsl-drills.py), which copies the tree itself (git in WSL can't
  read this worktree) and hands each drill to `run.py`'s own `drill()`, logged in
  [reports/m4b/wsl-drills.log](reports/m4b/wsl-drills.log). The macOS tests have no drill here: they can't run here.

## Integration notes

The APIs as delivered, and what each other milestone has to do with them. Nothing in `app.py`, `settings.py`,
`settingswin.py`, `cli.py`, CI or packaging was changed here.

### hotkey.py (M7, M1B, M0)

- `hotkey.register(sequence, callback, failed=None) -> str | None`: the M4B and M7 contract. `callback()` runs on the
  Qt thread. It returns a sentence to show (a shortcut that isn't one, a conflict, no display) or None. On Wayland it
  returns None once the request is on its way; a refusal, or a desktop without the portal, comes later through
  `failed(sentence)`. A failed change keeps the shortcut already set (except on Wayland, where a change asks again).
- `hotkey.unregister()`, `hotkey.current() -> str | None`, and `hotkey.parse(sequence) -> Combo` (ValueError with the
  sentence) for checking what a `QKeySequenceEdit` gives:
  `edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)`.
- `hotkey.Hotkey`, a QObject, for signals: `pressed`, `failed(str)`, and `bound(str)`, which says how to press it in
  the desktop's own words on Wayland (show it in Settings next to the field).
- M1B: a setting for it, for example `accessibility.hotkey = "Ctrl+Alt+Space"`, with an empty string for none. On
  macOS, Qt's Ctrl is Command, and Command+Option+Space is Finder's search window by default (macOS doesn't report
  its own shortcuts as conflicts), so a different default there would be kinder, for example `Ctrl+Shift+Space`.
- M7: register at start and whenever the setting changes, showing the sentence in Settings; the callback opens the ask
  box as a click on the chatmon does; `hotkey.unregister()` at quit.
- M0: `hotkey.NO_PORTAL` tells people on desktops without the portal (Sway, GNOME before 48) to bind a desktop
  shortcut to `chatmon ask`. That command doesn't exist yet: `cli.py` needs it (an `{"type": "ask"}` event that opens
  the ask box). If it isn't added, change `NO_PORTAL`.

### sound.py (M7, M1B, M6A, M1A)

- `sound.configure(enabled=True, volume=70, cues=None, quiet=None)` and `sound.play(cue) -> bool`; `sound.CUES`,
  `sound.ON_BY_DEFAULT`, and `sound.Sounds` for a separate instance. `volume` is a percentage. `cues` maps cue names
  to on or off; unnamed cues keep the owner's defaults (needs-you, reminder and focus-done on, the rest off), and
  unknown names are ignored. `quiet` is called before each sound; anything true means silence.
- M1B: settings for the one switch, the volume and each cue, for example
  `sounds = {on = true, volume = 70, cues = {}}`.
- M7: `sound.configure(..., quiet=lambda: self._quiet)` at start and after a settings change (`_quiet` already covers
  Do Not Disturb, Focus and a full-screen app). Play `needs-you` when an agent needs you, `reminder` for a reminder,
  `focus-done` at the end of a focus session, `done`, `success` and `error` for agents' events, and `pop` for a plain
  bubble.
- M6A: `chatmon/sounds/*.wav` in `[tool.setuptools.package-data]`.
- M1A: QtMultimedia is optional at run time. Linux packages could recommend it (Debian and Ubuntu:
  `python3-pyqt6.qtmultimedia`), or one of the fallback players (`pipewire-bin` for pw-play, `pulseaudio-utils` for
  paplay, `gnome-session-canberra` for canberra-gtk-play).

### wintoast.py (M7, M1A, M6A)

- `wintoast.show(title, text="", buttons=(), scenario=None) -> str | None`: the toast's tag, or None (with
  `wintoast.toaster().why_not` saying why) where none could be shown, so the caller uses `tray.showMessage` as today.
  `buttons` are labels or `(label, action)` pairs, up to five; an action runs on the Qt thread when its button is
  pressed. `scenario` is None, `"reminder"`, `"alarm"` or `"urgent"`.
- `wintoast.toaster()` is the app's `Toaster`: signals `activated(tag, button)` (button `wintoast.BODY` for the toast
  itself), `dismissed(tag, reason)` and `failed(tag, hresult)`; `hide(tag)`, `clear()`, `in_action_center()`.
- The app ID is read from the process (`app.py:2580` sets it from `APP_USER_MODEL_ID`), so it isn't repeated here.
- M7: where `app.py` calls `self.tray.showMessage(...)` on Windows (`alert()` under a full-screen app, and the
  screen-reader fallback while M4A-09 keeps one), use `wintoast.show(...)` first and the balloon when it returns None.
  Reminders: `scenario="reminder"` with the snooze buttons. At quit: `wintoast.toaster().clear()`, since nothing
  would hear a button pressed after.
- M7, pip installs: Windows shows the name and icon from a Start menu shortcut carrying the app ID (the installer
  makes one). Without it, call `wintoast.register_app_id(APP_USER_MODEL_ID, "Chatmon", icon)` at start when not
  frozen (`not getattr(sys, "frozen", False)`). `icon` is a .png or .ico path. No icon file ships in the package
  today (`packaging/icons/` isn't package data): M6A could add one, or it can be left out.

### wincaret.py (M7, M1B)

- `wincaret.magnifier_running() -> bool`, `wincaret.place(hwnd, x, y, width, height) -> bool`, `wincaret.clear()`.
- M1B: an option, for example `accessibility.magnifier_follows = true`. It does nothing unless Magnifier is running.
- M7: when a bubble shows on Windows, the option is on, `magnifier_running()` is true and the ask box doesn't have
  focus, call `place(stage hwnd, bubble rectangle)`. The rectangle is in the stage window's own pixels: Qt's logical
  coordinates times `devicePixelRatio()`. Call `clear()` when the bubble closes, and before the ask box takes focus.

### winrt.py and winfocus.py

`winfocus.py`'s API (`manager`, `is_active`, `Focus`) is unchanged; it now uses the shared helpers in `winrt.py`,
which nothing outside this milestone needs to call.

### CI (M6A)

- Add `xvfb libxtst6` to the Linux job's packages: `tests/test_hotkey.py`'s X11 test skips without Xvfb.
- `tests/test_hotkey_portal.py` needs `dbus-run-session` and `dbus-monitor` (Ubuntu's `dbus-bin`, which
  `test_portal_bus.py` already relies on for the first).
- The Windows runner is where a toast can be seen landing in Action Center (notifications are off on the PC this was
  built on); the macOS runner runs the Carbon and NSSound tests. Both are pending until the branch is pushed.

## Changelog notes

For the 0.10.0 entry, once M7 has wired these in:

- A shortcut opens the ask box from any app: Ctrl+Alt+Space, or one you choose in Settings. On Wayland your desktop
  asks you first, where it lets apps have shortcuts (KDE Plasma, GNOME 48 and later, Hyprland). Elsewhere, set one in
  your desktop's keyboard settings that runs `chatmon ask`.
- Sounds: something needing you, a reminder and the end of a focus session each have a short sound. An agent
  finishing, a success, an error and a soft pop for other bubbles can be turned on too. Each has its own switch, there's
  a volume, one switch turns them all off, and nothing sounds during Do Not Disturb, Focus or a full-screen app.
- On Windows, Chatmon's notifications are Windows' own: they carry buttons, wait in Action Center, and follow Do Not
  Disturb and Focus. A reminder stays on screen until you answer it.
- Windows Magnifier pans to a new bubble (a setting under Accessibility).

## README notes

- Features: the global shortcut, the sounds, Windows notifications with buttons, and Magnifier following bubbles.
- Linux: the shortcut on Wayland needs a desktop with the GlobalShortcuts portal; on X11 it works everywhere. Sound
  uses QtMultimedia where it's installed (Debian and Ubuntu package it as `python3-pyqt6.qtmultimedia`), else
  pw-play, paplay or canberra-gtk-play.
- macOS: the shortcut needs no Accessibility permission.
- Privacy: nothing here leaves the computer. If M7 calls `register_app_id` for pip installs, the README should say
  that Chatmon writes its name (and icon) under `HKEY_CURRENT_USER\Software\Classes\AppUserModelId` so Windows can
  show its notifications.

```quality-ledger
{
  "schema_version": 1,
  "work": {
    "id": "M4B",
    "title": "Hotkey, sound and Windows notifications",
    "scope_revision": 3,
    "brief": "docs/delivery/ASSESSMENT.md",
    "brief_reason": null,
    "rules": [
      {
        "path": "docs/delivery/ROADMAP.md",
        "revision": "5346385"
      },
      {
        "path": "pyproject.toml",
        "revision": "5346385"
      }
    ],
    "inputs": [
      "tests/conftest.py",
      "tests/drills/run.py"
    ],
    "environment": {
      "platform": "windows",
      "tools": {
        "python": "3.14.10",
        "pyqt6": "6.11.0",
        "pytest": "9.2.0",
        "ruff": "0.17.4"
      }
    }
  },
  "requirements": [
    {
      "id": "M4B-01",
      "statement": "hotkey.py registers a configurable global shortcut: RegisterHotKey on its own message-only window (Windows), RegisterEventHotKey (macOS), XGrabKey (X11), the GlobalShortcuts portal (Wayland), and reports a failure to register such as a conflict",
      "priority": "normal",
      "acceptance": [
        "AC-01A",
        "AC-01B",
        "AC-01C",
        "AC-01D",
        "AC-01E",
        "AC-01F"
      ],
      "superseded_by": null
    },
    {
      "id": "M4B-02",
      "statement": "sound.py plays the packaged cues with QSoundEffect when QtMultimedia is present, else PlaySound (Windows), NSSound (macOS), pw-play, paplay or canberra-gtk-play (Linux); silent during quiet times; a volume setting; every cue can be turned on or off; never blocks the screen's thread",
      "priority": "normal",
      "acceptance": [
        "AC-02A",
        "AC-02B",
        "AC-02C",
        "AC-02D",
        "AC-02E",
        "AC-02F"
      ],
      "superseded_by": null
    },
    {
      "id": "M4B-03",
      "statement": "WinRT toasts through combase carry action buttons and the reminder scenario, using the existing app ID, report activation back, and leave the tray balloon as the fallback",
      "priority": "normal",
      "acceptance": [
        "AC-03A",
        "AC-03B",
        "AC-03C",
        "AC-03D",
        "AC-03E"
      ],
      "superseded_by": null
    },
    {
      "id": "M4B-04",
      "statement": "As an option, the system caret is placed on the stage window at a new bubble, so Magnifier pans to it",
      "priority": "normal",
      "acceptance": [
        "AC-04A",
        "AC-04B"
      ],
      "superseded_by": null
    },
    {
      "id": "M4B-00",
      "statement": "Every module this milestone adds or changes imports safely on every OS",
      "priority": "normal",
      "acceptance": [
        "AC-00A",
        "AC-00B",
        "AC-00C"
      ],
      "superseded_by": null
    }
  ],
  "acceptance": [
    {
      "id": "AC-00A",
      "requirement": "M4B-00",
      "given": "Windows",
      "when": "hotkey, sound, wintoast, wincaret, winrt, winfocus, libdbus and shortcutportal are each imported in a fresh interpreter",
      "then": "each imports without error, and no OS library is loaded on import",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-00B",
      "requirement": "M4B-00",
      "given": "Linux",
      "when": "the same modules are each imported in a fresh interpreter",
      "then": "each imports without error",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-00C",
      "requirement": "M4B-00",
      "given": "macOS",
      "when": "the same modules are each imported in a fresh interpreter",
      "then": "each imports without error",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-01A",
      "requirement": "M4B-01",
      "given": "a portable sequence such as 'Ctrl+Alt+Space', 'meta+shift+f5' or a malformed one",
      "when": "hotkey.parse reads it",
      "then": "it gives the modifiers and key in canonical form, or a ValueError with a readable sentence for an empty sequence, an unknown key or modifier, two keys, or a typing key without Ctrl, Alt or Meta (F13-F24 may stand alone)",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-01B",
      "requirement": "M4B-01",
      "given": "Windows and an unusual combination (Ctrl+Alt+Shift+F24)",
      "when": "it is registered, WM_HOTKEY reaches its message-only window, and it is unregistered",
      "then": "registration succeeds on a message-only window, the callback runs once through Qt's native event filter, and after unregistering the combination is free for anyone",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-01C",
      "requirement": "M4B-01",
      "given": "a combination another registration already holds",
      "when": "hotkey.register is asked for it, with or without a shortcut already registered",
      "then": "it returns an error sentence naming the combination, and a shortcut already registered stays registered",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-01D",
      "requirement": "M4B-01",
      "given": "macOS",
      "when": "an unusual combination is registered, a hot-key event is sent to the application target, a second exclusive registration is attempted, and it is unregistered",
      "then": "the callback runs, the conflict is reported as an error, and unregistering frees it",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-01E",
      "requirement": "M4B-01",
      "given": "an X11 server (Xvfb)",
      "when": "a combination is grabbed and pressed with XTest, with and without NumLock, and another client grabs a combination first",
      "then": "the callback runs for each press, and the combination another client holds is reported as an error",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-01F",
      "requirement": "M4B-01",
      "given": "a Wayland session with a GlobalShortcuts portal (a pretend one on a private bus), or none",
      "when": "a shortcut is registered and the portal binds it and sends Activated, or turns it down, or is missing",
      "then": "BindShortcuts carries a(sa{sv}) with the XDG trigger, Activated for this session and shortcut (and no other) runs the callback, unregistering closes the session, and a refusal or a desktop without the portal comes through failed",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-02A",
      "requirement": "M4B-02",
      "given": "QtMultimedia and the cues' WAV files",
      "when": "play(cue) is called for an enabled cue",
      "then": "that cue's file starts playing through QSoundEffect at the configured volume and play returns True at once; an unknown cue is a ValueError, a missing file plays nothing, and a sound still playing as the app quits doesn't take the process down",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-02B",
      "requirement": "M4B-02",
      "given": "a quiet time, all sound off, or that cue off",
      "when": "play(cue) is called",
      "then": "nothing plays and play returns False",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-02C",
      "requirement": "M4B-02",
      "given": "no configuration",
      "when": "the cues' switches are read",
      "then": "needs-you, reminder and focus-done are on and done, success, error and pop are off",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-02D",
      "requirement": "M4B-02",
      "given": "Windows without a usable QtMultimedia",
      "when": "a cue is played",
      "then": "PlaySound plays it on a worker thread with its samples scaled to the volume and play returns before the sound ends; with QtMultimedia missing, the system's own player is chosen",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-02E",
      "requirement": "M4B-02",
      "given": "Linux without a usable QtMultimedia, and pw-play, paplay and canberra-gtk-play installed",
      "when": "the players are chosen and a cue is played",
      "then": "pw-play is used while PipeWire runs, paplay while PulseAudio runs, canberra-gtk-play otherwise; it gets the volume and play returns before it ends",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-02F",
      "requirement": "M4B-02",
      "given": "macOS without a usable QtMultimedia",
      "when": "a cue is played",
      "then": "NSSound plays the file at the volume, and an unreadable file plays nothing",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-03A",
      "requirement": "M4B-03",
      "given": "a title, text with markup characters, buttons and a scenario",
      "when": "toast_xml builds the toast",
      "then": "the XML is well formed with the text escaped, carries up to five actions whose arguments name the toast and button, the reminder scenario (with a dismiss button when none is given), a launch argument for the toast itself, and rejects an unknown scenario",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-03B",
      "requirement": "M4B-03",
      "given": "no toast can be shown: notifications turned off, no app ID, or not Windows",
      "when": "Toaster.show is called",
      "then": "it returns None and says why, so the caller uses the tray balloon",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-03C",
      "requirement": "M4B-03",
      "given": "a posted toast",
      "when": "Windows raises Dismissed, Failed or Activated on its own thread",
      "then": "dismissed(tag, reason), failed(tag, code) and activated(tag, button) are emitted on the Qt thread, and a button's action runs there",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-03D",
      "requirement": "M4B-03",
      "given": "an app installed without a Start menu shortcut",
      "when": "register_app_id and unregister_app_id are called",
      "then": "the per-user AppUserModelId registration has the display name and icon, and is gone after",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-03E",
      "requirement": "M4B-03",
      "given": "Windows with notifications on, and the process's AppUserModelID registered",
      "when": "Toaster.show is called, then hide",
      "then": "the toast is in Windows' history under the app ID with its tag, hiding it brings Dismissed(HIDDEN_BY_CHATMON) on the Qt thread, and nothing is left in the history after",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-04A",
      "requirement": "M4B-04",
      "given": "a window on Chatmon's thread",
      "when": "wincaret.place is called with a bubble's rectangle, then clear",
      "then": "the thread's caret is on that window at that rectangle, hidden, the caret location event Magnifier follows is raised for it, and clear removes the caret",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-04B",
      "requirement": "M4B-04",
      "given": "Magnifier's window present or absent",
      "when": "magnifier_running is asked",
      "then": "it says whether Magnifier is running",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    }
  ],
  "tasks": [
    {
      "id": "T-WINRT",
      "purpose": "Share winfocus.py's WinRT helpers in winrt.py, adding HSTRINGs, instances, interface queries and an agile delegate; winfocus.py uses them",
      "acceptance": [
        "AC-03C"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/winrt.py",
          "action": "create"
        },
        {
          "path": "chatmon/winfocus.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-WIN-TESTS",
        "EV-RED-D-03C-qt-thread",
        "EV-RED-D-03C-button",
        "EV-RED-D-03C-action"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-TOAST",
      "purpose": "WinRT toasts with buttons, scenarios and events, the balloon fallback, the app ID registration, and their tests",
      "acceptance": [
        "AC-03A",
        "AC-03B",
        "AC-03C",
        "AC-03D"
      ],
      "depends_on": [
        "T-WINRT"
      ],
      "changes": [
        {
          "path": "chatmon/wintoast.py",
          "action": "create"
        },
        {
          "path": "tests/test_wintoast.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-WIN-TESTS",
        "EV-RED-D-03A-escaped",
        "EV-RED-D-03A-control-chars",
        "EV-RED-D-03A-reminder-button",
        "EV-RED-D-03A-five-buttons",
        "EV-RED-D-03B-setting",
        "EV-RED-D-03C-qt-thread",
        "EV-RED-D-03C-button",
        "EV-RED-D-03C-action",
        "EV-RED-D-03D-icon"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-TOAST-SHOWN",
      "purpose": "A toast Windows shows (notifications on): in Action Center under its tag, hidden, cleared",
      "acceptance": [
        "AC-03E"
      ],
      "depends_on": [
        "T-TOAST"
      ],
      "changes": [
        {
          "path": "chatmon/wintoast.py",
          "action": "modify"
        },
        {
          "path": "tests/test_wintoast.py",
          "action": "modify"
        }
      ],
      "status": "implemented",
      "evidence": [
        "EV-CI-WINDOWS-TOASTS"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-CARET",
      "purpose": "The system caret for Magnifier, and its tests",
      "acceptance": [
        "AC-04A",
        "AC-04B"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/wincaret.py",
          "action": "create"
        },
        {
          "path": "tests/test_wincaret.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-WIN-TESTS",
        "EV-RED-D-04A-position",
        "EV-RED-D-04A-bubble-size",
        "EV-RED-D-04A-cleared",
        "EV-RED-D-04B-magnifier"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-SOUND",
      "purpose": "Cues, switches, volume, quiet times, QSoundEffect, PlaySound and choosing a player, and their tests",
      "acceptance": [
        "AC-02A",
        "AC-02B",
        "AC-02C",
        "AC-02D"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/sound.py",
          "action": "create"
        },
        {
          "path": "tests/test_sound.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-WIN-TESTS",
        "EV-RED-D-02A-volume",
        "EV-RED-D-02A-plays",
        "EV-RED-D-02B-quiet",
        "EV-RED-D-02B-one-switch",
        "EV-RED-D-02B-cue-off",
        "EV-RED-D-02C-defaults",
        "EV-RED-D-02D-own-thread",
        "EV-RED-D-02A-stopped-at-exit",
        "EV-RED-D-02D-scaled",
        "EV-RED-D-02D-without-qt"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-SOUND-LINUX",
      "purpose": "The Linux players, chosen by the sound server running",
      "acceptance": [
        "AC-02E"
      ],
      "depends_on": [
        "T-SOUND"
      ],
      "changes": [
        {
          "path": "chatmon/sound.py",
          "action": "modify"
        },
        {
          "path": "tests/test_sound.py",
          "action": "modify"
        }
      ],
      "status": "implemented",
      "evidence": [
        "EV-WSL-TESTS",
        "EV-RED-L-02D-linux-player"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-SOUND-MAC",
      "purpose": "NSSound through the Objective-C runtime",
      "acceptance": [
        "AC-02F"
      ],
      "depends_on": [
        "T-SOUND"
      ],
      "changes": [
        {
          "path": "chatmon/sound.py",
          "action": "modify"
        },
        {
          "path": "tests/test_sound.py",
          "action": "modify"
        }
      ],
      "status": "implemented",
      "evidence": [
        "EV-CI-MACOS"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-HOTKEY",
      "purpose": "Sequence parsing, the Hotkey object and the Windows backend, with tests",
      "acceptance": [
        "AC-01A",
        "AC-01B",
        "AC-01C"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/hotkey.py",
          "action": "create"
        },
        {
          "path": "tests/test_hotkey.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-WIN-TESTS",
        "EV-RED-D-01A-alone",
        "EV-RED-D-01A-order",
        "EV-RED-D-01B-message-only",
        "EV-RED-D-01B-filter",
        "EV-RED-D-01B-its-own-id",
        "EV-RED-D-01B-given-back",
        "EV-RED-D-01C-conflict",
        "EV-RED-D-01C-keeps-old"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-HOTKEY-MAC",
      "purpose": "Carbon's RegisterEventHotKey backend",
      "acceptance": [
        "AC-01D"
      ],
      "depends_on": [
        "T-HOTKEY"
      ],
      "changes": [
        {
          "path": "chatmon/hotkey.py",
          "action": "modify"
        },
        {
          "path": "tests/test_hotkey.py",
          "action": "modify"
        }
      ],
      "status": "implemented",
      "evidence": [
        "EV-CI-MACOS"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-HOTKEY-X11",
      "purpose": "The XGrabKey backend",
      "acceptance": [
        "AC-01E"
      ],
      "depends_on": [
        "T-HOTKEY"
      ],
      "changes": [
        {
          "path": "chatmon/hotkey.py",
          "action": "modify"
        },
        {
          "path": "tests/test_hotkey.py",
          "action": "modify"
        }
      ],
      "status": "implemented",
      "evidence": [
        "EV-WSL-TESTS",
        "EV-RED-L-01E-numlock",
        "EV-RED-L-01E-conflict"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-PORTAL",
      "purpose": "libdbus through ctypes, the GlobalShortcuts portal backend, a pretend portal, and tests",
      "acceptance": [
        "AC-01F"
      ],
      "depends_on": [
        "T-HOTKEY"
      ],
      "changes": [
        {
          "path": "chatmon/libdbus.py",
          "action": "create"
        },
        {
          "path": "chatmon/shortcutportal.py",
          "action": "create"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "action": "create"
        },
        {
          "path": "tests/test_hotkey_portal.py",
          "action": "create"
        }
      ],
      "status": "implemented",
      "evidence": [
        "EV-WSL-TESTS",
        "EV-RED-D-01F-trigger",
        "EV-RED-L-01F-its-own-session",
        "EV-RED-L-01F-response",
        "EV-RED-L-01F-carries-on",
        "EV-RED-L-01F-no-portal"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-IMPORTS",
      "purpose": "A test that imports every module of this milestone in a fresh interpreter",
      "acceptance": [
        "AC-00A"
      ],
      "depends_on": [
        "T-WINRT",
        "T-TOAST",
        "T-CARET",
        "T-SOUND",
        "T-HOTKEY"
      ],
      "changes": [
        {
          "path": "tests/test_m4b_imports.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-WIN-TESTS",
        "EV-RED-D-00A-lazy-library",
        "EV-RED-D-00A-eager-objc"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-IMPORTS-POSIX",
      "purpose": "The same imports on Linux and macOS",
      "acceptance": [
        "AC-00B",
        "AC-00C"
      ],
      "depends_on": [
        "T-IMPORTS"
      ],
      "changes": [
        {
          "path": "tests/test_m4b_imports.py",
          "action": "modify"
        }
      ],
      "status": "implemented",
      "evidence": [
        "EV-WSL-TESTS",
        "EV-CI-MACOS",
        "EV-RED-L-00B-eager-objc"
      ],
      "blocker": null,
      "superseded_by": null
    }
  ],
  "evidence": [
    {
      "id": "EV-READY-1",
      "acceptance": [
        "AC-00A",
        "AC-01A",
        "AC-01B",
        "AC-01C",
        "AC-01D",
        "AC-01E",
        "AC-01F",
        "AC-02A",
        "AC-02B",
        "AC-02C",
        "AC-02D",
        "AC-03A",
        "AC-03B",
        "AC-03C",
        "AC-03D",
        "AC-04A",
        "AC-04B"
      ],
      "kind": "readiness",
      "status": "stale",
      "command": [],
      "method": "Requirements review of the M4B plan against the assessment's M4B section, the roadmap's owner decisions, file ownership and M4B/M7 contract, and the code at 5346385; findings and resolutions in the artifact, with probes in probes.md",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m4b/readiness.md",
        "sha256": "00fa25945471fc475f56ff0761f81cd2a8b11ae6f3069d4c8ea691a420a5e0c7"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        }
      ],
      "scope_sha256": "91ca3fe9085fbe914e4c9c06ccbf8f835522fe25732577e333525ad57eec5c10",
      "red": null,
      "reason": "Scope revisions 2 and 3 changed AC-01F and split the per-platform criteria; superseded by EV-READY-2, a re-review of the same report's revision sections"
    },
    {
      "id": "EV-READY-2",
      "acceptance": [
        "AC-00A",
        "AC-00B",
        "AC-00C",
        "AC-01A",
        "AC-01B",
        "AC-01C",
        "AC-01D",
        "AC-01E",
        "AC-01F",
        "AC-02A",
        "AC-02B",
        "AC-02C",
        "AC-02D",
        "AC-02E",
        "AC-02F",
        "AC-03A",
        "AC-03B",
        "AC-03C",
        "AC-03D",
        "AC-03E",
        "AC-04A",
        "AC-04B"
      ],
      "kind": "readiness",
      "status": "pass",
      "command": [],
      "method": "Re-review of the requirements after scope revisions 2 and 3 (AC-01F's later failures, the portal client's own file, the per-platform split of AC-00A, AC-02D and AC-03B), recorded in the readiness report's revision sections",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m4b/readiness.md",
        "sha256": "edd4325e5f97f78e0caa7e33058b480850a25e277e5b25e937243037795fe783"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        }
      ],
      "scope_sha256": "cefc23c4fa8b4a74942cbf31eecca9a99992b515384713eb574bd02ac2d51b18",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-WIN-TESTS",
      "acceptance": [
        "AC-00A",
        "AC-01A",
        "AC-01B",
        "AC-01C",
        "AC-02A",
        "AC-02B",
        "AC-02C",
        "AC-02D",
        "AC-03A",
        "AC-03B",
        "AC-03C",
        "AC-03D",
        "AC-04A",
        "AC-04B"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_hotkey.py",
        "tests/test_hotkey_portal.py",
        "tests/test_sound.py",
        "tests/test_wintoast.py",
        "tests/test_wincaret.py",
        "tests/test_m4b_imports.py",
        "tests/test_presence.py"
      ],
      "method": "This milestone's tests and test_presence.py (winfocus) on Windows 11 under the offscreen platform at ea3474f: real RegisterHotKey, WinRT toasts, system caret, QSoundEffect and PlaySound; 70 passed, 15 skipped (other platforms' tests)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/m4b-tests-windows.txt",
        "sha256": "de5b45b3c0c138f8dcae36548d15031a628b7556e6010d73374420067b0c23c2"
      },
      "inputs": [
        {
          "path": "chatmon/hotkey.py",
          "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "a570924028029e6adbab036e623dee3448db04bd3014750e0cf4cc463de7575d"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "23ef764c87a6330410f9bbe499d253f8dc7d556fab3f0bceffbfbfcbeb89dbc8"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "c6a2ca98f0b623fd1df9a7afa5bab9b0c0cc39bffb893875bc58d5bfd8565bcd"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "eabc59fb1a0fa48201237e6b1f83c32f91f75f221d7f97e4cebafb401aff40f6"
        },
        {
          "path": "tests/test_m4b_imports.py",
          "sha256": "03bb2bb4a5fb34b628073875f153dfa9cd878ec21c7af0b0a8140b03f7809a64"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "99013b3e64dee7b2eec0cf180e6013a72caf169844ebadefbcb6bcea06139788"
        },
        {
          "path": "tests/test_wincaret.py",
          "sha256": "0c1ed4dde60d30937d948de00f5914e2d9b1793ef2b8622b0867d2e5d871d191"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "0c02f2a01dd40ac45f305e04578df6effa1b049d9b1f7f20b208bc61227152d2"
        }
      ],
      "scope_sha256": "e3989a800e733c825082281850c9911080284c1636395142f44ace610ccd08e5",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-WSL-TESTS",
      "acceptance": [
        "AC-00B",
        "AC-01E",
        "AC-01F",
        "AC-02E"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "env",
        "-u",
        "WAYLAND_DISPLAY",
        "QT_QPA_PLATFORM=offscreen",
        "python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_hotkey.py",
        "tests/test_hotkey_portal.py",
        "tests/test_sound.py",
        "tests/test_wintoast.py",
        "tests/test_wincaret.py",
        "tests/test_m4b_imports.py"
      ],
      "method": "The same tests on Linux (WSL 2, Arch Linux, kernel 6.18) at ea3474f: XGrabKey on a private Xvfb with XTest presses, the portal against tests/fake_shortcuts_portal.py on a dbus-run-session bus with dbus-monitor, the Linux players with stand-in commands, real QSoundEffect, and the imports; 62 passed, 14 skipped (Windows and macOS tests)",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pyqt6": "6.12.1",
          "pytest": "9.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/m4b-tests-wsl.txt",
        "sha256": "e6a2841354efb24a151494b3290dd2e6f1dbc052054da443f9207943518a41ba"
      },
      "inputs": [
        {
          "path": "chatmon/hotkey.py",
          "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "d591a04ac51df633e667d23f9ee6fb8bc96318a7c38dab75b7e0dc6830501a43"
        },
        {
          "path": "chatmon/shortcutportal.py",
          "sha256": "12ce92b60dce230959d4db70864a342a7862d22bf0d035a7cb049d2a8dc1b343"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "a570924028029e6adbab036e623dee3448db04bd3014750e0cf4cc463de7575d"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "23ef764c87a6330410f9bbe499d253f8dc7d556fab3f0bceffbfbfcbeb89dbc8"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "c6a2ca98f0b623fd1df9a7afa5bab9b0c0cc39bffb893875bc58d5bfd8565bcd"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "1a13ed68d62f9a44dd3ad140da5e7a0e4cf84d13931c1516e3475a347512d6e7"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "eabc59fb1a0fa48201237e6b1f83c32f91f75f221d7f97e4cebafb401aff40f6"
        },
        {
          "path": "tests/test_hotkey_portal.py",
          "sha256": "3b1e7969599e80972fb600806916c1140b96ed69dbf9245a2bf6f982feb65ccf"
        },
        {
          "path": "tests/test_m4b_imports.py",
          "sha256": "03bb2bb4a5fb34b628073875f153dfa9cd878ec21c7af0b0a8140b03f7809a64"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "99013b3e64dee7b2eec0cf180e6013a72caf169844ebadefbcb6bcea06139788"
        },
        {
          "path": "tests/test_wincaret.py",
          "sha256": "0c1ed4dde60d30937d948de00f5914e2d9b1793ef2b8622b0867d2e5d871d191"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "0c02f2a01dd40ac45f305e04578df6effa1b049d9b1f7f20b208bc61227152d2"
        }
      ],
      "scope_sha256": "4848d3e1dd4288ea6f9ebcef5faa34e5b084f33d86074534f97671037bdbf5a6",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-CI-MACOS",
      "acceptance": [
        "AC-00C",
        "AC-01D",
        "AC-02F"
      ],
      "kind": "behavior",
      "status": "deferred",
      "command": [
        "python",
        "-m",
        "pytest",
        "-q",
        "tests/test_hotkey.py",
        "tests/test_sound.py",
        "tests/test_m4b_imports.py"
      ],
      "method": "To run on CI's macOS runner: the Carbon hotkey tests, NSSound, and the imports; macOS code can't run on this PC",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": null,
      "artifact": null,
      "inputs": [],
      "scope_sha256": "9b51b25091167c5fcab2c0f53f41dc96d016e3adceade7e7bed6156fb61f1c79",
      "red": null,
      "reason": "No macOS here. Next: the coordinator pushes the merged branch; CI's macOS job runs these, and failures come back to M4B."
    },
    {
      "id": "EV-CI-WINDOWS-TOASTS",
      "acceptance": [
        "AC-03E"
      ],
      "kind": "behavior",
      "status": "deferred",
      "command": [
        "python",
        "-m",
        "pytest",
        "-q",
        "tests/test_wintoast.py"
      ],
      "method": "To run on CI's Windows runner, where notifications are on: a toast lands in the history under its tag and is hidden and cleared",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": null,
      "artifact": null,
      "inputs": [],
      "scope_sha256": "a9e37d85abb8b607cbf1c996131ad96bc3ecd0fc5bd62d47167c5f7e299a8a55",
      "red": null,
      "reason": "Notifications are turned off for this PC's user (ToastEnabled = 0), which isn't this milestone's to change. Next: CI's Windows job runs the notifications-on branch of the same tests."
    },
    {
      "id": "EV-RED-D-00A-lazy-library",
      "acceptance": [
        "AC-00A"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of tests/test_m4b_imports.py with libdbus.py loading its library on import",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": null
      },
      "inputs": [],
      "scope_sha256": "e3989a800e733c825082281850c9911080284c1636395142f44ace610ccd08e5",
      "red": null,
      "reason": "The drill passed, but libdbus.py is T-PORTAL's file, outside AC-00A's bound inputs, so the ledger can't hold it to the current source; EV-RED-D-00A-eager-objc drills the same defect in sound.py, which is bound. Kept as history."
    },
    {
      "id": "EV-RED-D-01A-alone",
      "acceptance": [
        "AC-01A"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_hotkey.py::test_what_isnt_a_shortcut_says_why with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/hotkey.py",
          "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "eabc59fb1a0fa48201237e6b1f83c32f91f75f221d7f97e4cebafb401aff40f6"
        }
      ],
      "scope_sha256": "7e6c16b5ebc057c09522740f432cd98e6dbe6659de1684625930f7ac4f75ebbc",
      "red": {
        "mutation": "chatmon/hotkey.py: 'and key not in ALONE:' -> 'and key in ALONE:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_what_isnt_a_shortcut_says_why",
        "observed_diagnostic": "__________ test_what_isnt_a_shortcut_says_why[A-would take that key] __________",
        "before": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "acc3fe6fe7e94758e26e06e07490a743e60842fb61fc70b8c1d9645d59434165"
          }
        ],
        "after": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-01A-order",
      "acceptance": [
        "AC-01A"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_hotkey.py::test_a_shortcut_is_read_as_qt_writes_it with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/hotkey.py",
          "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "eabc59fb1a0fa48201237e6b1f83c32f91f75f221d7f97e4cebafb401aff40f6"
        }
      ],
      "scope_sha256": "7e6c16b5ebc057c09522740f432cd98e6dbe6659de1684625930f7ac4f75ebbc",
      "red": {
        "mutation": "chatmon/hotkey.py: '[MODIFIER_NAMES[m] for m in MODIFIERS if m in self.modifiers]' -> '[MODIFIER_NAMES[m] for m in sorted(self.modifiers)]'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_shortcut_is_read_as_qt_writes_it",
        "observed_diagnostic": "___ test_a_shortcut_is_read_as_qt_writes_it[Ctrl+Alt+Space-Ctrl+Alt+Space] ____",
        "before": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "bfb16a851dd659d00aafb94c35b7c3f8ddc8a2153ed57eb8edc90bc6d099fca2"
          }
        ],
        "after": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-01B-message-only",
      "acceptance": [
        "AC-01B"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_hotkey.py::test_windows_registers_it_on_a_message_only_window_and_hears_it with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/hotkey.py",
          "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "eabc59fb1a0fa48201237e6b1f83c32f91f75f221d7f97e4cebafb401aff40f6"
        }
      ],
      "scope_sha256": "7e6c16b5ebc057c09522740f432cd98e6dbe6659de1684625930f7ac4f75ebbc",
      "red": {
        "mutation": "chatmon/hotkey.py: 'HWND_MESSAGE = -3' -> 'HWND_MESSAGE = 0'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_windows_registers_it_on_a_message_only_window_and_hears_it",
        "observed_diagnostic": "_______ test_windows_registers_it_on_a_message_only_window_and_hears_it _______",
        "before": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "2dee667e4b3b8b9cb358b918eee64065c88d5ce7f781cc303f3c37df59899a49"
          }
        ],
        "after": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-01B-filter",
      "acceptance": [
        "AC-01B"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_hotkey.py::test_windows_registers_it_on_a_message_only_window_and_hears_it with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/hotkey.py",
          "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "eabc59fb1a0fa48201237e6b1f83c32f91f75f221d7f97e4cebafb401aff40f6"
        }
      ],
      "scope_sha256": "7e6c16b5ebc057c09522740f432cd98e6dbe6659de1684625930f7ac4f75ebbc",
      "red": {
        "mutation": "chatmon/hotkey.py: 'msg.message == self.WM_HOTKEY' -> 'msg.message == self.WM_HOTKEY + 1'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_windows_registers_it_on_a_message_only_window_and_hears_it",
        "observed_diagnostic": "_______ test_windows_registers_it_on_a_message_only_window_and_hears_it _______",
        "before": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "081bca29c205039a0557d7df21e320a613834cbd6755bd3f6cf30bfb39aa5a83"
          }
        ],
        "after": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-01B-its-own-id",
      "acceptance": [
        "AC-01B"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_hotkey.py::test_windows_registers_it_on_a_message_only_window_and_hears_it with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/hotkey.py",
          "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "eabc59fb1a0fa48201237e6b1f83c32f91f75f221d7f97e4cebafb401aff40f6"
        }
      ],
      "scope_sha256": "7e6c16b5ebc057c09522740f432cd98e6dbe6659de1684625930f7ac4f75ebbc",
      "red": {
        "mutation": "chatmon/hotkey.py: 'msg.wParam == self.id' -> 'msg.wParam >= self.id'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert [True, True] == [True]",
        "observed_diagnostic": "E           assert [True, True] == [True]",
        "before": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "b66d78a5eae14338c413a070a579ca74929495af187c19412e1fac4cc87fc3ac"
          }
        ],
        "after": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-01B-given-back",
      "acceptance": [
        "AC-01B"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_hotkey.py::test_windows_registers_it_on_a_message_only_window_and_hears_it with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/hotkey.py",
          "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "eabc59fb1a0fa48201237e6b1f83c32f91f75f221d7f97e4cebafb401aff40f6"
        }
      ],
      "scope_sha256": "7e6c16b5ebc057c09522740f432cd98e6dbe6659de1684625930f7ac4f75ebbc",
      "red": {
        "mutation": "chatmon/hotkey.py: '            self._user32.UnregisterHotKey(self.hwnd, self.id)\\n' -> '            pass\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_windows_registers_it_on_a_message_only_window_and_hears_it",
        "observed_diagnostic": "_______ test_windows_registers_it_on_a_message_only_window_and_hears_it _______",
        "before": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "4223bc2ea8c58c909a40ca7101635aaa9dcdc05c1e3dcf2340cd5a6e4322b554"
          }
        ],
        "after": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-01C-conflict",
      "acceptance": [
        "AC-01C"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_hotkey.py::test_windows_reports_a_conflict_and_keeps_the_shortcut_it_had with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/hotkey.py",
          "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "eabc59fb1a0fa48201237e6b1f83c32f91f75f221d7f97e4cebafb401aff40f6"
        }
      ],
      "scope_sha256": "7e6c16b5ebc057c09522740f432cd98e6dbe6659de1684625930f7ac4f75ebbc",
      "red": {
        "mutation": "chatmon/hotkey.py: 'if error == self.ERROR_HOTKEY_ALREADY_REGISTERED:' -> 'if error != self.ERROR_HOTKEY_ALREADY_REGISTERED:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "wouldn't set up Ctrl+Alt+Shift+F23",
        "observed_diagnostic": "E             + Windows wouldn't set up Ctrl+Alt+Shift+F23 (error 1409).",
        "before": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "86c1940f677fc3a439652056bc609f9905a5d0961961c7a89af6661e61d2fee8"
          }
        ],
        "after": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-01C-keeps-old",
      "acceptance": [
        "AC-01C"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_hotkey.py::test_windows_reports_a_conflict_and_keeps_the_shortcut_it_had with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/hotkey.py",
          "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "eabc59fb1a0fa48201237e6b1f83c32f91f75f221d7f97e4cebafb401aff40f6"
        }
      ],
      "scope_sha256": "7e6c16b5ebc057c09522740f432cd98e6dbe6659de1684625930f7ac4f75ebbc",
      "red": {
        "mutation": "chatmon/hotkey.py: '        new_id = 2 if self.id == 1 else 1  # the old one stays until the new one is in\\n' -> '        self.release()\\n        new_id = 2 if self.id == 1 else 1\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_windows_reports_a_conflict_and_keeps_the_shortcut_it_had",
        "observed_diagnostic": "________ test_windows_reports_a_conflict_and_keeps_the_shortcut_it_had ________",
        "before": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "e7c1debe61b9083537fcf29561a92eae5ba6602c13f52cbd734c1c397c5f3bd1"
          }
        ],
        "after": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-02A-volume",
      "acceptance": [
        "AC-02A"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_sound.py::test_qsoundeffect_plays_it_without_waiting with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/sound.py",
          "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "99013b3e64dee7b2eec0cf180e6013a72caf169844ebadefbcb6bcea06139788"
        }
      ],
      "scope_sha256": "ce18af96abe40aa0a6bc1ae88429cfb59f9973db018fee215ba5c884c3b90773",
      "red": {
        "mutation": "chatmon/sound.py: '        effect.setVolume(volume)\\n' -> '        effect.setVolume(1.0)\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_qsoundeffect_plays_it_without_waiting",
        "observed_diagnostic": "_________________ test_qsoundeffect_plays_it_without_waiting __________________",
        "before": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sound.py",
            "sha256": "65ec0905b9ce7073b8355223994ad31d6084bc7e9f967585fca62d3a9e4cf34e"
          }
        ],
        "after": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-02A-plays",
      "acceptance": [
        "AC-02A"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_sound.py::test_qsoundeffect_plays_it_without_waiting with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/sound.py",
          "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "99013b3e64dee7b2eec0cf180e6013a72caf169844ebadefbcb6bcea06139788"
        }
      ],
      "scope_sha256": "ce18af96abe40aa0a6bc1ae88429cfb59f9973db018fee215ba5c884c3b90773",
      "red": {
        "mutation": "chatmon/sound.py: '        effect.play()\\n' -> '        effect.stop()\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "never played",
        "observed_diagnostic": ">       assert True in playing or effect.isPlaying(), f\"never played (status {effect.status()})\"",
        "before": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sound.py",
            "sha256": "bbb1c31168828c2047b4370a168f19e47f4edc3aa33658bb37c7b4a1fdc16d57"
          }
        ],
        "after": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-02B-quiet",
      "acceptance": [
        "AC-02B"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_sound.py::test_nothing_sounds_when_it_shouldnt with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/sound.py",
          "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "99013b3e64dee7b2eec0cf180e6013a72caf169844ebadefbcb6bcea06139788"
        }
      ],
      "scope_sha256": "ce18af96abe40aa0a6bc1ae88429cfb59f9973db018fee215ba5c884c3b90773",
      "red": {
        "mutation": "chatmon/sound.py: 'if self._quiet is not None and self._quiet():' -> 'if self._quiet is not None and not self._quiet():'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_nothing_sounds_when_it_shouldnt",
        "observed_diagnostic": "____________________ test_nothing_sounds_when_it_shouldnt _____________________",
        "before": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sound.py",
            "sha256": "7c329a38a362c62402e4d8d832c56caad8f180ab93b7107fe6ff129ea9119abd"
          }
        ],
        "after": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-02B-one-switch",
      "acceptance": [
        "AC-02B"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_sound.py::test_nothing_sounds_when_it_shouldnt with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/sound.py",
          "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "99013b3e64dee7b2eec0cf180e6013a72caf169844ebadefbcb6bcea06139788"
        }
      ],
      "scope_sha256": "ce18af96abe40aa0a6bc1ae88429cfb59f9973db018fee215ba5c884c3b90773",
      "red": {
        "mutation": "chatmon/sound.py: 'if not (self.enabled and self.cues[cue] and self.volume > 0):' -> 'if not (self.cues[cue] and self.volume > 0):'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_nothing_sounds_when_it_shouldnt",
        "observed_diagnostic": "____________________ test_nothing_sounds_when_it_shouldnt _____________________",
        "before": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sound.py",
            "sha256": "dd9477834fbfba5d6f70d9a767000994f774989ee1e530ff34694ee428ec0b22"
          }
        ],
        "after": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-02B-cue-off",
      "acceptance": [
        "AC-02B"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_sound.py::test_nothing_sounds_when_it_shouldnt with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/sound.py",
          "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "99013b3e64dee7b2eec0cf180e6013a72caf169844ebadefbcb6bcea06139788"
        }
      ],
      "scope_sha256": "ce18af96abe40aa0a6bc1ae88429cfb59f9973db018fee215ba5c884c3b90773",
      "red": {
        "mutation": "chatmon/sound.py: 'if not (self.enabled and self.cues[cue] and self.volume > 0):' -> 'if not (self.enabled and self.volume > 0):'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_nothing_sounds_when_it_shouldnt",
        "observed_diagnostic": "____________________ test_nothing_sounds_when_it_shouldnt _____________________",
        "before": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sound.py",
            "sha256": "2f978ab1d2b34b786a175ebe2668d4233bbcab21a5f9d1d488e7b6c7860fe674"
          }
        ],
        "after": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-02C-defaults",
      "acceptance": [
        "AC-02C"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_sound.py::test_only_the_alerts_sound_until_you_turn_the_others_on with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/sound.py",
          "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "99013b3e64dee7b2eec0cf180e6013a72caf169844ebadefbcb6bcea06139788"
        }
      ],
      "scope_sha256": "ce18af96abe40aa0a6bc1ae88429cfb59f9973db018fee215ba5c884c3b90773",
      "red": {
        "mutation": "chatmon/sound.py: 'ON_BY_DEFAULT = frozenset({\"needs-you\", \"reminder\", \"focus-done\"})' -> 'ON_BY_DEFAULT = frozenset({\"needs-you\", \"reminder\", \"focus-done\", \"pop\"})'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_only_the_alerts_sound_until_you_turn_the_others_on",
        "observed_diagnostic": "___________ test_only_the_alerts_sound_until_you_turn_the_others_on ___________",
        "before": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sound.py",
            "sha256": "2728e73fdaee9871a03d2a3e58ac593adc8039009e578b55fa8feb9ec199ee5e"
          }
        ],
        "after": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-02D-own-thread",
      "acceptance": [
        "AC-02D"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_sound.py::test_playsound_plays_on_its_own_thread with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/sound.py",
          "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "99013b3e64dee7b2eec0cf180e6013a72caf169844ebadefbcb6bcea06139788"
        }
      ],
      "scope_sha256": "ce18af96abe40aa0a6bc1ae88429cfb59f9973db018fee215ba5c884c3b90773",
      "red": {
        "mutation": "chatmon/sound.py: '        self._queue.put(data)\\n        return True\\n' -> '        import winsound\\n        winsound.PlaySound(data, winsound.SND_MEMORY | winsound.SND_NODEFAULT)\\n        return True\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_playsound_plays_on_its_own_thread",
        "observed_diagnostic": "___________________ test_playsound_plays_on_its_own_thread ____________________",
        "before": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sound.py",
            "sha256": "31d487707e8455d6381090cf678a79e58a5d73730426ba726cebc13e987fa806"
          }
        ],
        "after": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-02A-stopped-at-exit",
      "acceptance": [
        "AC-02A"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_sound.py::test_quitting_while_a_sound_plays_ends_cleanly with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/sound.py",
          "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "99013b3e64dee7b2eec0cf180e6013a72caf169844ebadefbcb6bcea06139788"
        }
      ],
      "scope_sha256": "ce18af96abe40aa0a6bc1ae88429cfb59f9973db018fee215ba5c884c3b90773",
      "red": {
        "mutation": "chatmon/sound.py: '        atexit.register(self.close)\\n' -> ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_quitting_while_a_sound_plays_ends_cleanly",
        "observed_diagnostic": "_______________ test_quitting_while_a_sound_plays_ends_cleanly ________________",
        "before": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sound.py",
            "sha256": "a263b37e96e6db28de8e649ecdb0f395cdb0db41bf1c6c940749ca3b13d821c0"
          }
        ],
        "after": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-02D-scaled",
      "acceptance": [
        "AC-02D"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_sound.py::test_samples_are_scaled_for_the_volume with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/sound.py",
          "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "99013b3e64dee7b2eec0cf180e6013a72caf169844ebadefbcb6bcea06139788"
        }
      ],
      "scope_sha256": "ce18af96abe40aa0a6bc1ae88429cfb59f9973db018fee215ba5c884c3b90773",
      "red": {
        "mutation": "chatmon/sound.py: '(round(v * volume) for v in values)' -> '(round(v) for v in values)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_samples_are_scaled_for_the_volume",
        "observed_diagnostic": "___________________ test_samples_are_scaled_for_the_volume ____________________",
        "before": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sound.py",
            "sha256": "425d376f0cfd6757e44927891d89f30e80451819ec2a05881cb4881611bc1e7e"
          }
        ],
        "after": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-02D-without-qt",
      "acceptance": [
        "AC-02D"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_sound.py::test_without_qtmultimedia_the_systems_own_player_is_used with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/sound.py",
          "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "99013b3e64dee7b2eec0cf180e6013a72caf169844ebadefbcb6bcea06139788"
        }
      ],
      "scope_sha256": "ce18af96abe40aa0a6bc1ae88429cfb59f9973db018fee215ba5c884c3b90773",
      "red": {
        "mutation": "chatmon/sound.py: \"except ImportError:  # QtMultimedia not installed (a distribution's PyQt6 without it)\\n            return False\" -> \"except ImportError:  # QtMultimedia not installed (a distribution's PyQt6 without it)\\n            return True\"",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_without_qtmultimedia_the_systems_own_player_is_used",
        "observed_diagnostic": "__________ test_without_qtmultimedia_the_systems_own_player_is_used ___________",
        "before": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sound.py",
            "sha256": "0bc809b03e0c46c0c490053cbd62f6b65246486aa56741ff8c3e177d5dd0850b"
          }
        ],
        "after": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-03A-escaped",
      "acceptance": [
        "AC-03A"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_wintoast.py::test_text_from_an_agent_is_text_never_markup with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/winfocus.py",
          "sha256": "23ef764c87a6330410f9bbe499d253f8dc7d556fab3f0bceffbfbfcbeb89dbc8"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "c6a2ca98f0b623fd1df9a7afa5bab9b0c0cc39bffb893875bc58d5bfd8565bcd"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "0c02f2a01dd40ac45f305e04578df6effa1b049d9b1f7f20b208bc61227152d2"
        }
      ],
      "scope_sha256": "27217289dc7a20c0fe1189687d3532c252744db02d20db33c6622fae5ab3d5a5",
      "red": {
        "mutation": "chatmon/wintoast.py: 'return ET.tostring(toast, encoding=\"unicode\")' -> 'return ET.tostring(toast, encoding=\"unicode\").replace(\"&lt;\", \"<\").replace(\"&gt;\", \">\")'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_text_from_an_agent_is_text_never_markup",
        "observed_diagnostic": "________________ test_text_from_an_agent_is_text_never_markup _________________",
        "before": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "c33bb0953848b5e1d2576285dc41c793597ebf000b877deb5e6f5a878a115af1"
          }
        ],
        "after": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-03A-control-chars",
      "acceptance": [
        "AC-03A"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_wintoast.py::test_text_from_an_agent_is_text_never_markup with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/winfocus.py",
          "sha256": "23ef764c87a6330410f9bbe499d253f8dc7d556fab3f0bceffbfbfcbeb89dbc8"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "c6a2ca98f0b623fd1df9a7afa5bab9b0c0cc39bffb893875bc58d5bfd8565bcd"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "0c02f2a01dd40ac45f305e04578df6effa1b049d9b1f7f20b208bc61227152d2"
        }
      ],
      "scope_sha256": "27217289dc7a20c0fe1189687d3532c252744db02d20db33c6622fae5ab3d5a5",
      "red": {
        "mutation": "chatmon/wintoast.py: 'return NOT_XML.sub(\"\", str(text))' -> 'return str(text)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_text_from_an_agent_is_text_never_markup",
        "observed_diagnostic": "________________ test_text_from_an_agent_is_text_never_markup _________________",
        "before": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "da6eafaaf291d77e8bd746c125137b6672c6ac6285bd5dbcb3303c04ecfa4bb3"
          }
        ],
        "after": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-03A-reminder-button",
      "acceptance": [
        "AC-03A"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_wintoast.py::test_a_reminder_stays_until_answered with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/winfocus.py",
          "sha256": "23ef764c87a6330410f9bbe499d253f8dc7d556fab3f0bceffbfbfcbeb89dbc8"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "c6a2ca98f0b623fd1df9a7afa5bab9b0c0cc39bffb893875bc58d5bfd8565bcd"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "0c02f2a01dd40ac45f305e04578df6effa1b049d9b1f7f20b208bc61227152d2"
        }
      ],
      "scope_sha256": "27217289dc7a20c0fe1189687d3532c252744db02d20db33c6622fae5ab3d5a5",
      "red": {
        "mutation": "chatmon/wintoast.py: \"        if not buttons:  # Windows' own Dismiss, so the scenario holds\" -> '        if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_reminder_stays_until_answered",
        "observed_diagnostic": "____________________ test_a_reminder_stays_until_answered _____________________",
        "before": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "1d7c7cdc92dcd0a0a625c280d29494dcb7f6483dec01051186d678f3cf0d071c"
          }
        ],
        "after": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-03A-five-buttons",
      "acceptance": [
        "AC-03A"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_wintoast.py::test_too_many_buttons_or_an_unknown_scenario_is_refused with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/winfocus.py",
          "sha256": "23ef764c87a6330410f9bbe499d253f8dc7d556fab3f0bceffbfbfcbeb89dbc8"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "c6a2ca98f0b623fd1df9a7afa5bab9b0c0cc39bffb893875bc58d5bfd8565bcd"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "0c02f2a01dd40ac45f305e04578df6effa1b049d9b1f7f20b208bc61227152d2"
        }
      ],
      "scope_sha256": "27217289dc7a20c0fe1189687d3532c252744db02d20db33c6622fae5ab3d5a5",
      "red": {
        "mutation": "chatmon/wintoast.py: 'if len(buttons) > MAX_BUTTONS:' -> 'if len(buttons) >= MAX_BUTTONS:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_too_many_buttons_or_an_unknown_scenario_is_refused",
        "observed_diagnostic": "___________ test_too_many_buttons_or_an_unknown_scenario_is_refused ___________",
        "before": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "5e34e81d20ae595f909486c027f729737df69a70a3ad942a38243bf515ecc679"
          }
        ],
        "after": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-03B-setting",
      "acceptance": [
        "AC-03B"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_wintoast.py::test_a_toast_is_shown_or_the_caller_is_told_to_use_the_balloon with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/winfocus.py",
          "sha256": "23ef764c87a6330410f9bbe499d253f8dc7d556fab3f0bceffbfbfcbeb89dbc8"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "c6a2ca98f0b623fd1df9a7afa5bab9b0c0cc39bffb893875bc58d5bfd8565bcd"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "0c02f2a01dd40ac45f305e04578df6effa1b049d9b1f7f20b208bc61227152d2"
        }
      ],
      "scope_sha256": "27217289dc7a20c0fe1189687d3532c252744db02d20db33c6622fae5ab3d5a5",
      "red": {
        "mutation": "chatmon/wintoast.py: '        if setting != ENABLED:\\n' -> '        if setting == OFF_BY_POLICY:\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_toast_is_shown_or_the_caller_is_told_to_use_the_balloon",
        "observed_diagnostic": "_______ test_a_toast_is_shown_or_the_caller_is_told_to_use_the_balloon ________",
        "before": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "ec9081ac2af0a6a6306327038cf4db60b2c847820d4dd78aec040f91f65c1b2c"
          }
        ],
        "after": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-03C-qt-thread",
      "acceptance": [
        "AC-03C"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_wintoast.py::test_what_windows_says_of_a_toast_comes_back_on_the_qt_thread with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/winfocus.py",
          "sha256": "23ef764c87a6330410f9bbe499d253f8dc7d556fab3f0bceffbfbfcbeb89dbc8"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "c6a2ca98f0b623fd1df9a7afa5bab9b0c0cc39bffb893875bc58d5bfd8565bcd"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "0c02f2a01dd40ac45f305e04578df6effa1b049d9b1f7f20b208bc61227152d2"
        }
      ],
      "scope_sha256": "27217289dc7a20c0fe1189687d3532c252744db02d20db33c6622fae5ab3d5a5",
      "red": {
        "mutation": "chatmon/wintoast.py: 'self._heard.emit(\"failed\", tag, code.value)' -> 'self.failed.emit(tag, code.value)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_what_windows_says_of_a_toast_comes_back_on_the_qt_thread",
        "observed_diagnostic": "________ test_what_windows_says_of_a_toast_comes_back_on_the_qt_thread ________",
        "before": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "cccf1018c2229277658d6796e6833e2e54b5c2a1336a7365d5e4db36e6231275"
          }
        ],
        "after": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-03C-button",
      "acceptance": [
        "AC-03C"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_wintoast.py::test_a_pressed_button_is_reported_and_its_action_runs_on_the_qt_thread with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/winfocus.py",
          "sha256": "23ef764c87a6330410f9bbe499d253f8dc7d556fab3f0bceffbfbfcbeb89dbc8"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "c6a2ca98f0b623fd1df9a7afa5bab9b0c0cc39bffb893875bc58d5bfd8565bcd"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "0c02f2a01dd40ac45f305e04578df6effa1b049d9b1f7f20b208bc61227152d2"
        }
      ],
      "scope_sha256": "27217289dc7a20c0fe1189687d3532c252744db02d20db33c6622fae5ab3d5a5",
      "red": {
        "mutation": "chatmon/wintoast.py: '                    index = parsed[1]\\n' -> '                    index = BODY\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_pressed_button_is_reported_and_its_action_runs_on_the_qt_thread",
        "observed_diagnostic": "___ test_a_pressed_button_is_reported_and_its_action_runs_on_the_qt_thread ____",
        "before": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "25f7fc0e41660a4029cbac163a748bab7c8db88abd16732560a8f27e887c3e91"
          }
        ],
        "after": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-03C-action",
      "acceptance": [
        "AC-03C"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_wintoast.py::test_a_pressed_button_is_reported_and_its_action_runs_on_the_qt_thread with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/winfocus.py",
          "sha256": "23ef764c87a6330410f9bbe499d253f8dc7d556fab3f0bceffbfbfcbeb89dbc8"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "c6a2ca98f0b623fd1df9a7afa5bab9b0c0cc39bffb893875bc58d5bfd8565bcd"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "0c02f2a01dd40ac45f305e04578df6effa1b049d9b1f7f20b208bc61227152d2"
        }
      ],
      "scope_sha256": "27217289dc7a20c0fe1189687d3532c252744db02d20db33c6622fae5ab3d5a5",
      "red": {
        "mutation": "chatmon/wintoast.py: '                action()\\n' -> '                pass\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_pressed_button_is_reported_and_its_action_runs_on_the_qt_thread",
        "observed_diagnostic": "___ test_a_pressed_button_is_reported_and_its_action_runs_on_the_qt_thread ____",
        "before": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "cc2652f522e24df1a219e8af25c77d6565fc40db47df3bf96576f98abc8d43ad"
          }
        ],
        "after": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-03D-icon",
      "acceptance": [
        "AC-03D"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_wintoast.py::test_a_pip_install_tells_windows_its_name_and_icon with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/winfocus.py",
          "sha256": "23ef764c87a6330410f9bbe499d253f8dc7d556fab3f0bceffbfbfcbeb89dbc8"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "c6a2ca98f0b623fd1df9a7afa5bab9b0c0cc39bffb893875bc58d5bfd8565bcd"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "0c02f2a01dd40ac45f305e04578df6effa1b049d9b1f7f20b208bc61227152d2"
        }
      ],
      "scope_sha256": "27217289dc7a20c0fe1189687d3532c252744db02d20db33c6622fae5ab3d5a5",
      "red": {
        "mutation": "chatmon/wintoast.py: '        if icon:\\n' -> '        if not icon:\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_pip_install_tells_windows_its_name_and_icon",
        "observed_diagnostic": "_____________ test_a_pip_install_tells_windows_its_name_and_icon ______________",
        "before": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "d8c21d85c2efa175fbedafdc7e154f3796670d5e7ad53be352317666a485ac23"
          }
        ],
        "after": [
          {
            "path": "chatmon/wintoast.py",
            "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-04A-position",
      "acceptance": [
        "AC-04A"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_wincaret.py::test_a_new_bubble_gets_the_caret_magnifier_follows with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/wincaret.py",
          "sha256": "a570924028029e6adbab036e623dee3448db04bd3014750e0cf4cc463de7575d"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_wincaret.py",
          "sha256": "0c1ed4dde60d30937d948de00f5914e2d9b1793ef2b8622b0867d2e5d871d191"
        }
      ],
      "scope_sha256": "bbeffac5c2302d37a646f2ca747ab903592829e03f0ba9b0b8547e912663815b",
      "red": {
        "mutation": "chatmon/wincaret.py: 'user32.SetCaretPos(int(x), int(y))' -> 'user32.SetCaretPos(int(y), int(x))'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_new_bubble_gets_the_caret_magnifier_follows",
        "observed_diagnostic": "_____________ test_a_new_bubble_gets_the_caret_magnifier_follows ______________",
        "before": [
          {
            "path": "chatmon/wincaret.py",
            "sha256": "a570924028029e6adbab036e623dee3448db04bd3014750e0cf4cc463de7575d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/wincaret.py",
            "sha256": "32eee77554f44a4ff52a64d6cebab3bab350b22e578df02b550d574995543538"
          }
        ],
        "after": [
          {
            "path": "chatmon/wincaret.py",
            "sha256": "a570924028029e6adbab036e623dee3448db04bd3014750e0cf4cc463de7575d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-04A-bubble-size",
      "acceptance": [
        "AC-04A"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_wincaret.py::test_a_new_bubble_gets_the_caret_magnifier_follows with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/wincaret.py",
          "sha256": "a570924028029e6adbab036e623dee3448db04bd3014750e0cf4cc463de7575d"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_wincaret.py",
          "sha256": "0c1ed4dde60d30937d948de00f5914e2d9b1793ef2b8622b0867d2e5d871d191"
        }
      ],
      "scope_sha256": "bbeffac5c2302d37a646f2ca747ab903592829e03f0ba9b0b8547e912663815b",
      "red": {
        "mutation": "chatmon/wincaret.py: 'max(1, int(width)), max(1, int(height))' -> 'max(1, int(width) // 2), max(1, int(height))'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_new_bubble_gets_the_caret_magnifier_follows",
        "observed_diagnostic": "_____________ test_a_new_bubble_gets_the_caret_magnifier_follows ______________",
        "before": [
          {
            "path": "chatmon/wincaret.py",
            "sha256": "a570924028029e6adbab036e623dee3448db04bd3014750e0cf4cc463de7575d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/wincaret.py",
            "sha256": "3adae2ad467b3d6ebae22b73dbb5468e0d9c69088112668e5cbe7c8bc1aeaed0"
          }
        ],
        "after": [
          {
            "path": "chatmon/wincaret.py",
            "sha256": "a570924028029e6adbab036e623dee3448db04bd3014750e0cf4cc463de7575d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-04A-cleared",
      "acceptance": [
        "AC-04A"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_wincaret.py::test_a_new_bubble_gets_the_caret_magnifier_follows with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/wincaret.py",
          "sha256": "a570924028029e6adbab036e623dee3448db04bd3014750e0cf4cc463de7575d"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_wincaret.py",
          "sha256": "0c1ed4dde60d30937d948de00f5914e2d9b1793ef2b8622b0867d2e5d871d191"
        }
      ],
      "scope_sha256": "bbeffac5c2302d37a646f2ca747ab903592829e03f0ba9b0b8547e912663815b",
      "red": {
        "mutation": "chatmon/wincaret.py: '            _api().DestroyCaret()\\n' -> '            pass\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_new_bubble_gets_the_caret_magnifier_follows",
        "observed_diagnostic": "_____________ test_a_new_bubble_gets_the_caret_magnifier_follows ______________",
        "before": [
          {
            "path": "chatmon/wincaret.py",
            "sha256": "a570924028029e6adbab036e623dee3448db04bd3014750e0cf4cc463de7575d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/wincaret.py",
            "sha256": "6f86036db1a76712f39e5dccbd1c62b22f9a66e824b18e1034a9615bb767d3c1"
          }
        ],
        "after": [
          {
            "path": "chatmon/wincaret.py",
            "sha256": "a570924028029e6adbab036e623dee3448db04bd3014750e0cf4cc463de7575d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-04B-magnifier",
      "acceptance": [
        "AC-04B"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m4b/drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_wincaret.py::test_the_caret_is_only_for_when_magnifier_runs with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills.log",
        "sha256": "800e74f7ba3cdd9eae5d6f54be668189c22c9aab9325bf0400754462cdd6660b"
      },
      "inputs": [
        {
          "path": "chatmon/wincaret.py",
          "sha256": "a570924028029e6adbab036e623dee3448db04bd3014750e0cf4cc463de7575d"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_wincaret.py",
          "sha256": "0c1ed4dde60d30937d948de00f5914e2d9b1793ef2b8622b0867d2e5d871d191"
        }
      ],
      "scope_sha256": "bbeffac5c2302d37a646f2ca747ab903592829e03f0ba9b0b8547e912663815b",
      "red": {
        "mutation": "chatmon/wincaret.py: 'return bool(_api().FindWindowW(MAGNIFIER_CLASS, None))' -> 'return not _api().FindWindowW(MAGNIFIER_CLASS, None)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_caret_is_only_for_when_magnifier_runs",
        "observed_diagnostic": "_______________ test_the_caret_is_only_for_when_magnifier_runs ________________",
        "before": [
          {
            "path": "chatmon/wincaret.py",
            "sha256": "a570924028029e6adbab036e623dee3448db04bd3014750e0cf4cc463de7575d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/wincaret.py",
            "sha256": "a5036ba7d38261236bc69e93fc9dfa87468c4fad0166ea399cf2698369cf1c66"
          }
        ],
        "after": [
          {
            "path": "chatmon/wincaret.py",
            "sha256": "a570924028029e6adbab036e623dee3448db04bd3014750e0cf4cc463de7575d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-01F-trigger",
      "acceptance": [
        "AC-01F"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--only",
        "D-01F-trigger",
        "--log",
        "docs/delivery/reports/m4b/drills-portal.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_hotkey_portal.py::test_the_keys_are_asked_for_in_the_xdg_shortcuts_format with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills-portal.log",
        "sha256": "e0c7ba0b13cf748ad7b79f102303d800ab17d8edeefc63b9db1bc21010214d0d"
      },
      "inputs": [
        {
          "path": "chatmon/hotkey.py",
          "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "d591a04ac51df633e667d23f9ee6fb8bc96318a7c38dab75b7e0dc6830501a43"
        },
        {
          "path": "chatmon/shortcutportal.py",
          "sha256": "12ce92b60dce230959d4db70864a342a7862d22bf0d035a7cb049d2a8dc1b343"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "1a13ed68d62f9a44dd3ad140da5e7a0e4cf84d13931c1516e3475a347512d6e7"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "eabc59fb1a0fa48201237e6b1f83c32f91f75f221d7f97e4cebafb401aff40f6"
        },
        {
          "path": "tests/test_hotkey_portal.py",
          "sha256": "3b1e7969599e80972fb600806916c1140b96ed69dbf9245a2bf6f982feb65ccf"
        }
      ],
      "scope_sha256": "2044a9ab9ce7e881e05fa71da16140e457d46e4c509363cc3b03b0628aeed991",
      "red": {
        "mutation": "chatmon/shortcutportal.py: '[KEYS[combo.key].x11]' -> '[combo.key]'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "CTRL+ALT+Space",
        "observed_diagnostic": "E       AssertionError: assert 'CTRL+ALT+Space' == 'CTRL+ALT+space'",
        "before": [
          {
            "path": "chatmon/shortcutportal.py",
            "sha256": "12ce92b60dce230959d4db70864a342a7862d22bf0d035a7cb049d2a8dc1b343"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/shortcutportal.py",
            "sha256": "944d60a4caa89d5d96dff12321e8dee0b571deae16551906404c8a262522299f"
          }
        ],
        "after": [
          {
            "path": "chatmon/shortcutportal.py",
            "sha256": "12ce92b60dce230959d4db70864a342a7862d22bf0d035a7cb049d2a8dc1b343"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-D-00A-eager-objc",
      "acceptance": [
        "AC-00A"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "tests/drills/run.py",
        "docs/delivery/reports/m4b/drill-spec.json",
        "--only",
        "D-00A-eager-objc",
        "--log",
        "docs/delivery/reports/m4b/drills-imports.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_m4b_imports.py::test_it_imports_here with the project's drill harness, on a temporary copy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/drills-imports.log",
        "sha256": "8d3fc0912ae1ebd225664cd2b17dc7176e5ac86913ba68a89e0fa03c02138d5a"
      },
      "inputs": [
        {
          "path": "chatmon/hotkey.py",
          "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "a570924028029e6adbab036e623dee3448db04bd3014750e0cf4cc463de7575d"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "23ef764c87a6330410f9bbe499d253f8dc7d556fab3f0bceffbfbfcbeb89dbc8"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "c6a2ca98f0b623fd1df9a7afa5bab9b0c0cc39bffb893875bc58d5bfd8565bcd"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "eabc59fb1a0fa48201237e6b1f83c32f91f75f221d7f97e4cebafb401aff40f6"
        },
        {
          "path": "tests/test_m4b_imports.py",
          "sha256": "03bb2bb4a5fb34b628073875f153dfa9cd878ec21c7af0b0a8140b03f7809a64"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "99013b3e64dee7b2eec0cf180e6013a72caf169844ebadefbcb6bcea06139788"
        },
        {
          "path": "tests/test_wincaret.py",
          "sha256": "0c1ed4dde60d30937d948de00f5914e2d9b1793ef2b8622b0867d2e5d871d191"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "0c02f2a01dd40ac45f305e04578df6effa1b049d9b1f7f20b208bc61227152d2"
        }
      ],
      "scope_sha256": "e3989a800e733c825082281850c9911080284c1636395142f44ace610ccd08e5",
      "red": {
        "mutation": "chatmon/sound.py: '_sounds = Sounds()\\n' -> '_sounds = Sounds()\\nMacPlayer()\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_it_imports_here[sound]",
        "observed_diagnostic": "_________________________ test_it_imports_here[sound] _________________________",
        "before": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sound.py",
            "sha256": "de42752dc1585e3714f78941da5d6533c00058b783b57ec676a3ee4a701caef0"
          }
        ],
        "after": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-L-00B-eager-objc",
      "acceptance": [
        "AC-00B"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "docs/delivery/reports/m4b/wsl-drills.py",
        "/mnt/c/Users/Randy/Coding/chatmon-wt/m4b",
        "docs/delivery/reports/m4b/wsl-drill-spec.json",
        "docs/delivery/reports/m4b/wsl-drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_m4b_imports.py::test_it_imports_here with run.py's drill() in WSL, on a copy under /var/tmp",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pyqt6": "6.12.1",
          "pytest": "9.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/wsl-drills.log",
        "sha256": "b6ab9f4fd932c9e4d7d1dfb4d41413c31d6bddab9ac0b2508431e0eec2524c78"
      },
      "inputs": [
        {
          "path": "chatmon/hotkey.py",
          "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "a570924028029e6adbab036e623dee3448db04bd3014750e0cf4cc463de7575d"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "23ef764c87a6330410f9bbe499d253f8dc7d556fab3f0bceffbfbfcbeb89dbc8"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "c6a2ca98f0b623fd1df9a7afa5bab9b0c0cc39bffb893875bc58d5bfd8565bcd"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "eabc59fb1a0fa48201237e6b1f83c32f91f75f221d7f97e4cebafb401aff40f6"
        },
        {
          "path": "tests/test_m4b_imports.py",
          "sha256": "03bb2bb4a5fb34b628073875f153dfa9cd878ec21c7af0b0a8140b03f7809a64"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "99013b3e64dee7b2eec0cf180e6013a72caf169844ebadefbcb6bcea06139788"
        },
        {
          "path": "tests/test_wincaret.py",
          "sha256": "0c1ed4dde60d30937d948de00f5914e2d9b1793ef2b8622b0867d2e5d871d191"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "0c02f2a01dd40ac45f305e04578df6effa1b049d9b1f7f20b208bc61227152d2"
        }
      ],
      "scope_sha256": "aeb9c3b9604272878f683e9448f8113cd676c72d48805b9947c47475da6a18e1",
      "red": {
        "mutation": "chatmon/sound.py: '_sounds = Sounds()\\n' -> '_sounds = Sounds()\\nMacPlayer()\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_it_imports_here[sound]",
        "observed_diagnostic": "_________________________ test_it_imports_here[sound] __________________________",
        "before": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sound.py",
            "sha256": "de42752dc1585e3714f78941da5d6533c00058b783b57ec676a3ee4a701caef0"
          }
        ],
        "after": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-L-01E-numlock",
      "acceptance": [
        "AC-01E"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "docs/delivery/reports/m4b/wsl-drills.py",
        "/mnt/c/Users/Randy/Coding/chatmon-wt/m4b",
        "docs/delivery/reports/m4b/wsl-drill-spec.json",
        "docs/delivery/reports/m4b/wsl-drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_hotkey.py::test_x11_grabs_it_whatever_numlock_says_and_reports_a_conflict with run.py's drill() in WSL, on a copy under /var/tmp",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pyqt6": "6.12.1",
          "pytest": "9.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/wsl-drills.log",
        "sha256": "b6ab9f4fd932c9e4d7d1dfb4d41413c31d6bddab9ac0b2508431e0eec2524c78"
      },
      "inputs": [
        {
          "path": "chatmon/hotkey.py",
          "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "eabc59fb1a0fa48201237e6b1f83c32f91f75f221d7f97e4cebafb401aff40f6"
        }
      ],
      "scope_sha256": "5527cc2ee1508cf71c3a054c11d2c53a23f715e5bd37b77b65520f1a0192c7c4",
      "red": {
        "mutation": "chatmon/hotkey.py: '(key.keycode, key.state & ~(self.LOCK | self.NUM_LOCK))' -> '(key.keycode, key.state)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_x11_grabs_it_whatever_numlock_says_and_reports_a_conflict",
        "observed_diagnostic": "________ test_x11_grabs_it_whatever_numlock_says_and_reports_a_conflict ________",
        "before": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "53eb1f27f9c443602322f22eb95f3dc302217c0563d9782689591ab9ba01d775"
          }
        ],
        "after": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-L-01E-conflict",
      "acceptance": [
        "AC-01E"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "docs/delivery/reports/m4b/wsl-drills.py",
        "/mnt/c/Users/Randy/Coding/chatmon-wt/m4b",
        "docs/delivery/reports/m4b/wsl-drill-spec.json",
        "docs/delivery/reports/m4b/wsl-drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_hotkey.py::test_x11_grabs_it_whatever_numlock_says_and_reports_a_conflict with run.py's drill() in WSL, on a copy under /var/tmp",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pyqt6": "6.12.1",
          "pytest": "9.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/wsl-drills.log",
        "sha256": "b6ab9f4fd932c9e4d7d1dfb4d41413c31d6bddab9ac0b2508431e0eec2524c78"
      },
      "inputs": [
        {
          "path": "chatmon/hotkey.py",
          "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "eabc59fb1a0fa48201237e6b1f83c32f91f75f221d7f97e4cebafb401aff40f6"
        }
      ],
      "scope_sha256": "5527cc2ee1508cf71c3a054c11d2c53a23f715e5bd37b77b65520f1a0192c7c4",
      "red": {
        "mutation": "chatmon/hotkey.py: '            if display == self.display:\\n' -> '            if False:\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_x11_grabs_it_whatever_numlock_says_and_reports_a_conflict",
        "observed_diagnostic": "________ test_x11_grabs_it_whatever_numlock_says_and_reports_a_conflict ________",
        "before": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "d122dc18a16cf8641c7ccc010e6a2835bddbefbe5c43f4e74a14495a57808f47"
          }
        ],
        "after": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-L-01F-its-own-session",
      "acceptance": [
        "AC-01F"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "docs/delivery/reports/m4b/wsl-drills.py",
        "/mnt/c/Users/Randy/Coding/chatmon-wt/m4b",
        "docs/delivery/reports/m4b/wsl-drill-spec.json",
        "docs/delivery/reports/m4b/wsl-drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_hotkey_portal.py::test_the_portal_binds_it_and_its_presses_reach_chatmon with run.py's drill() in WSL, on a copy under /var/tmp",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pyqt6": "6.12.1",
          "pytest": "9.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/wsl-drills.log",
        "sha256": "b6ab9f4fd932c9e4d7d1dfb4d41413c31d6bddab9ac0b2508431e0eec2524c78"
      },
      "inputs": [
        {
          "path": "chatmon/hotkey.py",
          "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "d591a04ac51df633e667d23f9ee6fb8bc96318a7c38dab75b7e0dc6830501a43"
        },
        {
          "path": "chatmon/shortcutportal.py",
          "sha256": "12ce92b60dce230959d4db70864a342a7862d22bf0d035a7cb049d2a8dc1b343"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "1a13ed68d62f9a44dd3ad140da5e7a0e4cf84d13931c1516e3475a347512d6e7"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "eabc59fb1a0fa48201237e6b1f83c32f91f75f221d7f97e4cebafb401aff40f6"
        },
        {
          "path": "tests/test_hotkey_portal.py",
          "sha256": "3b1e7969599e80972fb600806916c1140b96ed69dbf9245a2bf6f982feb65ccf"
        }
      ],
      "scope_sha256": "2044a9ab9ce7e881e05fa71da16140e457d46e4c509363cc3b03b0628aeed991",
      "red": {
        "mutation": "chatmon/shortcutportal.py: 'if self._session and str(message.args[0]) == self._session and message.args[1] == SHORTCUT_ID:' -> 'if self._session and message.args[1] == SHORTCUT_ID:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_portal_binds_it_and_its_presses_reach_chatmon",
        "observed_diagnostic": "____________ test_the_portal_binds_it_and_its_presses_reach_chatmon ____________",
        "before": [
          {
            "path": "chatmon/shortcutportal.py",
            "sha256": "12ce92b60dce230959d4db70864a342a7862d22bf0d035a7cb049d2a8dc1b343"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/shortcutportal.py",
            "sha256": "344447db7c58ec63e65b39dd486871ceea3960dd929d377f5bc06b3bb5551721"
          }
        ],
        "after": [
          {
            "path": "chatmon/shortcutportal.py",
            "sha256": "12ce92b60dce230959d4db70864a342a7862d22bf0d035a7cb049d2a8dc1b343"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-L-01F-response",
      "acceptance": [
        "AC-01F"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "docs/delivery/reports/m4b/wsl-drills.py",
        "/mnt/c/Users/Randy/Coding/chatmon-wt/m4b",
        "docs/delivery/reports/m4b/wsl-drill-spec.json",
        "docs/delivery/reports/m4b/wsl-drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_hotkey_portal.py::test_the_portal_binds_it_and_its_presses_reach_chatmon with run.py's drill() in WSL, on a copy under /var/tmp",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pyqt6": "6.12.1",
          "pytest": "9.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/wsl-drills.log",
        "sha256": "b6ab9f4fd932c9e4d7d1dfb4d41413c31d6bddab9ac0b2508431e0eec2524c78"
      },
      "inputs": [
        {
          "path": "chatmon/hotkey.py",
          "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "d591a04ac51df633e667d23f9ee6fb8bc96318a7c38dab75b7e0dc6830501a43"
        },
        {
          "path": "chatmon/shortcutportal.py",
          "sha256": "12ce92b60dce230959d4db70864a342a7862d22bf0d035a7cb049d2a8dc1b343"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "1a13ed68d62f9a44dd3ad140da5e7a0e4cf84d13931c1516e3475a347512d6e7"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "eabc59fb1a0fa48201237e6b1f83c32f91f75f221d7f97e4cebafb401aff40f6"
        },
        {
          "path": "tests/test_hotkey_portal.py",
          "sha256": "3b1e7969599e80972fb600806916c1140b96ed69dbf9245a2bf6f982feb65ccf"
        }
      ],
      "scope_sha256": "2044a9ab9ce7e881e05fa71da16140e457d46e4c509363cc3b03b0628aeed991",
      "red": {
        "mutation": "chatmon/shortcutportal.py: '            then(code, results)\\n' -> '            then(1, results)\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_portal_binds_it_and_its_presses_reach_chatmon",
        "observed_diagnostic": "____________ test_the_portal_binds_it_and_its_presses_reach_chatmon ____________",
        "before": [
          {
            "path": "chatmon/shortcutportal.py",
            "sha256": "12ce92b60dce230959d4db70864a342a7862d22bf0d035a7cb049d2a8dc1b343"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/shortcutportal.py",
            "sha256": "517e5b396f448328dc65fe1ce7e3d8fef5f5c150926b043f7d86a3e66c3bc298"
          }
        ],
        "after": [
          {
            "path": "chatmon/shortcutportal.py",
            "sha256": "12ce92b60dce230959d4db70864a342a7862d22bf0d035a7cb049d2a8dc1b343"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-L-01F-carries-on",
      "acceptance": [
        "AC-01F"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "docs/delivery/reports/m4b/wsl-drills.py",
        "/mnt/c/Users/Randy/Coding/chatmon-wt/m4b",
        "docs/delivery/reports/m4b/wsl-drill-spec.json",
        "docs/delivery/reports/m4b/wsl-drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_hotkey_portal.py::test_a_portal_answering_nonsense_fails_that_shortcut_and_the_next_can_still_be_asked with run.py's drill() in WSL, on a copy under /var/tmp",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pyqt6": "6.12.1",
          "pytest": "9.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/wsl-drills.log",
        "sha256": "b6ab9f4fd932c9e4d7d1dfb4d41413c31d6bddab9ac0b2508431e0eec2524c78"
      },
      "inputs": [
        {
          "path": "chatmon/hotkey.py",
          "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "d591a04ac51df633e667d23f9ee6fb8bc96318a7c38dab75b7e0dc6830501a43"
        },
        {
          "path": "chatmon/shortcutportal.py",
          "sha256": "12ce92b60dce230959d4db70864a342a7862d22bf0d035a7cb049d2a8dc1b343"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "1a13ed68d62f9a44dd3ad140da5e7a0e4cf84d13931c1516e3475a347512d6e7"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "eabc59fb1a0fa48201237e6b1f83c32f91f75f221d7f97e4cebafb401aff40f6"
        },
        {
          "path": "tests/test_hotkey_portal.py",
          "sha256": "3b1e7969599e80972fb600806916c1140b96ed69dbf9245a2bf6f982feb65ccf"
        }
      ],
      "scope_sha256": "2044a9ab9ce7e881e05fa71da16140e457d46e4c509363cc3b03b0628aeed991",
      "red": {
        "mutation": "chatmon/shortcutportal.py: 'except (libdbus.Failure, TypeError, ValueError, KeyError, IndexError, AttributeError):' -> 'except libdbus.Failure:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_portal_answering_nonsense_fails_that_shortcut_and_the_next_can_still_be_asked",
        "observed_diagnostic": "_ test_a_portal_answering_nonsense_fails_that_shortcut_and_the_next_can_still_be_asked _",
        "before": [
          {
            "path": "chatmon/shortcutportal.py",
            "sha256": "12ce92b60dce230959d4db70864a342a7862d22bf0d035a7cb049d2a8dc1b343"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/shortcutportal.py",
            "sha256": "8c970690b282622adf51c02dde6b0ba1488b10c9d6d8edb27be782233ab52794"
          }
        ],
        "after": [
          {
            "path": "chatmon/shortcutportal.py",
            "sha256": "12ce92b60dce230959d4db70864a342a7862d22bf0d035a7cb049d2a8dc1b343"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-L-01F-no-portal",
      "acceptance": [
        "AC-01F"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "docs/delivery/reports/m4b/wsl-drills.py",
        "/mnt/c/Users/Randy/Coding/chatmon-wt/m4b",
        "docs/delivery/reports/m4b/wsl-drill-spec.json",
        "docs/delivery/reports/m4b/wsl-drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_hotkey_portal.py::test_a_desktop_without_the_portal_says_how_to_do_it_instead with run.py's drill() in WSL, on a copy under /var/tmp",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pyqt6": "6.12.1",
          "pytest": "9.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/wsl-drills.log",
        "sha256": "b6ab9f4fd932c9e4d7d1dfb4d41413c31d6bddab9ac0b2508431e0eec2524c78"
      },
      "inputs": [
        {
          "path": "chatmon/hotkey.py",
          "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "d591a04ac51df633e667d23f9ee6fb8bc96318a7c38dab75b7e0dc6830501a43"
        },
        {
          "path": "chatmon/shortcutportal.py",
          "sha256": "12ce92b60dce230959d4db70864a342a7862d22bf0d035a7cb049d2a8dc1b343"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "1a13ed68d62f9a44dd3ad140da5e7a0e4cf84d13931c1516e3475a347512d6e7"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "eabc59fb1a0fa48201237e6b1f83c32f91f75f221d7f97e4cebafb401aff40f6"
        },
        {
          "path": "tests/test_hotkey_portal.py",
          "sha256": "3b1e7969599e80972fb600806916c1140b96ed69dbf9245a2bf6f982feb65ccf"
        }
      ],
      "scope_sha256": "2044a9ab9ce7e881e05fa71da16140e457d46e4c509363cc3b03b0628aeed991",
      "red": {
        "mutation": "chatmon/shortcutportal.py: '            self._tell(\"failed\", NO_PORTAL)\\n            return\\n        if not version:' -> '            return\\n        if not version:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_desktop_without_the_portal_says_how_to_do_it_instead",
        "observed_diagnostic": "______ test_a_desktop_without_the_portal_says_how_to_do_it_instead[None] _______",
        "before": [
          {
            "path": "chatmon/shortcutportal.py",
            "sha256": "12ce92b60dce230959d4db70864a342a7862d22bf0d035a7cb049d2a8dc1b343"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/shortcutportal.py",
            "sha256": "00a2039120fbfd4fc4e49abfcebf71d7c251e829d96c5a0383764a6a0dfaa939"
          }
        ],
        "after": [
          {
            "path": "chatmon/shortcutportal.py",
            "sha256": "12ce92b60dce230959d4db70864a342a7862d22bf0d035a7cb049d2a8dc1b343"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-RED-L-02D-linux-player",
      "acceptance": [
        "AC-02E"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "python",
        "docs/delivery/reports/m4b/wsl-drills.py",
        "/mnt/c/Users/Randy/Coding/chatmon-wt/m4b",
        "docs/delivery/reports/m4b/wsl-drill-spec.json",
        "docs/delivery/reports/m4b/wsl-drills.log"
      ],
      "method": "Green, mutated red, restored green of no:cacheprovider tests/test_sound.py::test_linux_players_follow_the_sound_server_and_never_make_you_wait with run.py's drill() in WSL, on a copy under /var/tmp",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pyqt6": "6.12.1",
          "pytest": "9.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4b/wsl-drills.log",
        "sha256": "b6ab9f4fd932c9e4d7d1dfb4d41413c31d6bddab9ac0b2508431e0eec2524c78"
      },
      "inputs": [
        {
          "path": "chatmon/sound.py",
          "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "99013b3e64dee7b2eec0cf180e6013a72caf169844ebadefbcb6bcea06139788"
        }
      ],
      "scope_sha256": "2b0edf9a41479613adaed35dc4895fe30acba0e204633a8896ef8d1b11bc54f0",
      "red": {
        "mutation": "chatmon/sound.py: 'servers = {\"pw-play\": runtime / \"pipewire-0\", \"paplay\": runtime / \"pulse\" / \"native\", \"canberra-gtk-play\": None}' -> 'servers = {\"pw-play\": None, \"paplay\": runtime / \"pulse\" / \"native\", \"canberra-gtk-play\": None}'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_linux_players_follow_the_sound_server_and_never_make_you_wait",
        "observed_diagnostic": "______ test_linux_players_follow_the_sound_server_and_never_make_you_wait ______",
        "before": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sound.py",
            "sha256": "949a4557249376094047de8cf999d5ce0be190ab4314cd38c0fac0d5978ec5e5"
          }
        ],
        "after": [
          {
            "path": "chatmon/sound.py",
            "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
          }
        ]
      },
      "reason": null
    }
  ],
  "checkpoint": {
    "environment": {
      "platform": "windows",
      "tools": {
        "python": "3.14.10",
        "pyqt6": "6.11.0",
        "pytest": "9.2.0",
        "ruff": "0.17.4"
      }
    },
    "pending_operations": [
      {
        "id": "CI-MACOS",
        "description": "macOS: the Carbon hotkey (AC-01D), NSSound (AC-02F) and the imports (AC-00C) haven't run anywhere yet: macOS code can't run on this PC",
        "next_action": "Coordinator pushes the merged branch; read the macOS job's tests/test_hotkey.py, tests/test_sound.py, tests/test_m4b_imports.py; failures back to M4B"
      },
      {
        "id": "CI-WINDOWS-TOASTS",
        "description": "Windows with notifications on: a toast in Action Center under its tag, hidden, cleared (AC-03E)",
        "next_action": "Read the Windows job's tests/test_wintoast.py; it takes the notifications-on branch there"
      },
      {
        "id": "CI-LINUX",
        "description": "Linux under the project's profile: the portal (AC-01F), the Linux players (AC-02E) and the imports (AC-00B), verified so far only in WSL; the X11 test (AC-01E) skips in CI until M6A installs xvfb and libxtst6",
        "next_action": "Read the Linux job's tests/test_hotkey_portal.py, tests/test_sound.py, tests/test_m4b_imports.py; M6A adds Xvfb for tests/test_hotkey.py's X11 test"
      }
    ],
    "next_action": "After CI: mark T-TOAST-SHOWN, T-SOUND-LINUX, T-SOUND-MAC, T-HOTKEY-MAC, T-HOTKEY-X11, T-PORTAL and T-IMPORTS-POSIX verified from its runs, or reopen them with its failures",
    "source_revision": "ea3474f7181ef8113d667bff177c3e5b5a45f42f",
    "scope_sha256": "cefc23c4fa8b4a74942cbf31eecca9a99992b515384713eb574bd02ac2d51b18",
    "inputs": [
      {
        "path": "chatmon/hotkey.py",
        "sha256": "9620bef724c1e171fe38e0def4c598e659a68392d423eb52de9455bb9d4be4d5"
      },
      {
        "path": "chatmon/libdbus.py",
        "sha256": "d591a04ac51df633e667d23f9ee6fb8bc96318a7c38dab75b7e0dc6830501a43"
      },
      {
        "path": "chatmon/shortcutportal.py",
        "sha256": "12ce92b60dce230959d4db70864a342a7862d22bf0d035a7cb049d2a8dc1b343"
      },
      {
        "path": "chatmon/sound.py",
        "sha256": "9865952ab178e37db8f710bb06dce4ba17e746fb53999392636e210415df3da6"
      },
      {
        "path": "chatmon/wincaret.py",
        "sha256": "a570924028029e6adbab036e623dee3448db04bd3014750e0cf4cc463de7575d"
      },
      {
        "path": "chatmon/winfocus.py",
        "sha256": "23ef764c87a6330410f9bbe499d253f8dc7d556fab3f0bceffbfbfcbeb89dbc8"
      },
      {
        "path": "chatmon/winrt.py",
        "sha256": "c6a2ca98f0b623fd1df9a7afa5bab9b0c0cc39bffb893875bc58d5bfd8565bcd"
      },
      {
        "path": "chatmon/wintoast.py",
        "sha256": "9150e1a9e5a0df7862af09018fde59edc2640b591cbbb0cae0c2f3d0d52efdb2"
      },
      {
        "path": "docs/delivery/ASSESSMENT.md",
        "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
      },
      {
        "path": "docs/delivery/ROADMAP.md",
        "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
      },
      {
        "path": "pyproject.toml",
        "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
      },
      {
        "path": "tests/conftest.py",
        "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
      },
      {
        "path": "tests/drills/run.py",
        "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
      },
      {
        "path": "tests/fake_shortcuts_portal.py",
        "sha256": "1a13ed68d62f9a44dd3ad140da5e7a0e4cf84d13931c1516e3475a347512d6e7"
      },
      {
        "path": "tests/test_hotkey.py",
        "sha256": "eabc59fb1a0fa48201237e6b1f83c32f91f75f221d7f97e4cebafb401aff40f6"
      },
      {
        "path": "tests/test_hotkey_portal.py",
        "sha256": "3b1e7969599e80972fb600806916c1140b96ed69dbf9245a2bf6f982feb65ccf"
      },
      {
        "path": "tests/test_m4b_imports.py",
        "sha256": "03bb2bb4a5fb34b628073875f153dfa9cd878ec21c7af0b0a8140b03f7809a64"
      },
      {
        "path": "tests/test_sound.py",
        "sha256": "99013b3e64dee7b2eec0cf180e6013a72caf169844ebadefbcb6bcea06139788"
      },
      {
        "path": "tests/test_wincaret.py",
        "sha256": "0c1ed4dde60d30937d948de00f5914e2d9b1793ef2b8622b0867d2e5d871d191"
      },
      {
        "path": "tests/test_wintoast.py",
        "sha256": "0c02f2a01dd40ac45f305e04578df6effa1b049d9b1f7f20b208bc61227152d2"
      }
    ],
    "verified_tasks": [
      "T-WINRT",
      "T-TOAST",
      "T-CARET",
      "T-SOUND",
      "T-HOTKEY",
      "T-IMPORTS"
    ]
  }
}
```
