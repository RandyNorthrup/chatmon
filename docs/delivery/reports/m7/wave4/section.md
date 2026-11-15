## Reconciliation, wave 4 (2026-11-14)

Wave 4 read the CI run this plan's checkpoint was waiting for, and re-ran every check whose receipt had gone stale. The
evidence is for **fb19cb9** (`improve/assessment-fixes`), bound to the repository's own bytes: LF, as git stores them
(ROADMAP.md, *Canonical bytes*). Two other workers were changing code at the same time (wayland: the overlay and
`ci.yml`; followups: packaging, the requirements and the mypy settings). Their merges will make some of these receipts
stale again.

**What CI answered.** CI-ALL-PLATFORMS is resolved. CI run 43677128712 on fb19cb9 had every job green. Every test that
M7's drills run passed on its Windows legs, where the smoke and ask-box tests that failed before (AC-CI-1 to AC-CI-3)
now pass. It passed on its Linux legs (POSIX `events.request`, the windows with Linux's fonts) and on its macOS legs too
([reports/m7/ci/observed.txt](reports/m7/ci/observed.txt)).

**What was re-run.** The whole suite on Windows ([wave4/suite-windows.log](reports/wave4/suite-windows.log): 1241
passed, 148 skipped). Then 73 of the plan's 81 drills, every one green, red and green again. Eight mutated text in
`app.py` and `menus.py` that M8 and M6B rewrote ([wave4/drills-left-out.txt](reports/m7/wave4/drills-left-out.txt)).
Their criteria have other drills, except AC-02-1 and AC-02-3. Those got W4-M7-02-no-next-brain (the "Ask {brain}"
button) and W4-M7-02-welcome-without-brain (the line naming the brain), and both went green, red and green. The
requirements were reviewed again against the amended rules ([wave4/readiness.md](reports/m7/wave4/readiness.md)).

**What remains.** WAYLAND-HOSTING: `set_hosting(False)` with Orca on a real Wayland compositor (Hyprland or KDE), where
the ask box should be a window of its own and the penguin's menu should stay on the stage. This is a check for a
person. There is no compositor or screen reader here or in CI. It is recorded as a deferred manual receipt on AC-11-5
(W4-MAN-WAYLAND-HOSTING) and stays a pending operation. Owner: Randy, before release. AC-11-5's automated tests prove
the switch itself.

**Receipts.** Every earlier passing receipt is now marked stale, as history, with its hashes untouched. The W4-
receipts replace them.
