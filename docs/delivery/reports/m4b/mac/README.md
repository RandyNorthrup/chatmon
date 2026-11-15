# M4B's macOS drills, and the whole suite, on the owner's MacBook Pro (2026-11-15)

M4B's three macOS red drills had been deferred: AC-00C (imports), AC-01D (Carbon's hot keys) and AC-02F (NSSound).
They needed a Mac. The owner approved his MacBook Pro for them on 2026-11-15 ("yeah use the macbook pro"). They ran
there from the Windows workstation, on **3586a0d** (`improve/assessment-fixes`). Each went green, red and green again.
The whole suite ran there too, as CI's macOS job runs it.

The plan isn't changed here: another worker (wave4/m4b-toast) is editing it. [bindings.json](bindings.json) holds
the three red receipts for it (MAC-RED-AC-00C, MAC-RED-AC-01D, MAC-RED-AC-02F). Its `next_action` is left to fill
in when they're bound, after that branch merges.

## Where it ran

- macOS 15.7.9 (24G830), Intel x86_64, with the owner signed in at the console.
- Homebrew's Python 3.13.7, already installed, in a venv of its own with `packaging/requirements-test.txt`
  (`--require-hashes`): PyQt6 6.11.0 (Qt 6.11.2's wheels), pytest 9.2.0. The versions, read inside the Aqua session
  as the drills ran, are in [context-observed-aqua.txt](context-observed-aqua.txt).
- The code: `git archive --format=tar.gz HEAD` of 3586a0d, unpacked into `~/chatmon-drills-tmp/src`, with every
  file in a git index of its own (no commit).
- The scripts are M1A's, in [../../m1a/mac/](../../m1a/mac/README.md). [job.sh](../../m1a/mac/job.sh) runs each step
  with `HOME` and `TMPDIR` inside `~/chatmon-drills-tmp`. [aqua.sh](../../m1a/mac/aqua.sh) runs a step in the
  owner's Aqua session, where the window server is. A process started over ssh isn't there, and `launchctl asuser`
  needs root. The step runs as a one-shot launchd job in `gui/503`, from a plist in that folder, not in
  `~/Library/LaunchAgents`. It is booted out once it ends.
- The drills and the offscreen suite ran with the job.sh before its observe step also printed the Qt version that
  runs. Nothing else in it changed.

## The drills

[drill-spec.json](drill-spec.json), run in the Aqua session with `sh aqua.sh m4b-drills drills SPEC LOG`
([drills.log](drills.log), [drills-results.json](drills-results.json), [drills-run.txt](drills-run.txt)):

| Drill | Mutation | Red (pytest's exit 1) |
|---|---|---|
| MAC-00C-linux-import (AC-00C) | `chatmon/libdbus.py` gets a top-level `from select import epoll`, a name only Linux's `select` has | `test_it_imports_here[libdbus]` and `[shortcutportal]` (which imports it) fail: `ImportError: cannot import name 'epoll' from 'select'` in the fresh interpreter. The other six pass. |
| MAC-01D-conflict-unreported (AC-01D) | In `_Carbon.grab`, the `eventHotKeyExistsErr` branch returns `None` instead of the conflict | `test_macos_reports_a_conflict_and_keeps_the_shortcut_it_had` fails at `tests/test_hotkey.py:281`: `assert None == 'Ctrl+Alt+Shift+F18 is already used by another app. Pick another shortcut.'` |
| MAC-02F-volume-unset (AC-02F) | `MacPlayer.play` leaves out `setVolume:` on the NSSound | `test_nssound_plays_at_the_volume` fails at `tests/test_sound.py:267`: `assert 1.0 == 0.5 ± 5.0e-07`. That's NSSound's own volume, not the one asked for. |

The SHA-256 of each file was checked after it was put back: libdbus.py 625148fb…, hotkey.py cc781737…, sound.py
17a6ab89…, as committed. The drills ran twice, before and after the setup put `src/` in a git index (see *The
suite*), and both runs passed. The harness copies files without `.git`, so the index made no difference to them.
These logs are the second run.

The hot keys the tests use are Command+Option+Shift with F17, F18 and F19. They're held only while each test runs.
Afterwards, a separate process could register each of the three exclusively, so none was still held
([hotkeys-free.txt](hotkeys-free.txt)). The Mac's output was already muted, at volume 0, and stayed that way
throughout. The drills didn't change it.

## The suite

As CI's macOS job runs it: every test with `QT_QPA_PLATFORM=offscreen`, then `tests/test_macnative.py` with
`QT_QPA_PLATFORM=cocoa`. Both ran in the Aqua session.

| Step | Result | Log |
|---|---|---|
| Every test, offscreen | **1235 passed, 201 skipped, 1 deselected** in 263.85s, exit 0 (1437 collected) | [suite-offscreen.log](suite-offscreen.log) |
| `tests/test_macnative.py`, cocoa | **8 passed** in 2.54s, exit 0 | [suite-macnative-cocoa.log](suite-macnative-cocoa.log) |

For comparison, CI's macos-latest 3.14 leg at bf9d8ac had 1233 passed and 201 skipped, of 1434 collected, and
then 8 passed on cocoa (run 43701523023). 3586a0d has 3 more tests, from wave4/crash in `tests/test_app_smoke.py`.
Every macOS test of M4B's ran and passed: `tests/test_hotkey.py`'s Carbon tests, `tests/test_sound.py`'s
NSSound test, and all 8 of `tests/test_m4b_imports.py`. The skips are other platforms' tests, and tools this Mac
doesn't have (dbus, libxkbcommon, Wayland, a built wheel). Each skip's reason is at the end of the log.

Two things differ from CI. Both were done to protect the owner's own state:

- `tests/test_keychain.py::test_macos_keychain_keeps_replaces_and_forgets_a_key` was deselected. It adds a key to
  the owner's own login keychain and removes it again. CI's macOS legs run it (W4B-BEH-CI-MACOS).
- `CHATMON_TEST_CLIPBOARD` wasn't set, because the clipboard is the owner's. One Windows test
  (`tests/test_windows.py:795`) was skipped for that reason instead of "Windows only", so the count is the same.

`tests/test_macnative.py` on cocoa shows real windows for a few seconds. One of them is a full-screen window, in a
Space of its own. They all closed when the tests ended. The owner's Mac had been idle for 4.7 days, and Finder was
the front app before and after.

**The first attempt** ([suite-offscreen-attempt1.log](suite-offscreen-attempt1.log)) had 2 failed, 1233 passed,
201 skipped and 1 deselected. Both failures were in `tests/test_package_data.py`: "the listing didn't find the
package". `src/` was then a git work tree with nothing in its index, so `git ls-files -- chatmon` listed nothing.
On a checkout it lists the tracked files, and with no git at all the test lists the folder. The setup now indexes
every file (`git add -A`, in job.sh), and the second run is the one above.

## What was left as found

[state.sh](../../m1a/mac/state.sh) read what the drills could have touched, before
([state-before.txt](../../m1a/mac/state-before.txt)) and after ([state-after.txt](../../m1a/mac/state-after.txt)).
The two are identical. That covers sound (output muted, volume 0), the front app (Finder),
`~/Library/LaunchAgents`, launchd's jobs, Chatmon's folders (none), `/private/tmp` and the owner's own temporary
folder, the keychain, and Homebrew's 153 formulae (same list hash). It also covers the Pythons
(`/usr/local/bin/python3` is still python@3.13 3.13.7), uv (never installed; the owner's own `~/.cache/uv` and
`~/.local/share/uv` untouched), and pip's cache.

- The drills installed nothing outside `~/chatmon-drills-tmp`. The venv was made from the Python 3.13.7 that
  Homebrew had already installed. No uv, no Homebrew change, no sudo, no system setting, no login item.
- `~/chatmon-drills-tmp` (574 MB: the code, the venv, the test runs' temporary files) was removed, and
  `launchctl list` has no job of the drills. No process of theirs was left.
- Homebrew: `brew config`, `brew info`, `brew outdated` and `brew install --dry-run python@3.15` were run to check a request for
  Python 3.15. The first of them refreshed Homebrew's downloaded formula list, in its cache. The drills made no
  change to Homebrew.
