# M4B's macOS drills, and the whole suite, on the owner's MacBook Pro (2026-11-15)

M4B's three macOS red drills had been deferred: AC-00C (imports), AC-01D (Carbon's hot keys) and AC-02F (NSSound).
They needed a Mac. The owner approved his MacBook Pro for them on 2026-11-15 ("yeah use the macbook pro"). They ran
there from the Windows workstation, and the whole suite ran with them, as CI's macOS job runs it. There were two
sessions that day:

- **3586a0d** (`improve/assessment-fixes`), in [3586a0d/](3586a0d/), while another worker (wave4/m4b-toast) was
  editing the plan.
- **a4fe9f8**: this branch with `improve/assessment-fixes` merged in (cbeed17, the toast merge, and 86e84e0, the quit
  guard). The logs at the top of this folder are this session's, and the plan binds them. 8c24b1c changed
  `tests/test_wintoast.py`, a file of a task AC-00C depends on, so the first session's runs couldn't stand for this
  tree.

The receipts are MAC-RED-AC-00C, MAC-RED-AC-01D, MAC-RED-AC-02F and MAC-BEH-MACOS. They were bound together with
round three's re-run of every other M4B check ([../w4d/README.md](../w4d/README.md)), and M4B now closes.

## Where it ran

- macOS 15.7.9 (24G830), Intel x86_64, with the owner signed in at the console.
- Homebrew's Python 3.13.7, which was already installed, in a venv of its own with `packaging/requirements-test.txt`
  (`--require-hashes`): PyQt6 6.11.0 (Qt 6.11.2's wheels), pytest 9.2.0. The versions, read inside the Aqua session,
  are in [context-observed-aqua.txt](context-observed-aqua.txt). The Python 3.15 installed between the sessions
  (see the end) wasn't used for these runs, so both sessions ran on the same interpreter.
- The code: `git archive --format=tar.gz HEAD`, unpacked into `~/chatmon-drills-tmp/src`, with every file in a git
  index of its own (no commit). In the second session that index's tree was a4fe9f8's own (`6fa4a57f`).
- The scripts are M1A's, in [../../m1a/mac/](../../m1a/mac/README.md). [job.sh](../../m1a/mac/job.sh) runs each step
  with `HOME` and `TMPDIR` inside `~/chatmon-drills-tmp`. [aqua.sh](../../m1a/mac/aqua.sh) runs a step in the owner's
  Aqua session, where the window server is. A process started over ssh isn't there, and `launchctl asuser` needs
  root. The step runs as a one-shot launchd job in `gui/503`, from a plist in that folder, not in
  `~/Library/LaunchAgents`. It is booted out once it ends.

## The drills

[drill-spec.json](drill-spec.json), run in the Aqua session with `sh aqua.sh m4b-drills drills SPEC LOG`
([drills.log](drills.log), [drills-results.json](drills-results.json), [drills-run.txt](drills-run.txt)):

| Drill | Mutation | Red (pytest's exit 1) |
|---|---|---|
| MAC-00C-linux-import-sound (AC-00C) | `chatmon/sound.py` gets a top-level `from select import epoll`, a name only Linux's `select` has | `test_it_imports_here[sound]` fails: `ImportError: cannot import name 'epoll' from 'select'` in the fresh interpreter. The other seven pass. |
| MAC-01D-conflict-unreported (AC-01D) | In `_Carbon.grab`, the `eventHotKeyExistsErr` branch returns `None` instead of the conflict | `test_macos_reports_a_conflict_and_keeps_the_shortcut_it_had` fails at `tests/test_hotkey.py:281`: `assert None == 'Ctrl+Alt+Shift+F18 is already used by another app. Pick another shortcut.'` |
| MAC-02F-volume-unset (AC-02F) | `MacPlayer.play` leaves out `setVolume:` on the NSSound | `test_nssound_plays_at_the_volume` fails at `tests/test_sound.py:267`: `assert 1.0 == 0.5 ± 5.0e-07`. That's NSSound's own volume, not the one asked for. |

Each went green, red and green again, in both sessions. The SHA-256 of each file was checked after it was put back:
hotkey.py cc781737… and sound.py 17a6ab89…, as committed.

**Earlier runs**, in [3586a0d/](3586a0d/). The first session's first two runs put the Linux-only import in
`chatmon/libdbus.py` instead ([drill-spec-first.json](3586a0d/drill-spec-first.json); the second run's logs are
`drills-first*`). There, `test_it_imports_here[libdbus]` and `[shortcutportal]` (which imports it) failed with the
same `ImportError`, and every drill went green, red and green. But `libdbus.py` belongs to the portal's task, not to
AC-00C's task or the tasks it depends on. So the validator wouldn't take that drill as AC-00C's red, and the drill
moved to `sound.py` for the first session's third run ([3586a0d/drills.log](3586a0d/drills.log)).

The hot keys the tests use are Command+Option+Shift with F17, F18 and F19. They're held only while each test runs.
After each session, a separate process could register each of the three exclusively, so none was still held
([hotkeys-free.txt](hotkeys-free.txt)). The Mac's output was already muted, at volume 0, and stayed that way
throughout. The drills didn't change it.

## The suite

As CI's macOS job runs it: every test with `QT_QPA_PLATFORM=offscreen`, then `tests/test_macnative.py` with
`QT_QPA_PLATFORM=cocoa`. Both ran in the Aqua session.

| Step | a4fe9f8 (bound) | 3586a0d | Logs |
|---|---|---|---|
| Every test, offscreen | **1235 passed, 201 skipped, 1 deselected**, exit 0 (1437 collected) | the same | [suite-offscreen.log](suite-offscreen.log), [3586a0d/](3586a0d/suite-offscreen.log) |
| `tests/test_macnative.py`, cocoa | **8 passed**, exit 0 | the same | [suite-macnative-cocoa.log](suite-macnative-cocoa.log), [3586a0d/](3586a0d/suite-macnative-cocoa.log) |

For comparison, CI's macos-latest 3.14 leg at bf9d8ac had 1233 passed and 201 skipped, of 1434 collected, and then
8 passed on cocoa (run 43701523023). wave4/crash added 3 tests to `tests/test_app_smoke.py` since. Every macOS test
of M4B's ran and passed: `tests/test_hotkey.py`'s Carbon tests, `tests/test_sound.py`'s NSSound test, and all 8 of
`tests/test_m4b_imports.py`. The skips are other platforms' tests, and tools this Mac doesn't have (dbus,
libxkbcommon, Wayland, a built wheel). Each skip's reason is at the end of the log.

Two things differ from CI. Both were done to protect the owner's own state:

- `tests/test_keychain.py::test_macos_keychain_keeps_replaces_and_forgets_a_key` was deselected. It adds a key to
  the owner's own login keychain and removes it again. CI's macOS legs run it.
- `CHATMON_TEST_CLIPBOARD` wasn't set, because the clipboard is the owner's. One Windows test
  (`tests/test_windows.py:795`) was skipped for that reason instead of "Windows only", so the count is the same.

`tests/test_macnative.py` on cocoa shows real windows for a few seconds. One of them is a full-screen window, in a
Space of its own. They all closed when the tests ended. The owner's Mac had been idle for 4.7 days, and Finder was
the front app before and after each session.

**The first attempt** ([3586a0d/suite-offscreen-attempt1.log](3586a0d/suite-offscreen-attempt1.log)) had 2 failed,
1233 passed, 201 skipped and 1 deselected. Both failures were in `tests/test_package_data.py`: "the listing didn't
find the package". `src/` was then a git work tree with nothing in its index, so `git ls-files -- chatmon` listed
nothing. On a checkout it lists the tracked files, and with no git at all the test lists the folder. The setup now
indexes every file (`git add -A`, in job.sh). The first session's suite and its first two drill runs used the
job.sh from before its observe step also printed the Qt version that runs. Nothing else in it changed. Everything
else, the second session included, used the job.sh that's here.

## What was left as found

[state.sh](../../m1a/mac/state.sh) reads what the drills could have touched. It ran before and after each session:
[3586a0d/state-before.txt](../../m1a/mac/3586a0d/state-before.txt) and
[3586a0d/state-after.txt](../../m1a/mac/3586a0d/state-after.txt), then
[state-before.txt](../../m1a/mac/state-before.txt) and [state-after.txt](../../m1a/mac/state-after.txt). Each pair is
identical. They cover:

- sound (output muted, volume 0) and the front app (Finder);
- `~/Library/LaunchAgents` and launchd's jobs;
- Chatmon's folders (none), `/private/tmp` and the owner's own temporary folder;
- the keychain;
- Homebrew's formulae (list hash and count) and the Pythons;
- uv: never installed. The owner's own `~/.cache/uv` and `~/.local/share/uv` were untouched;
- pip's cache.

- The drills installed nothing outside `~/chatmon-drills-tmp`. No uv, no sudo, no system setting, no login item.
- `~/chatmon-drills-tmp` was removed after each session (574 MB, then 593 MB: the code, the venv, the test runs'
  temporary files). `launchctl list` has no job of the drills, and no process of theirs was left.

## Python 3.15, installed between the sessions on the owner's decision

The coordinator relayed the owner's request ("install the latest python global and leave it for future stuff") and
then his decision to allow its upgrades. Homebrew's `python@3.15` was installed and left installed. It wasn't used
for the drills. Everything is in [python-3.15/](python-3.15/):

- Command (17:05 to 17:29 UTC, `brew-started.txt`, `brew-finished.txt`):
  `HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK=1 HOMEBREW_NO_INSTALL_CLEANUP=1 /usr/local/bin/brew install python@3.15`
  ([brew-install.log](python-3.15/brew-install.log)).
  - No auto-update: the install is exactly what the dry run showed and the owner approved. Homebrew's formula list
    had been refreshed by `brew config` earlier that day.
  - No cleanup: the older versions stay, as the owner keeps them.
  - This Intel Mac is Homebrew's Tier 3, which has no bottles. So everything but ca-certificates was compiled from
    source: openssl@4 in 3 minutes, cmake in 10, python@3.15 in 6.
- New: python@3.15 3.15.2 and openssl@4 4.1.0.
- Upgraded, with the old versions kept: ca-certificates 2026-11-05, readline 8.3.6, sqlite 3.54.1, xz 5.8.4,
  cmake 4.5.0 and lz4 1.11.1.
- Nothing removed. `brew list` went from 153 formulae to 155 ([brew-before.txt](python-3.15/brew-before.txt),
  [brew-after.txt](python-3.15/brew-after.txt)).
- Links in `/usr/local/bin` ([links-before.txt](python-3.15/links-before.txt),
  [links-after.txt](python-3.15/links-after.txt)):
  - `python3`, `python3-config`, `pip3`, `pydoc3` and `idle3` now point at 3.15.2, where they pointed at 3.13.7.
  - New: `python3.15`, `python3.15-config`, `pip3.15`, `pydoc3.15` and `idle3.15`.
  - `python3.13`, `python3.12` and their tools are unchanged.
  - Homebrew backed up what it relinked (also the python3 man page, pkg-config files and
    `/usr/local/Frameworks/Python.framework`'s current version) in `~/Library/Caches/Homebrew/Backup`.
- Verified ([verify.txt](python-3.15/verify.txt)):
  - `/usr/local/bin/python3 --version` and `python3.15 --version` give Python 3.15.2. `python3.13` gives 3.13.7, and
    `python3.12` gives 3.12.12.
  - `pip3` is 3.15's pip 26.2.2.
  - The owner's login shell finds `/usr/local/bin/python3` first, and it is 3.15.2.
  - 3.15's `ssl`, `sqlite3`, `lzma`, `readline`, `ctypes`, `zlib`, `bz2` and `decimal` import: OpenSSL 4.1.0,
    SQLite 3.54.1, libmpdec 4.0.1.
  - `tkinter` isn't there: it comes separately, as `python-tk@3.15`, which wasn't asked for.
- Warnings in the log: a newer Command Line Tools is available (not installed: it would be a system update), and
  three of the owner's taps aren't trusted (Homebrew 7's tap trust; nothing from them was installed). Over ssh,
  `/usr/bin` comes before `/usr/local/bin` on the PATH, so `python3` there still means Apple's 3.9.6. The owner's
  login shell has Homebrew first.
