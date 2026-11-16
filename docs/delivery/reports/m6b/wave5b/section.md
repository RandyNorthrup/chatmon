## Reconciliation, the plans round for v0.10.0 (2026-11-15)

This round re-bound the plan at **7816159**, v0.10.0's commit: `main` with PR #22 merged (the KDE and Hyprland
overlay fixes, the screen-reader fixes and the Dependabot replacement). 50 of its 56 passing receipts went stale, on `chatmon/a11y.py`, `chatmon/bubble.py`, `chatmon/cli.py`, `chatmon/clickthrough.py`, `chatmon/layer.py`, `chatmon/macnative.py`, `chatmon/penguin.py`, `tests/test_clickthrough.py`, `tests/test_macnative.py`, `tests/test_overlay_stage.py`, `tests/test_platform_events.py`, `tests/test_presence.py`, `tests/test_stage_features.py`, `tests/test_wayland.py` ([reports/wave5/stale-at-7816159.md](reports/wave5/stale-at-7816159.md)). Writing this section into the
plan changes its prose, which every receipt's scope includes, so the others went stale with it: every check
was run again on 7816159 or read from main's CI run of it.

**What was re-run.** The whole suite on Windows ([wave5/suite-windows.log](reports/wave5/suite-windows.log): 1293 passed, 225 skipped),
then 30 Windows drills and 5 Linux ones (in WSL), and 16 gate drills. Every one went green, red and green again. main's CI run 43778643147 on 7816159 (all 19 jobs green; each
checked out 7816159 itself: [reports/wave5/ci/checkout.txt](reports/wave5/ci/checkout.txt)) was read again
([reports/m6b/ci/observed-7816159.txt](reports/m6b/ci/observed-7816159.txt)). The requirements were
reviewed again ([wave5/readiness.md](reports/m6b/wave5/readiness.md)).

**Archived history, again.** Binding this round's 56 receipts would have taken the plan to the validator's
4 MiB limit. So, as in the final round, the oldest stale receipts were moved out first, byte for byte: round
two's 55 `W4B-` receipts are in [reports/m6b/history/w4b-round-two.json](reports/m6b/history/README.md), by
[reports/wave5/archive_receipts.py](reports/wave5/archive_receipts.py). Nothing else in the ledger changed
with them.

**M6B-02.A1's 6.12 half fails again.** mypy 2.4.1 with PyQt6 6.12.1's stubs finds two errors on linux, win32
and darwin: `chatmon/layer.py:824: error: Need type annotation for "app"  [var-annotated]`, and `:917` the same.
It does so in WSL ([reports/m6a/wave5/mypy-pyqt6-6.12.1-linux.log](reports/m6a/wave5/mypy-pyqt6-6.12.1-linux.log),
`-win32`, `-darwin`) and here ([reports/m10/wave5/mypy-6121.log](reports/m10/wave5/mypy-6121.log)). Both lines are
`app = QGuiApplication.instance()` in PR #22's KWin and Hyprland fixes (6f7dd3f). 6.12.1's stubs type the static
`instance()` as returning `Self`, which CONTRIBUTING.md's second workaround covers, and the two lines don't
have it. CI is green because its types jobs lock 6.11's stubs. This round changes no product code, so
W5-BEH-WSL-MYPY-6121 is recorded as failing. T4-mypy is blocked, with T6-phase-b and T7-leftovers, which depend
on it and whose own receipts pass. Next: the coordinator gives `app` its type on both lines
(`app: QCoreApplication | None = QGuiApplication.instance()`); then mypy with 6.12.1's stubs runs again.

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

df3e93c changed `chatmon/layer.py` and 56caddd `tests/test_app_smoke.py`, which its tasks own, and it binds the M6A and M8 plans, so its receipts went stale ([reports/wave5b/stale-at-56caddd.md](reports/wave5b/stale-at-56caddd.md)),
and this paragraph changes the plan's prose, which every receipt's scope includes. Every check ran again on
56caddd: the whole suite on Windows ([reports/wave5b/suite-windows.log](reports/wave5b/suite-windows.log): 1293 passed, 225 skipped), then 30 Windows drills and 5 Linux ones (in WSL), and 16 gate drills, every one green, red and green again. PR #24's CI run
43794815103 on 56caddd (all 19 jobs green; its test merge has 56caddd's own tree:
[reports/wave5b/ci/merge-tree.txt](reports/wave5b/ci/merge-tree.txt)) was read again
([reports/m6b/ci/observed-56caddd.txt](reports/m6b/ci/observed-56caddd.txt)), and the requirements were
reviewed again ([wave5b/readiness.md](reports/m6b/wave5b/readiness.md)).

**Archived history, a third time.** This binding's 56 receipts would have taken the plan past the 4 MiB limit
again, so round three's 56 `W4C-` receipts (55 stale, 1 failed) were moved out first, byte for byte, to
[reports/m6b/history/w4c-round-three.json](reports/m6b/history/README.md). Nothing else in the ledger changed
with them.

**M6B-02.A1's 6.12 half passes now.** With df3e93c, mypy 2.4.1 with PyQt6 6.12.1's stubs finds no issues on
linux, win32 and darwin, in WSL ([reports/m6a/wave5b/mypy-pyqt6-6.12.1-linux.log](reports/m6a/wave5b/mypy-pyqt6-6.12.1-linux.log),
`-win32`, `-darwin`) and here ([reports/m10/wave5b/mypy-6121.log](reports/m10/wave5b/mypy-6121.log)). T4-mypy is
verified, and with it T6-phase-b and T7-leftovers. W5-BEH-WSL-MYPY-6121, the failed run at 7816159, stays as
history.

**Receipts.** The stale ones are kept as history, with their hashes untouched, and so are the failed ones;
the W5B- receipts replace them. M6B is closed on 56caddd.
