# M3 readiness, round three at 3586a0d (wave 4, 2026-11-15)

Round two's review is [../wave4b/readiness.md](../wave4b/readiness.md) (at bf9d8ac). Its receipt went stale
because ROADMAP.md (a rule) is amended for round three, and wave4/crash changed files. This review re-reads the
plan's obligations against the brief and rules as they are now. It is a requirements review, not proof that the
code works: the behavior and red receipts are.

## Inputs read

- [ASSESSMENT.md](../../../ASSESSMENT.md): unchanged since round one.
- [ROADMAP.md](../../../ROADMAP.md), amended in round three: the Outcome now reads 3586a0d, and the evidence rules
  say how round three binds. No owner decision changed, and `main` still requires the same 19 checks
  ([reports/wave4c/github-settings.txt](../../wave4c/github-settings.txt)).
- `pyproject.toml`: unchanged since bf9d8ac.
- The code: only wave4/crash's merge changed it, in `chatmon/app.py`, `chatmon/brains.py`, `tests/app_harness.py` and `tests/test_app_smoke.py`, and one
  changelog line. A quit Companion runs nothing it had waiting. Its one-off waits go through `Companion._later`,
  which holds it weakly and checks it hasn't quit. Its timers are stopped and silenced. `Background` and
  `brains.Finder` hand nothing back once stopped, and the agents aren't looked at once it has quit. The tests free
  each quit Companion between tests. Nothing changes while Chatmon runs.

## This plan

M3-01 to M3-15, M3-M2 and M3-RC (scope revision 3) map both ways to their 28 criteria, as in round two. No task
of this plan owns a file the crash fix changed. Round two's receipts bound `chatmon/app.py` and
`tests/app_harness.py` through the plan's inputs, so they had to be renewed. M3-RC's CI half is again the `sway`
job, still one of `main`'s 19 required checks ([reports/wave4c/github-settings.txt](../../wave4c/github-settings.txt)).
M3-14's real-Orca half is again proven in WSL, because CI has no Orca.

Result: ready. No requirement is unclear, conflicting or missing failure behavior.
