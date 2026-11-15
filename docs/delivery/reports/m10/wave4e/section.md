## Reconciliation, wave 4, final round (2026-11-15)

The final round re-bound this plan at **45a17b3**: `improve/assessment-fixes` with the quit guard
(`86e84e0`), the toast fix (`8c24b1c`), wave4/mac-drills and wave4/mac-owner merged. 8 of its 21 passing receipts went stale, on `chatmon/app.py` ([reports/wave4e/stale-at-45a17b3.md](reports/wave4e/stale-at-45a17b3.md)). Writing this section into the
plan changes its prose, which every receipt's scope includes, so the others went stale with it: every check
was run again on 45a17b3 or read from its CI run.

**What was re-run.** The whole suite on Windows ([wave4e/suite-windows.log](reports/wave4e/suite-windows.log)),
then 15 Windows drills. Every one went green, red and green again. CI run 43743804662 (PR #18 at 45a17b3, all 19 jobs green, its test merge `eb8a996`
with 45a17b3's own tree: [reports/wave4e/ci/merge-tree.txt](reports/wave4e/ci/merge-tree.txt)) was read again
([reports/m10/ci/observed-45a17b3.txt](reports/m10/ci/observed-45a17b3.txt)). The requirements were
reviewed again ([wave4e/readiness.md](reports/m10/wave4e/readiness.md)).

**M10-03.A1's 6.12.1 half passes again.** mypy with PyQt6 6.12.1's stubs on the tree finds no issues on linux,
win32 and darwin ([wave4e/mypy-6121.log](reports/m10/wave4e/mypy-6121.log)), and with 6.11's none either
([wave4e/mypy-611.log](reports/m10/wave4e/mypy-611.log)). All five gate drills went green, red and green again
([wave4e/gate-drills.log](reports/m10/wave4e/gate-drills.log)); in round three four of them couldn't start. The
how-to was reviewed and replayed in WSL again ([wave4e/howto-review.md](reports/m10/wave4e/howto-review.md)).
T3-qt612-types is verified. The locks (locked again, byte for byte the committed ones), the UI Automation test
in the CI-shaped venv and its red drill ran again too, and passed ([wave4e/locks.log](reports/m10/wave4e/locks.log),
[wave4e/uia-ci-venv.log](reports/m10/wave4e/uia-ci-venv.log)).

**What remains, outside the criteria.** From 2026-11-28, when 6.12.1 can be hash-locked, the `types` job's check
against the next stubs (P-CI-NEXT-STUBS, integration note 2): the coordinator. The upstream report on PyQt6's
stubs (note 4): the owner, with his PyQt mailing-list account.

**Receipts.** The stale ones are kept as history, with their hashes untouched; the W4E- receipts replace
them.
