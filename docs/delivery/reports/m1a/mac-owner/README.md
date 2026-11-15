# M1A: the owner half of `_MACOS_ROOT`'s check gets a test (2026-11-15, 3bcd857)

`_MACOS_ROOT` refuses a copy of Chatmon.app with any entry that root doesn't own (`! -user root`) or that group or
others can write (`-perm +022`). The macOS drills ([../mac/README.md](../mac/README.md)) showed that only the second
half had a test that noticed it going. The `mac` fixture takes the test user for root (`! -user root` becomes
`! -user <uid>`), so a drill on that text only broke the fixture's setup. The owner asked for the gap to be closed.

## The change (3bcd857, `tests/test_install_update.py`)

- `mac_app(tmp_path)` builds the app copy, which used to be built inside the `mac` fixture. It is the test user's,
  with modes only its owner can write (0755 and 0644). Its `install-update` takes the test user for root and runs a
  recorder for `installer`. `run_root()` runs root code as osascript hands it to sh. The `mac` fixture uses both and
  substitutes `! -user root` as before, so the other macOS tests are unchanged.
- `test_mac_an_app_that_isnt_roots_is_never_run_as_root` runs `_MACOS_ROOT` as shipped, with only the app's path
  substituted. It first checks that no entry of the app can be written by group or others, so the owner is the only
  reason left to refuse it. It then asserts exit 3 with "isn't the system's own", that nothing of the app ran, and
  that nothing was installed. It skips off macOS, and when run as root, since the app would then be root's own.

Gates on the workstation ([gates-windows.log](gates-windows.log)): `ruff check .` passes, and `mypy --platform`
passes for linux, win32 and darwin. mypy reads `chatmon/` only, as CI's does.

## Checks, on 3bcd857

| Where | What | Result | Files |
|---|---|---|---|
| the owner's MacBook Pro, over ssh | MAC-AC-01-MACOS-owner: `! -user root -o ` taken out of `_MACOS_ROOT` | green; red in the new test's body at `tests/test_install_update.py:319`: the root script exited 0 (`returncode=0, stdout='', stderr=''`), having installed; green after the restore | `drills.log`, `drills-results.json`, `drills-run.txt`, `drill-spec.json` |
| the same | MAC-AC-01-MACOS-writable: `-o -perm +022` becomes `-o -name nothing`, run again | green; red at `:300`, the same way; green | the same |
| the same, in the owner's Aqua session | the whole suite, offscreen | 1236 passed (the new test among them), 201 skipped, 1 deselected (the owner's keychain), exit 0 | `suite-offscreen.log`, `context-observed*.txt`, `hotkeys-free.txt` |
| This Windows workstation | the whole suite (`run-windows.sh`) | 1259 passed, 179 skipped (the new test skips here), exit 0 | `suite-windows.log` |
| the same | AC-01-USER-handoff (`wave4c/drill-spec.json --only`) | green, red, green | `drills-windows*.{log,json,txt}` |
| WSL (Arch), `run-wsl.sh` | M1A's 8 Linux drills | every one green, red, green | `drills-linux*`, `files.lst` |
| the same | the root-side, postinstall, backup and attachment test files | 76 passed, 11 skipped (macOS and Windows only), exit 0 | `linux-tests.log`, `wsl-progress.txt` |

On the Mac, as in the earlier sessions:

- Everything ran in `~/chatmon-drills-tmp`, which was removed afterwards, with Homebrew's Python 3.13.7. The
  unpacked tree checked as 3bcd857's own (`80fd2bd0`).
- [state-before.txt](state-before.txt) and [state-after.txt](state-after.txt) are identical: sound still muted at 0,
  Finder in front, Homebrew's 155 formulae, `python3` still 3.15.2.
- Afterwards there was no job or process of the drills, and the test hot keys were free.

## Into the plan

[mkbind.py](mkbind.py) wrote [bindings.json](bindings.json), which `wave4/bind.py` bound into
[m1a-security-updates.md](../../../m1a-security-updates.md) through `update-delivery.py`.

- Changing the test file staled the 10 of M1A's 33 receipts that bind it. Eight of them got a W4D- receipt from
  their check, run again above. The two from the Packages workflow (W4C-BEH-PKG-CONTAINERS and -PKG-MACOS) can't be
  re-run without a push, so they stay stale history. AC-01-LINUX and AC-01-MACOS have W4D-BEH-LINUX and -MACOS
  instead.
- The new receipt is W4D-RED-AC-01-MACOS-owner.
- Every task is verified. Readiness, closure and resume pass ([validate-*.txt](validate-closure.txt)), against the
  Windows profile observed for it ([context.json](context.json), [context-windows-observed.log](context-windows-observed.log)).
- The plan's narrative has no "no test covers it" note. That was in MAC-RED-AC-01-MACOS's method and in
  [../mac/README.md](../mac/README.md), which now points here. The narrative is left as it is, so the other 23
  receipts stay fresh.

M6B's plan binds `tests/test_install_update.py` too, so its receipts that do are stale as well. They were already
stale from the quit guard's changes to `chatmon/app.py` and `tests/test_app_smoke.py`.
