# M6B readiness, reviewed again at fb19cb9 (wave 4, 2026-11-14)

The earlier review is [readiness.md](../readiness.md), through phase B. Its receipt went stale because the rules and
inputs it was bound to changed. This review re-reads M6B's obligations against the brief and rules as they are now. It is
a requirements review, not proof that the code works.

## Inputs read

- [ASSESSMENT.md](../../../ASSESSMENT.md): the M6B items. Unchanged.
- [ROADMAP.md](../../../ROADMAP.md) as amended in wave 4: the canonical-bytes rule, the rule for evidence from elsewhere,
  the owner decisions of 2026-11-14 and the Outcome. Two decisions touch M6B's ground. `main` now requires the lint and
  types jobs that run M6B's ruff and mypy settings. Push protection now backs M6B-03's key blanking. Neither changes an
  M6B obligation.
- `pyproject.toml` at fb19cb9, which is as M6B left it: the eleven ruff families, mypy with no overrides, every warning
  an error.
- The two plans M6B takes as inputs, [m6a-ci-tooling.md](../../../m6a-ci-tooling.md) and
  [m8-translation.md](../../../m8-translation.md). Both were re-bound in this wave before M6B, so M6B's receipts are
  taken against their final bytes.

## Requirements and criteria

M6B-01 to M6B-03, M6B-RW and M6B-LEFT map both ways to their 17 criteria, each with an owning task and an observable
result.

## Since the last review

- Integration note 1 asked for the feature branch's CI run on Linux under xvfb, in the distribution containers and on
  macOS. CI run 43677128712 is that run, and every job is green.
- `ruff check .` and `mypy --platform` for linux, win32 and darwin are CI's lint and types jobs, which `main` now
  requires.

## Findings

- The followups worker is changing the mypy settings in `pyproject.toml` right now. Its merge makes these receipts
  stale, so the gate drills and the types jobs need running again then.

Result: ready. No requirement is unclear, conflicting or missing failure behavior.
