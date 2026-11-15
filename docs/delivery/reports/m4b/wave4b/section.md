## Reconciliation, wave 4, round two (2026-11-15)

Round two re-bound this plan at **bf9d8ac**: `improve/assessment-fixes` after the wayland, followups, a11y and
sway-ci merges, and round one's own. Its earlier receipts went stale, because `pyproject.toml` (a rule) and files they
were bound to changed. The evidence is for bf9d8ac only. wave4/crash, not merged yet, fixes an intermittent Qt crash
in `chatmon/app.py`, `chatmon/brains.py`, `tests/app_harness.py` and `tests/test_app_smoke.py`. The checkpoint's next
action names the receipts that bind those files, and only those need a refresh when it merges.

**What was re-run.** The whole suite on Windows ([wave4b/suite-windows.log](reports/wave4b/suite-windows.log): 1256 passed, 178 skipped), then 36 Windows drills and 7 Linux ones (in WSL). Every one went green, red and green again. CI run 43701523023 (PR #18 at bf9d8ac, all 19
jobs green) was read for its Linux, macOS and Windows legs ([reports/m4b/ci/observed-bf9d8ac.txt](reports/m4b/ci/observed-bf9d8ac.txt)). The
requirements were reviewed again ([wave4b/readiness.md](reports/m4b/wave4b/readiness.md)).

**What remains.** The same four red drills need somewhere to run, each recorded as a deferred receipt that says how:

- AC-00C, AC-01D and AC-02F need macOS. Owner: Randy on a Mac, or the coordinator through CI.
- AC-03E needs a Windows desktop with notifications on. Owner: Randy (notifications on for one run, or a test PC's
  signed-in desktop), or the coordinator through CI.

**Receipts.** Round one's W4- receipts are now stale history, with their hashes untouched. The W4B- receipts replace
them.
