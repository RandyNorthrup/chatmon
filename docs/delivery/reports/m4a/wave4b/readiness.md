# M4A readiness, round two at bf9d8ac (wave 4, 2026-11-15)

Round one's review is [../wave4/readiness.md](../wave4/readiness.md) (readiness-review-4 and the M4A worker's readers/readiness.md). Its receipt went stale because the rules
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

M4A-01 to M4A-12 map both ways to their criteria. M4A-12, a running Linux screen reader detected with at-spi2-core
2.62 as before it, was added by the M4A worker, with AC-12a to AC-12e. T-04 and T-09 were implemented and waiting
only on CI's macOS legs. CI-macos and CI-linux name exact tests, and CI run 43701523023 ran them on the merged tree.

Round one's CI-windows-comtypes follow-up is done: comtypes is in the test lock, so CI's Windows legs run the UI
Automation client test (AC-09a). Hearing a real screen reader speak is still outside these criteria, which stop at the
accessibility API. The WSL runs drive the real Orca, but only as an AT-SPI client.

Result: ready. No requirement is unclear, conflicting or missing failure behavior. Evidence for bf9d8ac only: another
worker (wave4/crash) may change code for an intermittent Qt crash.
