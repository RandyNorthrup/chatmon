## Reconciliation, wave 4, round two (2026-11-15)

Round two re-bound this plan at **bf9d8ac**: `improve/assessment-fixes` after the wayland, followups, a11y and
sway-ci merges, and round one's own. Its earlier receipts went stale, because `pyproject.toml` (a rule) and files they
were bound to changed. The evidence is for bf9d8ac only. wave4/crash, not merged yet, fixes an intermittent Qt crash
in `chatmon/app.py`, `chatmon/brains.py`, `tests/app_harness.py` and `tests/test_app_smoke.py`. The checkpoint's next
action names the receipts that bind those files, and only those need a refresh when it merges.

**What was re-run.** The whole suite on Windows ([wave4b/suite-windows.log](reports/wave4b/suite-windows.log): 1256 passed, 178 skipped), then 75 Windows drills. Every one went green, red and green again. CI run 43701523023 (PR #18 at bf9d8ac, all 19
jobs green) was read for its Windows, Linux and macOS legs ([reports/m7/ci/observed-bf9d8ac.txt](reports/m7/ci/observed-bf9d8ac.txt)). The
requirements were reviewed again ([wave4b/readiness.md](reports/m7/wave4b/readiness.md)).

**WAYLAND-HOSTING is answered on a real compositor.** On sway 1.12 with the real Orca 51.1 (WSL,
[reports/m3/wave4b/sway-tests-linux.log](reports/m3/wave4b/sway-tests-linux.log): 52 passed, none skipped), the ask box is a window of its own that sway
floats, centres and focuses. Orca announces it and echoes what's typed. The penguin's menu works and gives the
keyboard back, and the box drawn on the overlay is neither announced nor echoed. The same tests, without Orca, passed
in CI's `sway` job on Ubuntu's sway 1.9. The wayland worker's runs are in [m3-stage-overlay.md](m3-stage-overlay.md).

**Hyprland and KDE themselves were not tested.** sway is the only real compositor here and in CI. A person with
either desktop can still try it before release, and that isn't a criterion.

**Receipts.** Round one's W4- receipts are now stale history, with their hashes untouched. The W4B- receipts replace
them. M7 is closed on bf9d8ac.
