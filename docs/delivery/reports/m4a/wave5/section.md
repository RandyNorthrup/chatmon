## Reconciliation, the plans round for v0.10.0 (2026-11-15)

This round re-bound the plan at **7816159**, v0.10.0's commit: `main` with PR #22 merged (the KDE and Hyprland
overlay fixes, the screen-reader fixes and the Dependabot replacement). 56 of its 63 passing receipts went stale, on `chatmon/a11y.py`, `chatmon/macnative.py`, `tests/test_macnative.py`, `tests/test_platform_events.py`, `tests/test_presence.py` ([reports/wave5/stale-at-7816159.md](reports/wave5/stale-at-7816159.md)). Writing this section into the
plan changes its prose, which every receipt's scope includes, so the others went stale with it: every check
was run again on 7816159 or read from main's CI run of it.

**What was re-run.** The whole suite on Windows ([wave5/suite-windows.log](reports/wave5/suite-windows.log): 1293 passed, 225 skipped),
then 40 Windows drills and 15 Linux ones (in WSL). Every one went green, red and green again. main's CI run 43778643147 on 7816159 (all 19 jobs green; each
checked out 7816159 itself: [reports/wave5/ci/checkout.txt](reports/wave5/ci/checkout.txt)) was read again
([reports/m4a/ci/observed-7816159.txt](reports/m4a/ci/observed-7816159.txt)). The requirements were
reviewed again ([wave5/readiness.md](reports/m4a/wave5/readiness.md)).

**Linux and the real readers.** M4A's tests in WSL with PyQt6 6.12.1
([wave5/suite-linux-qt612.log](reports/m4a/wave5/suite-linux-qt612.log): 80 passed, 27 skipped) and the real sway's screen-reader
tests with Orca ([reports/wave5/sway-readers.log](reports/wave5/sway-readers.log): 7 passed, 13 deselected) passed again. CI's macOS,
Linux, Windows and GNOME legs were read again. The release round heard the real readers too, which no criterion
asks: VoiceOver with the fixes on GitHub's macOS runner, NVDA, and Narrator on testpc2, heard by the owner
([reports/release/screen-readers/](reports/release/screen-readers/README.md)).

**One drill run again.** In the batch, AC-03-sleep-wake's green run crashed after its test had passed: a
Windows access violation in pytest's own summary hook (hypothesis's plugin asking `platform.system()`, which
runs `ver` in a subprocess), exit 0xC0000005, with the WSL suite running beside it. That is the test run's host
process, not Chatmon. Run again on its own, the drill went green, red and green
([wave5/w4-drills-rerun.log](reports/m4a/wave5/w4-drills-rerun.log)); the batch's log keeps the crash
([wave5/w4-drills.log](reports/m4a/wave5/w4-drills.log)).

**Receipts.** The stale ones are kept as history, with their hashes untouched; the W5- receipts replace
them. M4A is closed on 7816159.
