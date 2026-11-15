# M6A readiness, reviewed again at fb19cb9 (wave 4, 2026-11-14)

The earlier review is [readiness.md](../readiness.md). Its receipts went stale because the rules they were bound to
changed. This review re-reads M6A's obligations against the brief and rules as they are now. It is a requirements
review, not proof that the workflows work.

## Inputs read

- [ASSESSMENT.md](../../../ASSESSMENT.md): M6A-01 to M6A-15 (M6A-14 is M1A's) and the integration item M6A-I1. Unchanged.
- [ROADMAP.md](../../../ROADMAP.md) as amended in wave 4: the canonical-bytes rule, the rule for evidence from elsewhere,
  the owner decisions of 2026-11-14 and the Outcome. Two decisions bear on M6A:
  - The repository's security settings are now on: secret scanning, push protection, Dependabot alerts and security
    updates (observed in [github-settings.txt](../../wave4/github-settings.txt)).
  - `main` is protected and requires the 18 CI checks. They are exactly the 18 jobs of `ci.yml` (lint, types ×3,
    test ×9, distro ×3, gnome, coverage). That backs M6A-01's bounded, pinned CI rather than changing it. Dependabot's
    security updates are separate from M6A-02's version updates, which still need `.github/dependabot.yml` on `main`.
- `pyproject.toml` at fb19cb9. Since M6A, M6B made every warning an error (ResourceWarning too) and removed mypy's
  exemption list. M6A-01.A3 (warnings are errors, strict marks) and M6A-13.A1 (mypy gated on three platforms) still
  hold, and are now stricter. Neither criterion asked for the exemptions to stay.

## Requirements and criteria

The 15 requirements map both ways to their 24 criteria: 14 behavior-and-red and 10 manual. Every manual criterion's
reason is still true, but most of them said the workflows had never run on GitHub, and now they have. CI run
43677128712 and Packages run 43675230966 turn those reviews into observations of real runs
([ci-review.md](ci-review.md)), except the tagged release and Dependabot's first run, which haven't happened.

## Findings

- **CONTRIBUTING.md is stale in two sentences** (the ResourceWarning exception, the mypy exemption list), because
  M6B changed `pyproject.toml` after M6A wrote them. M6A-10.A1's re-check fails on that
  ([docs-review.md](docs-review.md)). The fix is in a file outside `docs/delivery/`.
- **P-COVERAGE-FLOOR is answered.** The three OSes combined measure 86.2%, and the plan's own next action, raising
  `fail_under` to about two points under that, is a `pyproject.toml` change for its current owner.
- **P-RELEASE and P-DEPENDABOT are still open.** Neither can be observed before a tag is pushed and the PR reaches
  `main`.

Result: ready. No requirement is unclear or conflicting. What remains is the one documentation fix and two outcomes
that only time and a merge can bring.
