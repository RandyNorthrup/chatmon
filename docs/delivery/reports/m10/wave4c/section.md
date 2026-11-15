## Reconciliation, wave 4, round three (2026-11-15)

Round three re-bound this plan at **3586a0d**: `improve/assessment-fixes` with wave4/crash and round two merged.
wave4/crash frees quit test Companions between tests (CI's fedora:44 crash) and makes sure nothing a quit Chatmon
had waiting runs: its one-off waits, its timers, its threads' answers. It changed `chatmon/app.py`, `chatmon/brains.py`, `tests/app_harness.py` and `tests/test_app_smoke.py`.

**Why every receipt was renewed.** Rounds one and two didn't re-bind this plan, the followups worker's. Its
receipts were hashed on a CRLF checkout, against ROADMAP's *Canonical bytes*, and the a11y, wayland and crash
merges changed its inputs since. Round three ran every check again on an LF checkout of 3586a0d.

**What was re-run.** The whole suite on Windows ([wave4c/suite-windows.log](reports/wave4c/suite-windows.log):
1259 passed, 178 skipped), then 11 Windows drills. 4 did not go green, red and green: see below. CI run 43729628408 (PR #18 at 3586a0d, all 19 jobs green, its test merge `5545f5a` with 3586a0d's own tree:
[reports/wave4c/ci/merge-tree.txt](reports/wave4c/ci/merge-tree.txt)) was read for its Windows test legs (the UI
Automation test, with comtypes from the test lock) and its three types jobs
([reports/m10/ci/observed-3586a0d.txt](reports/m10/ci/observed-3586a0d.txt)). The requirements were reviewed
again ([wave4c/readiness.md](reports/m10/wave4c/readiness.md)).

**The crash fix's own drills.** CRASH-01 to CRASH-07 (the harness freeing a quit Companion; no look at the
agents once quit; `_later`, Background, the Finder, the timers and the event filter each doing nothing once
quit) went green, red and green again on 3586a0d here too
([reports/wave4c/crash/drills.log](reports/wave4c/crash/drills.log)). They prove wave4/crash's own
requirements, which are none of this plan's criteria, so they are cited as context, not bound as receipts.

**What failed: M10-03.A1's 6.12.1 half.** Integration note 1 is in the tree, so mypy with PyQt6 6.12.1's
stubs was run on the tree itself, not a patched copy. It found one error, the same on linux, win32 and darwin
([wave4c/mypy-6121.log](reports/m10/wave4c/mypy-6121.log)). The crash fix's new
`widget.removeEventFilter(self)` in `Companion._stop_for_good` (`chatmon/app.py:3173`) gives `Argument 1 to
"removeEventFilter" of "QObject" has incompatible type "Companion"; expected "AskBox"  [arg-type]`. 6.12.1's
stubs type the filter as `Self`, the watched object: the plan's third kind of stub bug, which the line
doesn't work around. CI is green because it locks 6.11's stubs, which pass
([wave4c/mypy-611.log](reports/m10/wave4c/mypy-611.log), and the three `types` jobs). The four gate drills on
6.12.1's stubs couldn't start, because mypy isn't green on the copy. They are recorded as failing
([wave4c/gate-drills.log](reports/m10/wave4c/gate-drills.log)). The fifth, on 6.11's, went green, red and
green. Everything else passed: the locks, the UI Automation test in the CI-shaped venv and on CI's Windows
legs, Qt's translations, the 10 pytest drills, and the how-to, replayed in WSL. The replay reports the same
error, which is what the how-to is for.

**What remains.** The coordinator adds `# type: ignore[arg-type]` with the reason to `chatmon/app.py:3173`,
as CONTRIBUTING.md says for an argument the stubs type as `Self`. It is product code, not this work's to
change. Then `mypy_runs.py` with the 6.12.1 venv and `wave4c/gate_drills.py` run again, and T3-qt612-types can
be verified. After that, from 2026-11-28, the `types` job's check against the next stubs (P-CI-NEXT-STUBS,
integration note 2) is the coordinator's too. It is not a criterion, but it would have caught this line in CI.

**Receipts.** Its earlier receipts are now stale history, with their hashes untouched. The W4C- receipts replace
them.
