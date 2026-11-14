# M4A: platform awareness and screen readers

Brief: [ASSESSMENT.md](ASSESSMENT.md#m4a-platform-awareness-and-screen-readers-presencepy-a11ypy-macnativepy-linuxsessionpy-sysnotifypy-heads_uppy-portalpy-winlockpy),
items M4A-01 to M4A-11. Rules: [ROADMAP.md](ROADMAP.md) and `pyproject.toml`. Worktree branch `wave1/m4a`, from
`improve/assessment-fixes` at `5346385`. Reports, logs and drill results are in [reports/m4a/](reports/m4a/).

## Scope

This milestone gives the platform modules the readings and signals the app needs. It doesn't change `app.py`:
what the app does with them is M7's work (M7-11), listed under **Integration notes**. Only the files M4A owns
change (`presence.py`, `a11y.py`, `macnative.py`, `linuxsession.py`, `sysnotify.py`, `heads_up.py`,
`winlock.py`; `portal.py` needed no change), plus one new module (`winuia.py`), new tests and test fakes.

Non-goals: wiring in `app.py`, `settingswin.py` or `penguin.py`; Windows toasts (M4B's `wintoast.py`); sounds.

## Findings re-checked

Each finding was traced in the code at `5346385` before planning:

- **M4A-01** ✓ as written: `Desk.high_contrast()` on Linux and macOS asks only Qt 6.10's `contrastPreference()`.
  On macOS it never asks AppKit.
- **M4A-02** true: `_X11.fullscreen_in_front()` checks only that the active window is full screen.
  Decision: `quiet()` stays system-wide, as Windows' `SHQueryUserNotificationState` is (a full-screen video on
  either monitor holds bubbles), and `covered()`, which hides the stage, becomes per screen, as `_win_covered` is.
- **M4A-03** true: `app._watch_screen_lock()` returns early on macOS.
- **M4A-04** true: `app._check_time()` calls `_check_accessibility()` every 30 s, and `Desk.reduce_motion()` makes
  a blocking portal `ReadOne` (up to 500 ms) each time. GNOME's `gsettings monitor` already hears changes, but
  tells no one. KDE's Do Not Disturb is also a blocking call, every 5 s; it moves to M4A-05's asynchronous reader.
- **M4A-05** true: only KDE's `Inhibited` and GNOME's `show-banners` are read. The servers' own interfaces were
  checked in their sources: dunst `org.dunstproject.cmd0` property `paused`; mako `fr.emersion.Mako.ListModes`
  (mode `do-not-disturb`, as mako's man page suggests); SwayNotificationCenter `org.erikreider.swaync.cc.GetDnd`
  on its own name; xfce4-notifyd's xfconf `/do-not-disturb` in channel `xfce4-notifyd`. `GetServerInformation`
  names them "dunst", "mako", "SwayNotificationCenter" and "Xfce Notify Daemon".
- **M4A-06** true: power saving comes only from Windows' Energy Saver and power-profiles-daemon.
- **M4A-07** ✓ as written: `sysnotify.send` has no hints but `desktop-entry`, no actions, and never replaces.
- **M4A-08** true: `_voiceover` posts whether or not Chatmon is active.
- **M4A-09** partly as written. **PyQt6 has no `QAccessibleAnnouncementEvent`**: checked in PyQt6 6.11.0 (Windows,
  this venv) and 6.12.1 (Linux, pip); PyQt6 wraps no part of `QAccessible`, so it can't be preferred anywhere and
  no code path is written for it. UI Automation is reached directly (`winuia.py`). What a UI Automation client
  (comtypes, validated against Calculator's own notifications) was seen to receive, on Windows 11: an event raised
  from a provider of the app's own (`IRawElementProviderSimple`) that doesn't use COM threading, on a dedicated
  window shown at least a moment before. Dropped without an error: one raised on `UiaHostProviderFromHwnd`'s
  provider; one whose provider rides on an ordinary Qt window that hands out Qt's provider (a line edit); one
  raised right after the window is shown; one from a provider with `ProviderOptions_UseComThreading`. The
  announcer window hands out its own provider for `WM_GETOBJECT`, so it doesn't depend on what Qt answers for that
  window. NVDA ignores notifications from apps in the background, so UIA is used while Chatmon is in front, and
  the notification remains the fallback.
- **M4A-10** true: `upower_battery()` makes up to three blocking calls. Nothing in it is tied to the screen's
  thread (QtDBus connections can be used from any thread), so the fix is one call, and a test on a worker thread.
- **M4A-11** true: `SessionWatcher` reports the lock only for breaks, and repeats it once per source.

## Design

- `presence.Desk` becomes a `QObject` with `settings_changed` and `screen_reader_changed` signals. Linux readings
  come from caches kept by listeners started on first use: `linuxsession.PortalSettings` (asynchronous `ReadOne`,
  or `Read` on an older portal, then `SettingChanged`), `presence._GSetting` (now with a change callback), and
  `linuxsession.NotificationDnd` (asynchronous, never starting a service: `NoAutoStart` on every message). The
  D-Bus listeners live in `linuxsession.py` because a D-Bus slot needs QtDBus when its class is defined, and
  `presence.py` is imported everywhere. High contrast on Linux: the portal's `contrast`, then GNOME's
  `high-contrast`, then Qt's; on macOS, `accessibilityDisplayShouldIncreaseContrast`. Qt's
  `contrastPreferenceChanged` is connected where PyQt has it as a signal (6.12; 6.11 wraps it as a method).
  The listeners belong to the Desk (Qt parent) and say changes with Qt signals, so an answer still on its way when
  the Desk goes reaches nothing: the whole suite on Linux aborted without this, where a test replaced the Desk.
- `winlock.LockWatcher` takes a `settings(action)` callback for `WM_SETTINGCHANGE`, from its own window only.
- `macnative.WorkspaceWatcher` is an Objective-C class of Chatmon's own (as `_Menus` is) observing NSWorkspace's
  sleep, wake, screens-sleep, screens-wake and accessibility-display notifications, and NSProcessInfo's power state.
- `linuxsession.PowerProfile` adds UPower's `OnBattery` (power saving while either is on), with asynchronous first
  reads; `SessionWatcher` reports `seen(bool)` and tells each change once.
- `sysnotify.Notifier` sends read-aloud notifications as transient, each replacing the last, alerts at urgency 2,
  and buttons as actions, reporting `ActionInvoked`.
- `a11y.announce()` is the one way to have something read out: UIA notifications on Windows while Chatmon is in
  front (`winuia.py`: a one-pixel see-through window, made when a screen reader is found, and its provider in
  ctypes), Orca, VoiceOver (held until Chatmon is active, or spoken by an opt-in fallback), else the app's notifier.
- `heads_up.upower_battery()` is one `GetAll` call, and the readings are safe on any thread.

Reuse: the D-Bus helpers in `presence.py`, the existing fakes (`fake_portal.py` gains Settings), the native event
filter in `winlock.py`, and `macnative`'s runtime and class pattern. New: `chatmon/winuia.py` (a COM object and
a native event filter of its own, like `winlock.py`); `tests/fake_notifications.py` and `tests/fake_upower.py`
(no existing fake serves those interfaces); `tests/uia_client.py` (a UI Automation client, with comtypes, a
test-only tool); `tests/private_bus.py` (a fake service and a client on a bus standing in for the system bus);
`tests/test_winlock.py` and `tests/test_platform_events.py` (M6A owns `test_windows.py`).

## Verification

- Windows: the whole suite and ruff, plus red drills (`reports/m4a/drill-spec.json`, results in `drills.log` and
  `drills.json`) on Windows-runnable tests.
- Linux: the Linux tests run in WSL (Arch, a throwaway venv in `/var/tmp/m4a-venv` with PyQt6 6.12.1, against the
  worktree's files), output in `suite-linux.log`; Linux red drills (`drill-spec-linux.json`, results in
  `drills-linux.log` and `drills-linux.json`) run in a throwaway clone of the branch in `/var/tmp/m4a-src`.
- macOS: tests that run on CI's macOS runner only; pending until the coordinator's CI run.
- Line endings: the evidence hashes are of the files as committed (LF). A Windows checkout with
  `core.autocrlf=true` writes CRLF, which changes the files' hashes but not their content in Git.

```quality-ledger
{
  "schema_version": 1,
  "work": {
    "id": "M4A",
    "title": "Platform awareness and screen readers",
    "scope_revision": 2,
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
        "pytest": "9.2.0",
        "ruff": "0.17.4",
        "pyqt6": "6.11.0"
      }
    }
  },
  "requirements": [
    {
      "id": "M4A-01",
      "statement": "High contrast is detected in the Linux packages (portal contrast, then GNOME high-contrast) and on macOS (accessibilityDisplayShouldIncreaseContrast).",
      "priority": "critical",
      "acceptance": [
        "AC-01a",
        "AC-01b",
        "AC-01c"
      ],
      "superseded_by": null
    },
    {
      "id": "M4A-02",
      "statement": "On Linux, covered() counts a full-screen window only on the stage's own screen.",
      "priority": "normal",
      "acceptance": [
        "AC-02"
      ],
      "superseded_by": null
    },
    {
      "id": "M4A-03",
      "statement": "macOS reports sleep, wake, screens-sleep and screens-wake through NSWorkspace observers.",
      "priority": "normal",
      "acceptance": [
        "AC-03"
      ],
      "superseded_by": null
    },
    {
      "id": "M4A-04",
      "statement": "Reduced motion and high contrast changes arrive as events (portal SettingChanged, Qt contrastPreferenceChanged, WM_SETTINGCHANGE) instead of blocking polls.",
      "priority": "normal",
      "acceptance": [
        "AC-04a",
        "AC-04b",
        "AC-04c"
      ],
      "superseded_by": null
    },
    {
      "id": "M4A-05",
      "statement": "Do Not Disturb is read from swaync, dunst, mako and xfce4-notifyd.",
      "priority": "normal",
      "acceptance": [
        "AC-05"
      ],
      "superseded_by": null
    },
    {
      "id": "M4A-06",
      "statement": "macOS Low Power Mode and UPower OnBattery feed power saving.",
      "priority": "normal",
      "acceptance": [
        "AC-06a",
        "AC-06b"
      ],
      "superseded_by": null
    },
    {
      "id": "M4A-07",
      "statement": "Linux read-aloud notifications are transient and replace each other, held alerts use urgency 2, and buttons are actions with ActionInvoked reported.",
      "priority": "critical",
      "acceptance": [
        "AC-07a",
        "AC-07b"
      ],
      "superseded_by": null
    },
    {
      "id": "M4A-08",
      "statement": "VoiceOver announcements made while Chatmon isn't in front are held until it is, or spoken by an opt-in speech fallback.",
      "priority": "normal",
      "acceptance": [
        "AC-08"
      ],
      "superseded_by": null
    },
    {
      "id": "M4A-09",
      "statement": "Windows screen readers get announcements through UI Automation notifications, with the notification only as a fallback.",
      "priority": "critical",
      "acceptance": [
        "AC-09a",
        "AC-09b"
      ],
      "superseded_by": null
    },
    {
      "id": "M4A-10",
      "statement": "Heads-up readings can run off the screen's thread, with one UPower call.",
      "priority": "normal",
      "acceptance": [
        "AC-10"
      ],
      "superseded_by": null
    },
    {
      "id": "M4A-11",
      "statement": "SessionWatcher reports the Linux lock so the stage can stop drawing.",
      "priority": "normal",
      "acceptance": [
        "AC-11"
      ],
      "superseded_by": null
    }
  ],
  "acceptance": [
    {
      "id": "AC-01a",
      "requirement": "M4A-01",
      "given": "A Linux desktop whose portal answers org.freedesktop.appearance contrast",
      "when": "Desk.high_contrast() is read",
      "then": "It is true for 1 and false for 0, whatever GNOME or Qt say",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-01b",
      "requirement": "M4A-01",
      "given": "A Linux desktop whose portal doesn't answer contrast",
      "when": "Desk.high_contrast() is read",
      "then": "GNOME's org.gnome.desktop.a11y.interface high-contrast decides, then Qt's contrast preference",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-01c",
      "requirement": "M4A-01",
      "given": "macOS",
      "when": "Desk.high_contrast() is read",
      "then": "It is NSWorkspace's accessibilityDisplayShouldIncreaseContrast",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-02",
      "requirement": "M4A-02",
      "given": "An X11 session with a full-screen window in front",
      "when": "Desk.covered(stage_window) is asked",
      "then": "It is true only when the full-screen window is on the stage's screen",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-03",
      "requirement": "M4A-03",
      "given": "A macnative.WorkspaceWatcher",
      "when": "NSWorkspace posts will-sleep, did-wake, screens-did-sleep and screens-did-wake",
      "then": "It emits slept(True), slept(False), screens_slept(True) and screens_slept(False)",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-04a",
      "requirement": "M4A-04",
      "given": "Desk reading the portal's settings on Linux",
      "when": "The portal sends SettingChanged for contrast or reduced-motion",
      "then": "settings_changed is emitted and the new value is read from the cache, with no further D-Bus call",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-04b",
      "requirement": "M4A-04",
      "given": "Qt 6.10 or later",
      "when": "Qt's contrastPreferenceChanged is emitted",
      "then": "Desk emits settings_changed",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-04c",
      "requirement": "M4A-04",
      "given": "winlock.LockWatcher with a settings callback, and Desk.windows_setting_changed",
      "when": "Its window gets WM_SETTINGCHANGE for high contrast, animation, message duration or the screen reader",
      "then": "The callback gets the action once; Desk emits settings_changed, or screen_reader_changed for the screen reader",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-05",
      "requirement": "M4A-05",
      "given": "dunst, mako, swaync or xfce4-notifyd running with Do Not Disturb on or off",
      "when": "Desk.quiet() is asked (and asked again once the asynchronous answer is in)",
      "then": "It says Do Not Disturb exactly when that server's own DND state is on, without starting any service",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-06a",
      "requirement": "M4A-06",
      "given": "linuxsession.PowerProfile",
      "when": "UPower's OnBattery or the power-saver profile changes",
      "then": "saving(True) is called while either is on, and saving(False) once both are off, each change once",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-06b",
      "requirement": "M4A-06",
      "given": "macOS",
      "when": "NSProcessInfo posts its power-state change",
      "then": "WorkspaceWatcher emits low_power_changed with isLowPowerModeEnabled, and macnative.low_power_mode() reads it",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-07a",
      "requirement": "M4A-07",
      "given": "sysnotify.Notifier on Linux",
      "when": "Two read-aloud notifications and one alert are sent",
      "then": "Read-aloud ones carry transient true and the second replaces the first's id; the alert carries urgency byte 2",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-07b",
      "requirement": "M4A-07",
      "given": "A notification sent with buttons",
      "when": "The server sends ActionInvoked for it (or for another app's id)",
      "then": "The buttons were sent as actions, and only our notification's action is reported, with its button",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-08",
      "requirement": "M4A-08",
      "given": "VoiceOver running and Chatmon not the active app",
      "when": "Something is announced",
      "then": "It is held and posted when Chatmon becomes active; with the speech fallback on, it is spoken at once instead",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-09a",
      "requirement": "M4A-09",
      "given": "Windows, a screen reader, and Chatmon the app in front",
      "when": "a11y.announce() is called",
      "then": "A UI Automation client receives a notification event with the words, and no notification is sent",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-09b",
      "requirement": "M4A-09",
      "given": "Windows with Chatmon in the background, or UIA unavailable",
      "when": "a11y.announce() is called",
      "then": "The notification fallback says it",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-10",
      "requirement": "M4A-10",
      "given": "A worker thread",
      "when": "heads_up.read_battery() and read_disks() run on it",
      "then": "They return the readings without error, and UPower is asked with one GetAll call",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-11",
      "requirement": "M4A-11",
      "given": "linuxsession.SessionWatcher with a seen callback",
      "when": "logind's LockedHint and the ScreenSaver's ActiveChanged report the lock and unlock",
      "then": "seen(False) is called once on locking and seen(True) once on unlocking, and locked() once per change",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    }
  ],
  "tasks": [
    {
      "id": "T-01",
      "purpose": "Desk as a QObject with change signals; portal settings cache; Linux high contrast; Qt's contrast signal; Windows setting changes; per-screen covered on X11",
      "acceptance": [
        "AC-01a",
        "AC-01b",
        "AC-02",
        "AC-04a",
        "AC-04b"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/presence.py",
          "action": "modify"
        },
        {
          "path": "chatmon/linuxsession.py",
          "action": "modify"
        },
        {
          "path": "tests/test_presence.py",
          "action": "modify"
        },
        {
          "path": "tests/test_linuxsession.py",
          "action": "modify"
        },
        {
          "path": "tests/fake_portal.py",
          "action": "modify"
        },
        {
          "path": "tests/test_portal_bus.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-win-tests",
        "EV-win-suite",
        "EV-linux-tests",
        "EV-linux-suite",
        "EV-red-AC-01a-portal-key",
        "EV-red-AC-01a-portal-flag",
        "EV-red-AC-01b-gnome-skipped",
        "EV-red-AC-02-any-monitor",
        "EV-red-AC-04a-setting-changed-ignored",
        "EV-red-AC-04a-no-dedupe",
        "EV-red-AC-04a-listener-outlives-desk",
        "EV-red-L-AC-01a-read-fallback",
        "EV-red-L-AC-04a-asked-each-time",
        "EV-red-L-AC-04b-qt-signal",
        "EV-red-L-AC-04a-listener-outlives-desk",
        "EV-red-L-AC-02-x11-place"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-02",
      "purpose": "WM_SETTINGCHANGE through winlock's filter, to Desk",
      "acceptance": [
        "AC-04c"
      ],
      "depends_on": [
        "T-01"
      ],
      "changes": [
        {
          "path": "chatmon/winlock.py",
          "action": "modify"
        },
        {
          "path": "tests/test_winlock.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-win-tests",
        "EV-win-suite",
        "EV-red-AC-04c-other-windows-copy",
        "EV-red-AC-04c-screen-reader"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-03",
      "purpose": "Do Not Disturb from dunst, mako, swaync and xfce4-notifyd (and KDE without blocking)",
      "acceptance": [
        "AC-05"
      ],
      "depends_on": [
        "T-01"
      ],
      "changes": [
        {
          "path": "chatmon/presence.py",
          "action": "modify"
        },
        {
          "path": "chatmon/linuxsession.py",
          "action": "modify"
        },
        {
          "path": "tests/test_presence.py",
          "action": "modify"
        },
        {
          "path": "tests/fake_notifications.py",
          "action": "create"
        },
        {
          "path": "tests/test_platform_events.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-win-tests",
        "EV-win-suite",
        "EV-linux-tests",
        "EV-linux-suite",
        "EV-red-AC-05-mako-modes",
        "EV-red-AC-05-dnd-ignored",
        "EV-red-L-AC-05-starts-services",
        "EV-red-L-AC-05-dunst-question"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-04",
      "purpose": "NSWorkspace and NSProcessInfo observers on macOS",
      "acceptance": [
        "AC-03",
        "AC-06b"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/macnative.py",
          "action": "modify"
        },
        {
          "path": "tests/test_macnative.py",
          "action": "modify"
        },
        {
          "path": "tests/test_platform_events.py",
          "action": "create"
        }
      ],
      "status": "implemented",
      "evidence": [
        "EV-win-tests",
        "EV-win-suite",
        "EV-linux-tests",
        "EV-linux-suite",
        "EV-macos-ci",
        "EV-red-AC-03-sleep-wake",
        "EV-red-AC-06b-low-power"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-05",
      "purpose": "UPower OnBattery in power saving; the lock reported for drawing, once per change",
      "acceptance": [
        "AC-06a",
        "AC-11"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/linuxsession.py",
          "action": "modify"
        },
        {
          "path": "tests/test_linuxsession.py",
          "action": "modify"
        },
        {
          "path": "tests/fake_upower.py",
          "action": "create"
        },
        {
          "path": "tests/private_bus.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-win-tests",
        "EV-win-suite",
        "EV-linux-tests",
        "EV-linux-suite",
        "EV-red-AC-06a-battery-ignored",
        "EV-red-AC-11-told-twice",
        "EV-red-AC-11-seen-inverted",
        "EV-red-L-AC-06a-upower-not-followed"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-06",
      "purpose": "Linux notifications: transient replacing read-aloud, urgent alerts, actions",
      "acceptance": [
        "AC-07a",
        "AC-07b"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/sysnotify.py",
          "action": "modify"
        },
        {
          "path": "tests/test_platform_events.py",
          "action": "create"
        },
        {
          "path": "tests/fake_notifications.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-win-tests",
        "EV-win-suite",
        "EV-linux-tests",
        "EV-linux-suite",
        "EV-red-AC-07a-transient",
        "EV-red-AC-07a-urgency-byte",
        "EV-red-AC-07b-replaced-buttons",
        "EV-red-AC-07b-other-apps",
        "EV-red-L-AC-07a-not-replaced",
        "EV-red-L-AC-07b-action-unheard"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-07",
      "purpose": "a11y.announce(): UIA notifications on Windows, VoiceOver held or spoken, the notifier as fallback",
      "acceptance": [
        "AC-08",
        "AC-09a",
        "AC-09b"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/a11y.py",
          "action": "modify"
        },
        {
          "path": "chatmon/winuia.py",
          "action": "create"
        },
        {
          "path": "tests/test_platform_events.py",
          "action": "create"
        },
        {
          "path": "tests/uia_client.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-win-tests",
        "EV-win-suite",
        "EV-linux-tests",
        "EV-linux-suite",
        "EV-red-AC-08-not-held",
        "EV-red-AC-08-no-fallback",
        "EV-red-AC-09a-client-side",
        "EV-red-AC-09a-not-handed-out",
        "EV-red-AC-09a-host-provider",
        "EV-red-AC-09b-behind",
        "EV-red-AC-09b-no-notification"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-08",
      "purpose": "One UPower call, and heads-up readings tested on a worker thread",
      "acceptance": [
        "AC-10"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/heads_up.py",
          "action": "modify"
        },
        {
          "path": "tests/test_heads_up.py",
          "action": "modify"
        },
        {
          "path": "tests/fake_upower.py",
          "action": "create"
        },
        {
          "path": "tests/private_bus.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-win-tests",
        "EV-win-suite",
        "EV-linux-tests",
        "EV-linux-suite",
        "EV-red-AC-10-plugged",
        "EV-red-L-AC-10-not-one-call"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-09",
      "purpose": "macOS high contrast from AppKit's Increase contrast",
      "acceptance": [
        "AC-01c"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/presence.py",
          "action": "modify"
        },
        {
          "path": "tests/test_presence.py",
          "action": "modify"
        }
      ],
      "status": "implemented",
      "evidence": [
        "EV-win-tests",
        "EV-win-suite",
        "EV-macos-ci",
        "EV-red-AC-01c-mac-contrast"
      ],
      "blocker": null,
      "superseded_by": null
    }
  ],
  "evidence": [
    {
      "id": "EV-readiness-1",
      "acceptance": [
        "AC-01a",
        "AC-01b",
        "AC-01c",
        "AC-02",
        "AC-03",
        "AC-04a",
        "AC-04b",
        "AC-04c",
        "AC-05",
        "AC-06a",
        "AC-06b",
        "AC-07a",
        "AC-07b",
        "AC-08",
        "AC-09a",
        "AC-09b",
        "AC-10",
        "AC-11"
      ],
      "kind": "readiness",
      "status": "stale",
      "command": [],
      "method": "Requirements review: each M4A finding traced in the source at 5346385, then the plan's criteria checked against the brief's Done-when lines, the roadmap's ownership and rules, and each other (coverage, conflicts, failure behavior, testability, terminology). Recorded in the artifact.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m4a/readiness-review.txt",
        "sha256": "029bd9239d3ca7660994415b29f92de40ab589f2181c3bd3ad802e03797e5878"
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
      "scope_sha256": "b266357bb32b6390b2ff18a2ef029246517f0bf7d2e748b092c6dee551b491b2",
      "red": null,
      "reason": "The plan was amended at scope_revision 2 (a new module, winuia.py; the Linux listeners in linuxsession.py; new test helpers; findings from implementation). Next action: the second review, readiness-review-2.txt, recorded as EV-readiness-2."
    },
    {
      "id": "EV-readiness-2",
      "acceptance": [
        "AC-01a",
        "AC-01b",
        "AC-01c",
        "AC-02",
        "AC-03",
        "AC-04a",
        "AC-04b",
        "AC-04c",
        "AC-05",
        "AC-06a",
        "AC-06b",
        "AC-07a",
        "AC-07b",
        "AC-08",
        "AC-09a",
        "AC-09b",
        "AC-10",
        "AC-11"
      ],
      "kind": "readiness",
      "status": "stale",
      "command": [],
      "method": "Second requirements review of the plan as amended at scope_revision 2: each change (new module, listener placement, test helpers, the macOS task split, findings from implementation and red drills) checked against the brief, the roadmap's ownership and rules, and the first review's coverage, conflicts and failure behavior. Recorded in the artifact.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m4a/readiness-review-2.txt",
        "sha256": "1078174ea19ee6adb33735e3b01ec16cc040a6e47f68b2a0aa35faee89eb0304"
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
      "scope_sha256": "be5c8f40e07c66c6412d3e2991e574c2bc4bc514a334e3038ed6fb7e5d8aaa0e",
      "red": null,
      "reason": "The plan's design and integration notes changed (the Linux listeners' ownership, found by the whole suite on Linux). Next action: readiness-review-3.txt, recorded as EV-readiness-3."
    },
    {
      "id": "EV-readiness-3",
      "acceptance": [
        "AC-01a",
        "AC-01b",
        "AC-01c",
        "AC-02",
        "AC-03",
        "AC-04a",
        "AC-04b",
        "AC-04c",
        "AC-05",
        "AC-06a",
        "AC-06b",
        "AC-07a",
        "AC-07b",
        "AC-08",
        "AC-09a",
        "AC-09b",
        "AC-10",
        "AC-11"
      ],
      "kind": "readiness",
      "status": "pass",
      "command": [],
      "method": "Third requirements review: the amended design and integration notes (the Linux listeners belong to the Desk; new parent parameters) checked against the criteria, ownership and the earlier reviews. Recorded in the artifact.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m4a/readiness-review-3.txt",
        "sha256": "4cf492f21dc3add15d6a42febce6c71e4027c8b75f02792abac0c017c216281c"
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
      "scope_sha256": "a6f6dc15f82ac8616b4a175cef36e0eaa1fe7ff3b0a8570399380f06aeded536",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-win-tests",
      "acceptance": [
        "AC-01a",
        "AC-01b",
        "AC-01c",
        "AC-02",
        "AC-03",
        "AC-04a",
        "AC-04c",
        "AC-05",
        "AC-06a",
        "AC-06b",
        "AC-07a",
        "AC-07b",
        "AC-08",
        "AC-09a",
        "AC-09b",
        "AC-10",
        "AC-11"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_presence.py",
        "tests/test_linuxsession.py",
        "tests/test_winlock.py",
        "tests/test_heads_up.py",
        "tests/test_platform_events.py",
        "tests/test_a11y.py",
        "tests/test_macnative.py",
        "tests/test_portal_bus.py"
      ],
      "method": "The M4A tests on Windows 11 (offscreen Qt for most; Qt's real Windows platform and a comtypes UI Automation client in subprocesses for the announcer and WM_SETTINGCHANGE): 55 passed, 32 skipped (other platforms' tests, and Qt's contrast signal, which PyQt6 6.11 wraps as a method). Output in the artifact.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/m4a-tests-windows.log",
        "sha256": "e20fe72e8f72b17b9b53d49b80869eaf846a5cd88334d95e13a51991b054944a"
      },
      "inputs": [
        {
          "path": "chatmon/a11y.py",
          "sha256": "aba945249b89b5da40f4b61d67a16299887ac3447c5fca64361155e12f2937e0"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "2fdd651948e492aa10423bc38bdd5fd4af268dead65f0b942627868365c63183"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "3938c335464e2f6a828677604897e0bb972ddb65adddcf8b0e78e3b46eeacb63"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "0e3f947994aaaf76eb53c94fb5e882be09f7feea9ea1a4eca848417eda3e2203"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "29527329a9d3735cd4baa157f97941f40a1d4b32443804aa7343b924e7e20598"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "07b3d8e2f97b38cb0f39173825d054b93caab1c9888453ac90226679ba58d410"
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
          "path": "tests/fake_notifications.py",
          "sha256": "4dcd214a2c4ba2303d1355dcc538f3ffdc7063a0504587e92f03fb3538d5b912"
        },
        {
          "path": "tests/fake_portal.py",
          "sha256": "546c8e803b87141a3998ca2e966c91309d4db52b112f72f9c1483b949cd5b24b"
        },
        {
          "path": "tests/fake_upower.py",
          "sha256": "bfa76d5e4e755f6987421e5ade5b9f7c1c50ff97eac5c322ed1de874b7c2ce3e"
        },
        {
          "path": "tests/private_bus.py",
          "sha256": "229b227961118c72f9f204952bdd5508450174a2c1043b1eb4d5fd7ff8bba9a2"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "fa2b96199f5dee5a8c91ac095f321e2c82a51b5fa2904de968cea5859c44f088"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        },
        {
          "path": "tests/test_macnative.py",
          "sha256": "7ed927e244aa95eb68462b6f86c28a23518daffb57f16d4f6ded257456981a30"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
        },
        {
          "path": "tests/test_portal_bus.py",
          "sha256": "f3a80e308add6b3c7f672f4092d4c349aaca93be9cf19208c93bdb7a1464c7a3"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
        },
        {
          "path": "tests/test_winlock.py",
          "sha256": "67a5738fa278f9cb52814236c203fb598abee92b9d72ecd631f38a8e610784d3"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "7075f36a283687bfb6f63b9f6650ae7542eeb87adde641bedcbb12b443fd7e70"
        }
      ],
      "scope_sha256": "a6f6dc15f82ac8616b4a175cef36e0eaa1fe7ff3b0a8570399380f06aeded536",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-win-suite",
      "acceptance": [
        "AC-01a",
        "AC-01b",
        "AC-01c",
        "AC-02",
        "AC-03",
        "AC-04a",
        "AC-04c",
        "AC-05",
        "AC-06a",
        "AC-06b",
        "AC-07a",
        "AC-07b",
        "AC-08",
        "AC-09a",
        "AC-09b",
        "AC-10",
        "AC-11"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider"
      ],
      "method": "The whole suite on Windows, the project's gate: 544 passed, 78 skipped. Output in the artifact.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/suite-windows.log",
        "sha256": "624e2ecbf658328f54e3489de44768ae4b76eb0de60588fa700429d2e35317cc"
      },
      "inputs": [
        {
          "path": "chatmon/a11y.py",
          "sha256": "aba945249b89b5da40f4b61d67a16299887ac3447c5fca64361155e12f2937e0"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "2fdd651948e492aa10423bc38bdd5fd4af268dead65f0b942627868365c63183"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "3938c335464e2f6a828677604897e0bb972ddb65adddcf8b0e78e3b46eeacb63"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "0e3f947994aaaf76eb53c94fb5e882be09f7feea9ea1a4eca848417eda3e2203"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "29527329a9d3735cd4baa157f97941f40a1d4b32443804aa7343b924e7e20598"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "07b3d8e2f97b38cb0f39173825d054b93caab1c9888453ac90226679ba58d410"
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
          "path": "tests/fake_notifications.py",
          "sha256": "4dcd214a2c4ba2303d1355dcc538f3ffdc7063a0504587e92f03fb3538d5b912"
        },
        {
          "path": "tests/fake_portal.py",
          "sha256": "546c8e803b87141a3998ca2e966c91309d4db52b112f72f9c1483b949cd5b24b"
        },
        {
          "path": "tests/fake_upower.py",
          "sha256": "bfa76d5e4e755f6987421e5ade5b9f7c1c50ff97eac5c322ed1de874b7c2ce3e"
        },
        {
          "path": "tests/private_bus.py",
          "sha256": "229b227961118c72f9f204952bdd5508450174a2c1043b1eb4d5fd7ff8bba9a2"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "fa2b96199f5dee5a8c91ac095f321e2c82a51b5fa2904de968cea5859c44f088"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        },
        {
          "path": "tests/test_macnative.py",
          "sha256": "7ed927e244aa95eb68462b6f86c28a23518daffb57f16d4f6ded257456981a30"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
        },
        {
          "path": "tests/test_portal_bus.py",
          "sha256": "f3a80e308add6b3c7f672f4092d4c349aaca93be9cf19208c93bdb7a1464c7a3"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
        },
        {
          "path": "tests/test_winlock.py",
          "sha256": "67a5738fa278f9cb52814236c203fb598abee92b9d72ecd631f38a8e610784d3"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "7075f36a283687bfb6f63b9f6650ae7542eeb87adde641bedcbb12b443fd7e70"
        }
      ],
      "scope_sha256": "a6f6dc15f82ac8616b4a175cef36e0eaa1fe7ff3b0a8570399380f06aeded536",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-linux-tests",
      "acceptance": [
        "AC-01a",
        "AC-01b",
        "AC-02",
        "AC-03",
        "AC-04a",
        "AC-04b",
        "AC-05",
        "AC-06a",
        "AC-06b",
        "AC-07a",
        "AC-07b",
        "AC-08",
        "AC-09b",
        "AC-10",
        "AC-11"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "/var/tmp/m4a-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_presence.py",
        "tests/test_linuxsession.py",
        "tests/test_winlock.py",
        "tests/test_heads_up.py",
        "tests/test_platform_events.py",
        "tests/test_a11y.py",
        "tests/test_macnative.py",
        "tests/test_portal_bus.py"
      ],
      "method": "The M4A tests on Linux: WSL 2 (Arch, kernel 6.18.58.1-microsoft-standard-WSL2) against the worktree's files, from a throwaway venv (Python 3.14.9, PyQt6 6.12.1), with dbus-run-session for the pretend portal, notification servers and UPower: 63 passed, 24 skipped (other platforms' tests). Output in the artifact.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "pyqt6": "6.12.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/suite-linux.log",
        "sha256": "e259f7709c1abe2a27c08f118b076157da1f9edea6fc8455267c8f1f3dc6347c"
      },
      "inputs": [
        {
          "path": "chatmon/a11y.py",
          "sha256": "aba945249b89b5da40f4b61d67a16299887ac3447c5fca64361155e12f2937e0"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "2fdd651948e492aa10423bc38bdd5fd4af268dead65f0b942627868365c63183"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "3938c335464e2f6a828677604897e0bb972ddb65adddcf8b0e78e3b46eeacb63"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "0e3f947994aaaf76eb53c94fb5e882be09f7feea9ea1a4eca848417eda3e2203"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "07b3d8e2f97b38cb0f39173825d054b93caab1c9888453ac90226679ba58d410"
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
          "path": "tests/fake_notifications.py",
          "sha256": "4dcd214a2c4ba2303d1355dcc538f3ffdc7063a0504587e92f03fb3538d5b912"
        },
        {
          "path": "tests/fake_portal.py",
          "sha256": "546c8e803b87141a3998ca2e966c91309d4db52b112f72f9c1483b949cd5b24b"
        },
        {
          "path": "tests/fake_upower.py",
          "sha256": "bfa76d5e4e755f6987421e5ade5b9f7c1c50ff97eac5c322ed1de874b7c2ce3e"
        },
        {
          "path": "tests/private_bus.py",
          "sha256": "229b227961118c72f9f204952bdd5508450174a2c1043b1eb4d5fd7ff8bba9a2"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "fa2b96199f5dee5a8c91ac095f321e2c82a51b5fa2904de968cea5859c44f088"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        },
        {
          "path": "tests/test_macnative.py",
          "sha256": "7ed927e244aa95eb68462b6f86c28a23518daffb57f16d4f6ded257456981a30"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
        },
        {
          "path": "tests/test_portal_bus.py",
          "sha256": "f3a80e308add6b3c7f672f4092d4c349aaca93be9cf19208c93bdb7a1464c7a3"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "7075f36a283687bfb6f63b9f6650ae7542eeb87adde641bedcbb12b443fd7e70"
        }
      ],
      "scope_sha256": "2bdfe510cfb51a8025218243ff0f9d9828ac3b8a7139a68d4d95ec40f3a92414",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-linux-suite",
      "acceptance": [
        "AC-01a",
        "AC-01b",
        "AC-02",
        "AC-03",
        "AC-04a",
        "AC-04b",
        "AC-05",
        "AC-06a",
        "AC-06b",
        "AC-07a",
        "AC-07b",
        "AC-08",
        "AC-09b",
        "AC-10",
        "AC-11"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "/var/tmp/m4a-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider"
      ],
      "method": "The whole suite on Linux, as above, with the machine's real session and system buses: 557 passed, 65 skipped (the base commit 5346385 gave 517 passed, 56 skipped there). Output in the artifact.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "pyqt6": "6.12.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/suite-linux-full.log",
        "sha256": "465c26dc47e1b3f1da5e96282b7459eb78a13c9f1332f35c3ad63708a734066a"
      },
      "inputs": [
        {
          "path": "chatmon/a11y.py",
          "sha256": "aba945249b89b5da40f4b61d67a16299887ac3447c5fca64361155e12f2937e0"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "2fdd651948e492aa10423bc38bdd5fd4af268dead65f0b942627868365c63183"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "3938c335464e2f6a828677604897e0bb972ddb65adddcf8b0e78e3b46eeacb63"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "0e3f947994aaaf76eb53c94fb5e882be09f7feea9ea1a4eca848417eda3e2203"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "07b3d8e2f97b38cb0f39173825d054b93caab1c9888453ac90226679ba58d410"
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
          "path": "tests/fake_notifications.py",
          "sha256": "4dcd214a2c4ba2303d1355dcc538f3ffdc7063a0504587e92f03fb3538d5b912"
        },
        {
          "path": "tests/fake_portal.py",
          "sha256": "546c8e803b87141a3998ca2e966c91309d4db52b112f72f9c1483b949cd5b24b"
        },
        {
          "path": "tests/fake_upower.py",
          "sha256": "bfa76d5e4e755f6987421e5ade5b9f7c1c50ff97eac5c322ed1de874b7c2ce3e"
        },
        {
          "path": "tests/private_bus.py",
          "sha256": "229b227961118c72f9f204952bdd5508450174a2c1043b1eb4d5fd7ff8bba9a2"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "fa2b96199f5dee5a8c91ac095f321e2c82a51b5fa2904de968cea5859c44f088"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        },
        {
          "path": "tests/test_macnative.py",
          "sha256": "7ed927e244aa95eb68462b6f86c28a23518daffb57f16d4f6ded257456981a30"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
        },
        {
          "path": "tests/test_portal_bus.py",
          "sha256": "f3a80e308add6b3c7f672f4092d4c349aaca93be9cf19208c93bdb7a1464c7a3"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "7075f36a283687bfb6f63b9f6650ae7542eeb87adde641bedcbb12b443fd7e70"
        }
      ],
      "scope_sha256": "2bdfe510cfb51a8025218243ff0f9d9828ac3b8a7139a68d4d95ec40f3a92414",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-macos-ci",
      "acceptance": [
        "AC-01c",
        "AC-03",
        "AC-06b"
      ],
      "kind": "behavior",
      "status": "deferred",
      "command": [
        "python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_macnative.py",
        "tests/test_presence.py"
      ],
      "method": "macOS end to end: NSWorkspace and NSProcessInfo notifications posted to a real WorkspaceWatcher, Low Power Mode read, and AppKit's Increase contrast read by Desk. Runs only on macOS.",
      "environment": {
        "platform": "macos",
        "tools": {
          "python": "CI",
          "pyqt6": "CI"
        }
      },
      "exit_code": null,
      "artifact": null,
      "inputs": [
        {
          "path": "chatmon/macnative.py",
          "sha256": "3938c335464e2f6a828677604897e0bb972ddb65adddcf8b0e78e3b46eeacb63"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
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
          "path": "tests/test_macnative.py",
          "sha256": "7ed927e244aa95eb68462b6f86c28a23518daffb57f16d4f6ded257456981a30"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
        }
      ],
      "scope_sha256": "6d08fdb0228cba105b80e3008fcc96c6a9f6333facd8edea95a22d08e000b513",
      "red": null,
      "reason": "No Mac here. Next action: the coordinator's CI run on macOS (test_macnative.py::test_sleep_wake_displays_accessibility_and_low_power_are_heard, test_presence.py::test_macos_reads_increase_contrast); on a failure, CI's output comes back to this milestone."
    },
    {
      "id": "EV-red-AC-01a-portal-key",
      "acceptance": [
        "AC-01a"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_presence.py::test_the_portals_contrast_decides_and_says_when_it_changes"
      ],
      "method": "Red drill AC-01a-portal-key (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/presence.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
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
          "path": "tests/fake_portal.py",
          "sha256": "546c8e803b87141a3998ca2e966c91309d4db52b112f72f9c1483b949cd5b24b"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        },
        {
          "path": "tests/test_portal_bus.py",
          "sha256": "f3a80e308add6b3c7f672f4092d4c349aaca93be9cf19208c93bdb7a1464c7a3"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
        }
      ],
      "scope_sha256": "ab438008853695f8ae3ab94dc6b9d2eafbaea5aeb0d27dffc6a5b54d59a624bb",
      "red": {
        "mutation": "chatmon/presence.py: 'portal = self._portal_flag(\"contrast\")' -> 'portal = self._portal_flag(\"reduced-motion\")'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_portals_contrast_decides_and_says_when_it_changes",
        "observed_diagnostic": "_________ test_the_portals_contrast_decides_and_says_when_it_changes __________",
        "before": [
          {
            "path": "chatmon/presence.py",
            "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/presence.py",
            "sha256": "2b491079c32cd9d955895161699258bb0edcb861b004c5ea1738cba129294327"
          }
        ],
        "after": [
          {
            "path": "chatmon/presence.py",
            "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-01a-portal-flag",
      "acceptance": [
        "AC-01a"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_linuxsession.py::test_portal_settings_are_yes_no_or_unknown",
        "tests/test_presence.py::test_the_portals_contrast_decides_and_says_when_it_changes"
      ],
      "method": "Red drill AC-01a-portal-flag (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/linuxsession.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
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
          "path": "tests/fake_portal.py",
          "sha256": "546c8e803b87141a3998ca2e966c91309d4db52b112f72f9c1483b949cd5b24b"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        },
        {
          "path": "tests/test_portal_bus.py",
          "sha256": "f3a80e308add6b3c7f672f4092d4c349aaca93be9cf19208c93bdb7a1464c7a3"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
        }
      ],
      "scope_sha256": "ab438008853695f8ae3ab94dc6b9d2eafbaea5aeb0d27dffc6a5b54d59a624bb",
      "red": {
        "mutation": "chatmon/linuxsession.py: '    return value == 1\\n' -> '    return value == 0\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_portal_settings_are_yes_no_or_unknown",
        "observed_diagnostic": "_________________ test_portal_settings_are_yes_no_or_unknown __________________",
        "before": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "c5d743693568af9269cc9f2a86bf118e5e7a6d8204f17ee59e470e4774b5596b"
          }
        ],
        "after": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-01b-gnome-skipped",
      "acceptance": [
        "AC-01b"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_presence.py::test_without_the_portal_gnome_then_qt_say_whether_contrast_is_high"
      ],
      "method": "Red drill AC-01b-gnome-skipped (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/presence.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
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
          "path": "tests/fake_portal.py",
          "sha256": "546c8e803b87141a3998ca2e966c91309d4db52b112f72f9c1483b949cd5b24b"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        },
        {
          "path": "tests/test_portal_bus.py",
          "sha256": "f3a80e308add6b3c7f672f4092d4c349aaca93be9cf19208c93bdb7a1464c7a3"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
        }
      ],
      "scope_sha256": "ab438008853695f8ae3ab94dc6b9d2eafbaea5aeb0d27dffc6a5b54d59a624bb",
      "red": {
        "mutation": "chatmon/presence.py: '        if gnome is not None:\\n            return gnome == \"true\"' -> '        if gnome is None:\\n            return gnome == \"true\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_without_the_portal_gnome_then_qt_say_whether_contrast_is_high",
        "observed_diagnostic": "_____ test_without_the_portal_gnome_then_qt_say_whether_contrast_is_high ______",
        "before": [
          {
            "path": "chatmon/presence.py",
            "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/presence.py",
            "sha256": "5f8cda0053aabcb22ab15aafb4f0c8b342d0d8f998546a00db717ea78adb9d41"
          }
        ],
        "after": [
          {
            "path": "chatmon/presence.py",
            "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-01c-mac-contrast",
      "acceptance": [
        "AC-01c"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_presence.py::test_macos_high_contrast_is_appkits_increase_contrast"
      ],
      "method": "Red drill AC-01c-mac-contrast (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/presence.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/presence.py",
          "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
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
          "path": "tests/test_presence.py",
          "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
        }
      ],
      "scope_sha256": "1566d5a0aad220e2f92b2fb3c3fd34277967fb87fee7e52e352a4a2efd23aa1d",
      "red": {
        "mutation": "chatmon/presence.py: 'return bool(_mac_increase_contrast())' -> 'return bool(_mac_reduce_motion())'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_macos_high_contrast_is_appkits_increase_contrast",
        "observed_diagnostic": "____________ test_macos_high_contrast_is_appkits_increase_contrast ____________",
        "before": [
          {
            "path": "chatmon/presence.py",
            "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/presence.py",
            "sha256": "fa603a586eed484413c1b45905ad45f80b4941142064dac357ac1152d0651220"
          }
        ],
        "after": [
          {
            "path": "chatmon/presence.py",
            "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-02-any-monitor",
      "acceptance": [
        "AC-02"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_presence.py::test_a_full_screen_window_counts_only_on_the_stages_screen",
        "tests/test_presence.py::test_covered_on_x11_asks_where_the_full_screen_window_is"
      ],
      "method": "Red drill AC-02-any-monitor (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/presence.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
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
          "path": "tests/fake_portal.py",
          "sha256": "546c8e803b87141a3998ca2e966c91309d4db52b112f72f9c1483b949cd5b24b"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        },
        {
          "path": "tests/test_portal_bus.py",
          "sha256": "f3a80e308add6b3c7f672f4092d4c349aaca93be9cf19208c93bdb7a1464c7a3"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
        }
      ],
      "scope_sha256": "ab438008853695f8ae3ab94dc6b9d2eafbaea5aeb0d27dffc6a5b54d59a624bb",
      "red": {
        "mutation": "chatmon/presence.py: 'return fx <= mx < fx + fw and fy <= my < fy + fh' -> 'return fy <= my < fy + fh'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_full_screen_window_counts_only_on_the_stages_screen",
        "observed_diagnostic": "_________ test_a_full_screen_window_counts_only_on_the_stages_screen __________",
        "before": [
          {
            "path": "chatmon/presence.py",
            "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/presence.py",
            "sha256": "2b3b871f0a00deaa7d5459a70d289aea3dd000959a9231bfe26670e93391904a"
          }
        ],
        "after": [
          {
            "path": "chatmon/presence.py",
            "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-03-sleep-wake",
      "acceptance": [
        "AC-03"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_platform_events.py::test_each_workspace_notification_is_its_own_signal"
      ],
      "method": "Red drill AC-03-sleep-wake (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/macnative.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/macnative.py",
          "sha256": "3938c335464e2f6a828677604897e0bb972ddb65adddcf8b0e78e3b46eeacb63"
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
          "path": "tests/test_macnative.py",
          "sha256": "7ed927e244aa95eb68462b6f86c28a23518daffb57f16d4f6ded257456981a30"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
        }
      ],
      "scope_sha256": "f5a78896b45e1d7078620dba028316c2e03a78f48bd4a8a98e33ae0eb12efc3d",
      "red": {
        "mutation": "chatmon/macnative.py: 'self.slept.emit(selector == \"willSleep:\")' -> 'self.slept.emit(selector == \"didWake:\")'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_each_workspace_notification_is_its_own_signal",
        "observed_diagnostic": "_____________ test_each_workspace_notification_is_its_own_signal ______________",
        "before": [
          {
            "path": "chatmon/macnative.py",
            "sha256": "3938c335464e2f6a828677604897e0bb972ddb65adddcf8b0e78e3b46eeacb63"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/macnative.py",
            "sha256": "aa5a9f028120a2185b69179816c3d96912dda509f561227c8fa81ce44220b424"
          }
        ],
        "after": [
          {
            "path": "chatmon/macnative.py",
            "sha256": "3938c335464e2f6a828677604897e0bb972ddb65adddcf8b0e78e3b46eeacb63"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-04a-setting-changed-ignored",
      "acceptance": [
        "AC-04a"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_presence.py::test_the_portals_contrast_decides_and_says_when_it_changes"
      ],
      "method": "Red drill AC-04a-setting-changed-ignored (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/linuxsession.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
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
          "path": "tests/fake_portal.py",
          "sha256": "546c8e803b87141a3998ca2e966c91309d4db52b112f72f9c1483b949cd5b24b"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        },
        {
          "path": "tests/test_portal_bus.py",
          "sha256": "f3a80e308add6b3c7f672f4092d4c349aaca93be9cf19208c93bdb7a1464c7a3"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
        }
      ],
      "scope_sha256": "ab438008853695f8ae3ab94dc6b9d2eafbaea5aeb0d27dffc6a5b54d59a624bb",
      "red": {
        "mutation": "chatmon/linuxsession.py: 'args[0] == APPEARANCE and args[1] in APPEARANCE_KEYS' -> 'args[0] == APPEARANCE and args[1] not in APPEARANCE_KEYS'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_portals_contrast_decides_and_says_when_it_changes",
        "observed_diagnostic": "_________ test_the_portals_contrast_decides_and_says_when_it_changes __________",
        "before": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "39513b678741527d360fc1e1f710d2ad506004a5415f033e4ec34534b0670300"
          }
        ],
        "after": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-04a-no-dedupe",
      "acceptance": [
        "AC-04a"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_linuxsession.py::test_portal_settings_are_yes_no_or_unknown",
        "tests/test_presence.py::test_the_portals_contrast_decides_and_says_when_it_changes"
      ],
      "method": "Red drill AC-04a-no-dedupe (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/linuxsession.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
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
          "path": "tests/fake_portal.py",
          "sha256": "546c8e803b87141a3998ca2e966c91309d4db52b112f72f9c1483b949cd5b24b"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        },
        {
          "path": "tests/test_portal_bus.py",
          "sha256": "f3a80e308add6b3c7f672f4092d4c349aaca93be9cf19208c93bdb7a1464c7a3"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
        }
      ],
      "scope_sha256": "ab438008853695f8ae3ab94dc6b9d2eafbaea5aeb0d27dffc6a5b54d59a624bb",
      "red": {
        "mutation": "chatmon/linuxsession.py: '        if key in self.values and self.values[key] == flag:\\n            return\\n' -> ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_portal_settings_are_yes_no_or_unknown",
        "observed_diagnostic": "_________________ test_portal_settings_are_yes_no_or_unknown __________________",
        "before": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "f5ffb7447a956cb62ed551c05196aef20e0cb7e03ec9cf01f3eb24bcde133a82"
          }
        ],
        "after": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-04c-other-windows-copy",
      "acceptance": [
        "AC-04c"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_winlock.py::test_a_setting_change_is_passed_on_once_from_its_own_window"
      ],
      "method": "Red drill AC-04c-other-windows-copy (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/winlock.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "29527329a9d3735cd4baa157f97941f40a1d4b32443804aa7343b924e7e20598"
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
          "path": "tests/fake_portal.py",
          "sha256": "546c8e803b87141a3998ca2e966c91309d4db52b112f72f9c1483b949cd5b24b"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        },
        {
          "path": "tests/test_portal_bus.py",
          "sha256": "f3a80e308add6b3c7f672f4092d4c349aaca93be9cf19208c93bdb7a1464c7a3"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
        },
        {
          "path": "tests/test_winlock.py",
          "sha256": "67a5738fa278f9cb52814236c203fb598abee92b9d72ecd631f38a8e610784d3"
        }
      ],
      "scope_sha256": "c2dee49d2dff483c030cf3cacf0dd649e8666de55fbd40e9e50893d7f42df187",
      "red": {
        "mutation": "chatmon/winlock.py: 'elif msg.hWnd == self.hwnd and msg.message == WM_SETTINGCHANGE' -> 'elif msg.message == WM_SETTINGCHANGE'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_setting_change_is_passed_on_once_from_its_own_window",
        "observed_diagnostic": "_________ test_a_setting_change_is_passed_on_once_from_its_own_window _________",
        "before": [
          {
            "path": "chatmon/winlock.py",
            "sha256": "29527329a9d3735cd4baa157f97941f40a1d4b32443804aa7343b924e7e20598"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/winlock.py",
            "sha256": "6f4d50c10561bfb02c19407e18e06a951ac41325a0735b0bfd1cf2a004cfdcac"
          }
        ],
        "after": [
          {
            "path": "chatmon/winlock.py",
            "sha256": "29527329a9d3735cd4baa157f97941f40a1d4b32443804aa7343b924e7e20598"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-04c-screen-reader",
      "acceptance": [
        "AC-04c"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_presence.py::test_windows_setting_changes_are_passed_on",
        "tests/test_winlock.py::test_a_sent_wm_settingchange_reaches_desk_through_qts_window_procedure"
      ],
      "method": "Red drill AC-04c-screen-reader (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/presence.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "29527329a9d3735cd4baa157f97941f40a1d4b32443804aa7343b924e7e20598"
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
          "path": "tests/fake_portal.py",
          "sha256": "546c8e803b87141a3998ca2e966c91309d4db52b112f72f9c1483b949cd5b24b"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        },
        {
          "path": "tests/test_portal_bus.py",
          "sha256": "f3a80e308add6b3c7f672f4092d4c349aaca93be9cf19208c93bdb7a1464c7a3"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
        },
        {
          "path": "tests/test_winlock.py",
          "sha256": "67a5738fa278f9cb52814236c203fb598abee92b9d72ecd631f38a8e610784d3"
        }
      ],
      "scope_sha256": "c2dee49d2dff483c030cf3cacf0dd649e8666de55fbd40e9e50893d7f42df187",
      "red": {
        "mutation": "chatmon/presence.py: '        if action == SPI_SETSCREENREADER:' -> '        if action == SPI_SETHIGHCONTRAST:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_windows_setting_changes_are_passed_on",
        "observed_diagnostic": "_________________ test_windows_setting_changes_are_passed_on __________________",
        "before": [
          {
            "path": "chatmon/presence.py",
            "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/presence.py",
            "sha256": "539c8cecc9fd58c18dac1f5a67d34578608e50507def4f6f0c29245f08271c2d"
          }
        ],
        "after": [
          {
            "path": "chatmon/presence.py",
            "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-05-mako-modes",
      "acceptance": [
        "AC-05"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_presence.py::test_each_notification_servers_do_not_disturb_holds_bubbles"
      ],
      "method": "Red drill AC-05-mako-modes (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/linuxsession.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
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
          "path": "tests/fake_notifications.py",
          "sha256": "4dcd214a2c4ba2303d1355dcc538f3ffdc7063a0504587e92f03fb3538d5b912"
        },
        {
          "path": "tests/fake_portal.py",
          "sha256": "546c8e803b87141a3998ca2e966c91309d4db52b112f72f9c1483b949cd5b24b"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
        },
        {
          "path": "tests/test_portal_bus.py",
          "sha256": "f3a80e308add6b3c7f672f4092d4c349aaca93be9cf19208c93bdb7a1464c7a3"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
        }
      ],
      "scope_sha256": "957b6ce8dd80c9b99b8657a7ccaa5b703461cfd9f94dd0b9d7b41b6e94a8ec82",
      "red": {
        "mutation": "chatmon/linuxsession.py: 'return MAKO_DND_MODE in answer if isinstance(answer, list) else None' -> 'return bool(answer) if isinstance(answer, list) else None'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_each_notification_servers_do_not_disturb_holds_bubbles[mako",
        "observed_diagnostic": "_ test_each_notification_servers_do_not_disturb_holds_bubbles[mako-on4-off4] __",
        "before": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "f2dedb5e78d357ffc17e29948531f443d5905d62ae12f9f7c1772b0dcd90350f"
          }
        ],
        "after": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-05-dnd-ignored",
      "acceptance": [
        "AC-05"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_presence.py::test_each_notification_servers_do_not_disturb_holds_bubbles"
      ],
      "method": "Red drill AC-05-dnd-ignored (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/presence.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
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
          "path": "tests/fake_notifications.py",
          "sha256": "4dcd214a2c4ba2303d1355dcc538f3ffdc7063a0504587e92f03fb3538d5b912"
        },
        {
          "path": "tests/fake_portal.py",
          "sha256": "546c8e803b87141a3998ca2e966c91309d4db52b112f72f9c1483b949cd5b24b"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
        },
        {
          "path": "tests/test_portal_bus.py",
          "sha256": "f3a80e308add6b3c7f672f4092d4c349aaca93be9cf19208c93bdb7a1464c7a3"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
        }
      ],
      "scope_sha256": "957b6ce8dd80c9b99b8657a7ccaa5b703461cfd9f94dd0b9d7b41b6e94a8ec82",
      "red": {
        "mutation": "chatmon/presence.py: '            if dnd.state:\\n' -> '            if dnd.state is None:\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_each_notification_servers_do_not_disturb_holds_bubbles[dunst",
        "observed_diagnostic": "_ test_each_notification_servers_do_not_disturb_holds_bubbles[dunst-True-False] _",
        "before": [
          {
            "path": "chatmon/presence.py",
            "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/presence.py",
            "sha256": "3e924aaef5ab73d9a7fb01b6d125f18e604d19d2a2380d7ce8c14fde340556bc"
          }
        ],
        "after": [
          {
            "path": "chatmon/presence.py",
            "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-06a-battery-ignored",
      "acceptance": [
        "AC-06a"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_linuxsession.py::test_running_on_battery_saves_power_too"
      ],
      "method": "Red drill AC-06a-battery-ignored (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/linuxsession.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
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
          "path": "tests/fake_upower.py",
          "sha256": "bfa76d5e4e755f6987421e5ade5b9f7c1c50ff97eac5c322ed1de874b7c2ce3e"
        },
        {
          "path": "tests/private_bus.py",
          "sha256": "229b227961118c72f9f204952bdd5508450174a2c1043b1eb4d5fd7ff8bba9a2"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        }
      ],
      "scope_sha256": "b7a4a03d139c596972ca1dab1627cb5e042e0a29abce3a3b56d8b7bc84685a14",
      "red": {
        "mutation": "chatmon/linuxsession.py: 'saving = self.profile_saver or self.on_battery' -> 'saving = self.profile_saver'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_running_on_battery_saves_power_too",
        "observed_diagnostic": "___________________ test_running_on_battery_saves_power_too ___________________",
        "before": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "b1bed7cbb55eb98193c276922c032c8d2d11c4ab427f4ae3e4203c7e853a8dac"
          }
        ],
        "after": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-06b-low-power",
      "acceptance": [
        "AC-06b"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_platform_events.py::test_each_workspace_notification_is_its_own_signal"
      ],
      "method": "Red drill AC-06b-low-power (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/macnative.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/macnative.py",
          "sha256": "3938c335464e2f6a828677604897e0bb972ddb65adddcf8b0e78e3b46eeacb63"
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
          "path": "tests/test_macnative.py",
          "sha256": "7ed927e244aa95eb68462b6f86c28a23518daffb57f16d4f6ded257456981a30"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
        }
      ],
      "scope_sha256": "f5a78896b45e1d7078620dba028316c2e03a78f48bd4a8a98e33ae0eb12efc3d",
      "red": {
        "mutation": "chatmon/macnative.py: 'self.low_power_changed.emit(bool(low_power_mode()))' -> 'self.low_power_changed.emit(False)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_each_workspace_notification_is_its_own_signal",
        "observed_diagnostic": "_____________ test_each_workspace_notification_is_its_own_signal ______________",
        "before": [
          {
            "path": "chatmon/macnative.py",
            "sha256": "3938c335464e2f6a828677604897e0bb972ddb65adddcf8b0e78e3b46eeacb63"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/macnative.py",
            "sha256": "d81aa6f9badcbd4301ffb2cf4cffa2b7288a84608f3e823160121d66d9a17686"
          }
        ],
        "after": [
          {
            "path": "chatmon/macnative.py",
            "sha256": "3938c335464e2f6a828677604897e0bb972ddb65adddcf8b0e78e3b46eeacb63"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-07a-transient",
      "acceptance": [
        "AC-07a"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_platform_events.py::test_read_aloud_notifications_are_transient_and_alerts_urgent"
      ],
      "method": "Red drill AC-07a-transient (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/sysnotify.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "0e3f947994aaaf76eb53c94fb5e882be09f7feea9ea1a4eca848417eda3e2203"
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
          "path": "tests/fake_notifications.py",
          "sha256": "4dcd214a2c4ba2303d1355dcc538f3ffdc7063a0504587e92f03fb3538d5b912"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
        }
      ],
      "scope_sha256": "f65953c7d401c4850328235ed4a1a636a12bf76ab36edb1af8128d8c4f02df0f",
      "red": {
        "mutation": "chatmon/sysnotify.py: '        out[\"transient\"] = True\\n' -> '        pass\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_read_aloud_notifications_are_transient_and_alerts_urgent",
        "observed_diagnostic": "________ test_read_aloud_notifications_are_transient_and_alerts_urgent ________",
        "before": [
          {
            "path": "chatmon/sysnotify.py",
            "sha256": "0e3f947994aaaf76eb53c94fb5e882be09f7feea9ea1a4eca848417eda3e2203"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sysnotify.py",
            "sha256": "f33fede36f01760aead4d1ffc4803d44021ee42f2b6a1cd09286433455a28c4a"
          }
        ],
        "after": [
          {
            "path": "chatmon/sysnotify.py",
            "sha256": "0e3f947994aaaf76eb53c94fb5e882be09f7feea9ea1a4eca848417eda3e2203"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-07a-urgency-byte",
      "acceptance": [
        "AC-07a"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_platform_events.py::test_read_aloud_notifications_are_transient_and_alerts_urgent"
      ],
      "method": "Red drill AC-07a-urgency-byte (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/sysnotify.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "0e3f947994aaaf76eb53c94fb5e882be09f7feea9ea1a4eca848417eda3e2203"
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
          "path": "tests/fake_notifications.py",
          "sha256": "4dcd214a2c4ba2303d1355dcc538f3ffdc7063a0504587e92f03fb3538d5b912"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
        }
      ],
      "scope_sha256": "f65953c7d401c4850328235ed4a1a636a12bf76ab36edb1af8128d8c4f02df0f",
      "red": {
        "mutation": "chatmon/sysnotify.py: 'out[\"urgency\"] = _typed(urgency, \"UChar\")' -> 'out[\"urgency\"] = _typed(urgency, \"Int\")'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_read_aloud_notifications_are_transient_and_alerts_urgent",
        "observed_diagnostic": "________ test_read_aloud_notifications_are_transient_and_alerts_urgent ________",
        "before": [
          {
            "path": "chatmon/sysnotify.py",
            "sha256": "0e3f947994aaaf76eb53c94fb5e882be09f7feea9ea1a4eca848417eda3e2203"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sysnotify.py",
            "sha256": "0ab9a0e77940a50ba2a5c1e42e6fcecae7540bc07b0f510cff80aeeb86be68bf"
          }
        ],
        "after": [
          {
            "path": "chatmon/sysnotify.py",
            "sha256": "0e3f947994aaaf76eb53c94fb5e882be09f7feea9ea1a4eca848417eda3e2203"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-07b-replaced-buttons",
      "acceptance": [
        "AC-07b"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_platform_events.py::test_a_notifications_buttons_are_answered_for_ours_alone"
      ],
      "method": "Red drill AC-07b-replaced-buttons (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/sysnotify.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "0e3f947994aaaf76eb53c94fb5e882be09f7feea9ea1a4eca848417eda3e2203"
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
          "path": "tests/fake_notifications.py",
          "sha256": "4dcd214a2c4ba2303d1355dcc538f3ffdc7063a0504587e92f03fb3538d5b912"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
        }
      ],
      "scope_sha256": "f65953c7d401c4850328235ed4a1a636a12bf76ab36edb1af8128d8c4f02df0f",
      "red": {
        "mutation": "chatmon/sysnotify.py: '                self._pressed.pop(self.read_aloud_id, None)' -> '                pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_notifications_buttons_are_answered_for_ours_alone",
        "observed_diagnostic": "__________ test_a_notifications_buttons_are_answered_for_ours_alone ___________",
        "before": [
          {
            "path": "chatmon/sysnotify.py",
            "sha256": "0e3f947994aaaf76eb53c94fb5e882be09f7feea9ea1a4eca848417eda3e2203"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sysnotify.py",
            "sha256": "9fd57b0b927c000b449769e6f8729a4b9583c11407b3cc70434e50c93b107b25"
          }
        ],
        "after": [
          {
            "path": "chatmon/sysnotify.py",
            "sha256": "0e3f947994aaaf76eb53c94fb5e882be09f7feea9ea1a4eca848417eda3e2203"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-07b-other-apps",
      "acceptance": [
        "AC-07b"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_platform_events.py::test_a_notifications_buttons_are_answered_for_ours_alone"
      ],
      "method": "Red drill AC-07b-other-apps (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/sysnotify.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "0e3f947994aaaf76eb53c94fb5e882be09f7feea9ea1a4eca848417eda3e2203"
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
          "path": "tests/fake_notifications.py",
          "sha256": "4dcd214a2c4ba2303d1355dcc538f3ffdc7063a0504587e92f03fb3538d5b912"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
        }
      ],
      "scope_sha256": "f65953c7d401c4850328235ed4a1a636a12bf76ab36edb1af8128d8c4f02df0f",
      "red": {
        "mutation": "chatmon/sysnotify.py: 'pressed = self._pressed.get(int(args[0]))' -> 'pressed = next(iter(self._pressed.values()), None)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_notifications_buttons_are_answered_for_ours_alone",
        "observed_diagnostic": "__________ test_a_notifications_buttons_are_answered_for_ours_alone ___________",
        "before": [
          {
            "path": "chatmon/sysnotify.py",
            "sha256": "0e3f947994aaaf76eb53c94fb5e882be09f7feea9ea1a4eca848417eda3e2203"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sysnotify.py",
            "sha256": "c1b25d580cbdc3bc74e85daa8cbf8bf04244989523c097886c8392e9586b0843"
          }
        ],
        "after": [
          {
            "path": "chatmon/sysnotify.py",
            "sha256": "0e3f947994aaaf76eb53c94fb5e882be09f7feea9ea1a4eca848417eda3e2203"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-08-not-held",
      "acceptance": [
        "AC-08"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_platform_events.py::test_voiceover_holds_announcements_until_chatmon_is_in_front"
      ],
      "method": "Red drill AC-08-not-held (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/a11y.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/a11y.py",
          "sha256": "aba945249b89b5da40f4b61d67a16299887ac3447c5fca64361155e12f2937e0"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "07b3d8e2f97b38cb0f39173825d054b93caab1c9888453ac90226679ba58d410"
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
          "path": "tests/test_platform_events.py",
          "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "7075f36a283687bfb6f63b9f6650ae7542eeb87adde641bedcbb12b443fd7e70"
        }
      ],
      "scope_sha256": "e6ffc89dd8e77b9c4389dd1d6cdf6ce055d24a41a7e00cc3377c8ef0647141af",
      "red": {
        "mutation": "chatmon/a11y.py: '            self.held = (self.held + [(text, important)])[-self.HELD:]' -> '            self._post(text, important)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_voiceover_holds_announcements_until_chatmon_is_in_front",
        "observed_diagnostic": "________ test_voiceover_holds_announcements_until_chatmon_is_in_front _________",
        "before": [
          {
            "path": "chatmon/a11y.py",
            "sha256": "aba945249b89b5da40f4b61d67a16299887ac3447c5fca64361155e12f2937e0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/a11y.py",
            "sha256": "8fee5e10a4233d2261e5696bcac11c73f0f430c829a182cef6b722ce85011806"
          }
        ],
        "after": [
          {
            "path": "chatmon/a11y.py",
            "sha256": "aba945249b89b5da40f4b61d67a16299887ac3447c5fca64361155e12f2937e0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-08-no-fallback",
      "acceptance": [
        "AC-08"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_platform_events.py::test_the_speech_fallback_says_it_at_once_instead"
      ],
      "method": "Red drill AC-08-no-fallback (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/a11y.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/a11y.py",
          "sha256": "aba945249b89b5da40f4b61d67a16299887ac3447c5fca64361155e12f2937e0"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "07b3d8e2f97b38cb0f39173825d054b93caab1c9888453ac90226679ba58d410"
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
          "path": "tests/test_platform_events.py",
          "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "7075f36a283687bfb6f63b9f6650ae7542eeb87adde641bedcbb12b443fd7e70"
        }
      ],
      "scope_sha256": "e6ffc89dd8e77b9c4389dd1d6cdf6ce055d24a41a7e00cc3377c8ef0647141af",
      "red": {
        "mutation": "chatmon/a11y.py: '        elif _speech_fallback:' -> '        elif False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_speech_fallback_says_it_at_once_instead",
        "observed_diagnostic": "______________ test_the_speech_fallback_says_it_at_once_instead _______________",
        "before": [
          {
            "path": "chatmon/a11y.py",
            "sha256": "aba945249b89b5da40f4b61d67a16299887ac3447c5fca64361155e12f2937e0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/a11y.py",
            "sha256": "7ad6c937f79c1143a769693368e77a37b229e5c0f3ed6f40c973f7a87742de03"
          }
        ],
        "after": [
          {
            "path": "chatmon/a11y.py",
            "sha256": "aba945249b89b5da40f4b61d67a16299887ac3447c5fca64361155e12f2937e0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-09a-client-side",
      "acceptance": [
        "AC-09a"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_platform_events.py::test_a_ui_automation_client_hears_the_announcement"
      ],
      "method": "Red drill AC-09a-client-side (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/winuia.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/a11y.py",
          "sha256": "aba945249b89b5da40f4b61d67a16299887ac3447c5fca64361155e12f2937e0"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "07b3d8e2f97b38cb0f39173825d054b93caab1c9888453ac90226679ba58d410"
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
          "path": "tests/test_platform_events.py",
          "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "7075f36a283687bfb6f63b9f6650ae7542eeb87adde641bedcbb12b443fd7e70"
        }
      ],
      "scope_sha256": "e6ffc89dd8e77b9c4389dd1d6cdf6ce055d24a41a7e00cc3377c8ef0647141af",
      "red": {
        "mutation": "chatmon/winuia.py: '        out[0] = SERVER_SIDE_PROVIDER\\n' -> '        out[0] = 0x1  # ProviderOptions_ClientSideProvider\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_ui_automation_client_hears_the_announcement",
        "observed_diagnostic": "_____________ test_a_ui_automation_client_hears_the_announcement ______________",
        "before": [
          {
            "path": "chatmon/winuia.py",
            "sha256": "07b3d8e2f97b38cb0f39173825d054b93caab1c9888453ac90226679ba58d410"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/winuia.py",
            "sha256": "81358b2505522bab4c8b5a30ffde43bcee3d0cfae25a1cab076bdfdead537e18"
          }
        ],
        "after": [
          {
            "path": "chatmon/winuia.py",
            "sha256": "07b3d8e2f97b38cb0f39173825d054b93caab1c9888453ac90226679ba58d410"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-09a-not-handed-out",
      "acceptance": [
        "AC-09a"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_platform_events.py::test_a_ui_automation_client_hears_the_announcement"
      ],
      "method": "Red drill AC-09a-not-handed-out (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/winuia.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/a11y.py",
          "sha256": "aba945249b89b5da40f4b61d67a16299887ac3447c5fca64361155e12f2937e0"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "07b3d8e2f97b38cb0f39173825d054b93caab1c9888453ac90226679ba58d410"
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
          "path": "tests/test_platform_events.py",
          "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "7075f36a283687bfb6f63b9f6650ae7542eeb87adde641bedcbb12b443fd7e70"
        }
      ],
      "scope_sha256": "e6ffc89dd8e77b9c4389dd1d6cdf6ce055d24a41a7e00cc3377c8ef0647141af",
      "red": {
        "mutation": "chatmon/winuia.py: 'msg.hWnd == self.hwnd and msg.message == WM_GETOBJECT' -> 'msg.hWnd == self.hwnd and msg.message == 0'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_ui_automation_client_hears_the_announcement",
        "observed_diagnostic": "_____________ test_a_ui_automation_client_hears_the_announcement ______________",
        "before": [
          {
            "path": "chatmon/winuia.py",
            "sha256": "07b3d8e2f97b38cb0f39173825d054b93caab1c9888453ac90226679ba58d410"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/winuia.py",
            "sha256": "fe18b58e2d4723d9dd6c7621791123125403ed4139be6cc80deabb8dce1d6f8c"
          }
        ],
        "after": [
          {
            "path": "chatmon/winuia.py",
            "sha256": "07b3d8e2f97b38cb0f39173825d054b93caab1c9888453ac90226679ba58d410"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-09a-host-provider",
      "acceptance": [
        "AC-09a"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_platform_events.py::test_a_ui_automation_client_hears_the_announcement"
      ],
      "method": "Red drill AC-09a-host-provider (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/winuia.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/a11y.py",
          "sha256": "aba945249b89b5da40f4b61d67a16299887ac3447c5fca64361155e12f2937e0"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "07b3d8e2f97b38cb0f39173825d054b93caab1c9888453ac90226679ba58d410"
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
          "path": "tests/test_platform_events.py",
          "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "7075f36a283687bfb6f63b9f6650ae7542eeb87adde641bedcbb12b443fd7e70"
        }
      ],
      "scope_sha256": "e6ffc89dd8e77b9c4389dd1d6cdf6ce055d24a41a7e00cc3377c8ef0647141af",
      "red": {
        "mutation": "chatmon/winuia.py: 'result = self._uia.UiaRaiseNotificationEvent(self.provider.pointer,' -> 'host = ctypes.c_void_p(); self._uia.UiaHostProviderFromHwnd(self.hwnd, ctypes.byref(host)); result = self._uia.UiaRaiseNotificationEvent(host.value,'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_ui_automation_client_hears_the_announcement",
        "observed_diagnostic": "_____________ test_a_ui_automation_client_hears_the_announcement ______________",
        "before": [
          {
            "path": "chatmon/winuia.py",
            "sha256": "07b3d8e2f97b38cb0f39173825d054b93caab1c9888453ac90226679ba58d410"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/winuia.py",
            "sha256": "08e870fbbc7434628d64ad1ae823e5b90306adaffb09e668a4ec31ba9f6824e4"
          }
        ],
        "after": [
          {
            "path": "chatmon/winuia.py",
            "sha256": "07b3d8e2f97b38cb0f39173825d054b93caab1c9888453ac90226679ba58d410"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-09b-behind",
      "acceptance": [
        "AC-09b"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_platform_events.py::test_on_windows_announcements_need_chatmon_in_front"
      ],
      "method": "Red drill AC-09b-behind (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/a11y.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/a11y.py",
          "sha256": "aba945249b89b5da40f4b61d67a16299887ac3447c5fca64361155e12f2937e0"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "07b3d8e2f97b38cb0f39173825d054b93caab1c9888453ac90226679ba58d410"
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
          "path": "tests/test_platform_events.py",
          "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "7075f36a283687bfb6f63b9f6650ae7542eeb87adde641bedcbb12b443fd7e70"
        }
      ],
      "scope_sha256": "e6ffc89dd8e77b9c4389dd1d6cdf6ce055d24a41a7e00cc3377c8ef0647141af",
      "red": {
        "mutation": "chatmon/a11y.py: 'return winuia.in_front() and winuia.say(words, important)' -> 'return winuia.say(words, important)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_on_windows_announcements_need_chatmon_in_front",
        "observed_diagnostic": "_____________ test_on_windows_announcements_need_chatmon_in_front _____________",
        "before": [
          {
            "path": "chatmon/a11y.py",
            "sha256": "aba945249b89b5da40f4b61d67a16299887ac3447c5fca64361155e12f2937e0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/a11y.py",
            "sha256": "e95c73ce5ea2ef791286d787ddb4dfe525df1ed03c623161a18f933e8652410e"
          }
        ],
        "after": [
          {
            "path": "chatmon/a11y.py",
            "sha256": "aba945249b89b5da40f4b61d67a16299887ac3447c5fca64361155e12f2937e0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-09b-no-notification",
      "acceptance": [
        "AC-09b"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_platform_events.py::test_announcements_fall_back_to_the_notification"
      ],
      "method": "Red drill AC-09b-no-notification (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/a11y.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/a11y.py",
          "sha256": "aba945249b89b5da40f4b61d67a16299887ac3447c5fca64361155e12f2937e0"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "07b3d8e2f97b38cb0f39173825d054b93caab1c9888453ac90226679ba58d410"
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
          "path": "tests/test_platform_events.py",
          "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "7075f36a283687bfb6f63b9f6650ae7542eeb87adde641bedcbb12b443fd7e70"
        }
      ],
      "scope_sha256": "e6ffc89dd8e77b9c4389dd1d6cdf6ce055d24a41a7e00cc3377c8ef0647141af",
      "red": {
        "mutation": "chatmon/a11y.py: '        notify()\\n        return \"notification\"' -> '        return \"notification\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_announcements_fall_back_to_the_notification",
        "observed_diagnostic": "______________ test_announcements_fall_back_to_the_notification _______________",
        "before": [
          {
            "path": "chatmon/a11y.py",
            "sha256": "aba945249b89b5da40f4b61d67a16299887ac3447c5fca64361155e12f2937e0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/a11y.py",
            "sha256": "c2a7b2e88fb7168e536dc351ed40ef48d15371b1d5fba6648a0d8c863cc2643a"
          }
        ],
        "after": [
          {
            "path": "chatmon/a11y.py",
            "sha256": "aba945249b89b5da40f4b61d67a16299887ac3447c5fca64361155e12f2937e0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-10-plugged",
      "acceptance": [
        "AC-10"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_heads_up.py::test_upowers_display_device_in_one_answer"
      ],
      "method": "Red drill AC-10-plugged (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/heads_up.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/heads_up.py",
          "sha256": "2fdd651948e492aa10423bc38bdd5fd4af268dead65f0b942627868365c63183"
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
          "path": "tests/fake_upower.py",
          "sha256": "bfa76d5e4e755f6987421e5ade5b9f7c1c50ff97eac5c322ed1de874b7c2ce3e"
        },
        {
          "path": "tests/private_bus.py",
          "sha256": "229b227961118c72f9f204952bdd5508450174a2c1043b1eb4d5fd7ff8bba9a2"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "fa2b96199f5dee5a8c91ac095f321e2c82a51b5fa2904de968cea5859c44f088"
        }
      ],
      "scope_sha256": "8021e5aea72bc9113e0d12bef9b994ccdb3aaa6c54af25c188049e5933d48d1e",
      "red": {
        "mutation": "chatmon/heads_up.py: 'return float(percent), state not in DISCHARGING_STATES' -> 'return float(percent), state != 2'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_upowers_display_device_in_one_answer",
        "observed_diagnostic": "__________________ test_upowers_display_device_in_one_answer __________________",
        "before": [
          {
            "path": "chatmon/heads_up.py",
            "sha256": "2fdd651948e492aa10423bc38bdd5fd4af268dead65f0b942627868365c63183"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/heads_up.py",
            "sha256": "6f09064818f136ecffc8e9e20b8b9553ba52c73dd4512a17e2631b9647e06f9c"
          }
        ],
        "after": [
          {
            "path": "chatmon/heads_up.py",
            "sha256": "2fdd651948e492aa10423bc38bdd5fd4af268dead65f0b942627868365c63183"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-11-told-twice",
      "acceptance": [
        "AC-11"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_linuxsession.py::test_the_lock_is_told_once_and_stops_drawing"
      ],
      "method": "Red drill AC-11-told-twice (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/linuxsession.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
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
          "path": "tests/fake_upower.py",
          "sha256": "bfa76d5e4e755f6987421e5ade5b9f7c1c50ff97eac5c322ed1de874b7c2ce3e"
        },
        {
          "path": "tests/private_bus.py",
          "sha256": "229b227961118c72f9f204952bdd5508450174a2c1043b1eb4d5fd7ff8bba9a2"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        }
      ],
      "scope_sha256": "b7a4a03d139c596972ca1dab1627cb5e042e0a29abce3a3b56d8b7bc84685a14",
      "red": {
        "mutation": "chatmon/linuxsession.py: '        if on == self.locked:\\n            return\\n        self.locked = on' -> '        self.locked = on'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_lock_is_told_once_and_stops_drawing",
        "observed_diagnostic": "________________ test_the_lock_is_told_once_and_stops_drawing _________________",
        "before": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "5f97c465996bab7c528a5bdf416ca390d93ea9f1f59dc621422821c47ed4ae9c"
          }
        ],
        "after": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-11-seen-inverted",
      "acceptance": [
        "AC-11"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_linuxsession.py::test_the_lock_is_told_once_and_stops_drawing"
      ],
      "method": "Red drill AC-11-seen-inverted (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/linuxsession.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
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
          "path": "tests/fake_upower.py",
          "sha256": "bfa76d5e4e755f6987421e5ade5b9f7c1c50ff97eac5c322ed1de874b7c2ce3e"
        },
        {
          "path": "tests/private_bus.py",
          "sha256": "229b227961118c72f9f204952bdd5508450174a2c1043b1eb4d5fd7ff8bba9a2"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        }
      ],
      "scope_sha256": "b7a4a03d139c596972ca1dab1627cb5e042e0a29abce3a3b56d8b7bc84685a14",
      "red": {
        "mutation": "chatmon/linuxsession.py: '            self._seen(not on)' -> '            self._seen(on)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_lock_is_told_once_and_stops_drawing",
        "observed_diagnostic": "________________ test_the_lock_is_told_once_and_stops_drawing _________________",
        "before": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "5a6c323ab49fea8ee03b6037819347545686ec419dd4135b06ea929a621f94e2"
          }
        ],
        "after": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-AC-04a-listener-outlives-desk",
      "acceptance": [
        "AC-04a"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_presence.py::test_the_linux_listeners_go_with_their_desk"
      ],
      "method": "Red drill AC-04a-listener-outlives-desk (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/presence.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills.log",
        "sha256": "0a8a2e32e98860e71bae1553ce3062e5dc900faaa8e403f8fee188a93843e850"
      },
      "inputs": [
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
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
          "path": "tests/fake_portal.py",
          "sha256": "546c8e803b87141a3998ca2e966c91309d4db52b112f72f9c1483b949cd5b24b"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        },
        {
          "path": "tests/test_portal_bus.py",
          "sha256": "f3a80e308add6b3c7f672f4092d4c349aaca93be9cf19208c93bdb7a1464c7a3"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
        }
      ],
      "scope_sha256": "ab438008853695f8ae3ab94dc6b9d2eafbaea5aeb0d27dffc6a5b54d59a624bb",
      "red": {
        "mutation": "chatmon/presence.py: 'made = linuxsession.PortalSettings(self)' -> 'made = linuxsession.PortalSettings()'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_linux_listeners_go_with_their_desk",
        "observed_diagnostic": "_________________ test_the_linux_listeners_go_with_their_desk _________________",
        "before": [
          {
            "path": "chatmon/presence.py",
            "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/presence.py",
            "sha256": "4e96995b0f7b3d7a30568491a9c2d532baf56dab38f019342020229b0b1291ed"
          }
        ],
        "after": [
          {
            "path": "chatmon/presence.py",
            "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-L-AC-01a-read-fallback",
      "acceptance": [
        "AC-01a"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/var/tmp/m4a-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_portal_bus.py::test_the_portals_appearance_settings_are_read_once_then_followed"
      ],
      "method": "Red drill L-AC-01a-read-fallback (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/linuxsession.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "pyqt6": "6.12.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills-linux.log",
        "sha256": "d1022302188ec0c34e6744e1b4d4ab73c6776ccb4896a0954d93259480703f6f"
      },
      "inputs": [
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
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
          "path": "tests/fake_portal.py",
          "sha256": "546c8e803b87141a3998ca2e966c91309d4db52b112f72f9c1483b949cd5b24b"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        },
        {
          "path": "tests/test_portal_bus.py",
          "sha256": "f3a80e308add6b3c7f672f4092d4c349aaca93be9cf19208c93bdb7a1464c7a3"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
        }
      ],
      "scope_sha256": "ab438008853695f8ae3ab94dc6b9d2eafbaea5aeb0d27dffc6a5b54d59a624bb",
      "red": {
        "mutation": "chatmon/linuxsession.py: 'elif method == \"ReadOne\" and reply.errorName() == \"org.freedesktop.DBus.Error.UnknownMethod\":' -> 'elif False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_portals_appearance_settings_are_read_once_then_followed[1-Read]",
        "observed_diagnostic": "___ test_the_portals_appearance_settings_are_read_once_then_followed[1-Read] ___",
        "before": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "9084c1c8d44849b92d0e162c47af9dd807c11ea9867ec5a8544a46c8f755d71a"
          }
        ],
        "after": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-L-AC-04a-asked-each-time",
      "acceptance": [
        "AC-04a"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/var/tmp/m4a-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_portal_bus.py::test_the_portals_appearance_settings_are_read_once_then_followed"
      ],
      "method": "Red drill L-AC-04a-asked-each-time (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/presence.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "pyqt6": "6.12.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills-linux.log",
        "sha256": "d1022302188ec0c34e6744e1b4d4ab73c6776ccb4896a0954d93259480703f6f"
      },
      "inputs": [
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
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
          "path": "tests/fake_portal.py",
          "sha256": "546c8e803b87141a3998ca2e966c91309d4db52b112f72f9c1483b949cd5b24b"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        },
        {
          "path": "tests/test_portal_bus.py",
          "sha256": "f3a80e308add6b3c7f672f4092d4c349aaca93be9cf19208c93bdb7a1464c7a3"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
        }
      ],
      "scope_sha256": "ab438008853695f8ae3ab94dc6b9d2eafbaea5aeb0d27dffc6a5b54d59a624bb",
      "red": {
        "mutation": "chatmon/presence.py: '            setattr(self, attr, made)\\n' -> ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_portals_appearance_settings_are_read_once_then_followed[2-ReadOne]",
        "observed_diagnostic": "_ test_the_portals_appearance_settings_are_read_once_then_followed[2-ReadOne] __",
        "before": [
          {
            "path": "chatmon/presence.py",
            "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/presence.py",
            "sha256": "356775fdd706e081ab4bad0e7883a609acffed6ced84b140c57f875433c6eb40"
          }
        ],
        "after": [
          {
            "path": "chatmon/presence.py",
            "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-L-AC-04b-qt-signal",
      "acceptance": [
        "AC-04b"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/var/tmp/m4a-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_presence.py::test_qts_contrast_change_is_passed_on"
      ],
      "method": "Red drill L-AC-04b-qt-signal (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/presence.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "pyqt6": "6.12.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills-linux.log",
        "sha256": "d1022302188ec0c34e6744e1b4d4ab73c6776ccb4896a0954d93259480703f6f"
      },
      "inputs": [
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
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
          "path": "tests/fake_portal.py",
          "sha256": "546c8e803b87141a3998ca2e966c91309d4db52b112f72f9c1483b949cd5b24b"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        },
        {
          "path": "tests/test_portal_bus.py",
          "sha256": "f3a80e308add6b3c7f672f4092d4c349aaca93be9cf19208c93bdb7a1464c7a3"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
        }
      ],
      "scope_sha256": "ab438008853695f8ae3ab94dc6b9d2eafbaea5aeb0d27dffc6a5b54d59a624bb",
      "red": {
        "mutation": "chatmon/presence.py: 'contrastPreferenceChanged.connect(self.settings_changed)' -> 'contrastPreferenceChanged.connect(lambda *_: None)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_qts_contrast_change_is_passed_on",
        "observed_diagnostic": "____________________ test_qts_contrast_change_is_passed_on _____________________",
        "before": [
          {
            "path": "chatmon/presence.py",
            "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/presence.py",
            "sha256": "f15188b67da8d94c9f0a532d46484b2a53920a289f106dceed5a5e5a6eb74d26"
          }
        ],
        "after": [
          {
            "path": "chatmon/presence.py",
            "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-L-AC-05-starts-services",
      "acceptance": [
        "AC-05"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/var/tmp/m4a-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_platform_events.py::test_asking_about_do_not_disturb_never_starts_a_service"
      ],
      "method": "Red drill L-AC-05-starts-services (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/linuxsession.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "pyqt6": "6.12.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills-linux.log",
        "sha256": "d1022302188ec0c34e6744e1b4d4ab73c6776ccb4896a0954d93259480703f6f"
      },
      "inputs": [
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
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
          "path": "tests/fake_notifications.py",
          "sha256": "4dcd214a2c4ba2303d1355dcc538f3ffdc7063a0504587e92f03fb3538d5b912"
        },
        {
          "path": "tests/fake_portal.py",
          "sha256": "546c8e803b87141a3998ca2e966c91309d4db52b112f72f9c1483b949cd5b24b"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
        },
        {
          "path": "tests/test_portal_bus.py",
          "sha256": "f3a80e308add6b3c7f672f4092d4c349aaca93be9cf19208c93bdb7a1464c7a3"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
        }
      ],
      "scope_sha256": "957b6ce8dd80c9b99b8657a7ccaa5b703461cfd9f94dd0b9d7b41b6e94a8ec82",
      "red": {
        "mutation": "chatmon/linuxsession.py: '    message.setAutoStartService(False)\\n' -> '    message.setAutoStartService(True)\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_asking_about_do_not_disturb_never_starts_a_service",
        "observed_diagnostic": "___________ test_asking_about_do_not_disturb_never_starts_a_service ____________",
        "before": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "ede18937a15bd6de53f6478b0900e3e52b8cde14050aaa9ae6decf4ad339d00e"
          }
        ],
        "after": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-L-AC-05-dunst-question",
      "acceptance": [
        "AC-05"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/var/tmp/m4a-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_platform_events.py::test_each_servers_do_not_disturb_is_read_from_the_server"
      ],
      "method": "Red drill L-AC-05-dunst-question (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/linuxsession.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "pyqt6": "6.12.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills-linux.log",
        "sha256": "d1022302188ec0c34e6744e1b4d4ab73c6776ccb4896a0954d93259480703f6f"
      },
      "inputs": [
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
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
          "path": "tests/fake_notifications.py",
          "sha256": "4dcd214a2c4ba2303d1355dcc538f3ffdc7063a0504587e92f03fb3538d5b912"
        },
        {
          "path": "tests/fake_portal.py",
          "sha256": "546c8e803b87141a3998ca2e966c91309d4db52b112f72f9c1483b949cd5b24b"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
        },
        {
          "path": "tests/test_portal_bus.py",
          "sha256": "f3a80e308add6b3c7f672f4092d4c349aaca93be9cf19208c93bdb7a1464c7a3"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
        }
      ],
      "scope_sha256": "957b6ce8dd80c9b99b8657a7ccaa5b703461cfd9f94dd0b9d7b41b6e94a8ec82",
      "red": {
        "mutation": "chatmon/linuxsession.py: '\"org.dunstproject.cmd0\", \"paused\"' -> '\"org.dunstproject.cmd1\", \"paused\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_each_servers_do_not_disturb_is_read_from_the_server[dunst-on-Do Not Disturb]",
        "observed_diagnostic": "_ test_each_servers_do_not_disturb_is_read_from_the_server[dunst-on-Do Not Disturb] _",
        "before": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "d172ab336e6411bbd7c5851405a32a6d6c0a6345a3016004cc8d38e6b868b544"
          }
        ],
        "after": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-L-AC-06a-upower-not-followed",
      "acceptance": [
        "AC-06a"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/var/tmp/m4a-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_linuxsession.py::test_power_saving_follows_upower_on_a_bus"
      ],
      "method": "Red drill L-AC-06a-upower-not-followed (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/linuxsession.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "pyqt6": "6.12.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills-linux.log",
        "sha256": "d1022302188ec0c34e6744e1b4d4ab73c6776ccb4896a0954d93259480703f6f"
      },
      "inputs": [
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
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
          "path": "tests/fake_upower.py",
          "sha256": "bfa76d5e4e755f6987421e5ade5b9f7c1c50ff97eac5c322ed1de874b7c2ce3e"
        },
        {
          "path": "tests/private_bus.py",
          "sha256": "229b227961118c72f9f204952bdd5508450174a2c1043b1eb4d5fd7ff8bba9a2"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        }
      ],
      "scope_sha256": "b7a4a03d139c596972ca1dab1627cb5e042e0a29abce3a3b56d8b7bc84685a14",
      "red": {
        "mutation": "chatmon/linuxsession.py: '        service, path = UPOWER\\n        if self._bus.connect(service, path, PROPERTIES, \"PropertiesChanged\", self._changed):' -> '        service, path = UPOWER\\n        if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_power_saving_follows_upower_on_a_bus",
        "observed_diagnostic": "__________________ test_power_saving_follows_upower_on_a_bus ___________________",
        "before": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "02a3199838fc2ed9496788e66e51acf9ebab0bcc8effa3e552432dec2f010927"
          }
        ],
        "after": [
          {
            "path": "chatmon/linuxsession.py",
            "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-L-AC-07a-not-replaced",
      "acceptance": [
        "AC-07a"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/var/tmp/m4a-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_platform_events.py::test_the_notification_server_gets_transient_replacing_and_urgent_notifications"
      ],
      "method": "Red drill L-AC-07a-not-replaced (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/sysnotify.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "pyqt6": "6.12.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills-linux.log",
        "sha256": "d1022302188ec0c34e6744e1b4d4ab73c6776ccb4896a0954d93259480703f6f"
      },
      "inputs": [
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "0e3f947994aaaf76eb53c94fb5e882be09f7feea9ea1a4eca848417eda3e2203"
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
          "path": "tests/fake_notifications.py",
          "sha256": "4dcd214a2c4ba2303d1355dcc538f3ffdc7063a0504587e92f03fb3538d5b912"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
        }
      ],
      "scope_sha256": "f65953c7d401c4850328235ed4a1a636a12bf76ab36edb1af8128d8c4f02df0f",
      "red": {
        "mutation": "chatmon/sysnotify.py: 'message(title, body, replaces=self.read_aloud_id,' -> 'message(title, body, replaces=0,'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_notification_server_gets_transient_replacing_and_urgent_notifications",
        "observed_diagnostic": "_ test_the_notification_server_gets_transient_replacing_and_urgent_notifications _",
        "before": [
          {
            "path": "chatmon/sysnotify.py",
            "sha256": "0e3f947994aaaf76eb53c94fb5e882be09f7feea9ea1a4eca848417eda3e2203"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sysnotify.py",
            "sha256": "60744d835c28e3887d6b5c89d9da27afc884c78c10d264d6d51dfb93f88ee197"
          }
        ],
        "after": [
          {
            "path": "chatmon/sysnotify.py",
            "sha256": "0e3f947994aaaf76eb53c94fb5e882be09f7feea9ea1a4eca848417eda3e2203"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-L-AC-07b-action-unheard",
      "acceptance": [
        "AC-07b"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/var/tmp/m4a-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_platform_events.py::test_the_notification_server_gets_transient_replacing_and_urgent_notifications"
      ],
      "method": "Red drill L-AC-07b-action-unheard (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/sysnotify.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "pyqt6": "6.12.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills-linux.log",
        "sha256": "d1022302188ec0c34e6744e1b4d4ab73c6776ccb4896a0954d93259480703f6f"
      },
      "inputs": [
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "0e3f947994aaaf76eb53c94fb5e882be09f7feea9ea1a4eca848417eda3e2203"
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
          "path": "tests/fake_notifications.py",
          "sha256": "4dcd214a2c4ba2303d1355dcc538f3ffdc7063a0504587e92f03fb3538d5b912"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
        }
      ],
      "scope_sha256": "f65953c7d401c4850328235ed4a1a636a12bf76ab36edb1af8128d8c4f02df0f",
      "red": {
        "mutation": "chatmon/sysnotify.py: 'bus.connect(SERVICE, PATH, SERVICE, \"ActionInvoked\", self._action_invoked)' -> 'bus.connect(SERVICE, PATH, SERVICE, \"ActionInvokedX\", self._action_invoked)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_notification_server_gets_transient_replacing_and_urgent_notifications",
        "observed_diagnostic": "_ test_the_notification_server_gets_transient_replacing_and_urgent_notifications _",
        "before": [
          {
            "path": "chatmon/sysnotify.py",
            "sha256": "0e3f947994aaaf76eb53c94fb5e882be09f7feea9ea1a4eca848417eda3e2203"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sysnotify.py",
            "sha256": "64d5b29f019601e855e46e04c1c9975e25065f101f847529160079a2daa4cf7d"
          }
        ],
        "after": [
          {
            "path": "chatmon/sysnotify.py",
            "sha256": "0e3f947994aaaf76eb53c94fb5e882be09f7feea9ea1a4eca848417eda3e2203"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-L-AC-10-not-one-call",
      "acceptance": [
        "AC-10"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/var/tmp/m4a-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_heads_up.py::test_upower_is_asked_once_from_a_worker_thread"
      ],
      "method": "Red drill L-AC-10-not-one-call (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/heads_up.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "pyqt6": "6.12.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills-linux.log",
        "sha256": "d1022302188ec0c34e6744e1b4d4ab73c6776ccb4896a0954d93259480703f6f"
      },
      "inputs": [
        {
          "path": "chatmon/heads_up.py",
          "sha256": "2fdd651948e492aa10423bc38bdd5fd4af268dead65f0b942627868365c63183"
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
          "path": "tests/fake_upower.py",
          "sha256": "bfa76d5e4e755f6987421e5ade5b9f7c1c50ff97eac5c322ed1de874b7c2ce3e"
        },
        {
          "path": "tests/private_bus.py",
          "sha256": "229b227961118c72f9f204952bdd5508450174a2c1043b1eb4d5fd7ff8bba9a2"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "fa2b96199f5dee5a8c91ac095f321e2c82a51b5fa2904de968cea5859c44f088"
        }
      ],
      "scope_sha256": "8021e5aea72bc9113e0d12bef9b994ccdb3aaa6c54af25c188049e5933d48d1e",
      "red": {
        "mutation": "chatmon/heads_up.py: '\"GetAll\", \"org.freedesktop.UPower.Device\"' -> '\"Get\", \"org.freedesktop.UPower.Device\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_upower_is_asked_once_from_a_worker_thread",
        "observed_diagnostic": "________________ test_upower_is_asked_once_from_a_worker_thread ________________",
        "before": [
          {
            "path": "chatmon/heads_up.py",
            "sha256": "2fdd651948e492aa10423bc38bdd5fd4af268dead65f0b942627868365c63183"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/heads_up.py",
            "sha256": "0e6a77414ce6b98378d09004c2ecaf41220cb9ffbd834adcb2c5fd1428e932d3"
          }
        ],
        "after": [
          {
            "path": "chatmon/heads_up.py",
            "sha256": "2fdd651948e492aa10423bc38bdd5fd4af268dead65f0b942627868365c63183"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-L-AC-04a-listener-outlives-desk",
      "acceptance": [
        "AC-04a"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/var/tmp/m4a-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_portal_bus.py::test_an_answer_that_comes_after_its_desk_has_gone_reaches_nothing"
      ],
      "method": "Red drill L-AC-04a-listener-outlives-desk (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/presence.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "pyqt6": "6.12.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills-linux.log",
        "sha256": "d1022302188ec0c34e6744e1b4d4ab73c6776ccb4896a0954d93259480703f6f"
      },
      "inputs": [
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
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
          "path": "tests/fake_portal.py",
          "sha256": "546c8e803b87141a3998ca2e966c91309d4db52b112f72f9c1483b949cd5b24b"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        },
        {
          "path": "tests/test_portal_bus.py",
          "sha256": "f3a80e308add6b3c7f672f4092d4c349aaca93be9cf19208c93bdb7a1464c7a3"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
        }
      ],
      "scope_sha256": "ab438008853695f8ae3ab94dc6b9d2eafbaea5aeb0d27dffc6a5b54d59a624bb",
      "red": {
        "mutation": "chatmon/presence.py: 'made = linuxsession.PortalSettings(self)\\n                    made.changed.connect(self.settings_changed)\\n' -> 'made = linuxsession.PortalSettings()\\n                    made.changed.connect(self.settings_changed.emit)\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_an_answer_that_comes_after_its_desk_has_gone_reaches_nothing",
        "observed_diagnostic": "______ test_an_answer_that_comes_after_its_desk_has_gone_reaches_nothing _______",
        "before": [
          {
            "path": "chatmon/presence.py",
            "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/presence.py",
            "sha256": "02b3d05d6a5748c4a6fe1d531d928abd1c64c8534a178206981ced4c25ab1841"
          }
        ],
        "after": [
          {
            "path": "chatmon/presence.py",
            "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-L-AC-02-x11-place",
      "acceptance": [
        "AC-02"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/var/tmp/m4a-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_presence.py::test_x11_says_where_a_window_is"
      ],
      "method": "Red drill L-AC-02-x11-place (tests/drills/run.py, in a temporary copy): green, then the mutation in chatmon/presence.py made the named tests fail with pytest's tests-failed exit and the expected test named, then the original bytes restored (checked by SHA-256) and green again.",
      "environment": {
        "platform": "linux",
        "tools": {
          "python": "3.14.9",
          "pytest": "9.2.0",
          "pyqt6": "6.12.1"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m4a/drills-linux.log",
        "sha256": "d1022302188ec0c34e6744e1b4d4ab73c6776ccb4896a0954d93259480703f6f"
      },
      "inputs": [
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
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
          "path": "tests/fake_portal.py",
          "sha256": "546c8e803b87141a3998ca2e966c91309d4db52b112f72f9c1483b949cd5b24b"
        },
        {
          "path": "tests/test_linuxsession.py",
          "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
        },
        {
          "path": "tests/test_portal_bus.py",
          "sha256": "f3a80e308add6b3c7f672f4092d4c349aaca93be9cf19208c93bdb7a1464c7a3"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
        }
      ],
      "scope_sha256": "ab438008853695f8ae3ab94dc6b9d2eafbaea5aeb0d27dffc6a5b54d59a624bb",
      "red": {
        "mutation": "chatmon/presence.py: 'return x.value, y.value, width.value, height.value' -> 'return 0, 0, width.value, height.value'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_x11_says_where_a_window_is",
        "observed_diagnostic": "_______________________ test_x11_says_where_a_window_is ________________________",
        "before": [
          {
            "path": "chatmon/presence.py",
            "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/presence.py",
            "sha256": "666a8842318340d801f53b0695a3df0229cf159a22636e2b2ba39579179b2a86"
          }
        ],
        "after": [
          {
            "path": "chatmon/presence.py",
            "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
          }
        ]
      },
      "reason": null
    }
  ],
  "checkpoint": {
    "scope_sha256": "a6f6dc15f82ac8616b4a175cef36e0eaa1fe7ff3b0a8570399380f06aeded536",
    "inputs": [
      {
        "path": "chatmon/a11y.py",
        "sha256": "aba945249b89b5da40f4b61d67a16299887ac3447c5fca64361155e12f2937e0"
      },
      {
        "path": "chatmon/heads_up.py",
        "sha256": "2fdd651948e492aa10423bc38bdd5fd4af268dead65f0b942627868365c63183"
      },
      {
        "path": "chatmon/linuxsession.py",
        "sha256": "fa24edd9227ca040fe7bbcec096093a72ac07e10b107b18a68a95e9fbca4e8a0"
      },
      {
        "path": "chatmon/macnative.py",
        "sha256": "3938c335464e2f6a828677604897e0bb972ddb65adddcf8b0e78e3b46eeacb63"
      },
      {
        "path": "chatmon/presence.py",
        "sha256": "2b1073598fa3ededc80cb408bff1a43e7b384d4d356973bcc022b5c5860320c1"
      },
      {
        "path": "chatmon/sysnotify.py",
        "sha256": "0e3f947994aaaf76eb53c94fb5e882be09f7feea9ea1a4eca848417eda3e2203"
      },
      {
        "path": "chatmon/winlock.py",
        "sha256": "29527329a9d3735cd4baa157f97941f40a1d4b32443804aa7343b924e7e20598"
      },
      {
        "path": "chatmon/winuia.py",
        "sha256": "07b3d8e2f97b38cb0f39173825d054b93caab1c9888453ac90226679ba58d410"
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
        "path": "tests/fake_notifications.py",
        "sha256": "4dcd214a2c4ba2303d1355dcc538f3ffdc7063a0504587e92f03fb3538d5b912"
      },
      {
        "path": "tests/fake_portal.py",
        "sha256": "546c8e803b87141a3998ca2e966c91309d4db52b112f72f9c1483b949cd5b24b"
      },
      {
        "path": "tests/fake_upower.py",
        "sha256": "bfa76d5e4e755f6987421e5ade5b9f7c1c50ff97eac5c322ed1de874b7c2ce3e"
      },
      {
        "path": "tests/private_bus.py",
        "sha256": "229b227961118c72f9f204952bdd5508450174a2c1043b1eb4d5fd7ff8bba9a2"
      },
      {
        "path": "tests/test_heads_up.py",
        "sha256": "fa2b96199f5dee5a8c91ac095f321e2c82a51b5fa2904de968cea5859c44f088"
      },
      {
        "path": "tests/test_linuxsession.py",
        "sha256": "0cf27e7aaac07820a626441deb8adef8df5a1b6376137cea4786d692e3e011b1"
      },
      {
        "path": "tests/test_macnative.py",
        "sha256": "7ed927e244aa95eb68462b6f86c28a23518daffb57f16d4f6ded257456981a30"
      },
      {
        "path": "tests/test_platform_events.py",
        "sha256": "468cd220421ec8cdbcd0bdce48ae5defcb645243ee3a5c8babc41d4ef4d1ad8c"
      },
      {
        "path": "tests/test_portal_bus.py",
        "sha256": "f3a80e308add6b3c7f672f4092d4c349aaca93be9cf19208c93bdb7a1464c7a3"
      },
      {
        "path": "tests/test_presence.py",
        "sha256": "9b717a33cf8bc4952d987d3d07de6e08d2f5a104651782c8619aaefd95e6f77e"
      },
      {
        "path": "tests/test_winlock.py",
        "sha256": "67a5738fa278f9cb52814236c203fb598abee92b9d72ecd631f38a8e610784d3"
      },
      {
        "path": "tests/uia_client.py",
        "sha256": "7075f36a283687bfb6f63b9f6650ae7542eeb87adde641bedcbb12b443fd7e70"
      }
    ],
    "environment": {
      "platform": "windows",
      "tools": {
        "python": "3.14.10",
        "pytest": "9.2.0",
        "ruff": "0.17.4",
        "pyqt6": "6.11.0"
      }
    },
    "verified_tasks": [
      "T-01",
      "T-02",
      "T-03",
      "T-05",
      "T-06",
      "T-07",
      "T-08"
    ],
    "pending_operations": [
      {
        "id": "CI-macos",
        "description": "macOS end to end (T-04, T-09): WorkspaceWatcher with real NSWorkspace and NSProcessInfo notifications, Low Power Mode, and AppKit's Increase contrast. No Mac here; EV-macos-ci is deferred.",
        "next_action": "Coordinator's CI run on macOS: tests/test_macnative.py::test_sleep_wake_displays_accessibility_and_low_power_are_heard and tests/test_presence.py::test_macos_reads_increase_contrast. On a pass, record EV-macos-ci as passing and mark T-04 and T-09 verified; on a failure, the output comes back to this milestone."
      },
      {
        "id": "CI-linux",
        "description": "The Linux receipts (EV-linux-*, EV-red-L-*) come from WSL (Arch, PyQt6 6.12.1), a profile other than this plan's Windows one, so closure flags them. CI's Ubuntu runner runs the same D-Bus tests under dbus-run-session.",
        "next_action": "Coordinator's CI run on Linux: tests/test_platform_events.py, tests/test_portal_bus.py, tests/test_heads_up.py, tests/test_linuxsession.py, tests/test_presence.py (the Qt contrast-signal test runs where pip's PyQt6 is 6.12 or later)."
      },
      {
        "id": "CI-windows-comtypes",
        "description": "The UI Automation end-to-end test (AC-09a) needs comtypes, a test-only tool not yet in the test extras; without it the test skips in CI. It ran here, with comtypes 1.5.0 in the shared venv.",
        "next_action": "M6A adds comtypes (Windows only) to the test extras; then the coordinator's Windows CI run includes tests/test_platform_events.py::test_a_ui_automation_client_hears_the_announcement."
      }
    ],
    "next_action": "Wait for the coordinator's CI results and fix any failure on wave1/m4a; M7 wires the APIs listed under Integration notes.",
    "source_revision": "5469377233f1536c5950e485f7ddb817b858c46e"
  }
}
```

## Integration notes

For M7 (M7-11 and M7-03), M0 (M0-06) and M6A. Nothing in `app.py` was changed; until these are wired, the app
behaves as before, except where noted as automatic.

**`presence.Desk`** (now a `QObject`):
- `settings_changed` signal: reduced motion or high contrast may have changed. Connect it to `_check_accessibility`,
  and take `_check_accessibility()` out of `_check_time`'s 30-second round. The first reading starts the Linux
  listeners; their first answers arrive a moment later as `settings_changed`, so connect before reading, or read
  again on the first signal.
- `screen_reader_changed` signal (Windows: NVDA, JAWS and others starting or stopping): set `_reader_seen` to
  `-inf`, so the next read-aloud looks again.
- `windows_setting_changed(action: int)`: pass it as `settings=` to `winlock.LockWatcher`.
- Automatic: Do Not Disturb from dunst, mako, SwayNotificationCenter, xfce4-notifyd and KDE in `quiet()`; per-screen
  `covered()` on X11; high contrast from the portal, GNOME and macOS in `high_contrast()`.

**`winlock.LockWatcher(changed, slept=None, seen=None, saving=None, settings=None)`**: `settings(action)` gets
WM_SETTINGCHANGE's action. Wire: `settings=self.desk.windows_setting_changed`.

**`macnative.WorkspaceWatcher()`** (macOS; works without the cocoa platform): signals `slept(bool)` (wire to
`_sleeping`), `screens_slept(bool)` (wire to `_seen(not on)`: nothing drawn while the displays sleep),
`accessibility_changed()` (wire to `_check_accessibility`), `low_power_changed(bool)` (wire to `_power_saving`).
Make it in `_watch_screen_lock`'s macOS branch, call `_power_saving(bool(macnative.low_power_mode()))` once at start,
and `close()` it at quit. `macnative.low_power_mode() -> bool | None`.

**`linuxsession.SessionWatcher(locked, slept, seen=None, parent=None)`**: pass `seen=self._seen` so the Linux lock
stops drawing (M7-11), and `parent=self`; each lock and unlock is told once now. `tests/test_app_smoke.py` (M0's)
replaces `SessionWatcher` with `lambda locked, slept: ...`, which needs `seen=None, parent=None` parameters once M7
passes them.

**`linuxsession.PowerProfile(saving, parent=None)`**: pass `parent=self`, so an answer that comes after the Companion
has gone reaches nothing. Automatic: running on battery (UPower `OnBattery`) saves power like the power-saver
profile; its first readings no longer wait. `heard` is now a list of services.

**`sysnotify.Notifier(parent=None)`** (Linux; one per app):
- `read_aloud(title, body, buttons=None, pressed=None) -> bool`: transient, replacing the last read-aloud one. Use it
  as `a11y.announce`'s `notify` on Linux instead of `sysnotify.send`.
- `alert(title, body, buttons=None, pressed=None, urgency=URGENCY_CRITICAL) -> bool`: for the held alert in
  `Companion.alert()`. Urgency 2 shows through GNOME's Do Not Disturb; pass `urgency=sysnotify.URGENCY_NORMAL`
  when the reason for waiting is Do Not Disturb (`self._quiet == "Do Not Disturb"`), if that's the call M7 makes.
- `pressed(index)` gets the place of the button pressed on the notification: pass
  `lambda i: buttons[i][1] and buttons[i][1]()` (a bubble's `(label, action)` list).
- `sysnotify.send(title, body)` stays, unchanged, until M7 moves to the Notifier.

**`a11y.announce(reader, words, important=False, notify=None) -> str`**: replaces the body of `_read_aloud` after
`words` is built: `a11y.announce(self._screen_reader(), words, important, notify=...)`, where `notify` sends the
fallback (Linux: `notifier.read_aloud(a11y.plain(title), words, labels, pressed)`; Windows: M4B's toast, or the
tray balloon as now). It returns "uia", "spoken", "notification" or "".
- Automatic: VoiceOver announcements wait while Chatmon isn't the active app and are said when it is.
- `a11y.set_speech_fallback(on: bool)`: a new setting for M7-03's Accessibility tab, off by default, macOS only:
  "Speak announcements aloud while Chatmon is in the background (macOS's own voice)". Config key suggestion:
  `accessibility.speech_fallback = false`.
- `a11y.reader()` on Windows now makes the UIA announcer window when it finds a screen reader (`winuia.prepare()`).

**`heads_up.read_battery()` and `heads_up.read_disks(folders)`**: safe on any thread; M0-06 can run both in
`Background`. `heads_up.battery_from_upower(properties)` is the UPower parsing.

**M6A**: `comtypes` (Windows only) as a test-only dependency, for `tests/uia_client.py`; without it the UI
Automation end-to-end test skips. Suggested: `test = ["pytest", "comtypes; sys_platform == 'win32'"]`.

## Changelog notes

- High contrast is followed on Linux (the desktop portal's setting, or GNOME's) and on macOS (Increase contrast).
- Turning reduced motion or high contrast on or off applies at once, instead of within half a minute.
- Do Not Disturb is respected with dunst, mako, SwayNotificationCenter and xfce4-notifyd (Hyprland, Sway, Xfce and
  others), as it already was with KDE and GNOME.
- With two monitors on X11, a full-screen app on the other monitor no longer hides the chatmon (bubbles still wait).
- On Linux, the chatmon draws fewer frames while the laptop runs on battery; on macOS, in Low Power Mode.
- On macOS, sleep counts as time away, and nothing is drawn while the displays sleep. On Linux, nothing is drawn
  while the screen is locked.
- Screen readers: on Windows, Narrator, NVDA and JAWS hear Chatmon directly while it's in front, instead of through
  a notification. On macOS, VoiceOver no longer misses what's said while Chatmon is in the background: it's said
  when you come back, or at once by macOS's voice if you turn that on. On Linux, read-aloud notifications no
  longer pile up in the notification history, and a bubble's buttons can be pressed in the notification.
- The battery check no longer holds up the screen on Linux.

## README notes

- Accessibility: high contrast and reduced motion follow the system on every platform (Linux: the desktop portal
  or GNOME's settings; macOS: Accessibility › Display; Windows: its own settings), and changes apply at once.
- Screen readers: Windows uses UI Automation notifications while Chatmon is in front, else a notification; macOS
  VoiceOver hears announcements when you come to Chatmon, or at once with the speech option (off by default);
  Linux uses Orca's own interface, else a notification that stays out of the history, with the bubble's buttons.
- Quiet times: Do Not Disturb is read from GNOME, KDE, dunst, mako, SwayNotificationCenter and xfce4-notifyd.
- Power: the chatmon draws less while on battery (Linux), in Low Power Mode (macOS) and in Energy Saver (Windows).
- Privacy: nothing new is stored or sent. The speech option uses macOS's own `say`, on the Mac.
