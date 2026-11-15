# M1A readiness, round two at bf9d8ac (wave 4, 2026-11-15)

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

M1A-01 to M1A-12 and M6A-14 still map both ways to their 17 criteria. The code changes since are small:
`updates.py` (nine lines, the mypy stub workarounds) and `packaging/build.py` (Qt's own translations in the Windows and
macOS builds). Neither touches what a criterion says.

AC-10 stays manual for its stated reason, and is re-read in [review-ac10.md](review-ac10.md). AC-01-MACOS's red drill
still needs macOS, which nothing here or in the test lab has. That is a place to run it, not a gap in the requirement.

Result: ready. No requirement is unclear, conflicting or missing failure behavior. Evidence for bf9d8ac only: another
worker (wave4/crash) may change code for an intermittent Qt crash.
