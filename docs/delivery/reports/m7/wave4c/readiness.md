# M7 readiness, round three at 3586a0d (wave 4, 2026-11-15)

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

M7-CI, M7-01 to M7-13 and the five INT- requirements still map both ways to their 52 criteria. Twenty-two tasks
own `chatmon/app.py`, `tests/app_harness.py` or `tests/test_app_smoke.py`. One drill's text moved with the fix:
M7-11-palette-ignored took out `QTimer.singleShot(0, self._palette_changed)`, which is now
`self._later(0, self._palette_changed)` (and the `not self._quitting` test moved into `_later`). Round three's
W4-M7-11-palette-ignored-v2 makes the same change on the new line, for the same test. WAYLAND-HOSTING stands as
in round two: sway with the real Orca in WSL, sway in CI; Hyprland and KDE themselves not tried.

Result: ready. No requirement is unclear, conflicting or missing failure behavior.
