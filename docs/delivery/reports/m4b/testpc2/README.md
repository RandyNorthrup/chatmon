# AC-03E's red drill on testpc2 (2026-11-15)

M4B's last Windows drill needs a desktop where Windows shows toasts. This workstation's user has notifications off
(`ToastEnabled = 0`), so the drill ran on testpc2's signed-in desktop, which the owner approved that day ("use testpc2
for the notifications drill"). The source was **3586a0d** (`improve/assessment-fixes`). Every file the receipt binds
has the same bytes there as at bf9d8ac. Times are testpc2's (UTC-8).

## What ran where

On the workstation, in the worktree `chatmon-wt/m4b-toast` (an LF checkout, ROADMAP.md *Canonical bytes*):
`git archive --format=zip HEAD` made `chatmon-3586a0d.zip` (123,379,652 bytes, SHA-256 `448b617d...b058c`), which went
to testpc2 by scp. Each script below went the same way and ran over `ssh testpc2` as Technician (an administrator)
with `powershell -NoProfile -ExecutionPolicy Bypass -File`.

On testpc2 (TESTPC2, Windows 11 Pro build 26200, booted 2026-11-12 11:59:51 and not restarted since):

| When | Script | What it did | Output |
|---|---|---|---|
| 08:29 | `survey.ps1` | identity, claims (none), sessions (Technician on the console, session 1, active), disks, notification settings and policies | in the worker's notes; the same facts are in `setup-folder.log` |
| 08:31 | `claim.ps1 take` | `C:\TESTLAB_CLAIMS\chatmon.txt`: `console`, and `drive 0025_38B8_21B7_37C0.` (W:, a folder written, nothing erased), until 10:31 | printed by the script |
| 08:35 | `setup.ps1 folder` | W: pinned to the spare (SAMSUNG MZVL2512HCJQ-00BH1, serial `0025_38B8_21B7_37C0.`, 512110190592 bytes, not boot); made `W:\chatmon-m4b`; no Chatmon app ID registered before | `setup-folder.log` |
| 08:35 | `setup.ps1 build` | unpacked the zip; `git write-tree` gave `2d3c01b0...`, 3586a0d's own tree; venv from `C:\Python314` (3.14.10) with `packaging/requirements-test.txt --require-hashes`: PyQt6 6.11.0 (Qt 6.11.2), pytest 9.2.0, pytest-timeout 2.4.0, comtypes 1.4.17 | `setup-build.log` |
| 08:36 | `task.ps1 run` | registered `ChatmonM4BToastDrill` (Technician, interactive logon, Limited run level, no trigger), started it, waited for it | `task.log` |
| 08:36 | `run.ps1`, in the task | ran in session 1 at Medium integrity, the steps below | `run.log` |
| 08:38 | `precheck.ps1` | the task had 0 triggers (`task.log`'s "triggers 1" counts `@($null)`); 11 notification-settings keys that Windows made for the tests' throwaway app IDs; no app ID registration left; no Python running | printed by the script |
| 08:38 | `cleanup.ps1` | put everything back (below) | `cleanup.log` |

`run.ps1`'s steps, each from `W:\chatmon-m4b\src` with `QT_QPA_PLATFORM=offscreen`, as the harness and the suite run:

1. `toast_probe.py` (`probe.log`): `ToastEnabled` absent (never turned off, so on), SHQueryUserNotificationState 5
   (accepts notifications: no quiet time or Do Not Disturb), Focus off. A toast shown under a throwaway app ID was in
   Windows' history under its tag after 0.02 s. `hide()` brought Dismissed with HIDDEN_BY_CHATMON (1), and the
   history was empty after `hide()`, before `clear()`.
2. The plain run of `tests/test_wintoast.py` (`plain-test.log`): 12 passed, 1 skipped (the test for other systems).
   This was green, so the drills ran.
3. The drill: `tests/drills/run.py drill-spec.json` (`drills.log`, `drills-results.json`, `drills-stdout.log`).
4. Two more probes of the same defect: `tests/drills/run.py probe-spec.json` (`probe-drills.log`,
   `probe-drills-results.json`, `probe-drills-stdout.log`). They aren't the receipt's drill.

## Results

**D-03E-hide-kept: green, red, green.** In `chatmon/wintoast.py`, `hide()` was made to return False without asking
Windows to hide the toast, which leaves it on screen and in Action Center.

- Green: exit 0.
- Red: exit 1. The test failed at `tests\test_wintoast.py:118`, after the two assertions before it had passed (so
  Windows had the toast under its tag):

  ```
  >           assert toaster.hide(tag)
  E           AssertionError: assert False
  E            +  where False = hide('6ae747fef66747a4')
  ```

- The file was put back (SHA-256 `e5e57cfe...` before and after), and the test went green again (exit 0).

**The probes: a hide() that does nothing yet answers True.** The mutation removes only Windows' Hide call.

- **P-03E-hide-lies survives the named test** (mutated exit 0). That test checks only what `hide()` answers, and the
  fixture's `clear()` takes the toast out of the history anyway.
- **P-03E-hide-lies-heard: AC-03E's other test catches the same mutation.** It is
  `test_what_windows_says_of_a_toast_comes_back_on_the_qt_thread` (green, red, green). Only TIMED_OUT (2) came
  back, never HIDDEN_BY_CHATMON (`tests\test_wintoast.py:165`).
- So AC-03E's tests together notice a `hide()` that leaves the toast in Action Center, but the named test alone notices
  only one that says so. One more line in that test would close the gap: after `hide()`, wait for the tag to leave
  `in_action_center()`. It isn't made here, because it changes `tests/test_wintoast.py`, which every M4B toast
  receipt binds.

## What changed on testpc2, and what put it back

| Made | Removed by |
|---|---|
| `C:\TESTLAB_CLAIMS\chatmon.txt` | `cleanup.ps1` (no other claim files existed, before or after) |
| `C:\Users\Technician\chatmon-survey` (the first scripts) | `cleanup.ps1`, last |
| `W:\chatmon-m4b` (source, venv, logs, the harness's temporary copies) | `cleanup.ps1`; W: holds only System Volume Information again |
| the scheduled task `ChatmonM4BToastDrill` | `cleanup.ps1` |
| 11 keys under `HKCU\Software\Microsoft\Windows\CurrentVersion\Notifications\Settings`, which Windows made for the tests' throwaway app IDs | `cleanup.ps1`, only those absent before the run (none were present) |
| `HKCU\Software\Classes\AppUserModelId\RandyNorthrup.Chatmon.Test*` | the tests' own fixture and the probe, each as it finished |
| the toasts themselves | `hide()` and the fixture's `clear()`; the history was empty after each test |

Not changed: notifications were already on, so `ToastEnabled` stayed absent, and Do Not Disturb, Focus, the display,
the theme and sleep were not touched. Nothing restarted, logged off or slept the PC.

## Files' SHA-256, as they ran

| File | SHA-256 |
|---|---|
| `drill-spec.json` | `5ad13c1164aa57a842fa9beeef2d10d85c01011673645b7c86b7d4b945d3c627` |
| `probe-spec.json` | `8f1ad5fe26e1962ab9f288638c1e5fd27ef2f10377a9c9290c39c8ea488a65e7` |
| `setup.ps1` | `6d2e55b229db59df4593564735c443f75c1ea0635d48f19d62c1269cd69bf2ec` |
| `run.ps1` | `4c3d9260f64b5547bba371e59fd4705ace4336abdf77a73df5f044431fbb9cae` |
| `task.ps1` | `e13f4fe7efd73968a38b7ae5d3adb235b6af4f1b5019882327889f13e065ee90` |
| `toast_probe.py` | `bc2829873f23fb84ce636dd8cf75534c4e027453d32b75f11934749150e26ad0` |
| `cleanup.ps1` | `84b03d18c0bcc37910bbce0b5080057e539a4e09064ae4fdc3ee68c1dfdc2cd9` |
| `claim.ps1` | `bc7cdb61c5e381494adbb2532c3fea67a1196c6726eae108505eccc56db9bf8a` |
| `survey.ps1` | `3f813c17a98ee5ca85618dd910f6f26298280c6263bdd508b5fc023532a966e4` |
| `precheck.ps1` | `8ecbc2ad9cc87a16bfec5196fb720676c9ee5c2445d52a3c6011c42c845a0a4f` |

The logs are byte for byte as their tools wrote them. Those written on testpc2 by Python, pytest and PowerShell are
CRLF. The `setup-*.log`, `task.log` and `cleanup.log` files are the ssh sessions' output, captured on the workstation,
and are LF. `context.json` is the workstation's context for the validator, observed as `context-observed.log` shows.

## Into the plan

`bindings.json` is what [reports/wave4/bind.py](../../wave4/bind.py) bound into
[m4b-hotkey-sound-toasts.md](../../../m4b-hotkey-sound-toasts.md), through `update-delivery.py`. It added
TP2-RED-D-03E-hide-kept, put T-TOAST-SHOWN at verified, and wrote a new checkpoint. W4-RED-AC-03E-deferred and
W4B-RED-AC-03E-deferred stay as history. The plan's prose is left as it was: every receipt's scope digest includes
it, so a new section would have made all 45 earlier receipts stale, and many of those (CI, WSL) can't be re-run here.
The story is told here instead, and the checkpoint points here. `validate-readiness.txt`, `validate-closure.txt` and
`validate-resume.txt` are the validator's results afterwards. Readiness and resume pass. Closure fails only on the
three macOS drills (AC-00C, AC-01D, AC-02F), as expected.
