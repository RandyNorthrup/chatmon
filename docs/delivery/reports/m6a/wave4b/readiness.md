# M6A readiness, round two at bf9d8ac (wave 4, 2026-11-15)

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

M6A-01 to M6A-15 and M6A-I1 still map both ways to their 24 criteria. Round one's three open items, and what
happened to them:

- **M6A-10.A1** failed its re-review on two stale CONTRIBUTING.md sentences. Both are rewritten, so the review runs
  again ([docs-review.md](docs-review.md)). It also checks the new claim that mypy passes with PyQt6 6.12.1's stubs.
- **P-RELEASE:** no v0.10.0 tag has been pushed. The tags are still v0.9.2 and earlier.
- **P-DEPENDABOT:** `.github/dependabot.yml` still isn't on `main`. Both stay pending operations with their owners.

Since round one, `ci.yml` gained the `sway` job, with its own `timeout-minutes` and sparse checkout. M6A-01.A2 holds
"every job has timeout-minutes", and the job keeps it. `dependabot.yml` gained an ignore for PyQt6 6.12.0, whose own
stubs break mypy. That changes no M6A-02.A1 obligation: the cooldown, the groups and the floor rule are as before.
`fail_under` is 84 now, and the coverage floor drill runs against it.

Result: ready. No requirement is unclear, conflicting or missing failure behavior. Evidence for bf9d8ac only: another
worker (wave4/crash) may change code for an intermittent Qt crash.
