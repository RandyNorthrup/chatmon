## Reconciliation, wave 4 (2026-11-14)

Wave 4 read the CI run this plan's checkpoint was waiting for, and re-ran every check whose receipt had gone stale. The
evidence is for **fb19cb9** (`improve/assessment-fixes`), bound to the repository's own bytes: LF, as git stores them
(ROADMAP.md, *Canonical bytes*). Two other workers were changing code at the same time (wayland: the overlay and
`ci.yml`; followups: packaging, the requirements and the mypy settings). Their merges will make some of these receipts
stale again.

**What CI answered.** CI run 43677128712 on fb19cb9, every job green. Each leg's result for this plan's tests is in
[reports/m4a/ci/observed.txt](reports/m4a/ci/observed.txt).

- **CI-macos: resolved.** `tests/test_macnative.py::test_sleep_wake_displays_accessibility_and_low_power_are_heard` and
  `tests/test_presence.py::test_macos_reads_increase_contrast` passed on all three macOS legs. All eight
  `test_macnative.py` tests passed again on macOS's real window server. T-04 and T-09's red drills had already run on
  Windows against stand-ins for AppKit, and they ran again in this wave. Both tasks are now verified.
- **CI-linux: resolved.** The D-Bus tests (the portal, notification servers, Do Not Disturb, UPower, PackageKit) and the
  X11 placement test passed on the Ubuntu legs. In a real GNOME session (the gnome job, Mutter 46.2), GNOME's own
  contrast answer passed. One test can't run on CI's locked PyQt6 6.11, `test_qts_contrast_change_is_passed_on` (AC-04b).
  It passed in WSL on PyQt6 6.12.1 ([wave4/presence-linux-qt612.log](reports/m4a/wave4/presence-linux-qt612.log)), and
  its drill, W4-L-AC-04b-qt-signal, now mutates the `changed.connect(self.settings_changed)` line that replaced the old
  text. Runs on Linux are recorded under the plan's own profile now (ROADMAP.md, *Evidence from elsewhere*), so closure
  no longer flags them.
- **CI-windows-comtypes: outcome observed.** CI still skips the UI Automation client test, because comtypes isn't in
  `packaging/requirements-test.txt`. AC-09a asks only that a UI Automation client hears the announcement, and on this
  workstation, where comtypes 1.5.0 is installed, the test ran and passed. Adding comtypes to the test locks is listed in
  ROADMAP.md's Outcome, for the owner of the locks.

**What was re-run.** The whole suite on Windows ([wave4/suite-windows.log](reports/wave4/suite-windows.log): 1241
passed, 148 skipped). Then the plan's 30 Windows drills and 10 Linux drills (in WSL) that still apply, plus the new Qt 6.12
drill, every one green, red and green again. AC-08-not-held's text in `a11y.py` has gone, and AC-08's other drills still
apply ([wave4/drills-left-out.txt](reports/m4a/wave4/drills-left-out.txt)). The requirements were reviewed again
against the amended rules ([wave4/readiness.md](reports/m4a/wave4/readiness.md)).

**Receipts.** Every earlier passing receipt is now marked stale, as history, with its hashes untouched. The W4-
receipts replace them. Nothing remains open in M4A on fb19cb9. Hearing real VoiceOver and Narrator speak is a person's
release check, outside these criteria, and ROADMAP.md's Outcome lists it.
