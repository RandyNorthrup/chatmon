## Reconciliation, the plans round for v0.10.0 (2026-11-15)

This round re-bound the plan at **7816159**, v0.10.0's commit: `main` with PR #22 merged (the KDE and Hyprland
overlay fixes, the screen-reader fixes and the Dependabot replacement). 47 of its 51 passing receipts went stale, on `chatmon/clickthrough.py`, `chatmon/layer.py`, `chatmon/penguin.py`, `tests/test_clickthrough.py`, `tests/test_overlay_stage.py`, `tests/test_stage_features.py`, `tests/test_wayland.py` ([reports/wave5/stale-at-7816159.md](reports/wave5/stale-at-7816159.md)). Writing this section into the
plan changes its prose, which every receipt's scope includes, so the others went stale with it: every check
was run again on 7816159 or read from main's CI run of it.

**What was re-run.** The whole suite on Windows ([wave5/suite-windows.log](reports/wave5/suite-windows.log): 1293 passed, 225 skipped),
then 30 Windows drills and 14 Linux ones (in WSL). All but 1 went green, red and green again; see below. main's CI run 43778643147 on 7816159 (all 19 jobs green; each
checked out 7816159 itself: [reports/wave5/ci/checkout.txt](reports/wave5/ci/checkout.txt)) was read again
([reports/m3/ci/observed-7816159.txt](reports/m3/ci/observed-7816159.txt)). The requirements were
reviewed again ([wave5/readiness.md](reports/m3/wave5/readiness.md)).

**The whole suite in WSL failed twice, on different tests, each passing alone.**

- **Beside the Windows runner's drills** ([wave5/suite-linux.log](reports/wave5/suite-linux.log)): 5 failed, 1385 passed, 127 skipped, 1 error.
  sway's click test errored at setup: the probe said nothing in 30 s, stuck in `shutil.which` over a PATH of
  `/mnt/c` folders. The hook smoke test failed, with the greeting still up when the hook's bubble came. So did
  four headless KWin and Hyprland checks of `tests/test_compositors.py`. Each of the six passed alone
  ([wave5/suite-linux-failures-rerun.log](reports/wave5/suite-linux-failures-rerun.log)).
- **Again, with nothing else running** ([wave5/suite-linux-quiet.log](reports/wave5/suite-linux-quiet.log)):
  1 failed, 1390 passed, 127 skipped. The one was `test_app_smoke.py::test_hide_menu_and_reload`: its menu had a 'Recent messages'
  entry. `tests/test_app_smoke.py` then passed five runs in five on its own
  ([wave5/smoke-wsl-5-runs.log](reports/wave5/smoke-wsl-5-runs.log)).

In main's CI run of 7816159 the two smoke tests passed on all twelve test legs and the sway click test in the
sway job; the compositor checks skip there, where KWin and Hyprland aren't installed. These are timing-sensitive
tests on WSL's `/mnt/c` tree, not M3 behaviour, and that is a finding for the coordinator. Both runs are kept as failed receipts
(W5-BEH-WSL-SUITE, W5-BEH-WSL-SUITE-LOADED); M3's criteria rest on the receipts below, the Windows suite, CI and
the drills.

**Linux, M3's own runs.** M3's own test files
([wave5/m3-tests-linux.log](reports/m3/wave5/m3-tests-linux.log): 151 passed, 6 skipped) and the real sway's tests
([wave5/sway-tests-linux.log](reports/m3/wave5/sway-tests-linux.log): 57 passed) passed again, as did the overlay's memory
check ([wave5/memory-after--window.json](reports/m3/wave5/memory-after--window.json)) and CI's sway job.

**One drill re-aimed, twice.** The KWin clipboard fix put a second `board.setText(text)` in `chatmon/layer.py`,
so M3-RC-clipboard's text occurs twice ([wave5/drills-left-out.txt](reports/m3/wave5/drills-left-out.txt)).
M3-RC-clipboard-v2 took out the line in `copy()` only. The pretend compositor's clipboard test went red, but the
real sway's stayed green, since the fix puts the copy on Qt's clipboard a second way, once one of Qt's windows
has the keyboard. So -v2 isn't bound ([wave5/drills-wayland-linux.log](reports/m3/wave5/drills-wayland-linux.log)).
M3-RC-clipboard-v3 takes out both lines, the whole of "Qt's clipboard is set too", and both tests fail
([wave5/drills-wayland-linux-v3.log](reports/m3/wave5/drills-wayland-linux-v3.log)), so AC-M3-RC-sway keeps its
red receipt.

**Receipts.** The stale ones are kept as history, with their hashes untouched; the W5- receipts replace
them. M3 is closed on 7816159.
