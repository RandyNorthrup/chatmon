# M4B readiness, reviewed again at fb19cb9 (wave 4, 2026-11-14)

The earlier review is [readiness.md](../readiness.md), through its fourth scope revision. Its receipts went stale
because the rules they were bound to changed. This review re-reads M4B's obligations against the brief and rules as they
are now. It is a requirements review, not proof that the code works.

## Inputs read

- [ASSESSMENT.md](../../../ASSESSMENT.md): the M4B items. Unchanged.
- [ROADMAP.md](../../../ROADMAP.md) as amended in wave 4: the canonical-bytes rule, the rule for evidence from elsewhere,
  the owner decisions of 2026-11-14 and the Outcome. Two decisions bear on M4B, and neither changes an obligation:
  - **The sound cues are accepted as they are.** M4B-02 plays "the packaged cues", and the cue files are M9's. The
    owner's acceptance settles the files, not how they are played.
  - **The sound defaults.** Alerts only, quiet in Do Not Disturb, Focus and full screen. These were already AC-02A
    to AC-02D.
- `pyproject.toml` at fb19cb9: every warning is now an error, `pytest-timeout` gives each test 120 s, and M6B's ruff and
  mypy settings have been added. The CI-LINUX operation's two ResourceWarnings would now fail their tests. They don't.

## Requirements and criteria

M4B-00 to M4B-04 still map both ways to their 22 criteria (AC-00A to AC-04B). Each has an owning task and an observable
result, and each platform-specific criterion names its platform in `given`.

## Since the last review

- CI run 43677128712 ran every platform leg the three pending operations named, on a source that includes
  `CommandPlayer.close`. The Windows legs take the notifications-on branch of the toast tests (run 43648733348's
  traceback shows it), so AC-03E's behavior was observed where notifications are on.
- One Linux drill (L-02D-linux-player) mutated a line of `sound.py` that later changed. Wave 4's W4-L-02E-linux-player
  mutates the line that replaced it, `servers = {...}` in `linux_players`. L-01F-no-portal's text is gone too, and
  AC-01F's other five drills still apply.

## Findings

- Four criteria can't get their red drill here: AC-00C, AC-01D and AC-02F (macOS) and AC-03E (a Windows desktop with
  notifications on, where this PC's user has them off). The criteria are clear and testable. What's missing is the place
  to run them, so they are recorded as deferred red receipts with how to run each and who can.

Result: ready. No requirement is unclear, conflicting or missing failure behavior.
