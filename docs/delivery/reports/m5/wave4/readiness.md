# M5 readiness, reviewed again at fb19cb9 (wave 4, 2026-11-14)

The first review is [readiness.md](../readiness.md). Its receipt went stale because the rules it was bound to changed.
This review re-reads M5's obligations against the brief and rules as they are now. It is a requirements review, not
proof that the code works.

## Inputs read

- [ASSESSMENT.md](../../../ASSESSMENT.md): M5-01 to M5-08. Unchanged.
- [ROADMAP.md](../../../ROADMAP.md) as amended in wave 4: the canonical-bytes rule, the rule for evidence from elsewhere,
  the owner decisions of 2026-11-14 and the Outcome. The M0/M5 reminder contract is unchanged: `due(now)`,
  `acknowledge`, `snooze` and `update`. So is the translation decision M5-05 and M5-06 rest on: locale formats, with
  per-language phrase data and English always accepted.
- `pyproject.toml` at fb19cb9: M6A's stricter pytest settings and M6B's ruff and mypy settings, added since. The
  Hypothesis tests (M5-07) still run fast and deterministic under the 120 s limit.

## Requirements and criteria

M5-01 to M5-08 still map both ways to their 15 criteria, each with an owning task and an observable result. No
terminology conflicts with M8's later gettext layer: M8 translates the help's words, and M5-06's per-language phrase
data is still the source of the commands' phrases and help.

## Since the last review

- Five drills mutated text in `chatmon/offline.py` that M8 and M6B later rewrote (wrapped strings, logged failures). The
  criteria they covered still have drills that apply, except M5-06.A2 (help in the active language). Its new drill,
  W4-M5-06-help-not-translated, mutates the line that now picks the section's name (`mine["name"]` if the language
  gives one).
- M7 wired the reminder contract into `app.py`. M7's plan covers that wiring (M7-04), and it is re-bound in this wave.

Result: ready. No requirement is unclear, conflicting or missing failure behavior.
