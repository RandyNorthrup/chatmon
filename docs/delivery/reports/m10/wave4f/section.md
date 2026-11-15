## Reconciliation, wave 4, final round (2026-11-15)

The final round re-bound this plan at **45a17b3**: `improve/assessment-fixes` with the quit guard
(`86e84e0`), the toast fix (`8c24b1c`), wave4/mac-drills and wave4/mac-owner merged. 8 of its 21 passing receipts went stale, on `chatmon/app.py` ([reports/wave4e/stale-at-45a17b3.md](reports/wave4e/stale-at-45a17b3.md)). Writing this section into the
plan changes its prose, which every receipt's scope includes, so the others went stale with it: every check
was run again on 45a17b3 or read from its CI run.

**What was re-run.** The whole suite on Windows ([wave4f/suite-windows.log](reports/wave4f/suite-windows.log)),
then 15 Windows drills. Every one went green, red and green again. CI run 43743804662 (PR #18 at 45a17b3, all 19 jobs green, its test merge `eb8a996`
with 45a17b3's own tree: [reports/wave4e/ci/merge-tree.txt](reports/wave4e/ci/merge-tree.txt)) was read again
([reports/m10/ci/observed-45a17b3.txt](reports/m10/ci/observed-45a17b3.txt)). The requirements were
reviewed again ([wave4f/readiness.md](reports/m10/wave4f/readiness.md)).

**M10-03.A1's 6.12.1 half passes again.** mypy with PyQt6 6.12.1's stubs on the tree finds no issues on linux,
win32 and darwin ([wave4f/mypy-6121.log](reports/m10/wave4f/mypy-6121.log)), and with 6.11's none either
([wave4f/mypy-611.log](reports/m10/wave4f/mypy-611.log)). All five gate drills went green, red and green again
([wave4f/gate-drills.log](reports/m10/wave4f/gate-drills.log)); in round three four of them couldn't start. The
how-to was reviewed and replayed in WSL again ([wave4f/howto-review.md](reports/m10/wave4f/howto-review.md)).
T3-qt612-types is verified. The locks (locked again, byte for byte the committed ones), the UI Automation test
in the CI-shaped venv and its red drill ran again too, and passed ([wave4f/locks.log](reports/m10/wave4f/locks.log),
[wave4f/uia-ci-venv.log](reports/m10/wave4f/uia-ci-venv.log)).

**What remains, outside the criteria.** From 2026-11-28, when 6.12.1 can be hash-locked, the `types` job's check
against the next stubs (P-CI-NEXT-STUBS, integration note 2): the coordinator. The upstream report on PyQt6's
stubs (note 4): the owner, with the owner's PyQt mailing-list account.

**Bound twice in this round.** This plan binds M6A's plan, which gained its final-round section after this plan's
first binding (W4E-). A plan's prose is in every receipt's scope, so that staled every W4E- receipt here. Every
check was run again on 45a17b3 ([wave4f/](reports/m10/wave4f/), with the suite in
[reports/wave4f/suite-windows.log](reports/wave4f/suite-windows.log): 1259 passed, 179 skipped), and bound as W4F-, with the same
results. The W4E- receipts are kept as stale history.

**Receipts.** The stale ones are kept as history, with their hashes untouched; the W4F- receipts replace
them.
