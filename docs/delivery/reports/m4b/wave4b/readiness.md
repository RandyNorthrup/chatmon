# M4B readiness, round two at bf9d8ac (wave 4, 2026-11-15)

Round one's review is [../wave4/readiness.md](../wave4/readiness.md) (at fb19cb9). Its receipt went stale because the rules
and files it was bound to changed by `bf9d8ac`. This review re-reads the plan's obligations against the brief and rules
as they are now. It is a requirements review, not proof that the code works: the behavior and red receipts are.

## Inputs read

- [ASSESSMENT.md](../../../ASSESSMENT.md): unchanged since round one.
- [ROADMAP.md](../../../ROADMAP.md), amended in round two. The Outcome now reads bf9d8ac. There is one more owner
  decision row: the `sway` job is now one of `main`'s 19 required checks, observed in
  [reports/wave4b/github-settings.txt](../../wave4b/github-settings.txt). The evidence rules are unchanged: canonical
  bytes, and evidence from elsewhere.
- `pyproject.toml` at bf9d8ac. The coverage floor is `fail_under = 84` (CI's three OSes measured 86.2%, then 86.5%).
  The test extra and the dev pins gain comtypes for Windows, and ruff gives `docs/delivery/reports/wave4/**`'s scripts
  the same rule exemptions the other reports have. None of these adds, removes or loosens a criterion of this plan.

## This plan

M4B-00 to M4B-04 still map both ways to AC-00A to AC-04B. `hotkey.py`, `sound.py` and `wintoast.py` changed
by a few lines each for the stub workarounds. The owner's acceptance of the sound cues (2026-11-14) still settles the
files, not how they play.

The four criteria whose red drills need a place to run are unchanged. AC-00C, AC-01D and AC-02F need macOS. AC-03E
needs a Windows desktop with notifications on. They stay recorded as deferred, with how to run each and who can.

Result: ready. No requirement is unclear, conflicting or missing failure behavior. Evidence for bf9d8ac only: another
worker (wave4/crash) may change code for an intermittent Qt crash.
