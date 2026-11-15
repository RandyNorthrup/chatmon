## Reconciliation, wave 4, round three (2026-11-15)

Round three re-bound this plan at **3586a0d**: `improve/assessment-fixes` with wave4/crash and round two merged.
wave4/crash frees quit test Companions between tests (CI's fedora:44 crash) and makes sure nothing a quit Chatmon
had waiting runs: its one-off waits, its timers, its threads' answers. It changed `chatmon/app.py`, `chatmon/brains.py`, `tests/app_harness.py` and `tests/test_app_smoke.py`.

**Why every receipt was renewed.** None of round two's receipts bound those files. But ROADMAP.md is a rule of
every plan, and round three amends it (the Outcome at 3586a0d), so every receipt went stale with it. Every
check was run again on 3586a0d or read from its CI run.

**What was re-run.** The whole suite on Windows ([wave4c/suite-windows.log](reports/wave4c/suite-windows.log):
1259 passed, 178 skipped), then 16 Windows drills and one Linux drill (in WSL). Every one went green, red and green again. CI run 43729628408 (PR #18 at 3586a0d, all 19 jobs green, its test merge `5545f5a` with 3586a0d's own tree:
[reports/wave4c/ci/merge-tree.txt](reports/wave4c/ci/merge-tree.txt)) was read for its lint, types, distro, coverage and test legs, with Packages run 43729628343 (the build jobs)
([reports/m6a/ci/observed-3586a0d.txt](reports/m6a/ci/observed-3586a0d.txt)). The requirements were reviewed
again ([wave4c/readiness.md](reports/m6a/wave4c/readiness.md)).

**M6A-10.A1 fails again, on one sentence** ([wave4c/docs-review.md](reports/m6a/wave4c/docs-review.md)).
CONTRIBUTING.md is unchanged since round two, but its "It also passes with the next PyQt6's stubs (6.12.1)" is
no longer true at 3586a0d. The crash fix's new `widget.removeEventFilter(self)` in `Companion._stop_for_good`
(`chatmon/app.py:3173`) fails mypy with 6.12.1's stubs on linux, win32 and darwin: `Argument 1 to
"removeEventFilter" of "QObject" has incompatible type "Companion"; expected "AskBox"  [arg-type]`. That was
seen here ([reports/m10/wave4c/mypy-6121.log](reports/m10/wave4c/mypy-6121.log)) and in WSL
([wave4c/mypy-pyqt6-6.12.1-linux.log](reports/m6a/wave4c/mypy-pyqt6-6.12.1-linux.log), `-win32`, `-darwin`).
It is the stub bug CONTRIBUTING.md's third workaround covers, and the line lacks the workaround. CI is green
because it locks 6.11's stubs. The fix is product code, not this work's: T7 is blocked on it. Round three's
other runs passed: the 10 gate drills on CI's combined coverage data for 3586a0d against `fail_under = 84`,
the distro drill under podman, the reproducible wheel, the Windows Update opt-in, and Dependabot's schema.

**What remains.**

- **M6A-10.A1.** The coordinator adds `# type: ignore[arg-type]` with the reason to `chatmon/app.py:3173`.
  Then M10's `mypy_runs.py` with the 6.12.1 venv runs again, and this review with it.
- **P-RELEASE**, a pending operation as in round two: no v0.10.0 tag exists yet
  ([reports/wave4c/github-settings.txt](reports/wave4c/github-settings.txt), observed again). Owner: Randy or
  the coordinator, at the release.
- **P-DEPENDABOT**, as in round two: `.github/dependabot.yml` isn't on `main` yet. Owner: the coordinator, after
  the merge.

**Receipts.** Round two's W4B- receipts are now stale history, with their hashes untouched. The W4C- receipts replace
them.
