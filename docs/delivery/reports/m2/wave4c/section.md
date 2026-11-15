## Reconciliation, wave 4, round three (2026-11-15)

Round three re-bound this plan at **3586a0d**: `improve/assessment-fixes` with wave4/crash and round two merged.
wave4/crash frees quit test Companions between tests (CI's fedora:44 crash) and makes sure nothing a quit Chatmon
had waiting runs: its one-off waits, its timers, its threads' answers. It changed `chatmon/app.py`, `chatmon/brains.py`, `tests/app_harness.py` and `tests/test_app_smoke.py`.

**Why every receipt was renewed.** None of round two's receipts bound those files. But ROADMAP.md is a rule of
every plan, and round three amends it (the Outcome at 3586a0d), so every receipt went stale with it. Every
check was run again on 3586a0d or read from its CI run.

**What was re-run.** The whole suite on Windows ([wave4c/suite-windows.log](reports/wave4c/suite-windows.log):
1259 passed, 178 skipped), then 49 Windows drills. Every one went green, red and green again. CI run 43729628408 (PR #18 at 3586a0d, all 19 jobs green, its test merge `5545f5a` with 3586a0d's own tree:
[reports/wave4c/ci/merge-tree.txt](reports/wave4c/ci/merge-tree.txt)) was read for its Linux and macOS legs
([reports/m2/ci/observed-3586a0d.txt](reports/m2/ci/observed-3586a0d.txt)). The requirements were reviewed
again ([wave4c/readiness.md](reports/m2/wave4c/readiness.md)).

**Receipts.** Round two's W4B- receipts are now stale history, with their hashes untouched. The W4C- receipts replace
them. M2 is closed on 3586a0d.
