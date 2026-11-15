# M4B, round three (2026-11-15, a4fe9f8)

ROADMAP.md was amended for wave 4's round three (`3586a0d+wave4c`). It is a rule of every plan, so all 46 of M4B's
passing receipts went stale, whatever files a merge had changed. The toast worker had bound them at 8c24b1c, before
the amendment reached this plan. Every one of their checks ran again on **a4fe9f8**: `wave4/mac-drills` with
`improve/assessment-fixes` merged in (cbeed17, the toast merge, and 86e84e0, the quit guard). The macOS checks the
plan was still missing ran on the owner's MacBook Pro ([../mac/README.md](../mac/README.md)). M4B now passes
readiness, closure and resume validation.

| Where | What | Result | Files |
|---|---|---|---|
| here | the requirements review | ready | `readiness.md` |
| This Windows workstation (notifications off, so the toast tests decline) | the whole suite, through `run-windows.sh` | 1259 passed, 178 skipped, exit 0 | `suite-windows.log` |
| the same | all 36 Windows drills of `wave4b/drill-spec.json` | every one green, red, green | `drills.log`, `drills-results.json`, `drills-run.txt` |
| WSL (Arch), `run-wsl.sh` | the 6 drills of `wave4b/wsl-drill-spec.json` and the one of `wsl-drill-spec-new.json`, through `wave4/wsl_drills.py` | every one green, red, green | `wsl-drills*.log`, `wsl-drills*-results.json`, `wsl-drills*-run.txt`, `files.lst` |
| the same | the Linux tests CI's Linux job had shown: the imports, the X11 grab, the GlobalShortcuts portal, the Linux players | 58 passed, 7 skipped (Windows or macOS only), exit 0 | `linux-tests.log`, `wsl-progress.txt` |
| testpc2's signed-in desktop (notifications on), [testpc2/](testpc2/) | the toast probe, `tests/test_wintoast.py`, and both `hide()` mutations | below | `testpc2/*.log`, `testpc2/drills-results.json` |
| the owner's MacBook Pro | the three macOS drills and the whole suite | see [../mac/README.md](../mac/README.md) | `../mac/` |

36 Windows drills ran, but 33 are bound. D-00A-lazy-library mutates `libdbus.py`, the portal task's file, as before.
D-03B-real-no and D-03C-settled weren't among the passing receipts either, so they get none here.

**testpc2.** These are the toast worker's scripts from [../w4c/testpc2/](../w4c/testpc2/), with the same bytes,
under the same rules:

- Before starting, `C:\TESTLAB_CLAIMS` had no claim files. Technician was active on the console (session 1), and
  the PC had been up since 2026-11-12 11:59:51.
- The claim was taken at 09:24 (`claim-take.log`). W: was pinned to the Samsung spare (model, serial, size) before
  anything was written (`setup-folder.log`).
- a4fe9f8's `git archive` zip went over by scp (125,351,002 bytes, SHA-256 `a4df6c1e...0bc46f`). Its unpacked tree
  checked as a4fe9f8's own, `6fa4a57f` (`setup-build.log`).
- It ran in a scheduled task in Technician's console session, at Medium integrity (`task.log`, `run.log`).
- The probe showed a toast in Windows' history under its tag, and gone after `hide()` (`probe.log`). The plain run
  had 12 passed and 1 skipped (`plain-test.log`).
- D-03E-hide-kept went red at `tests\test_wintoast.py:118` (`assert toaster.hide(tag)`). D-03E-hide-noop went red at
  `tests\test_wintoast.py:120` ("the hidden toast is still in Action Center"). Both went green again after the restore.
- Put back afterwards (`precheck.log`, `cleanup.log`): the task, the work folder, the claim, and the 9 notification
  settings keys Windows made for the tests' throwaway app IDs. `ToastEnabled` was never changed, nothing restarted,
  and the boot time is the same.
- `cleanup.ps1` couldn't remove `C:\Users\Technician\chatmon-survey` at first, because the ssh session that ran it
  had that folder as its current directory. A second session removed it, and found no Python process left. Both
  are at the end of `cleanup.log`, along with a mis-quoted process query whose count meant nothing, run again
  correctly.

**Into the plan.** `mkbind.py` wrote `bindings.json`, which [../../wave4/bind.py](../../wave4/bind.py) bound into the
plan through `update-delivery.py`. Each stale receipt gets a W4D- receipt from its check here, covering the same
criteria and binding the same drill. The macOS receipts are new: MAC-BEH-MACOS and MAC-RED-AC-00C, -01D and -02F. The
rules' labels are now `3586a0d+wave4c` and `3586a0d`, as in the other plans. Every receipt was being bound again
anyway, so the plan's narrative gains round three's section (`section.md`). `context.json` and `context-observed.log`
are the validator's context, observed here, and `validate-*.txt` its results.
