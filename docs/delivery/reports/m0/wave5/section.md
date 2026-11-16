## Reconciliation, the plans round for v0.10.0 (2026-11-15)

This round re-bound the plan at **7816159**, v0.10.0's commit: `main` with PR #22 merged (the KDE and Hyprland
overlay fixes, the screen-reader fixes and the Dependabot replacement). 9 of its 38 passing receipts went stale, on `chatmon/cli.py`, `tests/test_cli.py` ([reports/wave5/stale-at-7816159.md](reports/wave5/stale-at-7816159.md)). Writing this section into the
plan changes its prose, which every receipt's scope includes, so the others went stale with it: every check
was run again on 7816159 or read from main's CI run of it.

**What was re-run.** The whole suite on Windows ([wave5/suite-windows.log](reports/wave5/suite-windows.log): 1293 passed, 225 skipped),
then 32 Windows drills and 2 Linux ones (in WSL). Every one went green, red and green again. main's CI run 43778643147 on 7816159 (all 19 jobs green; each
checked out 7816159 itself: [reports/wave5/ci/checkout.txt](reports/wave5/ci/checkout.txt)) was read again
([reports/m0/ci/observed-7816159.txt](reports/m0/ci/observed-7816159.txt)). The requirements were
reviewed again ([wave5/readiness.md](reports/m0/wave5/readiness.md)).

**One drill re-aimed.** `chatmon ask` keeps `_send`'s answer now (`sent = _send(...)`), so M0-12-ask-sent's
text no longer occurs ([wave5/drills-left-out.txt](reports/m0/wave5/drills-left-out.txt)). M0-12-ask-sent-v2
makes the same defect in the new line, and the same test fails, so M0-12.A1 keeps its red receipt.

**Receipts.** The stale ones are kept as history, with their hashes untouched; the W5- receipts replace
them. M0 is closed on 7816159.
