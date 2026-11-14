# M0 readiness review

Requirements review of [m0-app-core.md](../../m0-app-core.md) against its brief, the M0 section of
[ASSESSMENT.md](../../ASSESSMENT.md#m0-companion-architecture-and-app-core-fixes-apppy-clipy), and the rules in
[ROADMAP.md](../../ROADMAP.md) (owner decisions, file ownership, contracts, rules for workers) and `pyproject.toml`
(ruff `F`, `E9`, `B`; pytest over `tests/`).

This is a review of the requirements and the plan, not evidence that code works. The requirements analysis was
done before any code changed (the plan's decisions section came out of it); this record of it was written on
2026-11-14 after the first implementation commits, from that analysis and a fresh pass over the brief. No finding
below was changed to fit an implementation.

## Method

For each item M0-01 to M0-13, and the brief's extra deliverable (`tests/test_cli.py`):

1. Read the assessment item and its "Done when" bullets, then the code it cites (`app.py`, `cli.py`, `penguin.py`,
   `bubble.py`, `brains.py`, `heads_up.py`, `chats.py`, `events.py`, `stagemenu.py`, `reminders.py`).
2. Checked each bullet for an observable outcome, a failure or boundary case, a conflict with another bullet or
   milestone, the file that would change and who owns it, and the terms used.
3. Mapped each bullet to an acceptance criterion and an owning task in the ledger.

## Findings

| # | Item | Finding | Resolution |
|---|---|---|---|
| R1 | M0-01 | "A visible bubble with buttons is never replaced by a lower-priority message" leaves equal priority open. Replacing an equal prompt loses it (two "Delete chat?" prompts, an update offer over a break prompt). | Equal-priority prompts wait. A prompt you caused takes the place of one that came on its own, which goes back in line, so what you did always answers at once. |
| R2 | M0-01 | "Every bubble gets a short minimum time" would delay the answer to something you just did behind a bubble that just appeared. | The minimum applies to what comes on its own (agents, scripts, heads-ups, alerts, reminders); what you did shows at once. `MIN_SHOWN = 2.0` s. |
| R3 | M0-01 | "Merged or dropped first" doesn't say what "merged" means. | Waiting messages with the same key (the same agent, the same reminder, the update offer) are replaced by the newest; past `PLAIN_LIMIT = 5` the oldest plain bubble goes. Nothing else is dropped. |
| R4 | M0-01 | "Focus holds the queue" overlaps M7-05 (focus holds non-alert bubbles and shows a summary). Holding everything would also hold the answers to what you do (a confirmation, "Delete it?"), which comes in from the menu after it has closed. | M0 holds what comes on its own below reminder priority during focus; M7-05 adds the summary. Integration note 2. |
| R5 | M0-01 | Persisting the queue across quits ("lost on quit") isn't in "Done when", and held bubbles' buttons run code. | Out of scope; reminders come back from the reminder book (M5-01, M7-04). Non-goal recorded. |
| R6 | M0-01 / M5 | The ROADMAP contract asks for a "reminder" priority that is never dropped; `reminders.py` is M5's. | Priority REMINDER, never dropped, merged by `reminder:<id>`. `_check_reminders` keeps `pop_due` until M7 joins M5's `due()`. Integration note 1. |
| R7 | M0-02 | "Held" doesn't bound how many questions may wait; "Esc to stop" exists today only as closing the box. | One waits (`MAX_WAITING = 1`); a third stays in the box with a note. Esc closes the box and drops both, as closing did; M7-01 changes closing. |
| R8 | M0-02 | Missing failure behavior: what happens to the waiting question when the first fails. | The failed question goes back in the box (as today), the failure stays visible, and the waiting one goes. |
| R9 | M0-03 | "Menus are built when they open": submenus filled lazily would be empty in the stage's own menu (`stagemenu.py` never asks a submenu to open) and in trays that read the layout first. | The whole menu is built on open and on real changes; never on a clock tick. |
| R10 | M0-03 | "The Chats submenu is built from light data" needs a listing in `chats.py`, which M1B owns; `ChatBook.recent()` deep-copies every chat. | Blocked on M1B. `menus.py` reads only id, title, updated and pinned, so M7 switches in one line. Integration note 5; task `T-M0-03-light` blocked. |
| R11 | M0-04 | The top-menu list doesn't place the Appearance submenu, and "Focus and Notes" could be one item or two. | One "Focus and notes" submenu; Appearance after AI agents. Recorded in the plan's decisions. |
| R12 | M0-05 | "A command table that M5's per-language phrase data can drive" needs stable keys for M5's data. | Command ids in `commands.PHRASES` are the keys; `Table(extra)` takes another language and always keeps English. Integration note 6. |
| R13 | M0-06 | Only `open_ask` must stop waiting; `submit` needs the brain to send, and M1B-11 owns a non-blocking lookup. | `submit` unchanged (integration note 7). The *status* command, also cited, is moved off the screen's thread too. |
| R14 | M0-08 | "Each round's results are tagged" doesn't say what happens to the old round's processes. | Late results are ignored by round; the timeout kills whatever still runs. |
| R15 | M0-09 | "A password reply" has to be recognised without changing `offline.py` (M5's). | `commands.run` asks `offline.password` first; a reply holding a made password (in backticks) is read out as the summary. Integration note for M5 if the reply's shape changes. |
| R16 | M0-12 | "`chatmon status` prints agent states": live states (working, needs you) are known only to the running companion; reading a reply needs a client beside `events.py`'s, and M1A-03 is rewriting the Windows pipe client because the current one allows impersonation. | The CLI prints connection states, reminders and the brain itself; live states wait for M1A's `events.request` and M7. Integration note 4. |
| R17 | M0-13 | POSIX file modes can't be observed on this Windows host. | A POSIX test that runs in CI on Linux and macOS and skips on Windows with its reason; recorded as a pending CI check. |
| R18 | Rules | Ownership: every change path in the ledger is an M0-owned file or a new file (`messages.py`, `asking.py`, `commands.py`, `menus.py`, their tests, `tests/test_cli.py`). `README.md`, `changelog.md`, `__init__.py` and `settingswin.py` are not touched; their changes are the plan's notes. | No conflict. |
| R19 | Rules | No new runtime dependency is needed: `ctypes` for `AllowSetForegroundWindow`, Qt for the rest. | No conflict. |

## Coverage

Every "Done when" bullet maps to one acceptance criterion in the ledger, and every criterion has one owning task.
Two criteria can't be fully proved on this host or in this wave: M0-03.A3 (blocked on M1B, R10) and M0-13.A1 (POSIX,
R17). The rest have a behavior test and a red drill that run on Windows.

Readiness verdict: ready to implement, with R10 and R17 carried as known gaps.
