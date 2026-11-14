# M4A: platform awareness and screen readers

Brief: [ASSESSMENT.md](ASSESSMENT.md#m4a-platform-awareness-and-screen-readers-presencepy-a11ypy-macnativepy-linuxsessionpy-sysnotifypy-heads_uppy-portalpy-winlockpy),
items M4A-01 to M4A-11. Rules: [ROADMAP.md](ROADMAP.md) and `pyproject.toml`. Worktree branch `wave1/m4a`, from
`improve/assessment-fixes` at `5346385`. Reports, logs and drill results are in [reports/m4a/](reports/m4a/).

## Scope

This milestone gives the platform modules the readings and signals the app needs. It doesn't change `app.py`:
what the app does with them is M7's work (M7-11), listed under **Integration notes**. Only the files M4A owns
change (`presence.py`, `a11y.py`, `macnative.py`, `linuxsession.py`, `sysnotify.py`, `heads_up.py`,
`winlock.py`; `portal.py` needed no change), plus new tests and test fakes.

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
  no code path is written for it. UI Automation is reached directly. Probes in this session showed that
  `UiaRaiseNotificationEvent` is delivered to a UIA client only from a provider the window hands out itself (for
  `WM_GETOBJECT`), with `ProviderOptions_ServerSideProvider` and `IsControlElement` true, from a shown window: a
  host provider from `UiaHostProviderFromHwnd`, or a provider no window handed out, is dropped without an error.
  NVDA ignores notifications from apps in the background, so UIA is used while Chatmon is in front, and the
  notification remains the fallback.
- **M4A-10** true: `upower_battery()` makes up to three blocking calls. Nothing in it is tied to the screen's
  thread (QtDBus connections can be used from any thread), so the fix is one call, and a test on a worker thread.
- **M4A-11** true: `SessionWatcher` reports the lock only for breaks, and repeats it once per source.

## Design

- `presence.Desk` becomes a `QObject` with `settings_changed` and `screen_reader_changed` signals. Linux readings
  come from caches kept by listeners started on first use: `_PortalSettings` (asynchronous `ReadOne`, then
  `SettingChanged`), `_GSetting` (now with a change callback), and `_NotificationDnd` (asynchronous, never
  starting a service: `NoAutoStart` on every message). High contrast on Linux: the portal's `contrast`, then GNOME's
  `high-contrast`, then Qt's hint; on macOS, `accessibilityDisplayShouldIncreaseContrast`.
- `winlock.LockWatcher` takes a `settings(action)` callback for `WM_SETTINGCHANGE`, from its own window only.
- `macnative.WorkspaceWatcher` is an Objective-C class of Chatmon's own (as `_Menus` is) observing NSWorkspace's
  sleep, wake, screens-sleep, screens-wake and accessibility-display notifications, and NSProcessInfo's power state.
- `linuxsession.PowerProfile` adds UPower's `OnBattery` (power saving while either is on), with asynchronous first
  reads; `SessionWatcher` reports `seen(bool)` and tells each change once.
- `sysnotify.Notifier` sends read-aloud notifications as transient, each replacing the last, alerts at urgency 2,
  and buttons as actions, reporting `ActionInvoked`.
- `a11y.announce()` is the one way to have something read out: UIA notifications on Windows while Chatmon is in
  front, Orca, VoiceOver (held until Chatmon is active, or spoken by an opt-in fallback), else the app's notifier.
- `heads_up.upower_battery()` is one `GetAll` call, and the readings are safe on any thread.

Reuse: the D-Bus helpers in `presence.py`, the existing fakes (`fake_portal.py` gains Settings), the native event
filter in `winlock.py`, and `macnative`'s runtime and class pattern. New: `tests/fake_notifications.py` and
`tests/fake_upower.py` (no existing fake serves those interfaces), and `tests/test_winlock.py` and
`tests/test_platform_events.py` (M6A owns `test_windows.py`).

## Verification

- Windows: the whole suite and ruff, plus red drills (`reports/m4a/drill-spec.json`) on Windows-runnable tests.
- Linux: the D-Bus tests run in WSL (Arch, throwaway venv under `/var/tmp/m4a-venv`, PyQt6 6.12.1) and in CI.
- macOS: tests that run on CI's macOS runner only; pending until the coordinator's CI run.

```quality-ledger
{
  "schema_version": 1,
  "work": {
    "id": "M4A",
    "title": "Platform awareness and screen readers",
    "scope_revision": 1,
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
      "purpose": "Desk as a QObject with change signals; portal settings cache; Linux and macOS high contrast; Qt's contrast signal; Windows setting changes; per-screen covered on X11",
      "acceptance": [
        "AC-01a",
        "AC-01b",
        "AC-01c",
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
          "path": "tests/test_presence.py",
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
        }
      ],
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
          "path": "tests/test_a11y.py",
          "action": "modify"
        }
      ],
      "status": "planned",
      "evidence": [],
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
        }
      ],
      "status": "planned",
      "evidence": [],
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
      "status": "pass",
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
      "reason": null
    }
  ],
  "checkpoint": null
}
```

## Integration notes

Filled in as the APIs land.

## Changelog notes

Filled in as the behavior lands.

## README notes

Filled in as the behavior lands.
