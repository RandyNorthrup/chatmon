## Reconciliation, wave 4, round two (2026-11-15)

Round two re-bound this plan at **bf9d8ac**: `improve/assessment-fixes` after the wayland, followups, a11y and
sway-ci merges, and round one's own. Its earlier receipts went stale, because `pyproject.toml` (a rule) and files they
were bound to changed. The evidence is for bf9d8ac only. wave4/crash, not merged yet, fixes an intermittent Qt crash
in `chatmon/app.py`, `chatmon/brains.py`, `tests/app_harness.py` and `tests/test_app_smoke.py`. The checkpoint's next
action names the receipts that bind those files, and only those need a refresh when it merges.

**What was re-run.** The whole suite on Windows ([wave4b/suite-windows.log](reports/wave4b/suite-windows.log): 1256 passed, 178 skipped), then 17 Windows drills and 8 Linux ones (in WSL). Every one went green, red and green again. CI run 43701523023 (PR #18 at bf9d8ac, all 19
jobs green) was read for its Linux and macOS legs, with PR #18's Packages run 43701523037 on bf9d8ac (the containers' and macOS's root-side checks) ([reports/m1a/ci/observed-bf9d8ac.txt](reports/m1a/ci/observed-bf9d8ac.txt)). The
requirements were reviewed again ([wave4b/readiness.md](reports/m1a/wave4b/readiness.md)).

AC-10's docstrings were read again ([wave4b/review-ac10.md](reports/m1a/wave4b/review-ac10.md)), and they hold.

**What remains.** AC-01-MACOS's red drill still needs macOS. It is recorded again as W4B-RED-AC-01-MACOS, which says
how to run it. Owner: Randy on a Mac, or the coordinator with a throwaway drill branch on CI.

**Receipts.** Round one's W4- receipts are now stale history, with their hashes untouched. The W4B- receipts replace
them.
