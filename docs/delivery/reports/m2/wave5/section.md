## Reconciliation, the plans round for v0.10.0 (2026-11-15)

This round re-bound the plan at **7816159**, v0.10.0's commit: `main` with PR #22 merged (the KDE and Hyprland
overlay fixes, the screen-reader fixes and the Dependabot replacement). 52 of its 53 passing receipts went stale, on `chatmon/bubble.py`, `tests/test_ask_box.py` ([reports/wave5/stale-at-7816159.md](reports/wave5/stale-at-7816159.md)). Writing this section into the
plan changes its prose, which every receipt's scope includes, so the others went stale with it: every check
was run again on 7816159 or read from main's CI run of it.

**What was re-run.** The whole suite on Windows ([wave5/suite-windows.log](reports/wave5/suite-windows.log): 1293 passed, 225 skipped),
then 49 Windows drills. Every one went green, red and green again. main's CI run 43778643147 on 7816159 (all 19 jobs green; each
checked out 7816159 itself: [reports/wave5/ci/checkout.txt](reports/wave5/ci/checkout.txt)) was read again
([reports/m2/ci/observed-7816159.txt](reports/m2/ci/observed-7816159.txt)). The requirements were
reviewed again ([wave5/readiness.md](reports/m2/wave5/readiness.md)).

**Receipts.** The stale ones are kept as history, with their hashes untouched; the W5- receipts replace
them. M2 is closed on 7816159.
