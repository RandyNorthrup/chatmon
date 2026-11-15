# M4B after the toast test's change (2026-11-15, 8c24b1c)

The testpc2 drill ([../testpc2/README.md](../testpc2/README.md)) found that
`test_a_toast_is_shown_or_the_caller_is_told_to_use_the_balloon` took `hide()`'s word for it: a `hide()` that answered
True without hiding passed. The coordinator asked for the fix. Commit **8c24b1c** makes the test also wait, with Qt's
event loop running, for the toast's tag to leave `in_action_center()`. Every receipt that binds
`tests/test_wintoast.py` went stale. That is every toast receipt, plus the imports criteria's (AC-00A/B/C), whose tasks
depend on the toast task. The checks were run again on 8c24b1c, as below, under the plan's profile (ROADMAP: evidence
from elsewhere).

| Where | What | Result | Files |
|---|---|---|---|
| This Windows workstation (notifications off, so the toast tests decline) | the whole suite | 1259 passed, 178 skipped, exit 0 | `suite-windows.log` |
| the same | the 10 Windows drills whose receipts bound the test (`wave4b/drill-spec.json --only ...`) | all green, red, green | `drills.log`, `drills-results.json`, `drills-run.txt` |
| WSL (Arch), `run-wsl.sh` | L-00B-eager-objc through `wave4/wsl_drills.py` | green, red, green | `wsl-drills.log`, `wsl-drills-results.json`, `wsl-drills-run.txt`, `wsl-drill-spec.json`, `files.lst` |
| the same | the Linux tests CI's Linux job had shown: imports, X11 grab, GlobalShortcuts portal, Linux players | 58 passed, 7 skipped (Windows or macOS only), exit 0 | `linux-tests.log`, `wsl-progress.txt` |
| testpc2's signed-in desktop (notifications on), [testpc2/](testpc2/) | the toast probe, the plain run, and both `hide()` mutations | below | `testpc2/*.log`, `testpc2/drills-results.json` |

**testpc2, round two.** Same rules and scripts as round one. The claim was read and taken at 09:08 (no other claim
files). W: was pinned to the Samsung spare (model, serial, size) before writing. 8c24b1c's tree (`73fd28a5...`) was
checked after unpacking. It ran in a scheduled task in Technician's console session (session 1, Medium integrity).
`setup.ps1` now takes the zip and tree as parameters; `run.ps1` runs one drill spec.

- The probe showed a toast in Windows' history under its tag, and gone after `hide()`. The plain run had 12 passed and
  1 skipped.
- D-03E-hide-kept (`hide()` returns False without hiding): red at `tests\test_wintoast.py:118`,
  `assert toaster.hide(tag)`, then green after restore.
- D-03E-hide-noop (`hide()` returns True without hiding, the mutation that had survived): red at
  `tests\test_wintoast.py:120`, "AssertionError: the hidden toast is still in Action Center", then green after restore.
- Put back afterwards (`cleanup.log`): the task, the work folder and the survey folder removed, and the 9 notification
  settings keys Windows made for the tests' throwaway app IDs. `ToastEnabled` was never changed, nothing restarted,
  and the claim was released.

**WSL.** One Xvfb (`:99`, started 01:34 that day) and `/var/tmp/chatmon-wsl-drill-5yxmbk30` were there before this
run: an earlier worker's, left alone. `wsl-progress.txt`'s "left running: 1" is that Xvfb.

**Not re-run: CI's macOS job.** W4B-BEH-CI-MACOS (AC-00C, AC-01D, AC-02F) is stale now, and nothing here can run macOS.
Those three criteria were already waiting on a Mac for their red drills. The same Mac or CI run now has to run the
macOS tests again too.

`bindings.json` is what [../../wave4/bind.py](../../wave4/bind.py) bound into the plan. `context.json` and
`context-observed.log` are the validator's context, and `validate-*.txt` its results. The plan's prose is left as it
was, since every receipt's scope includes it.
