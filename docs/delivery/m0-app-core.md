# M0: Companion architecture and app core

Milestone M0 of [ROADMAP.md](ROADMAP.md), items M0-01 to M0-13 of [ASSESSMENT.md](ASSESSMENT.md#m0-companion-architecture-and-app-core-fixes-apppy-clipy).
Branch `wave1/m0`, from `improve/assessment-fixes` at `5346385`. Reports, logs and drills are in
[reports/m0/](reports/m0/).

## Rationale

`app.py` is 2,609 lines and every wave-2 change lands in it. Four responsibilities that have grown inside it get a
module of their own, each with a contract that can be tested without a running companion, and then the app-core
findings are fixed on top of them.

| New module | Responsibility | Qt? | Replaces in `app.py` |
|---|---|---|---|
| `chatmon/messages.py` | Which bubble shows next, and which waits: priorities, holds, merging, the minimum time on screen | no | `_held`, `_waiting`, `_later`, the hold checks in `say()` and `alert()` |
| `chatmon/asking.py` | The question on its way and the ones waiting behind it: one object instead of positional tuples | no | `_asking`, `_asked`, `_folding` |
| `chatmon/commands.py` | The offline commands: a table from phrases to command ids, and what each command does | no (handlers call the companion they're given) | `_local`, `_kept`, `_memory_reply`, `_status`, `HELP_ALL` |
| `chatmon/menus.py` | The menu: built when it opens, its clock labels kept current in between | yes | `_fill_menu` and every `_*_menu` builder |

The rest of `app.py` keeps the names other modules and tests use (`say`, `alert`, `open_ask`, `submit`, `handle`,
`start_focus`, `stop_focus`, `set_hidden`, `open_settings`, `reload`, `quit`, `open_server`, `run`, `log_file`,
`_hold_instance_lock`, `_log_without_a_console`, `Background`, `pretty`, `listed`, `menu`). `offline_clock`, used
only inside `app.py`, moved to `commands.py` with the stopwatch. `app.py` went from 2,609 lines to 2,300.

### Decisions

- **Queue priorities** (M0-01). Alert, then reminder, then a *prompt* (a bubble with buttons or without a timeout),
  then a plain bubble. A showing bubble is replaced only by a higher priority, or by a newer message with the same
  key (the same agent, the same reminder), and only after it has been up for `MIN_SHOWN` seconds; a plain bubble is
  replaced by the next plain one after that time too. A replaced prompt, reminder or alert goes back in the queue and
  shows again after; a replaced plain bubble has been seen and is gone. Waiting plain bubbles merge by key, and past
  `PLAIN_LIMIT` the oldest plain one is dropped. Nothing else is ever dropped. The minimum time applies only to
  what comes on its own (`background`: agents, scripts, heads-ups, alerts, reminders): what answers something you did
  shows at once, ahead of what came on its own, and a prompt you caused takes the place of one that came on its own,
  which goes back in line.
- **Holds** (M0-01). A hold is a named rule saying which waiting messages may still show. Quiet times hold
  everything except what arrived while you were using Chatmon (`yours`) and alerts while nothing covers the
  companion: what `say()` and `alert()` did before, now for every message, not only the last five. Focus holds
  background messages (agents, scripts, update heads-ups, offers, problem reports) below reminder priority; what
  you asked for (a confirmation, a "Delete it?") still shows. The "While you focused" summary is M7-05.
- **Pending questions** (M0-02). One question is answered at a time, as `Asker` cancels any question in flight
  when asked another. A second question waits behind the first (`MAX_WAITING = 1`); a third is refused with the
  text left in the box. Closing the box still stops the answer and drops the waiting one ("Esc to stop"); M7-01
  makes closing let the answer finish in the background.
- **Menus built on open** (M0-03). The whole menu is built when it opens (`aboutToShow`, the stage's own menu),
  and when what it shows changes; never on a clock tick. The stage's menu (`stagemenu.py`, M3's) and some D-Bus
  trays read submenus without asking for them to open, so submenus aren't filled lazily: a tray reading the menu
  before opening it always finds it filled in. Clock ticks set the text of the actions that show a time. The
  agents are re-checked only when the menu opens.
- **Top menu** (M0-04): Ask, Chats, Remind (or Reminders (N)), Focus and notes, Brain, AI agents, Appearance, Hide
  (or Come out), [Update to …], Settings…, Help & updates, Quit. Appearance holds Companion, Bubble style, Walk around
  and Start when I log in; Help holds Reload settings file. The ROADMAP's list doesn't place Appearance; it goes
  after AI agents, with the other setup.
- **Command table** (M0-05). `commands.PHRASES` maps a stable command id to its English phrases. A `Table` takes
  extra phrases per id (M5's per-language data) and always keeps the English ones. The order in which the kinds
  of command are tried is unchanged: memory, reminders, kept things (notes, the stopwatch, reminders by number),
  offline answers, then the table.
- **`chatmon status`** (M0-12) is worked out by the CLI itself, from the same pure formatter the *status* command
  uses: the brain that would answer, the reminders in `state.json`, and each agent's connection state. Live agent
  states (working, needs you, for how long) are known only to the running companion, and asking it needs a client
  that reads a reply; the only Windows pipe client is in `events.py`, which M1A is rewriting for M1A-03 (a second
  copy would keep the impersonation hole M1A-03 closes). That part is an integration note for M1A and M7.
- **The light chat listing** (M0-03, last criterion) needs a listing in `chats.py`, which M1B owns. `menus.py`
  reads only `id`, `title`, `updated` and `pinned` from each chat, so switching to M1B's listing is one line.

### Non-goals

Streaming, the Stop button, failure buttons (M7-01, M7-02); the focus summary (M7-05); recent messages (M7-06);
the Chats window (M7-09); translation (M8); `logging` (M6B-03); keeping held bubbles across a restart (their buttons
run code; reminders come back from the reminder book, M5-01 and M7-04).

### Reuse

`Background` runs the battery, disk and status reads (M0-06). `a11y.spoken` and `_read_aloud` read bubbles out;
M0-09 passes them a summary instead of the password. `reminders.parse_command` (no Qt) parses `chatmon remind`
in the CLI before anything is sent (M0-11). `events.send` and `events.deliver` carry `ask` and the running check.
The tests reuse the `companion` fixture, `PretendBrain`, `PretendDesk` and `PretendReader` in
`tests/test_app_smoke.py`, and the temporary-home fixture style of `tests/test_agents.py`.

## Integration notes

Delivered APIs (M7 reads these):

- `messages.MessageQueue`: `add(message)`, `next(now, visible) -> Message | None`, `wake_at(now) -> float | None`,
  `closed()`, `withdraw(key)`, `hold(reason, passes)`, `release(reason)`, `holding(reason)`, `passes(message)`,
  `held(reason=None)`, `waiting`, `showing`. `messages.Message(title, text, buttons, timeout_s, key=, priority=,
  alert=, yours=, background=)`. Priorities `ALERT < REMINDER < PROMPT < PLAIN`; `MIN_SHOWN`, `PLAIN_LIMIT`.
- `Companion.say(title, text="", buttons=None, timeout_s=12, *, key=None, background=False)` and
  `Companion.alert(key, title, text, buttons=None, *, reminder=False)` (an alert always counts as `background`).
  `Companion._offline(question, reply, spoken=None)`: `spoken` is what a screen reader hears instead.
- `asking.Questions`: `ask(question) -> bool`, `finish() -> Question | None`, `drop()`, `answering(chat_id)`,
  `full()`, `failure`; `asking.Question(chat_id, text, attached, brain, retried, tokens, fold)`;
  `asking.tail(questions) -> list[str]` (the transcript's pending part).
- `commands.PHRASES` (command id: English phrases), `commands.Table(extra=None)` with `.find(text)`,
  `commands.run(c, text, table) -> bool`, `commands.status_lines(battery, disks, upcoming, now, brain_label,
  brain_detail) -> list[str]`, `commands.brain_in_use(brains, config, state, wait=True)`, `commands.notes(state)`,
  `commands.kept(c, asked)`, `commands.offline_clock`, `commands.HELP_ALL`, `commands.PASSWORD_MADE`.
- `menus.Menus(c)`: `.menu`, `.opening()` (built, and the agents looked at if stale), `.fill()`, `.changed()`,
  `.closed()`, `.tick()`, `.stop()`; builders `chats_menu`, `notes_menu`, `help_menu`, `brain_menu`, `agents_menu`,
  `companion_menu`, `style_menu`; `RECENT_CHATS`, `AGENTS_FRESH`.
- The CLI: `chatmon ask [TEXT]` calls `AllowSetForegroundWindow(ASFW_ANY)` on Windows, then sends
  `{"type": "ask", "text": ...}`; the companion handles it with `open_ask(text)`. `chatmon status` pings with
  `{"type": "ping"}` (ignored by the companion) and prints whether Chatmon runs, the brain, battery, disks,
  reminders and each agent's connection state. `chatmon remind` exits 2 on a reminder it can't parse, sending
  nothing.
- Constants in `app.py`: `MAX_CONNECTIONS = 64`, `UPDATE_CHECK_TIMEOUT_S = 60`.

What M7 (or the owner named) must wire:

1. **Reminders (M5 contract).** For each reminder from M5's `due(now)`, call
   `alert(f"reminder:{r.id}", title, text, buttons, reminder=True)`; the queue never drops priority REMINDER and
   merges by that key, so a reminder still showing isn't shown twice. Its buttons call `acknowledge(id)` and
   `snooze(id, until)`. `_check_reminders` still uses `pop_due` until then.
2. **Focus summary (M7-05).** The focus hold is `MessageQueue.hold("focus", ...)` in `Companion._sync_focus_hold`.
   At the end of a session, `MessageQueue.held("focus")` lists what waited: turn those into one "While you focused"
   bubble instead of releasing them one by one.
3. **Streaming (M7-01).** `asking.Question` is where a partial answer belongs; `asking.tail` renders the pending
   part of the transcript. Closing the box calls `Questions.drop()` in `_ask_closed`; M7-01 replaces that.
4. **Live agent states in `chatmon status` (M7-07, M5-08, M1A).** M1A: add `events.request(message, timeout) ->
   dict | None` beside `deliver`, sharing its owner checks and M1A-03's Windows pipe handle, returning the one JSON
   line the companion writes before its `ok`. M7: have `handle()` answer `{"type": "status"}` with the live states
   (M5-08's formatter over `Companion.agents`), and have `cli.status` print them when Chatmon runs.
5. **Light chat listing (M1B, then M7).** M1B: `ChatBook.listing(limit) -> list` of `id`, `title`, `updated` and
   `pinned`, without loading or copying the messages. M7: use it in `menus.chats_menu` in place of `recent()`.
   M7-09's Chats window replaces the per-chat submenus anyway.
6. **Per-language phrases (M5-06).** M5's phrase data uses the ids in `commands.PHRASES` as keys. Load the active
   language's file and hand it to `commands.Table(extra)`; English stays accepted.
7. **Non-blocking brain lookup (M1B-11).** `submit` and the status worker still call `_brain()` with waiting:
   switch them to M1B-11's cached lookup.
8. **Accepting connections (M1A-10).** `Companion._accept` is where `winpipe.client_is_me` would be called.
9. **Passwords (M5).** `commands.run` recognises a made password as `offline.password`'s reply holding a backticked
   code span. If M5 changes that reply's shape (phrase data, M5-06), keep the code span or expose a way to tell.
10. **The foreground on Windows (M1A).** `chatmon ask` allows any process to come forward (`ASFW_ANY`), as the
    CLI doesn't know Chatmon's process id. M1A's `CreateFileW` pipe handle (M1A-03) can give it
    (`GetNamedPipeServerProcessId`), to allow only Chatmon.

## Verification notes

- Gates: `python -m pytest -q -p no:cacheprovider` and `ruff check .` before every commit. Logs are in
  [reports/m0/](reports/m0/); the ledger below binds them.
- On this Windows host every Chatmon in a session shares the hooks' pipe name, so while other workers ran the suite
  at the same time `tests/test_events.py::test_send_without_a_running_companion` and
  `tests/test_app_smoke.py::test_a_hook_reaches_it` sometimes failed (another suite's companion answered). Both
  passed when run alone, and the first failed the same way on the unchanged baseline. The traffic went the other way
  too: once another suite's "hello from a hook" reached this suite's companion during
  `test_quiet_holds_bubbles_from_the_background_until_its_over` (kept in
  [reports/m0/pytest-crosstalk-run.log](reports/m0/pytest-crosstalk-run.log)). M0's new IPC tests use a server of
  their own under a unique name, and `tests/test_cli.py` records what it would send.
- `test_a_quit_companion_runs_and_paints_nothing_more` failed twice in full runs on a heavily loaded machine (one
  run took 224 s): a timer of the quit companion was running. The first time, a late look at the brains restarted
  the menu's refill; refills are now never started once quit (`Menus.stop`, and the message queue's `_quitting`).
  The second time it didn't reproduce in 25 isolated runs or three runs of the whole smoke file; the test now names
  each timer left running (interval and owner), so a recurrence says which.
- A run under load also showed the day's "Updates waiting" heads-up being skipped when a bubble was up, and lost
  until the next day (the watcher had already marked it told). It now waits its turn in the queue (M0-01), with a
  test and a drill.
- POSIX-only checks that can't run here (pending CI): `test_the_log_file_is_yours_alone` (M0-13) and
  `test_chatmon_ask_from_a_terminal_reaches_it` (M0-12, which the in-process `handle` test covers here).

## Changelog notes

- Messages no longer get lost: a bubble with buttons (Focus done, Delete chat?, a break) stays until you answer it
  or it times out, and anything that arrives meanwhile waits its turn. Needs-you alerts and reminders are never
  dropped, every bubble stays up long enough to read, and nothing is cut to the last five during quiet times. The
  day's "Updates waiting" heads-up waits for a bubble on screen instead of going unsaid until the next day.
- During a focus session, agents' and scripts' messages wait until it's over.
- Asking a second question while the first is still being answered no longer throws the first away: the second
  waits ("Still answering, Esc to stop") and both stay in the chat. Commands like *5 km in miles* still answer
  at once.
- The menu is tidier: Companion, Bubble style, Walk around and Start when I log in are under **Appearance**, focus
  and notes share one menu, and **Reload settings file** is under **Help & updates**.
- The menu no longer rebuilds itself every minute while a countdown shows, nor checks your coding agents each
  time; it checks them when you open it.
- Opening the ask box never waits to work out which brain will answer, and battery and disk checks no longer run
  on the screen's thread.
- Renaming your chatmon in Settings works even when the settings file names it.
- A system update check that hangs is stopped after a minute.
- With a screen reader, a generated password is read out as "Password made; it's in the box", so it never lands
  in the notification history.
- New: `chatmon ask [TEXT]` opens the ask box, filled in and ready to type; `chatmon status` prints the brain,
  your reminders and your agents.
- `chatmon remind` with a time it can't read says so and exits with status 2, instead of quietly doing nothing.
- The log file is readable only by you on Linux and macOS.
- Hook connections are capped in number and size.

## README notes

- "Using it" table: the menu is "ask, chats, remind, focus and notes, brain, AI agents, appearance (companion,
  bubble style, walking, start at login), hide, settings, help & updates".
- "Meet the chatmons": pick one under **Appearance › Companion**.
- Settings: "**Reload settings file** under **Help & updates** applies it."
- AI agents: add `chatmon ask [TEXT]` (opens the ask box, filled in) and `chatmon status` (the brain, reminders and
  agents) beside `chatmon say` and `chatmon remind`; `chatmon remind` exits 2 when it can't tell when.
- The name: what you set in Settings wins over `name` in the settings file (as for every other setting).
- "How it's put together": add `chatmon/messages.py` (which bubble shows next), `chatmon/asking.py` (questions on
  their way), `chatmon/commands.py` (what it does without any AI) and `chatmon/menus.py` (the menu).

```quality-ledger
{
  "schema_version": 1,
  "work": {
    "id": "M0",
    "title": "Companion architecture and app core",
    "scope_revision": 1,
    "brief": "docs/delivery/ASSESSMENT.md",
    "brief_reason": null,
    "rules": [
      {
        "path": "docs/delivery/ROADMAP.md",
        "revision": "5346385"
      },
      {
        "path": "pyproject.toml",
        "revision": "5346385"
      }
    ],
    "inputs": [
      "tests/conftest.py",
      "tests/drills/run.py"
    ],
    "environment": {
      "platform": "windows",
      "tools": {
        "python": "3.14.10",
        "ruff": "0.17.4",
        "pytest": "9.2.0",
        "pyqt6": "6.11.0"
      }
    }
  },
  "requirements": [
    {
      "id": "M0-01",
      "statement": "Messages are queued by priority, and alerts, reminders and bubbles with buttons are never lost",
      "priority": "critical",
      "acceptance": [
        "M0-01.A1",
        "M0-01.A2",
        "M0-01.A3",
        "M0-01.A4",
        "M0-01.A5"
      ],
      "superseded_by": null
    },
    {
      "id": "M0-02",
      "statement": "A question asked while another is answered waits instead of cancelling it, and both reach the chat",
      "priority": "critical",
      "acceptance": [
        "M0-02.A1",
        "M0-02.A2",
        "M0-02.A3",
        "M0-02.A4"
      ],
      "superseded_by": null
    },
    {
      "id": "M0-03",
      "statement": "Menus are built when they open, not on every clock tick",
      "priority": "normal",
      "acceptance": [
        "M0-03.A1",
        "M0-03.A2",
        "M0-03.A3"
      ],
      "superseded_by": null
    },
    {
      "id": "M0-04",
      "statement": "The top menu is uncluttered: tasks first, appearance and setup grouped",
      "priority": "normal",
      "acceptance": [
        "M0-04.A1",
        "M0-04.A2",
        "M0-04.A3"
      ],
      "superseded_by": null
    },
    {
      "id": "M0-05",
      "statement": "Offline commands come from a table of phrases that per-language data can extend",
      "priority": "normal",
      "acceptance": [
        "M0-05.A1",
        "M0-05.A2"
      ],
      "superseded_by": null
    },
    {
      "id": "M0-06",
      "statement": "The screen's thread doesn't wait on the brain lookup in open_ask or on battery and disk reads",
      "priority": "normal",
      "acceptance": [
        "M0-06.A1",
        "M0-06.A2"
      ],
      "superseded_by": null
    },
    {
      "id": "M0-07",
      "statement": "The companion's name set in Settings wins over config.toml",
      "priority": "normal",
      "acceptance": [
        "M0-07.A1"
      ],
      "superseded_by": null
    },
    {
      "id": "M0-08",
      "statement": "System update checks time out, and a late result from an earlier round is ignored",
      "priority": "normal",
      "acceptance": [
        "M0-08.A1",
        "M0-08.A2"
      ],
      "superseded_by": null
    },
    {
      "id": "M0-09",
      "statement": "A generated password is never read out through a notification",
      "priority": "critical",
      "acceptance": [
        "M0-09.A1"
      ],
      "superseded_by": null
    },
    {
      "id": "M0-10",
      "statement": "Hook connections are bounded in number and buffered size",
      "priority": "critical",
      "acceptance": [
        "M0-10.A1",
        "M0-10.A2"
      ],
      "superseded_by": null
    },
    {
      "id": "M0-11",
      "statement": "chatmon remind with a time it can't parse says so and exits 2",
      "priority": "normal",
      "acceptance": [
        "M0-11.A1"
      ],
      "superseded_by": null
    },
    {
      "id": "M0-12",
      "statement": "chatmon ask opens the ask box from outside, and chatmon status prints agents, reminders and the brain",
      "priority": "normal",
      "acceptance": [
        "M0-12.A1",
        "M0-12.A2",
        "M0-12.A3"
      ],
      "superseded_by": null
    },
    {
      "id": "M0-13",
      "statement": "The log file is created 0600 on POSIX",
      "priority": "normal",
      "acceptance": [
        "M0-13.A1"
      ],
      "superseded_by": null
    },
    {
      "id": "M0-CLI",
      "statement": "tests/test_cli.py covers CLI dispatch, ask, status, unparseable remind and the hooks subcommands",
      "priority": "normal",
      "acceptance": [
        "M0-CLI.A1"
      ],
      "superseded_by": null
    }
  ],
  "acceptance": [
    {
      "id": "M0-01.A1",
      "requirement": "M0-01",
      "given": "Alerts, reminders, prompts and plain bubbles waiting together",
      "when": "The queue hands out what to show",
      "then": "Alerts come first, then reminders, then prompts (buttons or no timeout), then plain bubbles; among equals what you did goes first",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-01.A2",
      "requirement": "M0-01",
      "given": "Twenty of each priority queued",
      "when": "They are all shown in turn",
      "then": "Every alert, reminder and prompt shows; only the newest PLAIN_LIMIT plain bubbles remain, and waiting news with the same key merges",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-01.A3",
      "requirement": "M0-01",
      "given": "A bubble with buttons on screen",
      "when": "An agent's news, an equal prompt, or an alert arrives",
      "then": "Nothing of equal or lower priority replaces it; an alert pushes it aside after the minimum and it comes back, still answerable",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-01.A4",
      "requirement": "M0-01",
      "given": "A bubble that has just appeared",
      "when": "Something that came on its own is waiting to take its place",
      "then": "It stays up MIN_SHOWN seconds first; the answer to something you did shows at once",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-01.A5",
      "requirement": "M0-01",
      "given": "A quiet time or a focus session",
      "when": "Bubbles arrive",
      "then": "Quiet holds all but what came while you used Chatmon (alerts too when covered), without a cap of five; focus holds background messages below reminder priority; both show when the hold ends",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-02.A1",
      "requirement": "M0-02",
      "given": "A question being answered",
      "when": "A second question is submitted",
      "then": "The brain is asked only the first; the second waits, shown as 'Still answering, Esc to stop'; a third stays in the box",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-02.A2",
      "requirement": "M0-02",
      "given": "A question being answered",
      "when": "An offline command is submitted",
      "then": "It is answered at once, and the pending questions stay in the transcript",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-02.A3",
      "requirement": "M0-02",
      "given": "Two questions, the second waiting",
      "when": "Each answer arrives (or the first fails)",
      "then": "The second is sent after the first; both questions and answers end up in the chat in order; a failed first goes back to the box and the second still goes",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-02.A4",
      "requirement": "M0-02",
      "given": "The question on its way",
      "when": "It is waited on, finished, dropped or folded",
      "then": "One Questions object holds it (chat, text, attachments, brain, retried, tokens, fold) instead of positional tuples",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-03.A1",
      "requirement": "M0-03",
      "given": "A menu showing a focus countdown, the stopwatch and a reminder",
      "when": "The clock ticks",
      "then": "The same menu items stay, and only their time labels change",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-03.A2",
      "requirement": "M0-03",
      "given": "A stale look at the agents",
      "when": "The menu is refilled for a change, or opened",
      "then": "Only opening it looks at the agents again",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-03.A3",
      "requirement": "M0-03",
      "given": "Many saved chats",
      "when": "The Chats submenu is built",
      "then": "It is built from light data (id, title, updated, pinned) without copying the chats",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-04.A1",
      "requirement": "M0-04",
      "given": "The companion running",
      "when": "Its top menu is built",
      "then": "It is Ask, Chats, Remind, Focus and notes, Brain, AI agents, Appearance, Hide, Settings…, Help & updates, Quit",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-04.A2",
      "requirement": "M0-04",
      "given": "The top menu",
      "when": "Appearance is opened",
      "then": "It holds Companion, Bubble style, Walk around and Start when I log in",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-04.A3",
      "requirement": "M0-04",
      "given": "The top menu",
      "when": "Help & updates is opened",
      "then": "It holds Reload settings file, which reloads the settings",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-05.A1",
      "requirement": "M0-05",
      "given": "Each of the 60 phrases the inline chain answered",
      "when": "It is typed in the ask box",
      "then": "The table finds the same command, which does what the chain did",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-05.A2",
      "requirement": "M0-05",
      "given": "Another language's phrases keyed by command id",
      "when": "A Table is made with them",
      "then": "Its phrases run their commands, English is still accepted and wins a shared phrase, and unknown ids are left out",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-06.A1",
      "requirement": "M0-06",
      "given": "No brain known yet",
      "when": "The ask box opens",
      "then": "The brain is looked up without waiting",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-06.A2",
      "requirement": "M0-06",
      "given": "The minute's system check and the status command",
      "when": "Battery and disks are read",
      "then": "They are read off the screen's thread, through Background, and a late status never covers a newer answer",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-07.A1",
      "requirement": "M0-07",
      "given": "config.toml names the companion and Settings renamed it",
      "when": "Its name is used",
      "then": "The name set in Settings wins; the file's is used only when none was set",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-08.A1",
      "requirement": "M0-08",
      "given": "A system update check that hangs beside one that answers",
      "when": "UPDATE_CHECK_TIMEOUT_S passes",
      "then": "The hung check is killed and counts as 0, and the round's heads-up still comes",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-08.A2",
      "requirement": "M0-08",
      "given": "A slow round of checks followed by a new round",
      "when": "The slow round answers late",
      "then": "Its result is ignored; the new round's counts stand",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-09.A1",
      "requirement": "M0-09",
      "given": "A screen reader running",
      "when": "A password is generated",
      "then": "It is read out only as \"Password made; it's in the box\", on a voice or through a notification",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-10.A1",
      "requirement": "M0-10",
      "given": "A hook connection",
      "when": "It sends more than MAX_MESSAGE without a newline",
      "then": "Its read buffer is MAX_MESSAGE + 1, no more is held, and the connection is cut with nothing handled",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-10.A2",
      "requirement": "M0-10",
      "given": "MAX_CONNECTIONS connections open",
      "when": "Another connects",
      "then": "It is turned away; once one closes there is room again",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-11.A1",
      "requirement": "M0-11",
      "given": "chatmon remind with a time it can't read, or none",
      "when": "It runs",
      "then": "It prints the problem, sends nothing and exits 2",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-12.A1",
      "requirement": "M0-12",
      "given": "Chatmon running",
      "when": "chatmon ask [TEXT] runs",
      "then": "The ask box opens with TEXT typed in and the keyboard on it",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-12.A2",
      "requirement": "M0-12",
      "given": "Windows",
      "when": "chatmon ask runs",
      "then": "AllowSetForegroundWindow is called before the message is sent",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-12.A3",
      "requirement": "M0-12",
      "given": "Saved reminders, a picked brain and agents' settings",
      "when": "chatmon status runs",
      "then": "It prints whether Chatmon runs, the brain with its options, the reminders and each agent's state",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-13.A1",
      "requirement": "M0-13",
      "given": "No console, on Linux or macOS",
      "when": "The log is opened",
      "then": "It is created 0600, and an older one made at the umask becomes 0600",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M0-CLI.A1",
      "requirement": "M0-CLI",
      "given": "A temporary home with agents' folders",
      "when": "help, version, unknown commands and the hooks subcommands run",
      "then": "Each prints and exits as documented: listing, show, connect and disconnect all, unknown agent (2), bad usage (2), a file it won't touch (1)",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    }
  ],
  "tasks": [
    {
      "id": "T-M0-01",
      "purpose": "Qt-free message queue (messages.py) wired into say/alert, quiet and focus holds",
      "acceptance": [
        "M0-01.A1",
        "M0-01.A2",
        "M0-01.A3",
        "M0-01.A4",
        "M0-01.A5"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/messages.py",
          "action": "create"
        },
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "tests/test_messages.py",
          "action": "create"
        },
        {
          "path": "tests/test_app_smoke.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-T-M0-01-behavior",
        "E-red-M0-01-priority",
        "E-red-M0-01-never-dropped",
        "E-red-M0-01-heads-up-not-lost",
        "E-red-M0-01-prompt-stays",
        "E-red-M0-01-pushed-comes-back",
        "E-red-M0-01-minimum-time",
        "E-red-M0-01-focus-holds",
        "E-red-M0-01-quiet-holds"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M0-02",
      "purpose": "Pending-question object (asking.py): one waits, both reach the chat",
      "acceptance": [
        "M0-02.A1",
        "M0-02.A2",
        "M0-02.A3",
        "M0-02.A4"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/asking.py",
          "action": "create"
        },
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "tests/test_asking.py",
          "action": "create"
        },
        {
          "path": "tests/test_app_smoke.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-T-M0-02-behavior",
        "E-red-M0-02-second-waits",
        "E-red-M0-02-still-answering-shown",
        "E-red-M0-02-nothing-vanishes",
        "E-red-M0-02-both-answered"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M0-05",
      "purpose": "Offline command table (commands.py) replacing _local and _kept",
      "acceptance": [
        "M0-05.A1",
        "M0-05.A2"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/commands.py",
          "action": "create"
        },
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "tests/test_commands.py",
          "action": "create"
        },
        {
          "path": "tests/test_app_smoke.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-T-M0-05-behavior",
        "E-red-M0-05-same-phrases",
        "E-red-M0-05-english-stays"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M0-03",
      "purpose": "Menus built on open (menus.py); clock ticks set time labels; agents looked at on open",
      "acceptance": [
        "M0-03.A1",
        "M0-03.A2"
      ],
      "depends_on": [
        "T-M0-05"
      ],
      "changes": [
        {
          "path": "chatmon/menus.py",
          "action": "create"
        },
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_smoke.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-T-M0-03-behavior",
        "E-red-M0-03-tick-only-labels",
        "E-red-M0-03-agents-on-open-only"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M0-03-light",
      "purpose": "Chats submenu from a light chat listing",
      "acceptance": [
        "M0-03.A3"
      ],
      "depends_on": [
        "T-M0-03"
      ],
      "changes": [
        {
          "path": "chatmon/menus.py",
          "action": "modify"
        }
      ],
      "status": "blocked",
      "evidence": [],
      "blocker": "chats.py belongs to M1B: it needs ChatBook.listing() (id, title, updated, pinned, no copies); then M7 switches menus.chats_menu to it (integration note 5)",
      "superseded_by": null
    },
    {
      "id": "T-M0-04",
      "purpose": "Top menu reorganised: Appearance, Focus and notes, Reload under Help",
      "acceptance": [
        "M0-04.A1",
        "M0-04.A2",
        "M0-04.A3"
      ],
      "depends_on": [
        "T-M0-03"
      ],
      "changes": [
        {
          "path": "chatmon/menus.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_smoke.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-T-M0-04-behavior",
        "E-red-M0-04-appearance",
        "E-red-M0-04-reload-under-help"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M0-06",
      "purpose": "open_ask doesn't wait; battery, disk and status reads through Background",
      "acceptance": [
        "M0-06.A1",
        "M0-06.A2"
      ],
      "depends_on": [
        "T-M0-05"
      ],
      "changes": [
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "chatmon/commands.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_smoke.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-T-M0-06-behavior",
        "E-red-M0-06-ask-box-doesnt-wait",
        "E-red-M0-06-readings-off-thread"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M0-07",
      "purpose": "State's name wins over config.toml",
      "acceptance": [
        "M0-07.A1"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_smoke.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-T-M0-07-behavior",
        "E-red-M0-07-state-name-wins"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M0-08",
      "purpose": "Update checks killed after a timeout; rounds tagged",
      "acceptance": [
        "M0-08.A1",
        "M0-08.A2"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_smoke.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-T-M0-08-behavior",
        "E-red-M0-08-hung-check-stopped",
        "E-red-M0-08-late-answer-ignored"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M0-09",
      "purpose": "Password replies read out as a summary only",
      "acceptance": [
        "M0-09.A1"
      ],
      "depends_on": [
        "T-M0-05"
      ],
      "changes": [
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "chatmon/commands.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_smoke.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-T-M0-09-behavior",
        "E-red-M0-09-password-not-read"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M0-10",
      "purpose": "Hook connections capped; read buffer limited",
      "acceptance": [
        "M0-10.A1",
        "M0-10.A2"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_smoke.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-T-M0-10-behavior",
        "E-red-M0-10-read-buffer",
        "E-red-M0-10-connection-cap"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M0-11",
      "purpose": "CLI parses a reminder before sending; exit 2 when it can't",
      "acceptance": [
        "M0-11.A1"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/cli.py",
          "action": "modify"
        },
        {
          "path": "tests/test_cli.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-T-M0-11-behavior",
        "E-red-M0-11-unparseable-remind"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M0-12",
      "purpose": "chatmon ask (with AllowSetForegroundWindow) and chatmon status",
      "acceptance": [
        "M0-12.A1",
        "M0-12.A2",
        "M0-12.A3"
      ],
      "depends_on": [
        "T-M0-05"
      ],
      "changes": [
        {
          "path": "chatmon/cli.py",
          "action": "modify"
        },
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "chatmon/commands.py",
          "action": "modify"
        },
        {
          "path": "tests/test_cli.py",
          "action": "create"
        },
        {
          "path": "tests/test_app_smoke.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-T-M0-12-behavior",
        "E-red-M0-12-ask-sent",
        "E-red-M0-12-ask-prefilled",
        "E-red-M0-12-come-forward",
        "E-red-M0-12-status-brain"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M0-13",
      "purpose": "Log file opened 0600 on POSIX",
      "acceptance": [
        "M0-13.A1"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_smoke.py",
          "action": "modify"
        }
      ],
      "status": "implemented",
      "evidence": [
        "E-T-M0-13-behavior"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M0-CLI",
      "purpose": "tests/test_cli.py: dispatch and hooks subcommands",
      "acceptance": [
        "M0-CLI.A1"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/cli.py",
          "action": "modify"
        },
        {
          "path": "tests/test_cli.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-T-M0-CLI-behavior",
        "E-red-M0-12-hooks-connect-all"
      ],
      "blocker": null,
      "superseded_by": null
    }
  ],
  "evidence": [
    {
      "id": "E-readiness",
      "acceptance": [
        "M0-01.A1",
        "M0-01.A2",
        "M0-01.A3",
        "M0-01.A4",
        "M0-01.A5",
        "M0-02.A1",
        "M0-02.A2",
        "M0-02.A3",
        "M0-02.A4",
        "M0-03.A1",
        "M0-03.A2",
        "M0-03.A3",
        "M0-04.A1",
        "M0-04.A2",
        "M0-04.A3",
        "M0-05.A1",
        "M0-05.A2",
        "M0-06.A1",
        "M0-06.A2",
        "M0-07.A1",
        "M0-08.A1",
        "M0-08.A2",
        "M0-09.A1",
        "M0-10.A1",
        "M0-10.A2",
        "M0-11.A1",
        "M0-12.A1",
        "M0-12.A2",
        "M0-12.A3",
        "M0-13.A1",
        "M0-CLI.A1"
      ],
      "kind": "readiness",
      "status": "pass",
      "command": [],
      "method": "Requirements review of the plan against ASSESSMENT.md (M0), ROADMAP.md and pyproject.toml: each Done-when bullet checked for an observable outcome, failure and boundary cases, conflicts, ownership and terms; findings R1-R19 and their resolutions recorded in the artifact",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m0/readiness-review.md",
        "sha256": "9940b59868380b8e12e24842c630d8c2d9af11959655d2873428076ad82b9d51"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        }
      ],
      "scope_sha256": "e1683bb25e3678e58501861c957d0c2054f6fd664df982d0fbc55e134822d5e3",
      "red": null,
      "reason": null
    },
    {
      "id": "E-T-M0-01-behavior",
      "acceptance": [
        "M0-01.A1",
        "M0-01.A2",
        "M0-01.A3",
        "M0-01.A4",
        "M0-01.A5"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs"
      ],
      "method": "The whole suite, run once on the final source; it includes every test this task's criteria name, and the log shows them passing (no failures)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/final-pytest.log",
        "sha256": "1df18df8e3af16c67cb492192711c25ae9d9d8e61dce938c832b1cbcb2a5e459"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "a3686eb3fd2c994c696f38da95faa5a54e6d1c6b930eba6b3714ed69b6fdade4"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "7bcff51f3f042ba83e2dde1c5f94a6772cc201b81e3677fd8a410f239f2ec363"
        }
      ],
      "scope_sha256": "7578ccfb355ee9235f77abc4539d17a317bbd8155e28b54c27749591368fbea2",
      "red": null,
      "reason": null
    },
    {
      "id": "E-T-M0-02-behavior",
      "acceptance": [
        "M0-02.A1",
        "M0-02.A2",
        "M0-02.A3",
        "M0-02.A4"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs"
      ],
      "method": "The whole suite, run once on the final source; it includes every test this task's criteria name, and the log shows them passing (no failures)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/final-pytest.log",
        "sha256": "1df18df8e3af16c67cb492192711c25ae9d9d8e61dce938c832b1cbcb2a5e459"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "29bfd44a58aedb2889d5bf8c47cfbca6f986ae865c76a6cf4a6bb33f6cedbb25"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a3ad4e6fdc3aebefd4c4cec2d576f5ffbf512cbca6bd7a703f02f578b756a812"
        }
      ],
      "scope_sha256": "d74ce928859802125ed2dea3c439b825b68ce3ca7583a4d3b17bf6ca7bdd3ed6",
      "red": null,
      "reason": null
    },
    {
      "id": "E-T-M0-05-behavior",
      "acceptance": [
        "M0-05.A1",
        "M0-05.A2"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs"
      ],
      "method": "The whole suite, run once on the final source; it includes every test this task's criteria name, and the log shows them passing (no failures)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/final-pytest.log",
        "sha256": "1df18df8e3af16c67cb492192711c25ae9d9d8e61dce938c832b1cbcb2a5e459"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "edebefed1b6c2d9a88c152cbfe10589386bb0c33739a0af07c71acb8de1627f3"
        }
      ],
      "scope_sha256": "ddee330026221993635cd2474cf4cee47f14b681b403649659d6ba1432874668",
      "red": null,
      "reason": null
    },
    {
      "id": "E-T-M0-03-behavior",
      "acceptance": [
        "M0-03.A1",
        "M0-03.A2"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs"
      ],
      "method": "The whole suite, run once on the final source; it includes every test this task's criteria name, and the log shows them passing (no failures)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/final-pytest.log",
        "sha256": "1df18df8e3af16c67cb492192711c25ae9d9d8e61dce938c832b1cbcb2a5e459"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "229bd0231c8f4578104f8127605ea590f08a1ec816f20ed5050c50a4db97cd77"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "edebefed1b6c2d9a88c152cbfe10589386bb0c33739a0af07c71acb8de1627f3"
        }
      ],
      "scope_sha256": "d015100d57ac6055b557e0cc3426fb97f402ee16332c029319efed82a6483718",
      "red": null,
      "reason": null
    },
    {
      "id": "E-T-M0-04-behavior",
      "acceptance": [
        "M0-04.A1",
        "M0-04.A2",
        "M0-04.A3"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs"
      ],
      "method": "The whole suite, run once on the final source; it includes every test this task's criteria name, and the log shows them passing (no failures)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/final-pytest.log",
        "sha256": "1df18df8e3af16c67cb492192711c25ae9d9d8e61dce938c832b1cbcb2a5e459"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "229bd0231c8f4578104f8127605ea590f08a1ec816f20ed5050c50a4db97cd77"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "edebefed1b6c2d9a88c152cbfe10589386bb0c33739a0af07c71acb8de1627f3"
        }
      ],
      "scope_sha256": "9a521b6c3769e4cf1306c99fc28a365fbf35abf990ddd525108662bda8696321",
      "red": null,
      "reason": null
    },
    {
      "id": "E-T-M0-06-behavior",
      "acceptance": [
        "M0-06.A1",
        "M0-06.A2"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs"
      ],
      "method": "The whole suite, run once on the final source; it includes every test this task's criteria name, and the log shows them passing (no failures)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/final-pytest.log",
        "sha256": "1df18df8e3af16c67cb492192711c25ae9d9d8e61dce938c832b1cbcb2a5e459"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "edebefed1b6c2d9a88c152cbfe10589386bb0c33739a0af07c71acb8de1627f3"
        }
      ],
      "scope_sha256": "6a1c4ebde921e712249cd973bd9abb1cde92df66cb39a390eeaaa78dbf4fd830",
      "red": null,
      "reason": null
    },
    {
      "id": "E-T-M0-07-behavior",
      "acceptance": [
        "M0-07.A1"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs"
      ],
      "method": "The whole suite, run once on the final source; it includes every test this task's criteria name, and the log shows them passing (no failures)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/final-pytest.log",
        "sha256": "1df18df8e3af16c67cb492192711c25ae9d9d8e61dce938c832b1cbcb2a5e459"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        }
      ],
      "scope_sha256": "d769dbbd843369ed174b8d254d41502920a39905f06245bf6a4c262bd996745c",
      "red": null,
      "reason": null
    },
    {
      "id": "E-T-M0-08-behavior",
      "acceptance": [
        "M0-08.A1",
        "M0-08.A2"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs"
      ],
      "method": "The whole suite, run once on the final source; it includes every test this task's criteria name, and the log shows them passing (no failures)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/final-pytest.log",
        "sha256": "1df18df8e3af16c67cb492192711c25ae9d9d8e61dce938c832b1cbcb2a5e459"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        }
      ],
      "scope_sha256": "4bd41498cd8e3fdb28ba41070b24fc929bf52bec9c2639e1ad2f9ed89353cf0f",
      "red": null,
      "reason": null
    },
    {
      "id": "E-T-M0-09-behavior",
      "acceptance": [
        "M0-09.A1"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs"
      ],
      "method": "The whole suite, run once on the final source; it includes every test this task's criteria name, and the log shows them passing (no failures)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/final-pytest.log",
        "sha256": "1df18df8e3af16c67cb492192711c25ae9d9d8e61dce938c832b1cbcb2a5e459"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "edebefed1b6c2d9a88c152cbfe10589386bb0c33739a0af07c71acb8de1627f3"
        }
      ],
      "scope_sha256": "1744d1f43548bf82ca767217fddf08f3c5b1a2c1132c88fb87381f5fd174e387",
      "red": null,
      "reason": null
    },
    {
      "id": "E-T-M0-10-behavior",
      "acceptance": [
        "M0-10.A1",
        "M0-10.A2"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs"
      ],
      "method": "The whole suite, run once on the final source; it includes every test this task's criteria name, and the log shows them passing (no failures)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/final-pytest.log",
        "sha256": "1df18df8e3af16c67cb492192711c25ae9d9d8e61dce938c832b1cbcb2a5e459"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        }
      ],
      "scope_sha256": "8c8d658b9c85415f2d4ecfd659c7c9a14bcf2ee727db7fc7ee97f9907d0ceda5",
      "red": null,
      "reason": null
    },
    {
      "id": "E-T-M0-11-behavior",
      "acceptance": [
        "M0-11.A1"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs"
      ],
      "method": "The whole suite, run once on the final source; it includes every test this task's criteria name, and the log shows them passing (no failures)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/final-pytest.log",
        "sha256": "1df18df8e3af16c67cb492192711c25ae9d9d8e61dce938c832b1cbcb2a5e459"
      },
      "inputs": [
        {
          "path": "chatmon/cli.py",
          "sha256": "21065a95289bfd1884e7451c61cc059f6613f17c489835080d646edd0d9491ec"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        }
      ],
      "scope_sha256": "3d335ee66962c112e7445141cbd439b82d1d5ceb1d13c899d2876513c5948270",
      "red": null,
      "reason": null
    },
    {
      "id": "E-T-M0-12-behavior",
      "acceptance": [
        "M0-12.A1",
        "M0-12.A2",
        "M0-12.A3"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs"
      ],
      "method": "The whole suite, run once on the final source; it includes every test this task's criteria name, and the log shows them passing (no failures)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/final-pytest.log",
        "sha256": "1df18df8e3af16c67cb492192711c25ae9d9d8e61dce938c832b1cbcb2a5e459"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "21065a95289bfd1884e7451c61cc059f6613f17c489835080d646edd0d9491ec"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "edebefed1b6c2d9a88c152cbfe10589386bb0c33739a0af07c71acb8de1627f3"
        }
      ],
      "scope_sha256": "a3915128b9bf8804f864230ca324db6e2a6c0b7d7b8fe64eb2f8598f2aca8f34",
      "red": null,
      "reason": null
    },
    {
      "id": "E-T-M0-13-behavior",
      "acceptance": [
        "M0-13.A1"
      ],
      "kind": "behavior",
      "status": "deferred",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs"
      ],
      "method": "The full suite ran here; the POSIX-only test for this criterion was collected and skipped on Windows",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/final-pytest.log",
        "sha256": "1df18df8e3af16c67cb492192711c25ae9d9d8e61dce938c832b1cbcb2a5e459"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        }
      ],
      "scope_sha256": "e2801f127412f30a84017ffa0c70c1a06ef91984cbf5dccf1c134cdb6f2c5c28",
      "red": null,
      "reason": "test_the_log_file_is_yours_alone is POSIX-only and skips on this Windows host; it runs in CI on Linux and macOS. Next: the coordinator's CI run on ubuntu and macos; a failure comes back to M0."
    },
    {
      "id": "E-T-M0-CLI-behavior",
      "acceptance": [
        "M0-CLI.A1"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs"
      ],
      "method": "The whole suite, run once on the final source; it includes every test this task's criteria name, and the log shows them passing (no failures)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/final-pytest.log",
        "sha256": "1df18df8e3af16c67cb492192711c25ae9d9d8e61dce938c832b1cbcb2a5e459"
      },
      "inputs": [
        {
          "path": "chatmon/cli.py",
          "sha256": "21065a95289bfd1884e7451c61cc059f6613f17c489835080d646edd0d9491ec"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        }
      ],
      "scope_sha256": "a76f2fb4e908e50f204b8c5830ffc7125101e4cd247a9ca9dd15bca8316f944b",
      "red": null,
      "reason": null
    },
    {
      "id": "E-red-M0-01-priority",
      "acceptance": [
        "M0-01.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_messages.py::test_alerts_then_reminders_then_prompts_then_plain_bubbles green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "a3686eb3fd2c994c696f38da95faa5a54e6d1c6b930eba6b3714ed69b6fdade4"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "7bcff51f3f042ba83e2dde1c5f94a6772cc201b81e3677fd8a410f239f2ec363"
        }
      ],
      "scope_sha256": "7578ccfb355ee9235f77abc4539d17a317bbd8155e28b54c27749591368fbea2",
      "red": {
        "mutation": "chatmon/messages.py: 'return min(ready, key=lambda m: (m.priority, m.background, m.seq)) if ready else None' -> 'return min(ready, key=lambda m: m.seq) if ready else None'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_alerts_then_reminders_then_prompts_then_plain_bubbles",
        "observed_diagnostic": "_________ test_alerts_then_reminders_then_prompts_then_plain_bubbles __________",
        "before": [
          {
            "path": "chatmon/messages.py",
            "sha256": "a3686eb3fd2c994c696f38da95faa5a54e6d1c6b930eba6b3714ed69b6fdade4"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/messages.py",
            "sha256": "d49da10b48d4206a544d51341db03a70661de36307e1bee012c64c21cf9746fb"
          }
        ],
        "after": [
          {
            "path": "chatmon/messages.py",
            "sha256": "a3686eb3fd2c994c696f38da95faa5a54e6d1c6b930eba6b3714ed69b6fdade4"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-01-never-dropped",
      "acceptance": [
        "M0-01.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_messages.py::test_nothing_but_plain_bubbles_is_ever_dropped green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "a3686eb3fd2c994c696f38da95faa5a54e6d1c6b930eba6b3714ed69b6fdade4"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "7bcff51f3f042ba83e2dde1c5f94a6772cc201b81e3677fd8a410f239f2ec363"
        }
      ],
      "scope_sha256": "7578ccfb355ee9235f77abc4539d17a317bbd8155e28b54c27749591368fbea2",
      "red": {
        "mutation": "chatmon/messages.py: 'plain = [m for m in self.waiting if m.priority == PLAIN]' -> 'plain = list(self.waiting)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_nothing_but_plain_bubbles_is_ever_dropped",
        "observed_diagnostic": "_______________ test_nothing_but_plain_bubbles_is_ever_dropped ________________",
        "before": [
          {
            "path": "chatmon/messages.py",
            "sha256": "a3686eb3fd2c994c696f38da95faa5a54e6d1c6b930eba6b3714ed69b6fdade4"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/messages.py",
            "sha256": "bd4e75eb687c2c68151cc3de4a9b2449145c07bbdfc3915d27ad560f0c3adad4"
          }
        ],
        "after": [
          {
            "path": "chatmon/messages.py",
            "sha256": "a3686eb3fd2c994c696f38da95faa5a54e6d1c6b930eba6b3714ed69b6fdade4"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-01-heads-up-not-lost",
      "acceptance": [
        "M0-01.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_app_smoke.py::test_the_days_updates_heads_up_waits_for_a_bubble_showing_instead_of_going_unsaid green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "a3686eb3fd2c994c696f38da95faa5a54e6d1c6b930eba6b3714ed69b6fdade4"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "7bcff51f3f042ba83e2dde1c5f94a6772cc201b81e3677fd8a410f239f2ec363"
        }
      ],
      "scope_sha256": "7578ccfb355ee9235f77abc4539d17a317bbd8155e28b54c27749591368fbea2",
      "red": {
        "mutation": "chatmon/app.py: 'if notice:  # told once a day: it waits its turn behind a bubble on screen, rather than going unsaid' -> 'if notice and not self.stage.message_visible():'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_days_updates_heads_up_waits_for_a_bubble_showing_instead_of_going_unsaid",
        "observed_diagnostic": "_ test_the_days_updates_heads_up_waits_for_a_bubble_showing_instead_of_going_unsaid _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "27c4df628f69fa97885a1c3297fc76b75bf8ce79d32c9ff516996a601e219eab"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-01-prompt-stays",
      "acceptance": [
        "M0-01.A3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_messages.py::test_a_bubble_with_buttons_is_never_replaced_by_anything_that_matters_as_much_or_less tests/test_app_smoke.py::test_a_bubble_with_buttons_waits_for_no_agent_and_comes_back_after_an_alert green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "a3686eb3fd2c994c696f38da95faa5a54e6d1c6b930eba6b3714ed69b6fdade4"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "7bcff51f3f042ba83e2dde1c5f94a6772cc201b81e3677fd8a410f239f2ec363"
        }
      ],
      "scope_sha256": "7578ccfb355ee9235f77abc4539d17a317bbd8155e28b54c27749591368fbea2",
      "red": {
        "mutation": "chatmon/messages.py: 'return best.priority == showing.priority and (best.priority == PLAIN or (showing.background and not best.background))' -> 'return True'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_bubble_with_buttons_is_never_replaced_by_anything_that_matters_as_much_or_less",
        "observed_diagnostic": "_ test_a_bubble_with_buttons_is_never_replaced_by_anything_that_matters_as_much_or_less _",
        "before": [
          {
            "path": "chatmon/messages.py",
            "sha256": "a3686eb3fd2c994c696f38da95faa5a54e6d1c6b930eba6b3714ed69b6fdade4"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/messages.py",
            "sha256": "7da320f918a023ddf53bd15e967f34e7fe6f32e020011a395c555de683c162b1"
          }
        ],
        "after": [
          {
            "path": "chatmon/messages.py",
            "sha256": "a3686eb3fd2c994c696f38da95faa5a54e6d1c6b930eba6b3714ed69b6fdade4"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-01-pushed-comes-back",
      "acceptance": [
        "M0-01.A3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_messages.py::test_something_more_important_takes_over_after_the_minimum_and_the_bubble_comes_back tests/test_app_smoke.py::test_a_bubble_with_buttons_waits_for_no_agent_and_comes_back_after_an_alert green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "a3686eb3fd2c994c696f38da95faa5a54e6d1c6b930eba6b3714ed69b6fdade4"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "7bcff51f3f042ba83e2dde1c5f94a6772cc201b81e3677fd8a410f239f2ec363"
        }
      ],
      "scope_sha256": "7578ccfb355ee9235f77abc4539d17a317bbd8155e28b54c27749591368fbea2",
      "red": {
        "mutation": "chatmon/messages.py: 'self.waiting.append(pushed)' -> 'pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_something_more_important_takes_over_after_the_minimum_and_the_bubble_comes_back",
        "observed_diagnostic": "_ test_something_more_important_takes_over_after_the_minimum_and_the_bubble_comes_back _",
        "before": [
          {
            "path": "chatmon/messages.py",
            "sha256": "a3686eb3fd2c994c696f38da95faa5a54e6d1c6b930eba6b3714ed69b6fdade4"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/messages.py",
            "sha256": "ba744d5e2437f11446287dec191758f2f5010c9c93d6e0be9a2e22515bcc925e"
          }
        ],
        "after": [
          {
            "path": "chatmon/messages.py",
            "sha256": "a3686eb3fd2c994c696f38da95faa5a54e6d1c6b930eba6b3714ed69b6fdade4"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-01-minimum-time",
      "acceptance": [
        "M0-01.A4"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_messages.py::test_a_plain_bubble_gives_way_to_the_next_plain_one_after_the_minimum_and_is_gone tests/test_messages.py::test_something_more_important_takes_over_after_the_minimum_and_the_bubble_comes_back green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "a3686eb3fd2c994c696f38da95faa5a54e6d1c6b930eba6b3714ed69b6fdade4"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "7bcff51f3f042ba83e2dde1c5f94a6772cc201b81e3677fd8a410f239f2ec363"
        }
      ],
      "scope_sha256": "7578ccfb355ee9235f77abc4539d17a317bbd8155e28b54c27749591368fbea2",
      "red": {
        "mutation": "chatmon/messages.py: 'if best.background and now - self.shown_at < MIN_SHOWN:' -> 'if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_plain_bubble_gives_way_to_the_next_plain_one_after_the_minimum_and_is_gone",
        "observed_diagnostic": "_ test_a_plain_bubble_gives_way_to_the_next_plain_one_after_the_minimum_and_is_gone _",
        "before": [
          {
            "path": "chatmon/messages.py",
            "sha256": "a3686eb3fd2c994c696f38da95faa5a54e6d1c6b930eba6b3714ed69b6fdade4"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/messages.py",
            "sha256": "1bd9db250b7f0d211d9c0372ce7f2a305b1fcec25cbb9aa369d21589e019d8d2"
          }
        ],
        "after": [
          {
            "path": "chatmon/messages.py",
            "sha256": "a3686eb3fd2c994c696f38da95faa5a54e6d1c6b930eba6b3714ed69b6fdade4"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-01-focus-holds",
      "acceptance": [
        "M0-01.A5"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_app_smoke.py::test_a_focus_session_holds_what_comes_on_its_own_until_its_over green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "a3686eb3fd2c994c696f38da95faa5a54e6d1c6b930eba6b3714ed69b6fdade4"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "7bcff51f3f042ba83e2dde1c5f94a6772cc201b81e3677fd8a410f239f2ec363"
        }
      ],
      "scope_sha256": "7578ccfb355ee9235f77abc4539d17a317bbd8155e28b54c27749591368fbea2",
      "red": {
        "mutation": "chatmon/app.py: 'self.messages.hold(\"focus\", lambda m: not m.background or m.priority <= messages.REMINDER)' -> 'self.messages.hold(\"focus\", lambda m: True)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_focus_session_holds_what_comes_on_its_own_until_its_over",
        "observed_diagnostic": "_______ test_a_focus_session_holds_what_comes_on_its_own_until_its_over _______",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "74e47f83e456e4b72a0fd9b2565473db44c33439a200c160621cd85defe77fa5"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-01-quiet-holds",
      "acceptance": [
        "M0-01.A5"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_app_smoke.py::test_quiet_holds_bubbles_from_the_background_until_its_over tests/test_app_smoke.py::test_an_alert_under_a_full_screen_app_is_a_system_notification_and_waits green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "a3686eb3fd2c994c696f38da95faa5a54e6d1c6b930eba6b3714ed69b6fdade4"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "7bcff51f3f042ba83e2dde1c5f94a6772cc201b81e3677fd8a410f239f2ec363"
        }
      ],
      "scope_sha256": "7578ccfb355ee9235f77abc4539d17a317bbd8155e28b54c27749591368fbea2",
      "red": {
        "mutation": "chatmon/app.py: 'self.messages.hold(\"quiet\", lambda m: m.yours or (m.alert and not covered))' -> 'self.messages.hold(\"quiet\", lambda m: True)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_quiet_holds_bubbles_from_the_background_until_its_over",
        "observed_diagnostic": "_________ test_quiet_holds_bubbles_from_the_background_until_its_over _________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "3dab655a067f7dbc6c80feaf601e5da4abde6d9507340ae310bf20b56a8773d2"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-02-second-waits",
      "acceptance": [
        "M0-02.A1",
        "M0-02.A4"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_app_smoke.py::test_a_question_asked_while_one_is_answered_waits_and_both_stay_in_the_chat tests/test_asking.py::test_the_first_question_goes_and_the_next_waits_its_turn green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "29bfd44a58aedb2889d5bf8c47cfbca6f986ae865c76a6cf4a6bb33f6cedbb25"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a3ad4e6fdc3aebefd4c4cec2d576f5ffbf512cbca6bd7a703f02f578b756a812"
        }
      ],
      "scope_sha256": "d74ce928859802125ed2dea3c439b825b68ce3ca7583a4d3b17bf6ca7bdd3ed6",
      "red": {
        "mutation": "chatmon/asking.py: 'if self.current is None:' -> 'if True:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_question_asked_while_one_is_answered_waits_and_both_stay_in_the_chat",
        "observed_diagnostic": "_ test_a_question_asked_while_one_is_answered_waits_and_both_stay_in_the_chat _",
        "before": [
          {
            "path": "chatmon/asking.py",
            "sha256": "29bfd44a58aedb2889d5bf8c47cfbca6f986ae865c76a6cf4a6bb33f6cedbb25"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/asking.py",
            "sha256": "6702d283fc602ec4270046ffe7c45fb75f6c3f64a0031e8c4fa230a6994b98eb"
          }
        ],
        "after": [
          {
            "path": "chatmon/asking.py",
            "sha256": "29bfd44a58aedb2889d5bf8c47cfbca6f986ae865c76a6cf4a6bb33f6cedbb25"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-02-still-answering-shown",
      "acceptance": [
        "M0-02.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_app_smoke.py::test_a_question_asked_while_one_is_answered_waits_and_both_stay_in_the_chat green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "29bfd44a58aedb2889d5bf8c47cfbca6f986ae865c76a6cf4a6bb33f6cedbb25"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a3ad4e6fdc3aebefd4c4cec2d576f5ffbf512cbca6bd7a703f02f578b756a812"
        }
      ],
      "scope_sha256": "d74ce928859802125ed2dea3c439b825b68ce3ca7583a4d3b17bf6ca7bdd3ed6",
      "red": {
        "mutation": "chatmon/asking.py: 'parts.append(f\"{_you(waiting)}\\\\n\\\\n*Still answering, Esc to stop. This one is next.*\")' -> 'pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_question_asked_while_one_is_answered_waits_and_both_stay_in_the_chat",
        "observed_diagnostic": "_ test_a_question_asked_while_one_is_answered_waits_and_both_stay_in_the_chat _",
        "before": [
          {
            "path": "chatmon/asking.py",
            "sha256": "29bfd44a58aedb2889d5bf8c47cfbca6f986ae865c76a6cf4a6bb33f6cedbb25"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/asking.py",
            "sha256": "f6967c33f627c306dbb63214a70dcc544c775e3538aef9648e0c8e3ab71bc063"
          }
        ],
        "after": [
          {
            "path": "chatmon/asking.py",
            "sha256": "29bfd44a58aedb2889d5bf8c47cfbca6f986ae865c76a6cf4a6bb33f6cedbb25"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-02-nothing-vanishes",
      "acceptance": [
        "M0-02.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_app_smoke.py::test_a_question_asked_while_one_is_answered_waits_and_both_stay_in_the_chat green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "29bfd44a58aedb2889d5bf8c47cfbca6f986ae865c76a6cf4a6bb33f6cedbb25"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a3ad4e6fdc3aebefd4c4cec2d576f5ffbf512cbca6bd7a703f02f578b756a812"
        }
      ],
      "scope_sha256": "d74ce928859802125ed2dea3c439b825b68ce3ca7583a4d3b17bf6ca7bdd3ed6",
      "red": {
        "mutation": "chatmon/app.py: 'parts += asking.tail(self.questions, self._thinking())' -> 'pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_question_asked_while_one_is_answered_waits_and_both_stay_in_the_chat",
        "observed_diagnostic": "_ test_a_question_asked_while_one_is_answered_waits_and_both_stay_in_the_chat _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "f49dc15a31c9a4000f1e2c64a82b04b95728c164e4839d8ebf46a75162b9ad6a"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-02-both-answered",
      "acceptance": [
        "M0-02.A3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_app_smoke.py::test_a_question_asked_while_one_is_answered_waits_and_both_stay_in_the_chat tests/test_app_smoke.py::test_a_failed_question_goes_back_in_the_box_and_the_one_waiting_goes green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "29bfd44a58aedb2889d5bf8c47cfbca6f986ae865c76a6cf4a6bb33f6cedbb25"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a3ad4e6fdc3aebefd4c4cec2d576f5ffbf512cbca6bd7a703f02f578b756a812"
        }
      ],
      "scope_sha256": "d74ce928859802125ed2dea3c439b825b68ce3ca7583a4d3b17bf6ca7bdd3ed6",
      "red": {
        "mutation": "chatmon/app.py: 'self._send(waiting)' -> 'pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_question_asked_while_one_is_answered_waits_and_both_stay_in_the_chat",
        "observed_diagnostic": "_ test_a_question_asked_while_one_is_answered_waits_and_both_stay_in_the_chat _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "707a65678665c90659b75cc862f3699813cf4267b85bd24449d2a7ecece9dbaf"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-03-tick-only-labels",
      "acceptance": [
        "M0-03.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_app_smoke.py::test_a_clock_tick_changes_only_the_times_in_the_menu green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "229bd0231c8f4578104f8127605ea590f08a1ec816f20ed5050c50a4db97cd77"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "edebefed1b6c2d9a88c152cbfe10589386bb0c33739a0af07c71acb8de1627f3"
        }
      ],
      "scope_sha256": "d015100d57ac6055b557e0cc3426fb97f402ee16332c029319efed82a6483718",
      "red": {
        "mutation": "chatmon/app.py: 'self.menus.tick()' -> 'self._menu_changed()'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_clock_tick_changes_only_the_times_in_the_menu",
        "observed_diagnostic": "____________ test_a_clock_tick_changes_only_the_times_in_the_menu _____________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "7c7ecf85c0bdb77d3195590f94bfa23b2ef99a93b1a4c0a3d79a17e1affb2153"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-03-agents-on-open-only",
      "acceptance": [
        "M0-03.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_app_smoke.py::test_looks_at_the_agents_one_look_at_a_time green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "229bd0231c8f4578104f8127605ea590f08a1ec816f20ed5050c50a4db97cd77"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "edebefed1b6c2d9a88c152cbfe10589386bb0c33739a0af07c71acb8de1627f3"
        }
      ],
      "scope_sha256": "d015100d57ac6055b557e0cc3426fb97f402ee16332c029319efed82a6483718",
      "red": {
        "mutation": "chatmon/menus.py: 'self._clocks = []' -> 'self._clocks = []; self.c._refresh_agents()'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_looks_at_the_agents_one_look_at_a_time",
        "observed_diagnostic": "_________________ test_looks_at_the_agents_one_look_at_a_time _________________",
        "before": [
          {
            "path": "chatmon/menus.py",
            "sha256": "229bd0231c8f4578104f8127605ea590f08a1ec816f20ed5050c50a4db97cd77"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/menus.py",
            "sha256": "f2ea301f33dd28c1da951c1f34ec99d7a4efa5ef44a8c95d3a055dff69a1dd1c"
          }
        ],
        "after": [
          {
            "path": "chatmon/menus.py",
            "sha256": "229bd0231c8f4578104f8127605ea590f08a1ec816f20ed5050c50a4db97cd77"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-04-appearance",
      "acceptance": [
        "M0-04.A1",
        "M0-04.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_app_smoke.py::test_hide_menu_and_reload green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "229bd0231c8f4578104f8127605ea590f08a1ec816f20ed5050c50a4db97cd77"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "edebefed1b6c2d9a88c152cbfe10589386bb0c33739a0af07c71acb8de1627f3"
        }
      ],
      "scope_sha256": "9a521b6c3769e4cf1306c99fc28a365fbf35abf990ddd525108662bda8696321",
      "red": {
        "mutation": "chatmon/menus.py: 'companion_menu(c, appearance.addMenu(\"Companion\"))' -> 'companion_menu(c, m.addMenu(\"Companion\"))'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_hide_menu_and_reload",
        "observed_diagnostic": "__________________________ test_hide_menu_and_reload __________________________",
        "before": [
          {
            "path": "chatmon/menus.py",
            "sha256": "229bd0231c8f4578104f8127605ea590f08a1ec816f20ed5050c50a4db97cd77"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/menus.py",
            "sha256": "95ca73727c957d7e8637256d138f090a0e81e633b508fdf161fad2bfc3de6f32"
          }
        ],
        "after": [
          {
            "path": "chatmon/menus.py",
            "sha256": "229bd0231c8f4578104f8127605ea590f08a1ec816f20ed5050c50a4db97cd77"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-04-reload-under-help",
      "acceptance": [
        "M0-04.A3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_app_smoke.py::test_hide_menu_and_reload green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "229bd0231c8f4578104f8127605ea590f08a1ec816f20ed5050c50a4db97cd77"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "edebefed1b6c2d9a88c152cbfe10589386bb0c33739a0af07c71acb8de1627f3"
        }
      ],
      "scope_sha256": "9a521b6c3769e4cf1306c99fc28a365fbf35abf990ddd525108662bda8696321",
      "red": {
        "mutation": "chatmon/menus.py: 'sub.addAction(\"Reload settings file\", c.reload)' -> 'pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_hide_menu_and_reload",
        "observed_diagnostic": "__________________________ test_hide_menu_and_reload __________________________",
        "before": [
          {
            "path": "chatmon/menus.py",
            "sha256": "229bd0231c8f4578104f8127605ea590f08a1ec816f20ed5050c50a4db97cd77"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/menus.py",
            "sha256": "c5cad9008ecb3dbb7f3f7fb9fa448b2c8ab75762b68c9a9cd74f52681f68ceff"
          }
        ],
        "after": [
          {
            "path": "chatmon/menus.py",
            "sha256": "229bd0231c8f4578104f8127605ea590f08a1ec816f20ed5050c50a4db97cd77"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-05-same-phrases",
      "acceptance": [
        "M0-05.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_commands.py::test_the_same_phrases_run_the_same_commands tests/test_app_smoke.py::test_every_command_in_the_table_does_what_it_did green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "edebefed1b6c2d9a88c152cbfe10589386bb0c33739a0af07c71acb8de1627f3"
        }
      ],
      "scope_sha256": "ddee330026221993635cd2474cf4cee47f14b681b403649659d6ba1432874668",
      "red": {
        "mutation": "chatmon/commands.py: '\"hide\": (\"hide\", \"go hide\", \"go away\"),' -> '\"hide\": (\"hide\", \"go hide\"),'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_same_phrases_run_the_same_commands",
        "observed_diagnostic": "_________________ test_the_same_phrases_run_the_same_commands _________________",
        "before": [
          {
            "path": "chatmon/commands.py",
            "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/commands.py",
            "sha256": "7d2250d87ca3860d5fb91476a76e6f4923e6aa94e68231ec0fad1ce13f737344"
          }
        ],
        "after": [
          {
            "path": "chatmon/commands.py",
            "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-05-english-stays",
      "acceptance": [
        "M0-05.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_commands.py::test_another_languages_phrases_join_english_which_stays green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "edebefed1b6c2d9a88c152cbfe10589386bb0c33739a0af07c71acb8de1627f3"
        }
      ],
      "scope_sha256": "ddee330026221993635cd2474cf4cee47f14b681b403649659d6ba1432874668",
      "red": {
        "mutation": "chatmon/commands.py: 'self._ids.setdefault(normal(phrase), cid)' -> 'self._ids[normal(phrase)] = cid'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_another_languages_phrases_join_english_which_stays",
        "observed_diagnostic": "___________ test_another_languages_phrases_join_english_which_stays ___________",
        "before": [
          {
            "path": "chatmon/commands.py",
            "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/commands.py",
            "sha256": "429b65e3229b3b4f9f1938121b532df0242b28250d9173f01762e56d0f698c01"
          }
        ],
        "after": [
          {
            "path": "chatmon/commands.py",
            "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-06-ask-box-doesnt-wait",
      "acceptance": [
        "M0-06.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_app_smoke.py::test_the_ask_box_never_waits_to_find_the_brain green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "edebefed1b6c2d9a88c152cbfe10589386bb0c33739a0af07c71acb8de1627f3"
        }
      ],
      "scope_sha256": "6a1c4ebde921e712249cd973bd9abb1cde92df66cb39a390eeaaa78dbf4fd830",
      "red": {
        "mutation": "chatmon/app.py: 'brain = self._brain(wait=False)  # only for the hint' -> 'brain = self._brain()  # only for the hint'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_ask_box_never_waits_to_find_the_brain",
        "observed_diagnostic": "_______________ test_the_ask_box_never_waits_to_find_the_brain ________________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "5f12d370c4f4727bab49841a5d7dfb6aae6fbf95eb7abfe647e1f2932717ff6c"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-06-readings-off-thread",
      "acceptance": [
        "M0-06.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_app_smoke.py::test_battery_disks_and_status_are_read_off_the_screens_thread green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "edebefed1b6c2d9a88c152cbfe10589386bb0c33739a0af07c71acb8de1627f3"
        }
      ],
      "scope_sha256": "6a1c4ebde921e712249cd973bd9abb1cde92df66cb39a390eeaaa78dbf4fd830",
      "red": {
        "mutation": "chatmon/app.py: 'self.background.run(_read_system, self._system_read)' -> 'self._system_read(_read_system())'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_battery_disks_and_status_are_read_off_the_screens_thread",
        "observed_diagnostic": "________ test_battery_disks_and_status_are_read_off_the_screens_thread ________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "e8f8de229e98b927811776a188564c22e836ba31575571c0461a11e38a7a09ef"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-07-state-name-wins",
      "acceptance": [
        "M0-07.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_app_smoke.py::test_the_name_you_gave_wins_over_the_settings_file green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        }
      ],
      "scope_sha256": "d769dbbd843369ed174b8d254d41502920a39905f06245bf6a4c262bd996745c",
      "red": {
        "mutation": "chatmon/app.py: 'return self.state.get(\"name\") or self.config[\"name\"] or self._companion().nickname' -> 'return self.config[\"name\"] or self.state.get(\"name\") or self._companion().nickname'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_name_you_gave_wins_over_the_settings_file",
        "observed_diagnostic": "_____________ test_the_name_you_gave_wins_over_the_settings_file ______________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "309598c01e2010e789c521016cd30962e3a336042bd612be8cb33ec48b8d6cc1"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-08-hung-check-stopped",
      "acceptance": [
        "M0-08.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_app_smoke.py::test_a_system_update_check_that_hangs_is_stopped_and_counts_as_none green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        }
      ],
      "scope_sha256": "4bd41498cd8e3fdb28ba41070b24fc929bf52bec9c2639e1ad2f9ed89353cf0f",
      "red": {
        "mutation": "chatmon/app.py: 'self._update_deadline.start(int(UPDATE_CHECK_TIMEOUT_S * 1000))' -> 'pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_system_update_check_that_hangs_is_stopped_and_counts_as_none",
        "observed_diagnostic": "_____ test_a_system_update_check_that_hangs_is_stopped_and_counts_as_none _____",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "912128d13b15504eb45016a428ae395a0eccf22602b26a81375c485ef5e3534e"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-08-late-answer-ignored",
      "acceptance": [
        "M0-08.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_app_smoke.py::test_a_late_answer_from_an_earlier_look_at_updates_is_ignored green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        }
      ],
      "scope_sha256": "4bd41498cd8e3fdb28ba41070b24fc929bf52bec9c2639e1ad2f9ed89353cf0f",
      "red": {
        "mutation": "chatmon/app.py: 'if tag != self._update_round:' -> 'if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_late_answer_from_an_earlier_look_at_updates_is_ignored",
        "observed_diagnostic": "________ test_a_late_answer_from_an_earlier_look_at_updates_is_ignored ________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "5a80ddabab4bb1673e881a4af1d9818e32d8d82126c1ad94b331a422af494f53"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-09-password-not-read",
      "acceptance": [
        "M0-09.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_app_smoke.py::test_a_password_made_is_never_read_out green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "edebefed1b6c2d9a88c152cbfe10589386bb0c33739a0af07c71acb8de1627f3"
        }
      ],
      "scope_sha256": "1744d1f43548bf82ca767217fddf08f3c5b1a2c1132c88fb87381f5fd174e387",
      "red": {
        "mutation": "chatmon/commands.py: 'c._offline(text, made, spoken=PASSWORD_MADE if \"`\" in made else None)' -> 'c._offline(text, made)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_password_made_is_never_read_out",
        "observed_diagnostic": "___________________ test_a_password_made_is_never_read_out ____________________",
        "before": [
          {
            "path": "chatmon/commands.py",
            "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/commands.py",
            "sha256": "6fd6dc6bfce50fb19bc5b815c1652c67edac9019bdfb500981e6081781ff6a1e"
          }
        ],
        "after": [
          {
            "path": "chatmon/commands.py",
            "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-10-read-buffer",
      "acceptance": [
        "M0-10.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_app_smoke.py::test_a_hook_connection_never_holds_more_than_a_message green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        }
      ],
      "scope_sha256": "8c8d658b9c85415f2d4ecfd659c7c9a14bcf2ee727db7fc7ee97f9907d0ceda5",
      "red": {
        "mutation": "chatmon/app.py: 'sock.setReadBufferSize(events.MAX_MESSAGE + 1)' -> 'sock.setReadBufferSize(0)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_hook_connection_never_holds_more_than_a_message",
        "observed_diagnostic": "___________ test_a_hook_connection_never_holds_more_than_a_message ____________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "4c536b25c8780804eead29d51ca689cbb6133ae98ef495e1a66c2a6e48247737"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-10-connection-cap",
      "acceptance": [
        "M0-10.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_app_smoke.py::test_hook_connections_past_the_cap_are_turned_away green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        }
      ],
      "scope_sha256": "8c8d658b9c85415f2d4ecfd659c7c9a14bcf2ee727db7fc7ee97f9907d0ceda5",
      "red": {
        "mutation": "chatmon/app.py: 'if len(self._connections) >= MAX_CONNECTIONS:' -> 'if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_hook_connections_past_the_cap_are_turned_away",
        "observed_diagnostic": "_____________ test_hook_connections_past_the_cap_are_turned_away ______________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "a7218f90fb9f2129fe19047480f593ab651ca507358b0c0158cc3967621fe584"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-11-unparseable-remind",
      "acceptance": [
        "M0-11.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_cli.py::test_a_reminder_it_cant_read_says_so_and_exits_2 green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/cli.py",
          "sha256": "21065a95289bfd1884e7451c61cc059f6613f17c489835080d646edd0d9491ec"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        }
      ],
      "scope_sha256": "3d335ee66962c112e7445141cbd439b82d1d5ceb1d13c899d2876513c5948270",
      "red": {
        "mutation": "chatmon/cli.py: 'if command is None or command.kind != \"reminder\":' -> 'if command is None:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_reminder_it_cant_read_says_so_and_exits_2",
        "observed_diagnostic": "______________ test_a_reminder_it_cant_read_says_so_and_exits_2 _______________",
        "before": [
          {
            "path": "chatmon/cli.py",
            "sha256": "21065a95289bfd1884e7451c61cc059f6613f17c489835080d646edd0d9491ec"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/cli.py",
            "sha256": "0a0f31148091a20269ef65ffece5354ac3aaa58d2e3ea1dd7e0a962a205ba512"
          }
        ],
        "after": [
          {
            "path": "chatmon/cli.py",
            "sha256": "21065a95289bfd1884e7451c61cc059f6613f17c489835080d646edd0d9491ec"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-12-ask-sent",
      "acceptance": [
        "M0-12.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_cli.py::test_ask_opens_the_box_with_the_text_typed_in green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "21065a95289bfd1884e7451c61cc059f6613f17c489835080d646edd0d9491ec"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "edebefed1b6c2d9a88c152cbfe10589386bb0c33739a0af07c71acb8de1627f3"
        }
      ],
      "scope_sha256": "a3915128b9bf8804f864230ca324db6e2a6c0b7d7b8fe64eb2f8598f2aca8f34",
      "red": {
        "mutation": "chatmon/cli.py: 'return _send({\"type\": \"ask\", \"text\": \" \".join(args)})' -> 'return _send({\"type\": \"say\", \"text\": \" \".join(args)})'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_ask_opens_the_box_with_the_text_typed_in",
        "observed_diagnostic": "________________ test_ask_opens_the_box_with_the_text_typed_in ________________",
        "before": [
          {
            "path": "chatmon/cli.py",
            "sha256": "21065a95289bfd1884e7451c61cc059f6613f17c489835080d646edd0d9491ec"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/cli.py",
            "sha256": "c4e1a11c37438aa4a0e5c9d6fa0e33fa374732cbcf27b9e96a349ce0ff59ccfa"
          }
        ],
        "after": [
          {
            "path": "chatmon/cli.py",
            "sha256": "21065a95289bfd1884e7451c61cc059f6613f17c489835080d646edd0d9491ec"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-12-ask-prefilled",
      "acceptance": [
        "M0-12.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_app_smoke.py::test_chatmon_ask_opens_the_box_with_the_text_typed_in_and_the_keyboard green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "21065a95289bfd1884e7451c61cc059f6613f17c489835080d646edd0d9491ec"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "edebefed1b6c2d9a88c152cbfe10589386bb0c33739a0af07c71acb8de1627f3"
        }
      ],
      "scope_sha256": "a3915128b9bf8804f864230ca324db6e2a6c0b7d7b8fe64eb2f8598f2aca8f34",
      "red": {
        "mutation": "chatmon/app.py: 'self.open_ask(str(message.get(\"text\") or \"\"))' -> 'self.open_ask()'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_chatmon_ask_opens_the_box_with_the_text_typed_in_and_the_keyboard",
        "observed_diagnostic": "___ test_chatmon_ask_opens_the_box_with_the_text_typed_in_and_the_keyboard ____",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "86a716bd3bb812017eaead9bc1d898639c98b33d7d028ebc02dfa7b446f9ce6c"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-12-come-forward",
      "acceptance": [
        "M0-12.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_cli.py::test_on_windows_ask_lets_chatmon_come_forward_before_sending green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "21065a95289bfd1884e7451c61cc059f6613f17c489835080d646edd0d9491ec"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "edebefed1b6c2d9a88c152cbfe10589386bb0c33739a0af07c71acb8de1627f3"
        }
      ],
      "scope_sha256": "a3915128b9bf8804f864230ca324db6e2a6c0b7d7b8fe64eb2f8598f2aca8f34",
      "red": {
        "mutation": "chatmon/cli.py: 'return bool(ctypes.windll.user32.AllowSetForegroundWindow(ctypes.c_ulong(ASFW_ANY)))' -> 'return False'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_on_windows_ask_lets_chatmon_come_forward_before_sending",
        "observed_diagnostic": "________ test_on_windows_ask_lets_chatmon_come_forward_before_sending _________",
        "before": [
          {
            "path": "chatmon/cli.py",
            "sha256": "21065a95289bfd1884e7451c61cc059f6613f17c489835080d646edd0d9491ec"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/cli.py",
            "sha256": "18566621247c27074e41daca4a02eadb492ffa40702e836c8461cc606637cf64"
          }
        ],
        "after": [
          {
            "path": "chatmon/cli.py",
            "sha256": "21065a95289bfd1884e7451c61cc059f6613f17c489835080d646edd0d9491ec"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-12-status-brain",
      "acceptance": [
        "M0-12.A3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_cli.py::test_status_says_whether_its_running_the_brain_reminders_and_agents green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "21065a95289bfd1884e7451c61cc059f6613f17c489835080d646edd0d9491ec"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "edebefed1b6c2d9a88c152cbfe10589386bb0c33739a0af07c71acb8de1627f3"
        }
      ],
      "scope_sha256": "a3915128b9bf8804f864230ca324db6e2a6c0b7d7b8fe64eb2f8598f2aca8f34",
      "red": {
        "mutation": "chatmon/commands.py: 'return brain.with_options(dict((state.get(\"brain_options\") or {}).get(brain.name) or {})) if brain else None' -> 'return brain'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_status_says_whether_its_running_the_brain_reminders_and_agents",
        "observed_diagnostic": "_____ test_status_says_whether_its_running_the_brain_reminders_and_agents _____",
        "before": [
          {
            "path": "chatmon/commands.py",
            "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/commands.py",
            "sha256": "73284e6bacabb96a79267bf9f02a88a0bbf888be66e5bb3208211e191ecfac4c"
          }
        ],
        "after": [
          {
            "path": "chatmon/commands.py",
            "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M0-12-hooks-connect-all",
      "acceptance": [
        "M0-CLI.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m0/drill-spec.json",
        "--log",
        "docs/delivery/reports/m0/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "tests/drills/run.py in a temporary copy: tests/test_cli.py::test_hooks_lists_shows_connects_and_disconnects green, then red with the mutation, then green with the file's bytes restored (SHA-256 checked)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "ruff": "0.17.4",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m0/drills.log",
        "sha256": "9ab2314d57d992410fed406f01f2e7aa9b30c57caa8f475c0bb4713180785111"
      },
      "inputs": [
        {
          "path": "chatmon/cli.py",
          "sha256": "21065a95289bfd1884e7451c61cc059f6613f17c489835080d646edd0d9491ec"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        }
      ],
      "scope_sha256": "a76f2fb4e908e50f204b8c5830ffc7125101e4cd247a9ca9dd15bca8316f944b",
      "red": {
        "mutation": "chatmon/cli.py: 'chosen = [a for a in agents.AGENTS if (a.detected() if action == \"connect\" else a.connected())]' -> 'chosen = list(agents.AGENTS)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_hooks_lists_shows_connects_and_disconnects",
        "observed_diagnostic": "_______________ test_hooks_lists_shows_connects_and_disconnects _______________",
        "before": [
          {
            "path": "chatmon/cli.py",
            "sha256": "21065a95289bfd1884e7451c61cc059f6613f17c489835080d646edd0d9491ec"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/cli.py",
            "sha256": "980a98ed0409ec8e8db46008152f7ffb4d68c820337f867ae3a093846d665b1d"
          }
        ],
        "after": [
          {
            "path": "chatmon/cli.py",
            "sha256": "21065a95289bfd1884e7451c61cc059f6613f17c489835080d646edd0d9491ec"
          }
        ]
      },
      "reason": null
    }
  ],
  "checkpoint": {
    "scope_sha256": "e1683bb25e3678e58501861c957d0c2054f6fd664df982d0fbc55e134822d5e3",
    "inputs": [
      {
        "path": "chatmon/app.py",
        "sha256": "cb362e95ded4ed26fec1ab6df21e79566b7f214f84728e8de1ad327a0f4a588f"
      },
      {
        "path": "chatmon/asking.py",
        "sha256": "29bfd44a58aedb2889d5bf8c47cfbca6f986ae865c76a6cf4a6bb33f6cedbb25"
      },
      {
        "path": "chatmon/cli.py",
        "sha256": "21065a95289bfd1884e7451c61cc059f6613f17c489835080d646edd0d9491ec"
      },
      {
        "path": "chatmon/commands.py",
        "sha256": "0924736a7e086953bfede9543f82198ddf8287ed2767a4811e9280751a371a2f"
      },
      {
        "path": "chatmon/menus.py",
        "sha256": "229bd0231c8f4578104f8127605ea590f08a1ec816f20ed5050c50a4db97cd77"
      },
      {
        "path": "chatmon/messages.py",
        "sha256": "a3686eb3fd2c994c696f38da95faa5a54e6d1c6b930eba6b3714ed69b6fdade4"
      },
      {
        "path": "docs/delivery/ASSESSMENT.md",
        "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
      },
      {
        "path": "docs/delivery/ROADMAP.md",
        "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
      },
      {
        "path": "pyproject.toml",
        "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
      },
      {
        "path": "tests/conftest.py",
        "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
      },
      {
        "path": "tests/drills/run.py",
        "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
      },
      {
        "path": "tests/test_app_smoke.py",
        "sha256": "77430293f269c8d8a5ed123c8e63f0a4c7abc0f9fc5771743fed78a5d5a8507d"
      },
      {
        "path": "tests/test_asking.py",
        "sha256": "a3ad4e6fdc3aebefd4c4cec2d576f5ffbf512cbca6bd7a703f02f578b756a812"
      },
      {
        "path": "tests/test_cli.py",
        "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
      },
      {
        "path": "tests/test_commands.py",
        "sha256": "edebefed1b6c2d9a88c152cbfe10589386bb0c33739a0af07c71acb8de1627f3"
      },
      {
        "path": "tests/test_messages.py",
        "sha256": "7bcff51f3f042ba83e2dde1c5f94a6772cc201b81e3677fd8a410f239f2ec363"
      }
    ],
    "environment": {
      "platform": "windows",
      "tools": {
        "python": "3.14.10",
        "ruff": "0.17.4",
        "pytest": "9.2.0",
        "pyqt6": "6.11.0"
      }
    },
    "verified_tasks": [
      "T-M0-01",
      "T-M0-02",
      "T-M0-05",
      "T-M0-03",
      "T-M0-04",
      "T-M0-06",
      "T-M0-07",
      "T-M0-08",
      "T-M0-09",
      "T-M0-10",
      "T-M0-11",
      "T-M0-12",
      "T-M0-CLI"
    ],
    "pending_operations": [
      {
        "id": "CI-posix",
        "description": "The POSIX-only checks (test_the_log_file_is_yours_alone for M0-13, test_chatmon_ask_from_a_terminal_reaches_it for M0-12) and the whole suite on ubuntu and macos run only in CI",
        "next_action": "Coordinator: push the merged branch so CI runs all three OSes; send any failure back to M0"
      }
    ],
    "next_action": "Wave 2 (M7): wire the integration notes. M1B: add ChatBook.listing() so T-M0-03-light can be done. After CI on ubuntu and macos, record T-M0-13's receipt and close.",
    "source_revision": "a0a24fa6601b5ed7ebed80ed4b31b2c854a42bf8"
  }
}
```
