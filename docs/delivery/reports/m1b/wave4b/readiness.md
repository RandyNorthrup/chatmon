# M1B readiness, round two at bf9d8ac (wave 4, 2026-11-15)

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

M1B-01 to M1B-17 still map one to one to AC-M1B-01 to AC-M1B-17. `brains.py` (thirteen lines) and
`keychain.py` (four) changed for PyQt6 6.12.1's stubs (`qtsignal.pyqtSignal`, typed bus connections). No criterion
depends on how a signal is declared.

Result: ready. No requirement is unclear, conflicting or missing failure behavior. Evidence for bf9d8ac only: another
worker (wave4/crash) may change code for an intermittent Qt crash.
