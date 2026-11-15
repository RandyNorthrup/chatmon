# M7 readiness, reviewed again at fb19cb9 (wave 4, 2026-11-14)

The earlier review is [readiness.md](../readiness.md). Its receipt went stale because the rules it was bound to changed.
This review re-reads M7's obligations against the brief and rules as they are now. It is a requirements review, not
proof that the code works.

## Inputs read

- [ASSESSMENT.md](../../../ASSESSMENT.md): the M7 feature items. Unchanged.
- [ROADMAP.md](../../../ROADMAP.md) as amended in wave 4: the canonical-bytes rule, the rule for evidence from elsewhere,
  the owner decisions of 2026-11-14 and the Outcome. The contracts M7 joins (M0 and M5 reminders, M2 and M7, M3 and M7,
  M1B and M7, M4B and M7) are unchanged. So is the sound decision M7-11's quiet rule rests on. The owner's acceptance of
  the sound cues settles the files, not when they play.
- `pyproject.toml` at fb19cb9: M6B's phase B came after M7. It brought ruff and mypy into `app.py` and `settingswin.py`,
  and made every warning an error. M7's tests pass under it, in this wave's suite run and on CI.

## Requirements and criteria

M7-CI, M7-01 to M7-13 and INT-M0, INT-M1B, INT-M2, INT-M8 and INT-M5 still map both ways to their 52 criteria, each with
an owning task and an observable result.

## Since the last review

- **CI-ALL-PLATFORMS.** It asked for the feature branch's CI on all three OSes. Run 43677128712 is that run, with every
  job green. The Windows legs ran the smoke and ask-box tests the coordinator's finding was about (AC-CI-1 to AC-CI-3).
- **Code that moved.** M8 and M6B rewrote lines of `app.py` and `menus.py` after M7. Eight of M7's drills mutated text
  that is gone (`wave4/drills-left-out.txt`). Two criteria, AC-02-1 and AC-02-3, had no other drill, so wave 4's drills
  mutate the lines that carry them now: the "Ask {brain}" button, and the welcome line that names the brain. Both are
  still in TASK-FAILURES' file, `app.py`.

## Findings

- **WAYLAND-HOSTING** is a person's check: Orca on Hyprland or KDE, the ask box as a window, the penguin's menu on the
  stage. AC-11-5's automated tests prove the switch itself. The real desktop has never been tried, and nothing here or
  in CI can try it. It stays a pending operation, with a deferred manual receipt naming the owner.

Result: ready. No requirement is unclear, conflicting or missing failure behavior.
