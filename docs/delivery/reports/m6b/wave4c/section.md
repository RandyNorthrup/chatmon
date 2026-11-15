## Reconciliation, wave 4, round three (2026-11-15)

Round three re-bound this plan at **3586a0d**: `improve/assessment-fixes` with wave4/crash and round two merged.
wave4/crash frees quit test Companions between tests (CI's fedora:44 crash) and makes sure nothing a quit Chatmon
had waiting runs: its one-off waits, its timers, its threads' answers. It changed `chatmon/app.py`, `chatmon/brains.py`, `tests/app_harness.py` and `tests/test_app_smoke.py`.

**Why every receipt was renewed.** Round two's checkpoint named 54 of its 55 receipts as binding those
files. ROADMAP.md is a rule of every plan, and round three amends it (the Outcome at 3586a0d), so the others
went stale with it. Every check was run again on 3586a0d or read from its CI run, not only those.

**What was re-run.** The whole suite on Windows ([wave4c/suite-windows.log](reports/wave4c/suite-windows.log):
1259 passed, 178 skipped), then 46 Windows drills and 5 Linux ones (in WSL). Every one went green, red and green again. CI run 43729628408 (PR #18 at 3586a0d, all 19 jobs green, its test merge `5545f5a` with 3586a0d's own tree:
[reports/wave4c/ci/merge-tree.txt](reports/wave4c/ci/merge-tree.txt)) was read for its lint, types and test legs
([reports/m6b/ci/observed-3586a0d.txt](reports/m6b/ci/observed-3586a0d.txt)). The requirements were reviewed
again ([wave4c/readiness.md](reports/m6b/wave4c/readiness.md)).

**The crash fix's own drills.** CRASH-01 to CRASH-07 (the harness freeing a quit Companion; no look at the
agents once quit; `_later`, Background, the Finder, the timers and the event filter each doing nothing once
quit) went green, red and green again on 3586a0d here too
([reports/wave4c/crash/drills.log](reports/wave4c/crash/drills.log)). They prove wave4/crash's own
requirements, which are none of this plan's criteria, so they are cited as context, not bound as receipts.

**M6B-02.A1's 6.12 half fails.** The crash fix's new `widget.removeEventFilter(self)` in
`Companion._stop_for_good` (`chatmon/app.py:3173`) fails mypy with PyQt6 6.12.1's stubs on linux, win32 and
darwin: `Argument 1 to "removeEventFilter" of "QObject" has incompatible type "Companion"; expected
"AskBox"  [arg-type]`. That was seen in WSL
([reports/m6a/wave4c/mypy-pyqt6-6.12.1-linux.log](reports/m6a/wave4c/mypy-pyqt6-6.12.1-linux.log), `-win32`,
`-darwin`) and here ([reports/m10/wave4c/mypy-6121.log](reports/m10/wave4c/mypy-6121.log)). 6.12.1's stubs type the
filter as `Self`, the watched object: the bug the other such lines carry `# type: ignore[arg-type]` for. CI's
`types` jobs lock 6.11's stubs and pass, and so does every gate drill. The 6.11 half and the rest of the plan
hold.

**What remains.** The coordinator adds `# type: ignore[arg-type]` with the reason to `chatmon/app.py:3173`.
Then mypy with 6.12.1's stubs runs again, and T4-mypy can be verified. T6-phase-b and T7-leftovers depend on
it, so they are blocked with it, though their own receipts pass. It is product code, not this work's to change.

**Receipts.** Round two's W4B- receipts are now stale history, with their hashes untouched. The W4C- receipts replace
them.
