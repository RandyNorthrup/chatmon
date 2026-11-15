## Reconciliation, wave 4, round three (2026-11-15)

Round three re-bound this plan at **3586a0d**: `improve/assessment-fixes` with wave4/crash and round two merged.
wave4/crash frees quit test Companions between tests (CI's fedora:44 crash) and makes sure nothing a quit Chatmon
had waiting runs: its one-off waits, its timers, its threads' answers. It changed `chatmon/app.py`, `chatmon/brains.py`, `tests/app_harness.py` and `tests/test_app_smoke.py`.

**Why every receipt was renewed.** Round two's checkpoint named 50 of its 50 receipts as binding those
files. ROADMAP.md is a rule of every plan, and round three amends it (the Outcome at 3586a0d), so the others
went stale with it. Every check was run again on 3586a0d or read from its CI run, not only those.

**What was re-run.** The whole suite on Windows ([wave4c/suite-windows.log](reports/wave4c/suite-windows.log):
1259 passed, 178 skipped), then 30 Windows drills and 14 Linux ones (in WSL). Every one went green, red and green again. CI run 43729628408 (PR #18 at 3586a0d, all 19 jobs green, its test merge `5545f5a` with 3586a0d's own tree:
[reports/wave4c/ci/merge-tree.txt](reports/wave4c/ci/merge-tree.txt)) was read for its `sway` job (49 passed; 3 skipped because CI has no Orca or wlr-protocols)
([reports/m3/ci/observed-3586a0d.txt](reports/m3/ci/observed-3586a0d.txt)). The requirements were reviewed
again ([wave4c/readiness.md](reports/m3/wave4c/readiness.md)).

**The crash fix's own drills.** CRASH-01 to CRASH-07 (the harness freeing a quit Companion; no look at the
agents once quit; `_later`, Background, the Finder, the timers and the event filter each doing nothing once
quit) went green, red and green again on 3586a0d here too
([reports/wave4c/crash/drills.log](reports/wave4c/crash/drills.log)). They prove wave4/crash's own
requirements, which are none of this plan's criteria, so they are cited as context, not bound as receipts.

**The whole suite in WSL fails one test, none of M3's** ([wave4c/suite-linux.log](reports/wave4c/suite-linux.log):
1 failed, 1315 passed, 121 skipped). It is the crash fix's own
`tests/test_app_smoke.py::test_a_quit_companion_runs_nothing_it_had_waiting`: after quit,
`Companion._power_saving` ran. `linuxsession.PowerProfile` asks the system bus for UPower's `OnBattery`, and
its answer comes back after quit, which `Companion._stop_for_good` doesn't stop. It fails five runs in five with
UPower on WSL's system bus, and passes without a system bus
([reports/wave4c/crash-test-wsl.log](reports/wave4c/crash-test-wsl.log)). CI's runners have no such bus, so CI
passes it. That is product code, the coordinator's, and is recorded as W4C-BEH-WSL-SUITE, failing. In its place,
M3's own test files ran on their own in WSL ([wave4c/m3-tests-linux.log](reports/m3/wave4c/m3-tests-linux.log):
145 passed, 4 skipped, exit 0) as W4C-BEH-WSL-M3. Those are every file any of M3's drills runs a test of, the
real-compositor and real-Orca tests among them.

**Receipts.** Round two's W4B- receipts are now stale history, with their hashes untouched. The W4C- receipts replace
them. M3 is closed on 3586a0d.
