# M8 readiness, reviewed again at fb19cb9 (wave 4, 2026-11-14)

The earlier reviews are [readiness.md](../readiness.md), [readiness-b.md](../readiness-b.md) and
[readiness-c.md](../readiness-c.md). Their receipts went stale because the rules and inputs they were bound to changed.
This review re-reads M8's obligation against the brief and rules as they are now. It is a requirements review, not proof
that the code works.

## Inputs read

- [ASSESSMENT.md](../../../ASSESSMENT.md): the translation items. Unchanged.
- [ROADMAP.md](../../../ROADMAP.md) as amended in wave 4: the canonical-bytes rule, the rule for evidence from elsewhere,
  the owner decisions of 2026-11-14 and the Outcome. The translation decision is unchanged: plumbing plus locale formats,
  every UI string translatable, per-language phrase data with English always accepted, only English shipping.
- `pyproject.toml` at fb19cb9. M6B's phase B came after M8 and changed it: the ruff families, mypy with no exemptions,
  and every warning an error. `locale/*` is still in the package data.
- The three plans M8 takes as inputs, [m0-app-core.md](../../../m0-app-core.md),
  [m5-reminders-offline-locale.md](../../../m5-reminders-offline-locale.md) and [m7-integration.md](../../../m7-integration.md).
  All three were re-bound in this wave before M8, so M8's receipts are taken against their final bytes. Their changes
  (reconciliation sections and new receipts) don't touch M8's contract with them, which is the strings they show and
  where they show them.

## Requirement and criteria

M8-01 still maps to M8-01.A1 through A10, each with an owning task and an observable result. M6B's later changes to the
same files (the log, the hub files' ruff and mypy fixes) kept every string wrapped. The template check, which is A7's
own check, still passes.

## Since the last review

- The plan's closing next action named CI's Linux and macOS legs for `tests/test_i18n.py`, `tests/test_i18n_app.py` and
  `tests/test_chatswin.py`. CI run 43677128712 ran them. Each skip there is by design and gives its reason.

Result: ready. No requirement is unclear, conflicting or missing failure behavior.
