# M10 readiness, the final round at 45a17b3 (wave 4, 2026-11-15) (after M6A's section)

This round's first review is [../wave4e/readiness.md](../wave4e/readiness.md), and round three's
[../wave4c/readiness.md](../wave4c/readiness.md) (at 3586a0d). The first went stale when M6A's plan, an
input of this one, gained its final-round section. This review re-reads the plan's obligations against the brief
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

M10-01 to M10-03 still map both ways to their seven criteria. T3-qt612-types owns `chatmon/app.py`, where the
line round three found failing now carries the plan's own workaround. Integration note 2's CI check is the
coordinator's from 2026-11-28 (P-CI-NEXT-STUBS) and note 4's upstream report the owner's: neither is a
criterion. The M6B plan this plan takes as an input is re-bound in this round before M10.

Result: ready. No requirement is unclear, conflicting or missing failure behavior.
