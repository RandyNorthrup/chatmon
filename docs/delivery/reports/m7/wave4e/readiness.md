# M7 readiness, the final round at 45a17b3 (wave 4, 2026-11-15)

Round three's review is [../wave4c/readiness.md](../wave4c/readiness.md) (at 3586a0d). Its receipt went stale
because files the plan's criteria bind changed. This review re-reads the plan's obligations against the brief
and rules as they are now. It is a requirements review, not proof that the code works: the behavior and red
receipts are.

## Inputs read

- [ASSESSMENT.md](../../../ASSESSMENT.md), [ROADMAP.md](../../../ROADMAP.md) and `pyproject.toml`: unchanged
  since round three. The final status is in [OUTCOME.md](../../../OUTCOME.md), which no plan binds.
- The code and tests, changed since 3586a0d in four files:
- The quit guard (`86e84e0`): every system watcher's callback (the lock, sleep, power and settings watchers on
  each OS) goes through `Companion._heard`, which does nothing once the Companion has quit and holds it only
  weakly, as `_later` does for its one-off waits. While Chatmon runs, each callback is called as before. The line
  round three found failing with PyQt6 6.12.1's stubs, `widget.removeEventFilter(self)`, now carries
  `# type: ignore[arg-type]` with its reason, as CONTRIBUTING.md says. `tests/test_app_smoke.py` gives its
  stand-in Companion a `_heard`, and its quit test no longer counts the guard itself as something that ran.
- The toast fix (`8c24b1c`): `tests/test_wintoast.py` waits for a hidden toast to leave Action Center, rather than
  taking `hide()`'s True for it.
- The macOS owner test (`3bcd857`): `tests/test_install_update.py` gains
  `test_mac_an_app_that_isnt_roots_is_never_run_as_root`, with the macOS fixture split so both tests share it.

## This plan

M7-CI, M7-01 to M7-13 and the five INT- requirements still map both ways to their 52 criteria. The toast
test's new wait is on its notifications-on branch; this workstation's notifications are off, so here it takes
the other branch, as before (CI's Windows runners take the notifications-on one). Two drills' lines moved
with the quit guard: M4A-desk-changes-unheard and M4A-mac-sleep-unheard took out a `connect` line that now
passes its method through `_heard`. W4-M7-desk-changes-unheard-v2 and W4-M7-mac-sleep-unheard-v2 take out
the new lines, for the same tests.

Result: ready. No requirement is unclear, conflicting or missing failure behavior.
