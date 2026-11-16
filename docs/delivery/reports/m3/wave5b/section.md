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

**Bound again at 56caddd.** The coordinator's two commits on this branch, after this section's first binding:

- **df3e93c** (the coordinator's): `chatmon/layer.py`'s two `app = QGuiApplication.instance()` lines are
  `app: QCoreApplication | None = QGuiApplication.instance()`, CONTRIBUTING.md's second workaround for 6.12.1's
  stubs, with no change at run time; CONTRIBUTING.md's opt-in table names `CHATMON_PINS_NETWORK=1`.
- **56caddd** (the coordinator's): `tests/test_app_smoke.py::test_hide_menu_and_reload` waits for the greeting
  before it hides the chatmon, and expects the "Recent messages" entry the greeting adds. The greeting could land
  inside the test's one-second spin when the companion was slow to start: the WSL failure of this round's first
  binding. The coordinator's drill ([reports/wave5/flaky-hide-menu/drill.py.txt](reports/wave5/flaky-hide-menu/drill.py.txt)),
  run again here, fails the old body with the start slowed by 0.6 s and passes the new one at 0, 0.6, 1.4 and 2 s
  ([reports/wave5b/flaky-hide-menu-drill-windows.log](reports/wave5b/flaky-hide-menu-drill-windows.log), and in WSL
  [reports/wave5b/flaky-hide-menu-drill-wsl.log](reports/wave5b/flaky-hide-menu-drill-wsl.log)).

df3e93c changed `chatmon/layer.py`, which M3's overlay tasks own, so its receipts went stale ([reports/wave5b/stale-at-56caddd.md](reports/wave5b/stale-at-56caddd.md)),
and this paragraph changes the plan's prose, which every receipt's scope includes. Every check ran again on
56caddd: the whole suite on Windows ([reports/wave5b/suite-windows.log](reports/wave5b/suite-windows.log): 1293 passed, 225 skipped), then 30 Windows drills and 14 Linux ones (in WSL), every one green, red and green again. PR #24's CI run
43794815103 on 56caddd (all 19 jobs green; its test merge has 56caddd's own tree:
[reports/wave5b/ci/merge-tree.txt](reports/wave5b/ci/merge-tree.txt)) was read again
([reports/m3/ci/observed-56caddd.txt](reports/m3/ci/observed-56caddd.txt)), and the requirements were
reviewed again ([wave5b/readiness.md](reports/m3/wave5b/readiness.md)).

In WSL, M3's own test files ([wave5b/m3-tests-linux.log](reports/m3/wave5b/m3-tests-linux.log): 151 passed, 6 skipped),
the real sway ([wave5b/sway-tests-linux.log](reports/m3/wave5b/sway-tests-linux.log): 57 passed) and the
memory check ([wave5b/memory-after--window.json](reports/m3/wave5b/memory-after--window.json)) ran again. The
Wayland drills ran with M3-RC-clipboard-v3 in -v2's place. **The whole suite in WSL**, retried at 56caddd on
a quiet machine, gave 1391 passed, 127 skipped ([reports/wave5b/suite-linux.log](reports/wave5b/suite-linux.log)). The two failed
runs at 7816159 stay as history.

**Receipts.** The stale ones are kept as history, with their hashes untouched, and so are the failed ones;
the W5B- receipts replace them. M3 is closed on 56caddd.
