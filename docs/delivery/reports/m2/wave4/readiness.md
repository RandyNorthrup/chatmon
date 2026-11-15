# M2 readiness, reviewed again at fb19cb9 (wave 4, 2026-11-14)

The earlier review is [readiness.md](../readiness.md). Its receipts went stale because the rules they were bound to
changed. This review re-reads M2's obligations against the brief and rules as they are now. It is a requirements review,
not proof that the code works.

## Inputs read

- [ASSESSMENT.md](../../../ASSESSMENT.md): the M2 items. Unchanged.
- [ROADMAP.md](../../../ROADMAP.md) as amended in wave 4: the canonical-bytes rule, the rule for evidence from elsewhere,
  the owner decisions of 2026-11-14 and the Outcome. The M2 and M7 contract (the ask box's signals, `set_busy`,
  `append_partial`, `set_text_scale`, the bubbles' `set_hovered` and `timeout_policy`) is unchanged. No new decision
  touches bubbles or the ask box.
- `pyproject.toml` at fb19cb9: M6A's stricter pytest settings and M6B's ruff and mypy settings, added since. No
  criterion depends on a laxer setting.

## Requirements and criteria

R-M2-01 to R-M2-20 still map one to one to their criteria, each with an owning task and an observable result. The 4.5:1
contrast figures (R-M2-05, R-M2-20) and the size limits (about 40% and 55% of the screen, 2 px outlines) are still
stated as measurable numbers.

## Since the last review

- M8 wrapped the bubbles' and ask box's strings for translation. The English text, which the criteria name, is
  unchanged.
- One drill, M2-11-no-rules, mutated text in `chatmon/richtext.py` that later merges replaced. Its criterion has other
  drills in the same spec, and those still apply. It is listed in `wave4/drills-left-out.txt`.
- P-M2-ci asked for M2's tests on Linux and macOS. CI run 43677128712 ran all six of M2's test files there, with no
  failures and no skips.

Result: ready. No requirement is unclear, conflicting or missing failure behavior.
