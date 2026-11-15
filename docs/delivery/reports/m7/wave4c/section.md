## Reconciliation, wave 4, round three (2026-11-15)

Round three re-bound this plan at **3586a0d**: `improve/assessment-fixes` with wave4/crash and round two merged.
wave4/crash frees quit test Companions between tests (CI's fedora:44 crash) and makes sure nothing a quit Chatmon
had waiting runs: its one-off waits, its timers, its threads' answers. It changed `chatmon/app.py`, `chatmon/brains.py`, `tests/app_harness.py` and `tests/test_app_smoke.py`.

**Why every receipt was renewed.** Round two's checkpoint named 80 of its 81 receipts as binding those
files. ROADMAP.md is a rule of every plan, and round three amends it (the Outcome at 3586a0d), so the others
went stale with it. Every check was run again on 3586a0d or read from its CI run, not only those.

**What was re-run.** The whole suite on Windows ([wave4c/suite-windows.log](reports/wave4c/suite-windows.log):
1259 passed, 178 skipped), then 75 Windows drills. Every one went green, red and green again. CI run 43729628408 (PR #18 at 3586a0d, all 19 jobs green, its test merge `5545f5a` with 3586a0d's own tree:
[reports/wave4c/ci/merge-tree.txt](reports/wave4c/ci/merge-tree.txt)) was read for its Windows, Linux and macOS legs
([reports/m7/ci/observed-3586a0d.txt](reports/m7/ci/observed-3586a0d.txt)). The requirements were reviewed
again ([wave4c/readiness.md](reports/m7/wave4c/readiness.md)).

**The crash fix's own drills.** CRASH-01 to CRASH-07 (the harness freeing a quit Companion; no look at the
agents once quit; `_later`, Background, the Finder, the timers and the event filter each doing nothing once
quit) went green, red and green again on 3586a0d here too
([reports/wave4c/crash/drills.log](reports/wave4c/crash/drills.log)). They prove wave4/crash's own
requirements, which are none of this plan's criteria, so they are cited as context, not bound as receipts.

**One drill re-aimed.** M7-11-palette-ignored's text no longer occurs (the fix moved the palette's one-off wait
to `self._later`), so it is left out of the copy ([wave4c/drills-left-out.txt](reports/m7/wave4c/drills-left-out.txt)).
W4-M7-11-palette-ignored-v2 takes the new line out for the same test, which fails, so AC-11-2 keeps its red receipt.

**Receipts.** Round two's W4B- receipts are now stale history, with their hashes untouched. The W4C- receipts replace
them. M7 is closed on 3586a0d.
