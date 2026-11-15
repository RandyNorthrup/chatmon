# M4B readiness, round three at cbeed17's merge (wave 4, 2026-11-15)

Round two's review is [../wave4b/readiness.md](../wave4b/readiness.md) (at bf9d8ac). Its receipt, W4B-READY, went stale
when ROADMAP.md was amended for round three (`3586a0d+wave4c`), because ROADMAP.md is a rule of every plan. This review
re-reads the plan's obligations against the brief and rules as they are now, on this branch: `wave4/mac-drills` with
`improve/assessment-fixes` merged in (cbeed17, the toast merge, and 86e84e0, the quit guard). It is a requirements
review, not proof that the code works: the behavior and red receipts are.

## Inputs read

- [ASSESSMENT.md](../../../ASSESSMENT.md): unchanged since round two.
- [ROADMAP.md](../../../ROADMAP.md), amended in round three. *Evidence rules* gains round three's note, which says
  that amending this file stales every receipt of every plan. There are two new *Rule amendments* rows, and
  *Outcome* is rewritten for 3586a0d. That *Outcome* still lists M4B as a checkpoint with four red drills to run.
  No owner decision changed. *Canonical bytes* and *Evidence from elsewhere* are unchanged. The second covers checks
  run elsewhere, recorded under the plan's one profile with the method saying where they ran. This round's checks
  on testpc2 and on the owner's MacBook Pro are recorded that way, as the toast worker's testpc2 receipts were.
- `pyproject.toml`: unchanged since bf9d8ac. Its label is now `3586a0d`, as in the other plans.

## This plan

M4B-00 to M4B-04 still map both ways to AC-00A to AC-04B, and each of the 13 tasks owns its criteria as before. Since
round two, the only changes to this plan's files are the toast worker's (8c24b1c). The toast test waits for a hidden
toast to leave Action Center, which tightens how AC-03E is checked without changing what AC-03E asks. 86e84e0
changes `chatmon/app.py`, which none of this plan's tasks names.

The four criteria whose red drills needed a place to run now have one, approved by the owner on 2026-11-15:

- AC-03E: testpc2's signed-in desktop, with notifications on ("use testpc2 for the notifications drill").
- AC-00C, AC-01D and AC-02F: the owner's MacBook Pro ("yeah use the macbook pro").

Their criteria are unchanged. AC-00C asks that each module imports on macOS. Its drill must change one of its own
task's files, or a file of a task it depends on: `sound.py` is one, `libdbus.py` (the portal's) isn't. AC-01D and
AC-02F are as written. The deferred receipts that said how to run them stay as history.

Result: ready. No requirement is unclear, conflicting or missing failure behavior.
