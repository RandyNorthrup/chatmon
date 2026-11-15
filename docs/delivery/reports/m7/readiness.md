# M7 readiness review

Reviewed 2026-11-14 on `wave2/m7` at `310f7db` (base `4827b0c`, `81af7c7` merged), before any M7 wiring beyond the
coordinator's CI finding. Inputs: [ASSESSMENT.md](../../ASSESSMENT.md) section M7, [ROADMAP.md](../../ROADMAP.md)
(owner decisions, file ownership, contracts, rules), the Integration notes of the M0, M1A, M1B, M2 and M5 plans,
`pyproject.toml`, and the code they name. This is a review of the requirements; it proves nothing about the code.

## Clarity and observability

Each M7 item's "Done when" became criteria with a precondition, an action and an observable result in the ledger.
Where the assessment was loose, the plan decides and says so:

- M7-01 "a bubble '<brain> answered: Read'": a bubble titled "<brain label> answered" with a **Read** button that
  opens the box at the chat. The answer's words stay out of the bubble (a screen reader's notification would keep
  them).
- M7-02 "Ask <next brain>": the next brain Automatic would pick other than the one that failed, else the first other
  brain that can answer (one with a key). Settings opens the window.
- M7-06 "after a missed message": a bubble that timed out while you were away (idle past `presence.AWAY_AFTER`), or a
  plain bubble the queue dropped.
- M7-12 "carry on with the last one": typed (*carry on*), as the box can't take an action from a link without letting
  an answer's links do the same.
- M7-13 "first unlock": the first unlock (or start) each calendar day; no bubble when there's nothing to name.

## Conflicts and decisions

- Closing the box used to stop the answer (M0's test `test_closing_the_box_stops_the_answer_and_the_question_waiting`);
  M7-01 reverses that. The test is replaced by one for the new behavior; Stop is the way to stop.
- M0's note 6 assumed M5's phrase ids match `commands.PHRASES`; they don't. M5's note (dispatch on
  `offline.command`) wins: the table takes M5's ids.
- M0's note 7 asks for the status worker to stop waiting too; it runs off the screen's thread and must report the
  settled brain, so it keeps waiting there (recorded in the plan).
- Owner decision on sound (alerts only by default; quiet during Do Not Disturb, Focus and full screen; one switch):
  the defaults and `_cue`'s rule follow it exactly.
- No new runtime dependencies: everything uses Qt, the standard library and wave 1's modules.

## Missing failure behavior, filled in

- Keychain refusals (`keychain.set` returning a sentence) are said in a bubble; nothing is saved elsewhere.
- A backup that fails to read (`BackupError`) changes nothing and says why; a write failure says why.
- `events.request` with no reply (an older Chatmon, a timeout) falls back to what's on disk in `chatmon status`;
  `chatmon ask` falls back to letting any process come forward only when Chatmon's id can't be learnt.
- A reminder edit that `update` refuses (blank words, a time that can't be told) changes nothing and says why.
- A brain test that's cancelled (window closed) emits nothing further into a closed window.

## Scope and terminology

Scope is M7-01..13 plus the notes; everything else stays with its owner. Items needing M3/M4A/M4B APIs are scoped to
settings and plumbing now and listed under "Waiting for M3 and M4"; their criteria (AC-11-3 and the waiting parts of
M7-07 and M7-11) say what is checked now. Words follow the app's own: *bubble*, *ask box*, *brain*, *chat*,
*reminder*, *alert*, *focus session*, *quiet*.

## Rules

ROADMAP rules 1-8 apply: tests in the project's style (real Qt objects offscreen, no mocks that bypass the behavior),
platform code tested on its platform or skipped with a reason, drills through `tests/drills/run.py`, both gates
before each commit, commits in the repository's style, privacy promises kept (clipboard read only on the user's
action, keys never in state, config or logs, chat text not in notifications).

## Coverage and order

Every requirement has criteria, every criterion a task, and every criterion asks for behavior tests and a red
drill. Order: the CI fix and the shared test harness first; then answers and failures (they change `submit`), then
the per-chat context; settings before what reads new settings (reminders' snooze, platform, hello); the command
table before the agents command and *carry on*; IPC after `events.request`. Merged-module edits are listed in the
plan with the note that asks for each.

## Result

Ready, with the decisions above recorded in the plan. Open external items: the M3/M4 merges (coordinator), CI on
Linux and macOS for platform-specific tests (coordinator's run).
