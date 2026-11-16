## Reconciliation, the plans round for v0.10.0 (2026-11-15)

This round re-bound the plan at **7816159**, v0.10.0's commit: `main` with PR #22 merged (the KDE and Hyprland
overlay fixes, the screen-reader fixes and the Dependabot replacement). 80 of its 81 passing receipts went stale, on `chatmon/bubble.py`, `chatmon/cli.py`, `chatmon/penguin.py`, `tests/test_cli.py` ([reports/wave5/stale-at-7816159.md](reports/wave5/stale-at-7816159.md)). Writing this section into the
plan changes its prose, which every receipt's scope includes, so the others went stale with it: every check
was run again on 7816159 or read from main's CI run of it.

**What was re-run.** The whole suite on Windows ([wave5/suite-windows.log](reports/wave5/suite-windows.log): 1293 passed, 225 skipped),
then 75 Windows drills. Every one went green, red and green again. main's CI run 43778643147 on 7816159 (all 19 jobs green; each
checked out 7816159 itself: [reports/wave5/ci/checkout.txt](reports/wave5/ci/checkout.txt)) was read again
([reports/m7/ci/observed-7816159.txt](reports/m7/ci/observed-7816159.txt)). The requirements were
reviewed again ([wave5/readiness.md](reports/m7/wave5/readiness.md)).

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

56caddd changed `tests/test_app_smoke.py`, which M7's tasks bind, so its receipts went stale ([reports/wave5b/stale-at-56caddd.md](reports/wave5b/stale-at-56caddd.md)),
and this paragraph changes the plan's prose, which every receipt's scope includes. Every check ran again on
56caddd: the whole suite on Windows ([reports/wave5b/suite-windows.log](reports/wave5b/suite-windows.log): 1293 passed, 225 skipped), then 75 Windows drills, every one green, red and green again. PR #24's CI run
43794815103 on 56caddd (all 19 jobs green; its test merge has 56caddd's own tree:
[reports/wave5b/ci/merge-tree.txt](reports/wave5b/ci/merge-tree.txt)) was read again
([reports/m7/ci/observed-56caddd.txt](reports/m7/ci/observed-56caddd.txt)), and the requirements were
reviewed again ([wave5b/readiness.md](reports/m7/wave5b/readiness.md)).

**Receipts.** The stale ones are kept as history, with their hashes untouched, and so are the failed ones;
the W5B- receipts replace them. M7 is closed on 56caddd.
