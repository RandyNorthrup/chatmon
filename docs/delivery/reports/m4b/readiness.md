# M4B readiness review, 2026-11-14

A review of the requirements in [../../m4b-hotkey-sound-toasts.md](../../m4b-hotkey-sound-toasts.md) against the brief
([ASSESSMENT.md](../../ASSESSMENT.md), section M4B), the [ROADMAP](../../ROADMAP.md) (owner decisions, file ownership,
the M4B and M7 contract, rules for workers), the coordinator's instructions for this milestone, and the code as it
stands at `5346385`. It reviews the requirements, not the code: it proves nothing works.

## Coverage

| Brief item | Requirement | Acceptance |
|---|---|---|
| M4B-01 hotkey: Windows, macOS, X11, Wayland, failure reported | M4B-01 | AC-01A (parsing), AC-01B (Windows), AC-01C (conflict), AC-01D (macOS), AC-01E (X11), AC-01F (Wayland portal) |
| M4B-02 sound: QSoundEffect, fallbacks, quiet, volume, per cue | M4B-02 | AC-02A, AC-02B, AC-02C (owner's defaults), AC-02D (fallbacks, never blocking) |
| M4B-03 WinRT toasts: buttons, reminder scenario, app ID, balloon fallback | M4B-03 | AC-03A (XML), AC-03B (shown, or declined for the fallback), AC-03C (activation and events), AC-03D (app ID registration) |
| M4B-04 Magnifier follows bubbles, as an option | M4B-04 | AC-04A (caret), AC-04B (only while Magnifier runs) |
| "Every module must import safely on every OS" (coordinator) | M4B-00 | AC-00A |

Every requirement has acceptance, every acceptance criterion has an owning task, and the tasks' dependencies are
ordered (T-TOAST after T-WINRT, T-PORTAL after T-HOTKEY).

## Findings

1. **Conflict: the portal "over QtDBus".** The coordinator's brief says the GlobalShortcuts portal is reached over
   QtDBus. Probe 3 in [probes.md](probes.md) shows PyQt6 can neither send nor receive its `a(sa{sv})` argument: sending
   aborts the process inside libdbus, receiving is refused. Resolution: talk to the portal through libdbus with
   ctypes (`chatmon/libdbus.py`). That keeps the owner's rule (no new runtime dependency; OS facilities through
   ctypes, QtDBus or Qt modules already shipped): libdbus is the library QtDBus itself loads. Recorded in the plan's
   Rationale.
2. **Contract detail: errors that come later.** The M4B and M7 contract is `hotkey.register(sequence, callback) ->
   error | None`. The portal answers after the call returns (the desktop may ask the user), so a refusal can't be
   the return value. Resolution: `register()` keeps the contract and takes an optional `failed` callback;
   `Hotkey.failed` is the same as a signal. Not a scope change.
3. **Failure behavior made explicit.** No audio device or a broken QtMultimedia: the next player is tried. A missing
   cue file: nothing plays, no error (M9's files may not be packaged yet). Notifications turned off or no app ID:
   `show()` returns None and says why, and the caller uses the tray balloon. A toast clicked after Chatmon quit isn't
   delivered (no COM activator is registered); `Toaster.clear()` lets M7 remove Chatmon's toasts at quit.
4. **Quiet times belong to the caller.** The owner decided all sound is quiet during Do Not Disturb, Focus and
   full-screen. Those states are worked out in `presence.py` (M4A) and `app.py` (M0/M7), so `sound.configure()`
   takes a `quiet` callable rather than `sound.py` asking the OS again.
5. **"Ctrl" on macOS.** A portable sequence is ambiguous on macOS. Resolution: Qt's own convention (Ctrl is Command,
   Meta is Control), so a sequence from `QKeySequenceEdit` (which M7's settings would use) means what the user
   pressed.
6. **"As an option" (M4B-04).** The setting itself is M1B's (`settings.py`) and M7's (settings window). This
   milestone delivers the mechanism, and `magnifier_running()` so the caret is placed only while Magnifier runs.
   Placing a caret while the ask box has focus could move the ask box's own; M7 is told not to.
7. **Terminology.** Cue names are M9's file names (`needs-you`, `reminder`, `focus-done`, `done`, `success`,
   `error`, `pop`). Volume is a percentage (0 to 100), as a settings slider holds it.
8. **Testability limits.** macOS code can't run here: its tests run on macOS CI and are pending. X11 needs an X
   server: Xvfb runs here in WSL, but CI installs none, so the X11 test skips there until M6A adds it. The portal
   test needs `dbus-run-session`, which CI's Ubuntu has. Toasts can't be seen landing in the history on this PC
   (notifications are off for this user, which isn't this milestone's to change); CI's runner shows it.
9. **Leave nothing behind.** Hotkey tests unregister in `finally`; toast tests clear their app ID's history and
   delete any registry key they write; sound tests write WAVs only under pytest's temp folder; the caret test
   destroys its window.

## Rules checked

- File ownership: only `hotkey.py`, `sound.py`, `wintoast.py`, `winfocus.py`, new files and their tests are changed.
  `README.md`, `chatmon/changelog.md`, `chatmon/__init__.py`, `chatmon/settingswin.py` are untouched; app wiring,
  settings keys, CI and package data are Integration notes.
- No new runtime dependency: ctypes, the standard library (`winsound`, `xml.etree`, `winreg`), PyQt6 modules
  already in the wheel (QtMultimedia is optional and checked at run time).
- Tests: real Qt objects under the offscreen platform, the `qapp` fixture, OS-specific tests that skip elsewhere
  with a reason.

Result: ready, with findings 1 and 2 resolved in the plan as described.

## Revision 2 (scope revision 2), 2026-11-14

Re-reviewed after building the portal client, which changed two things:

- **AC-01F, what comes back when.** The portal backend never blocks the screen's thread, so it can't tell during
  `register()` whether the portal exists: that is learned on its own thread. A desktop without the portal is now
  reported through `failed` (with `hotkey.NO_PORTAL`), like a refusal, and `register()` returns None once the request
  is on its way. AC-01F also now says Activated for another session is ignored and unregistering closes the session,
  which the tests check. This narrows no requirement: M4B-01 says a failure is reported, not how.
- **T-PORTAL's files.** The portal client is `chatmon/shortcutportal.py`, apart from `hotkey.py`, so `hotkey.py`
  never imports libdbus unless a Wayland shortcut is set.
- **Portal changes don't keep the old shortcut.** A desktop binds a session's shortcuts once, so a new shortcut means a
  new session, and the old one is closed first. On Windows, macOS and X11 a failed change still keeps the old one
  (AC-01C).

Coverage, ordering and the other findings above are unchanged. Result: ready.

## Revision 3 (scope revision 3), 2026-11-14

The criteria that bundled several platforms are split, one per platform, so each is verified where it can run and
the rest stay visibly pending rather than being half-verified:

- AC-00A (imports) is Windows; AC-00B is Linux and AC-00C macOS.
- AC-02D (players without QtMultimedia) is Windows, plus choosing the system's player when QtMultimedia is missing;
  AC-02E is the Linux players and AC-02F NSSound.
- AC-03B is a toast that can't be shown (notifications off, no app ID, not Windows); AC-03E is a toast Windows does
  show, which needs notifications on: CI's Windows runner.
- AC-02A also says a sound still playing as the app quits doesn't take the process down: a red drill found that it
  did (a fail-fast, 0xC0000409, from a QSoundEffect destroyed while playing), and the fix and its test are in.

The tasks follow the split (T-TOAST-SHOWN, T-SOUND-LINUX, T-SOUND-MAC, T-HOTKEY-MAC, T-HOTKEY-X11,
T-IMPORTS-POSIX), each depending on the task whose code it extends. No requirement changed: M4B-00 to M4B-04 have
the same obligations, stated per platform. Result: ready.

## Revision 4 (scope revision 4), 2026-11-14

After the merge into `improve/assessment-fixes` and CI run 43648733348:

- **Rules changed.** `pyproject.toml` now has strict pytest settings (warnings are errors, `--strict-markers`,
  pytest-timeout at 120 s) and `tests/conftest.py` gives each run a Chatmon address of its own. Every earlier receipt
  was bound to the old files, so all of them are stale, and every test and drill is run again.
- **AC-03C** adds that nothing more is reported for a toast already settled: Windows reported one toast hidden and
  then timed out. **AC-03E** says a toast sent straight to Action Center may be reported timed out before hidden,
  and hidden is the last word. **AC-03B** is unchanged in words ("turned off" is a real no from Windows); what
  changed is the code, which treated Windows' silence as a no.
- CI's macOS and Linux jobs ran this milestone's tests and passed; they are recorded as receipts with their own
  environments, which the plan's single Windows profile can't count as verification.

No requirement changed. Result: ready.
