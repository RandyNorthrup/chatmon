## Reconciliation, wave 4, round two (2026-11-15)

Round two re-bound this plan at **bf9d8ac**: `improve/assessment-fixes` after the wayland, followups, a11y and
sway-ci merges, and round one's own. Its earlier receipts went stale, because `pyproject.toml` (a rule) and files they
were bound to changed. The evidence is for bf9d8ac only. wave4/crash, not merged yet, fixes an intermittent Qt crash
in `chatmon/app.py`, `chatmon/brains.py`, `tests/app_harness.py` and `tests/test_app_smoke.py`. The checkpoint's next
action names the receipts that bind those files, and only those need a refresh when it merges.

**What was re-run.** The whole suite on Windows ([wave4b/suite-windows.log](reports/wave4b/suite-windows.log): 1256 passed, 178 skipped), then 40 Windows drills and 15 Linux ones (in WSL). Every one went green, red and green again. CI run 43701523023 (PR #18 at bf9d8ac, all 19
jobs green) was read for its macOS, Linux, Windows and gnome legs ([reports/m4a/ci/observed-bf9d8ac.txt](reports/m4a/ci/observed-bf9d8ac.txt)). The
requirements were reviewed again ([wave4b/readiness.md](reports/m4a/wave4b/readiness.md)).

**CI-macos is answered.** `test_sleep_wake_displays_accessibility_and_low_power_are_heard` and
`test_macos_reads_increase_contrast` passed on CI's three macOS legs on the merged tree, so T-04 and T-09 are verified.

**CI-linux is answered.** `tests/test_screen_readers.py` and `tests/test_a11y.py` each run on Ubuntu, or skip with their
reason where the runner lacks AT-SPI's launcher or GNOME's schema, and pass. The Arm and fedora legs, which have
those pieces, ran them too.

The UI Automation client test now runs in CI as well, with comtypes. The M4A worker's checks were re-run here as they
ran them: the M4A tests in WSL on PyQt6 6.12.1 ([wave4b/suite-linux-qt612.log](reports/m4a/wave4b/suite-linux-qt612.log)),
and the real-sway screen-reader tests with Orca 51.1 ([reports/wave4b/sway-readers.log](reports/wave4b/sway-readers.log)).

**Receipts.** Round one's W4- receipts are now stale history, with their hashes untouched. The W4B- receipts replace
them. M4A is closed on bf9d8ac.
