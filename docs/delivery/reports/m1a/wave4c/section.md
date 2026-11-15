## Reconciliation, wave 4, round three (2026-11-15)

Round three re-bound this plan at **3586a0d**: `improve/assessment-fixes` with wave4/crash and round two merged.
wave4/crash frees quit test Companions between tests (CI's fedora:44 crash) and makes sure nothing a quit Chatmon
had waiting runs: its one-off waits, its timers, its threads' answers. It changed `chatmon/app.py`, `chatmon/brains.py`, `tests/app_harness.py` and `tests/test_app_smoke.py`.

**Why every receipt was renewed.** None of round two's receipts bound those files. But ROADMAP.md is a rule of
every plan, and round three amends it (the Outcome at 3586a0d), so every receipt went stale with it. Every
check was run again on 3586a0d or read from its CI run.

**What was re-run.** The whole suite on Windows ([wave4c/suite-windows.log](reports/wave4c/suite-windows.log):
1259 passed, 178 skipped), then 17 Windows drills and 8 Linux ones (in WSL). Every one went green, red and green again. CI run 43729628408 (PR #18 at 3586a0d, all 19 jobs green, its test merge `5545f5a` with 3586a0d's own tree:
[reports/wave4c/ci/merge-tree.txt](reports/wave4c/ci/merge-tree.txt)) was read for its Linux and macOS legs, with PR #18's Packages run 43729628343 on 3586a0d (the containers' and macOS's root-side checks)
([reports/m1a/ci/observed-3586a0d.txt](reports/m1a/ci/observed-3586a0d.txt)). The requirements were reviewed
again ([wave4c/readiness.md](reports/m1a/wave4c/readiness.md)).

AC-10's docstrings were read again ([wave4c/review-ac10.md](reports/m1a/wave4c/review-ac10.md)), and they hold.

**What remains.** AC-01-MACOS's red drill still needs macOS, as in round two. It is recorded again as
W4C-RED-AC-01-MACOS, which says how to run it. Owner: Randy on a Mac, or the coordinator with a throwaway drill
branch on CI.

**Receipts.** Round two's W4B- receipts are now stale history, with their hashes untouched. The W4C- receipts replace
them.
