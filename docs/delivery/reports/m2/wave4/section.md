## Reconciliation, wave 4 (2026-11-14)

Wave 4 read the CI run this plan's checkpoint was waiting for, and re-ran every check whose receipt had gone stale. The
evidence is for **fb19cb9** (`improve/assessment-fixes`), bound to the repository's own bytes: LF, as git stores them
(ROADMAP.md, *Canonical bytes*). Two other workers were changing code at the same time (wayland: the overlay and
`ci.yml`; followups: packaging, the requirements and the mypy settings). Their merges will make some of these receipts
stale again.

**What CI answered.** P-M2-ci asked for the new tests on Linux and macOS. CI run 43677128712 on fb19cb9 had every job
green, and it ran all six of M2's test files on every leg with none failed or skipped: the three Ubuntu legs, the three
macOS legs, the three Windows legs and the ubuntu, debian and fedora containers on their own Qt
([reports/m2/ci/observed.txt](reports/m2/ci/observed.txt)).

**What was re-run.** The whole suite on Windows ([wave4/suite-windows.log](reports/wave4/suite-windows.log): 1241
passed, 148 skipped). Then 49 of the plan's 50 drills, every one green, red and green again. M2-11-no-rules mutated text
in `richtext.py` that a later merge replaced, and its criterion's other drills still apply
([wave4/drills-left-out.txt](reports/m2/wave4/drills-left-out.txt)). The requirements were reviewed again against the
amended rules ([wave4/readiness.md](reports/m2/wave4/readiness.md)).

**Receipts.** Every earlier passing receipt is now marked stale, as history, with its hashes untouched. The W4-
receipts replace them. Nothing remains open in M2 on fb19cb9.
