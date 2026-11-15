## Reconciliation, wave 4, final round (2026-11-15)

The final round re-bound this plan at **45a17b3**: `improve/assessment-fixes` with the quit guard
(`86e84e0`), the toast fix (`8c24b1c`), wave4/mac-drills and wave4/mac-owner merged. 36 of its 55 passing receipts went stale, on `chatmon/app.py`, `tests/test_app_smoke.py`, `tests/test_install_update.py` ([reports/wave4e/stale-at-45a17b3.md](reports/wave4e/stale-at-45a17b3.md)). Writing this section into the
plan changes its prose, which every receipt's scope includes, so the others went stale with it: every check
was run again on 45a17b3 or read from its CI run.

**What was re-run.** The whole suite on Windows ([wave4f/suite-windows.log](reports/wave4f/suite-windows.log)),
then 46 Windows drills and 5 Linux ones (in WSL). Every one went green, red and green again. CI run 43743804662 (PR #18 at 45a17b3, all 19 jobs green, its test merge `eb8a996`
with 45a17b3's own tree: [reports/wave4e/ci/merge-tree.txt](reports/wave4e/ci/merge-tree.txt)) was read again
([reports/m6b/ci/observed-45a17b3.txt](reports/m6b/ci/observed-45a17b3.txt)). The requirements were
reviewed again ([wave4f/readiness.md](reports/m6b/wave4f/readiness.md)).

**M6B-02.A1's 6.12 half passes again.** mypy 2.4.1 with PyQt6 6.12.1's stubs finds no issues on linux, win32 and
darwin, in WSL ([reports/m6a/wave4f/mypy-pyqt6-6.12.1-linux.log](reports/m6a/wave4f/mypy-pyqt6-6.12.1-linux.log),
`-win32`, `-darwin`) and here ([reports/m10/wave4f/mypy-6121.log](reports/m10/wave4f/mypy-6121.log)). The quit
guard gave `chatmon/app.py`'s `removeEventFilter(self)` the `# type: ignore[arg-type]` with its reason. T4-mypy
is verified again, and with it T6-phase-b and T7-leftovers, which depend on it and were blocked only by it.

**Bound twice in this round.** This plan binds M6A's plan, which gained its final-round section after this plan's
first binding (W4E-). A plan's prose is in every receipt's scope, so that staled every W4E- receipt here. Every
check was run again on 45a17b3 ([wave4f/](reports/m6b/wave4f/), with the suite in
[reports/wave4f/suite-windows.log](reports/wave4f/suite-windows.log): 1259 passed, 179 skipped), and bound as W4F-, with the same
results. The W4E- receipts are kept as stale history.

**Receipts.** The stale ones are kept as history, with their hashes untouched; the W4F- receipts replace
them. M6B is closed on 45a17b3.
