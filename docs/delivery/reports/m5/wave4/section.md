## Reconciliation, wave 4 (2026-11-14)

This plan closed with no pending operation, but every receipt had gone stale. Later merges changed the files they were
bound to (M7's wiring, M8's strings, M6B's logging). The hashes had also been taken on a CRLF checkout, and git stores
LF. Wave 4 re-ran the checks on **fb19cb9** (`improve/assessment-fixes`), bound to the repository's own bytes (ROADMAP.md,
*Canonical bytes*). Two other workers were changing code at the same time (wayland: the overlay and `ci.yml`; followups:
packaging, the requirements and the mypy settings). Their merges will make some of these receipts stale again.

**What was re-run.** The whole suite on Windows ([wave4/suite-windows.log](reports/wave4/suite-windows.log): 1241
passed, 148 skipped). Then 23 of the plan's 28 drills, every one green, red and green again. Five mutated text in
`offline.py` that M8 and M6B rewrote ([wave4/drills-left-out.txt](reports/m5/wave4/drills-left-out.txt)). Their criteria
still have drills that apply, except M5-06.A2. Its new drill, W4-M5-06-help-not-translated, mutates the line that now
picks a help section's name, and it went green, red and green. CI run 43677128712 ran the same tests on Linux and macOS,
on their own time zone data and C libraries ([reports/m5/ci/observed.txt](reports/m5/ci/observed.txt)). The
requirements were reviewed again against the amended rules ([wave4/readiness.md](reports/m5/wave4/readiness.md)).

**Receipts.** Every earlier passing receipt is now marked stale, as history, with its hashes untouched. The W4-
receipts replace them. Nothing remains open in M5 on fb19cb9.
