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

**Receipts.** The stale ones are kept as history, with their hashes untouched; the W5- receipts replace
them. M6B stops on M6B-02.A1's 6.12 half at 7816159; every other criterion passes.
