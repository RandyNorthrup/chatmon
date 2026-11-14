# M7: integration

The work unit for items M7-01 to M7-13 of [ASSESSMENT.md](ASSESSMENT.md#m7-integration-apppy-settingswinpy-clipy-wiring-after-wave-1),
and for every integration note the merged wave-1 plans address to M7 or "the app": [M0](m0-app-core.md#integration-notes),
[M1A](m1a-security-updates.md#integration-notes), [M1B](m1b-brains-and-stored-data.md#integration-notes),
[M2](m2-bubbles-askbox.md#integration-notes) and [M5](m5-reminders-offline-locale.md#integration-notes). Ordered and
bounded by [ROADMAP.md](ROADMAP.md). Branch `wave2/m7`, from `improve/assessment-fixes` at `4827b0c`, with `81af7c7`
merged. Reports, logs and the ledger's generator are in [reports/m7](reports/m7/).

## Rationale

Wave 1 delivered the pieces (streaming, keys and brain tests, the reminder book's due/acknowledge/snooze, the
message queue, safe bubbles with Copy and Stop, phrase data) and left them unwired, because only `app.py`,
`settingswin.py` and `cli.py` can join them. M7 joins them, and adds what exists only at the app level: the
Accessibility tab, the Chats window, quick actions, missed messages, the focus summary and the first-unlock hello.

**Scope.** Owned: `chatmon/app.py`, `settingswin.py`, `cli.py`, `menus.py`, `messages.py`, `asking.py`,
`commands.py`, new `chatmon/chatswin.py`, `settings.py` (defaults for new keys; M1B is done), and their tests (new
files `tests/app_harness.py`, `test_app_answers.py`, `test_app_reminders.py`, `test_app_m7.py`,
`test_settingswin.py`, `test_chatswin.py`). Small wiring changes in merged modules, each asked for by a note and
listed under [Changes outside M7's files](#changes-outside-m7s-files).

**Non-goals.** README, `changelog.md` and the version (the consolidation's; notes below). Translation (M8).
Anything needing M3's, M4A's or M4B's APIs is built up to one call and finished when those branches are merged
(see [Waiting for M3 and M4](#waiting-for-m3-and-m4)). No new runtime dependencies.

### The coordinator's CI finding (done first)

Windows CI (runs 43638268829 and 43638815195) failed `test_greets_and_reacts_to_agents`,
`test_a_bubble_with_buttons_waits_for_no_agent_and_comes_back_after_an_alert`,
`test_a_system_update_check_that_hangs_is_stopped_and_counts_as_none`, and on one leg each
`test_the_days_updates_heads_up_waits_for_a_bubble_showing_instead_of_going_unsaid` and
`test_bubble_styles.py::test_the_ask_box_settles_and_wakes`.

- **Cause of the four smoke failures: the tests read the runner's desktop.** The smoke companion used the real
  `presence.Desk`. On the runner the desktop reports quiet (`SHQueryUserNotificationState` or Focus), so from the
  first `_check_quiet` (five seconds in) every bubble from the background was held: what showed before five
  seconds passed, what came after never did. Reproduced here at the same three lines by having the desktop report
  quiet ([ci-quiet-repro.log](reports/m7/ci-quiet-repro.log)); fixed by giving each smoke companion a desk of the
  test's own, and pinned by `test_the_computer_the_tests_run_on_holds_nothing_back`
  ([ci-quiet-fixed.log](reports/m7/ci-quiet-fixed.log)). Nothing was made to wait longer.
- **Cause of the ask-box failure: a real Windows bug.** `time.monotonic()` moves in steps of about 15 ms there.
  Woken by new words, the box's effects rise from strength 0, and at that same instant the strength was still 0,
  so `_run_frames` decided there was nothing to draw and the frames never started: on Windows the box didn't
  move again after new words. It now draws while the effects play (`Effects.playing`), not while their strength
  is above 0; pinned by a test with the clock standing still. The stage's own bubble wasn't affected (it looks
  again every frame).
- **The queue suspect was real but separate.** `MessageQueue` looked only at its best-placed message: when that one
  couldn't push aside the bubble on screen, newer news of the bubble on screen, or the answer to something you just
  did, waited until it closed. `next()` and `wake_at()` now consider every ready message in order. The suspect that
  `_takes_over` checks the minimum before `_same` is the documented design (a flurry of background news of one
  thing can't flash past), kept: with the fix it shows once the minimum is up.

### Re-checked findings and notes

- **`ChatBook.listing` was never delivered** (M0's note 5 expected it from M1B). M7 adds it to `chats.py`: each chat's
  id, title, time and pin, cached per file by modification time and size, without keeping or copying messages.
- **`events.request` was never delivered** (M0's note 4 expected it from M1A). M7 adds it to `events.py`, with
  `winpipe.deliver` taking an optional buffer for the reply on Windows: the one JSON line the companion writes
  before its `ok`. Same owner checks, same pipe handle.
- **M5's phrase ids differ from `commands.PHRASES`'** ("new chat", "stop focus" against "new-chat", "stop-focus"),
  so M0's note 6 ("M5's data uses the ids in `commands.PHRASES`") doesn't hold. The command table now takes M5's
  phrases and ids (`offline.phrases()`), which M5's note asks for anyway; `commands.PHRASES` goes.
- **A fired focus session would hold bubbles forever.** `ReminderBook.fire` keeps what fired until acknowledged, and
  `focus()` returns a fired one too: the app acknowledges a focus session as it ends.
- **Brains: the status worker keeps waiting for the brain** (M0's note 7 asks to switch it too). It runs off the
  screen's thread already, and *status* should say the settled answer, so it keeps `wait=True`; only `submit`, on
  the screen's thread, moves to `brains.Finder`.
- **Streaming: `append_partial` and a question waiting.** The box draws streamed text after the whole transcript;
  with a second question waiting, that text follows the waiting question's line until the answer is complete and
  the chat is drawn again. Accepted for the rare case (one question can wait) rather than drawing the whole chat
  for every piece, which would also move the reader.

### Design

- **Answers (M7-01).** `asking.Question` gains `partial` and `started`; `Asker.partial` adds to it and to the box
  (`append_partial`); every redraw of the chat hands the box the text so far (`set_partial`). Closing the box no
  longer cancels: the answer finishes, is kept, and a bubble "<brain> answered" with **Read** reopens the chat.
  `set_busy(label, started)` from the moment a question goes (a summing-up step too) to its end. **Stop** cancels;
  what came so far stays in the chat marked as stopped, or the question goes back in the box if nothing came.
  Leaving the chat still drops its question, as before.
- **Failures (M7-02).** A failed question goes back in the box as before, and a bubble offers **Try again**, **Ask
  <next brain>** (the next one Automatic would pick, else one with a key) and **Settings**. A brain picked in the
  menu that isn't available is announced once per pick. After naming, the welcome says which brain will answer, or
  how to set one up. A model server here that isn't yours is offered once (M1B's note 6); confirmed servers are kept
  in state as `trusted_servers` and handed back at start.
- **Settings (M7-03).** The window stays a form that emits `saved`; a key typed for an API brain is handed back as
  `api_key` and saved by the app with `keychain.set` (never into state or `config.toml`), **Remove key** with
  `keychain.delete`, and **Test** asks the app (`test_requested`) to run `brain.test()` with the typed key and
  shows the result. New Accessibility tab: text size, how long bubbles stay (Normal, Longer, Much longer, Until I
  close them), sounds (one switch, volume, alerts on and the rest off by default, as the owner decided), the
  hotkey, reduced motion (follow the system, always, never), the accessible ask box, and read aloud (moved from
  General). New settings, with defaults in `settings.py` and the template: `[reminders] snooze_minutes`,
  `[accessibility] text_scale, bubble_time, reduced_motion, accessible_ask_box`, `[sound] enabled, volume, cues`,
  `hotkey`, `follow_pointer_screen`. The updates timer is kept and given the new interval on reload. "Almost
  empty" is kept below "low" by the window and by the app for the file.
- **Reminders (M7-04).** `_check_reminders` uses `fire`; at start `due` is shown again. One alert per reminder,
  keyed `reminder:<id>`: **Done** (`acknowledge`), **Snooze <own>** and **Later** (a bubble of every
  `snooze_choices`). The menu gives each reminder **Edit…** (the box prefilled, read with `parse_when`, applied with
  `update`), **Repeat** (rules described by `describe_repeat`, or Never) and **Cancel**. Saved after each change.
  `pop_due` and its test are deleted, as M5 asks.
- **Focus (M7-05).** At a session's end the plain bubbles it held become one "While you focused" bubble
  (`MessageQueue.take`); ones with buttons stay queued and follow.
- **Missed messages (M7-06).** Shown bubbles are kept in a short list (`Recent messages` in the menu shows them
  again). A bubble that timed out while you were away, or a plain one the queue dropped, counts as missed; a click
  on the chatmon brings it back.
- **Agents (M7-07).** Agent states (M5's `agents_report`, plain) go in the tray's tooltip and the stage window's
  accessible name; a needs-you puts a dot on the tray icon. The *agents* command answers with the report.
  `handle()` answers `{"type": "status"}` with the live states, which `chatmon status` prints.
- **Quick actions (M7-08).** A **Clipboard** submenu: Explain, Summarize, Translate (into the desktop's language),
  Fix. Each reads the clipboard only when chosen, attaches it, and opens the box with the prompt typed in.
- **Chats (M7-09).** New `chatswin.py`: a window with a search field (titles at once, words inside chats a moment
  after typing stops) and a list, with Carry on, Rename, Instructions, Pin, Save as Markdown, Delete and Ask another
  brain; it emits what was chosen and the app does it. The Chats menu keeps New chat, Rename, the most recent chats
  (one item each: carry on) and **All chats…**. Brain per chat as M1B's note 8; backup and bring-back in Settings
  (M1B's note 11).
- **Copy and keys (M7-10).** `copy_requested` goes to `_copy` (the overlay's clipboard where it draws one). Ctrl+1 to
  Ctrl+9 in the box press a bubble's buttons. A bubble with buttons that closed without being answered stays
  answerable by typing for `ANSWERABLE_FOR`.
- **Platform (M7-11).** Lock from logind and Hyprland stops drawing; the power saver reaches the bubble and the box;
  a palette change sets the styles again and reduced motion reaches the box. Sound: `_cue(name)` decides (the
  switch, the cue, not during quiet or focus) and calls `sound.play` when M4B's module exists.
- **New chat after 15 minutes (M7-12).** Not while a question is on its way. The empty box says "New chat · carry on
  with the last one"; *carry on* goes back to it.
- **Hello (M7-13).** The first unlock each day (and the first start of the day): one bubble with today's reminders,
  agents waiting and updates pending, if there are any.

### Changes outside M7's files

| File | Change | Asked for by |
|---|---|---|
| `chatmon/bubble.py` | `Effects.playing`; the ask box draws while effects play (CI finding) | Coordinator, 2026-11-14 |
| `chatmon/chats.py` | `ChatBook.listing`; dates through `localefmt` | M0 note 5; M5 (localefmt) |
| `chatmon/events.py`, `chatmon/winpipe.py` | `events.request`; `winpipe.deliver(..., reply=None)` | M0 note 4 |
| `chatmon/reminders.py` | `pop_due` deleted | M5 (step 6) |
| `tests/test_reminders.py` | `pop_due`'s test deleted | M5 (step 6) |
| `tests/test_bubble_styles.py` | the coarse-clock test | Coordinator, 2026-11-14 |

### Waiting for M3 and M4

Built to one call, finished when the coordinator says the branch is merged: the stage badge (M3-13,
`stage.set_badge`), reduced motion in the stage (`set_reduced_motion`), the unhosted ask box with a screen reader,
following the pointer's monitor (`follow_pointer_screen`), macOS sleep stopping drawing (M4A), live high-contrast
and reduced-motion events (M4A), sound playback (`sound.play`, M4B), toasts in place of balloons (`wintoast.show`,
M4B) and the hotkey (`hotkey.register`, M4B).

## Verification

- Gates: `python -m pytest -q -p no:cacheprovider` (the whole suite, one run at a time) and `ruff check .` before every
  commit; logs in [reports/m7](reports/m7/).
- Every acceptance criterion has behavior tests in the project's style (real Qt objects, offscreen) and at least one
  red drill in [drill-spec.json](reports/m7/drill-spec.json), run by `tests/drills/run.py` in a temporary copy.
- The smoke companion fixture moves to `tests/app_harness.py` (`make_companion`), shared by the new app test files;
  it gives every companion its own desk and an in-memory keychain (M1B's note 14), so no test reads the computer's
  desktop state or keychain.

## Integration notes

None yet.

## Changelog notes

Filled in from what shipped.

## README notes

Filled in from what shipped.

```quality-ledger
{
  "schema_version": 1,
  "work": {
    "id": "M7",
    "title": "Integration: wiring wave 1 into the app, the settings window and the command line",
    "scope_revision": 1,
    "brief": "docs/delivery/ASSESSMENT.md",
    "brief_reason": null,
    "rules": [
      {
        "path": "docs/delivery/ROADMAP.md",
        "revision": "81af7c7"
      },
      {
        "path": "pyproject.toml",
        "revision": "81af7c7"
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
        "pytest": "9.2.0",
        "PyQt6": "6.11.0",
        "ruff": "0.17.4"
      }
    }
  },
  "requirements": [
    {
      "id": "M7-CI",
      "statement": "Windows CI's failing smoke and ask-box tests pass for the right reason (coordinator's finding)",
      "priority": "critical",
      "acceptance": [
        "AC-CI-1",
        "AC-CI-2",
        "AC-CI-3"
      ],
      "superseded_by": null
    },
    {
      "id": "M7-01",
      "statement": "Answers stream in, finish after the box closes, and can be stopped",
      "priority": "critical",
      "acceptance": [
        "AC-01-1",
        "AC-01-2",
        "AC-01-3"
      ],
      "superseded_by": null
    },
    {
      "id": "M7-02",
      "statement": "Failures say what to do next, and which brain answers is never a surprise",
      "priority": "critical",
      "acceptance": [
        "AC-02-1",
        "AC-02-2",
        "AC-02-3",
        "AC-02-4"
      ],
      "superseded_by": null
    },
    {
      "id": "M7-03",
      "statement": "The settings window covers keys, a test, accessibility, reminders' snooze, and applies at once",
      "priority": "critical",
      "acceptance": [
        "AC-03-1",
        "AC-03-2",
        "AC-03-3",
        "AC-03-4",
        "AC-03-5"
      ],
      "superseded_by": null
    },
    {
      "id": "M7-04",
      "statement": "Reminders wait until done or snoozed, can be edited and repeat, across restarts",
      "priority": "critical",
      "acceptance": [
        "AC-04-1",
        "AC-04-2",
        "AC-04-3",
        "AC-04-4"
      ],
      "superseded_by": null
    },
    {
      "id": "M7-05",
      "statement": "A focus session ends with one summary of what waited",
      "priority": "normal",
      "acceptance": [
        "AC-05-1"
      ],
      "superseded_by": null
    },
    {
      "id": "M7-06",
      "statement": "Missed messages can be brought back",
      "priority": "normal",
      "acceptance": [
        "AC-06-1",
        "AC-06-2"
      ],
      "superseded_by": null
    },
    {
      "id": "M7-07",
      "statement": "Agents at a glance",
      "priority": "normal",
      "acceptance": [
        "AC-07-1",
        "AC-07-2",
        "AC-07-3"
      ],
      "superseded_by": null
    },
    {
      "id": "M7-08",
      "statement": "Quick actions on the clipboard",
      "priority": "normal",
      "acceptance": [
        "AC-08-1"
      ],
      "superseded_by": null
    },
    {
      "id": "M7-09",
      "statement": "Chats: a window with search, a brain per chat, another brain, backup",
      "priority": "critical",
      "acceptance": [
        "AC-09-1",
        "AC-09-2",
        "AC-09-3",
        "AC-09-4"
      ],
      "superseded_by": null
    },
    {
      "id": "M7-10",
      "statement": "Copy and keys",
      "priority": "normal",
      "acceptance": [
        "AC-10-1",
        "AC-10-2",
        "AC-10-3"
      ],
      "superseded_by": null
    },
    {
      "id": "M7-11",
      "statement": "Platform wiring that wave 1 made possible",
      "priority": "normal",
      "acceptance": [
        "AC-11-1",
        "AC-11-2",
        "AC-11-3"
      ],
      "superseded_by": null
    },
    {
      "id": "M7-12",
      "statement": "A new chat after 15 idle minutes says so",
      "priority": "normal",
      "acceptance": [
        "AC-12-1"
      ],
      "superseded_by": null
    },
    {
      "id": "M7-13",
      "statement": "A first-unlock hello",
      "priority": "normal",
      "acceptance": [
        "AC-13-1"
      ],
      "superseded_by": null
    },
    {
      "id": "INT-M0",
      "statement": "M0's integration notes: phrases, non-blocking brain, connections, foreground",
      "priority": "normal",
      "acceptance": [
        "AC-M0-6",
        "AC-M0-7",
        "AC-M0-8",
        "AC-M0-10"
      ],
      "superseded_by": null
    },
    {
      "id": "INT-M1B",
      "statement": "M1B's integration notes: brains that read files, settings problems, damaged files, test isolation",
      "priority": "critical",
      "acceptance": [
        "AC-M1B-7",
        "AC-M1B-9",
        "AC-M1B-10"
      ],
      "superseded_by": null
    },
    {
      "id": "INT-M2",
      "statement": "M2's integration notes: More, remembered size, hint, line breaks",
      "priority": "normal",
      "acceptance": [
        "AC-M2-1"
      ],
      "superseded_by": null
    },
    {
      "id": "INT-M5",
      "statement": "M5's integration notes outside reminders: dates in chats follow the locale",
      "priority": "low",
      "acceptance": [
        "AC-M5-1"
      ],
      "superseded_by": null
    }
  ],
  "acceptance": [
    {
      "id": "AC-CI-1",
      "requirement": "M7-CI",
      "given": "The computer the tests run on reports a full-screen app, a presentation or reduced motion",
      "when": "A smoke test's companion runs",
      "then": "Bubbles from the background show and it walks: its desk readings are the test's own",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-CI-2",
      "requirement": "M7-CI",
      "given": "A bubble showing, and a better-placed message waiting that can't push it aside",
      "when": "Newer news of the bubble showing, or something you did, arrives",
      "then": "It takes over (after the minimum, if it came on its own); nothing waits behind what can't show",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-CI-3",
      "requirement": "M7-CI",
      "given": "The ask box's effects have settled and the clock hasn't moved since it woke",
      "when": "New words arrive",
      "then": "Its frames start, rising from the still picture",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-01-1",
      "requirement": "M7-01",
      "given": "A brain streams an answer",
      "when": "Pieces arrive, the box is redrawn, closed and opened again",
      "then": "The text so far shows under the question, in order, and survives each redraw",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-01-2",
      "requirement": "M7-01",
      "given": "A question on its way",
      "when": "The ask box is closed",
      "then": "The answer still arrives, is kept in the chat, and a bubble '<brain> answered' with Read opens the box at it",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-01-3",
      "requirement": "M7-01",
      "given": "A question on its way",
      "when": "It's sent, answered, fails or Stop is pressed",
      "then": "The box shows who is answering and for how long while it's on its way; Stop cancels it, keeps what came so far (or puts the question back), and the question waiting goes",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-02-1",
      "requirement": "M7-02",
      "given": "A question failed",
      "when": "The failure arrives (box open or closed)",
      "then": "A bubble offers Try again, Ask <next brain> and Settings, and each does that",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-02-2",
      "requirement": "M7-02",
      "given": "The brain picked in the menu isn't available",
      "when": "Questions are asked",
      "then": "The fallback is announced once, not on every question, and again after the pick changes",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-02-3",
      "requirement": "M7-02",
      "given": "The first run",
      "when": "The chatmon is named",
      "then": "It says which brain will answer, or how to set one up",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-02-4",
      "requirement": "M7-02",
      "given": "A model server is running here that isn't yours, and nothing else answers",
      "when": "A question is asked",
      "then": "It offers 'Use the model server at host:port?' once; Use it confirms it and keeps it for later starts",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-03-1",
      "requirement": "M7-03",
      "given": "An API brain is chosen in the AI tab",
      "when": "A key is typed and Saved, removed, or Test is pressed",
      "then": "The key goes to the keychain (never state or config.toml) or is removed, and Test shows the time taken or the error",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-03-2",
      "requirement": "M7-03",
      "given": "The Accessibility tab",
      "when": "Text size, how long bubbles stay (until I close them included), sounds and volume, the hotkey, reduced motion and the accessible ask box are set and saved",
      "then": "They're kept, and text size, bubble timing and reduced motion apply at once",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-03-3",
      "requirement": "M7-03",
      "given": "Reminders",
      "when": "Their snooze is set in the window or reminders.snooze_minutes",
      "then": "Reminder snoozes use it; breaks keep their own",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-03-4",
      "requirement": "M7-03",
      "given": "Chatmon runs",
      "when": "The update-check interval is changed",
      "then": "The timer takes the new interval without a restart",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-03-5",
      "requirement": "M7-03",
      "given": "Battery warnings",
      "when": "'Almost empty' is set at or above 'low'",
      "then": "It's kept below 'low', in the window and from the file",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-04-1",
      "requirement": "M7-04",
      "given": "A reminder comes due",
      "when": "Its bubble shows",
      "then": "It's an alert keyed reminder:<id> with Done, Snooze <own> and Later; Done acknowledges (a repeat moves on), snoozes put it off; saved each time",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-04-2",
      "requirement": "M7-04",
      "given": "Reminders fired and not done when Chatmon quit",
      "when": "It starts",
      "then": "Each is shown again; a focus session that ended is over, not held",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-04-3",
      "requirement": "M7-04",
      "given": "A reminder in the menu",
      "when": "Edit, Repeat or Cancel is chosen",
      "then": "Edit opens the box prefilled and applies new words or time; Repeat sets a described rule or Never",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-04-4",
      "requirement": "M7-04",
      "given": "A reminder is added in the box, by a script or by chatmon remind",
      "when": "It repeats, or its time is unclear",
      "then": "The repeat is kept and described; an unclear time is explained (the CLI prints it and exits 2)",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-05-1",
      "requirement": "M7-05",
      "given": "Bubbles from the background held during a focus session",
      "when": "The session ends (or is stopped)",
      "then": "One 'While you focused' bubble lists the plain ones; ones with buttons follow in turn; nothing is lost",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-06-1",
      "requirement": "M7-06",
      "given": "Bubbles were shown",
      "when": "Recent messages is opened from the menu",
      "then": "It lists them, and picking one shows it again",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-06-2",
      "requirement": "M7-06",
      "given": "A bubble timed out while you were away, or was dropped",
      "when": "You click the chatmon",
      "then": "It's brought back",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-07-1",
      "requirement": "M7-07",
      "given": "Agents working or needing you",
      "when": "Their state changes",
      "then": "The tray's tooltip and the stage's accessible name say each one's state, and the tray icon has a badge while one needs you",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-07-2",
      "requirement": "M7-07",
      "given": "Agents working or waiting",
      "when": "agents is asked",
      "then": "Each agent's state and for how long is answered here",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-07-3",
      "requirement": "M7-07",
      "given": "Chatmon running, with agents' states",
      "when": "chatmon status is run",
      "then": "It prints the live states from the running Chatmon (its own status answer); not running, what's on disk",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-08-1",
      "requirement": "M7-08",
      "given": "Text or a picture on the clipboard",
      "when": "Explain, Summarize, Translate or Fix is chosen",
      "then": "The clipboard is attached then (never before) and the box opens with that prompt typed in",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-09-1",
      "requirement": "M7-09",
      "given": "Saved chats",
      "when": "Chats is opened",
      "then": "A window lists them with search (titles and words in them) and carries on, renames, pins, saves and deletes; the menu shows recent chats and All chats, not a submenu per chat",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-09-2",
      "requirement": "M7-09",
      "given": "A chat answered by one brain",
      "when": "It's carried on, or Ask another brain is chosen",
      "then": "It goes to the chat's brain; another brain is asked the last question with the history before it, and its answer kept as its own",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-09-3",
      "requirement": "M7-09",
      "given": "Settings",
      "when": "Back up or Bring back is chosen",
      "then": "A zip is written and its contents said; a backup is checked, its contents confirmed, brought back and everything read again",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-09-4",
      "requirement": "M7-09",
      "given": "Many saved chats",
      "when": "The menu or window lists them",
      "then": "Only each chat's id, title, time and pin are read (cached by file), never copies of every message",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-10-1",
      "requirement": "M7-10",
      "given": "An answer or code block",
      "when": "Copy is clicked",
      "then": "Its text is on the clipboard (the overlay's own where Chatmon draws one)",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-10-2",
      "requirement": "M7-10",
      "given": "A bubble with buttons and the ask box open",
      "when": "Ctrl+1 to Ctrl+9 is pressed",
      "then": "That button is pressed",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-10-3",
      "requirement": "M7-10",
      "given": "A bubble with buttons that expired or was closed",
      "when": "A button's label is typed in the box",
      "then": "It's pressed within ANSWERABLE_FOR, and not after",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-11-1",
      "requirement": "M7-11",
      "given": "The session locks (logind, Hyprland) or the power saver is on",
      "when": "Chatmon hears it",
      "then": "Nothing is drawn while locked; the bubble and the ask box show their still pictures while saving power",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-11-2",
      "requirement": "M7-11",
      "given": "The desktop's colours or reduced motion change",
      "when": "Chatmon hears it",
      "then": "The bubble styles are set again at once and the ask box stops fading",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-11-3",
      "requirement": "M7-11",
      "given": "Sound settings (alerts only by default)",
      "when": "A cue is due",
      "then": "It plays only when sound is on, the cue is on, and it isn't Do Not Disturb, Focus or full screen; one call to sound.play once M4B lands",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-12-1",
      "requirement": "M7-12",
      "given": "A chat last used over 15 minutes ago",
      "when": "The box opens",
      "then": "A new chat says 'New chat · carry on with the last one', and carry on goes back to it; a question on its way is never dropped by this",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-13-1",
      "requirement": "M7-13",
      "given": "Today's reminders, agents waiting or updates pending",
      "when": "The screen is unlocked the first time today",
      "then": "One bubble names them; not again that day; nothing to say, no bubble",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M0-6",
      "requirement": "INT-M0",
      "given": "Commands in M5's phrase data",
      "when": "A phrase is typed",
      "then": "The command table finds it by M5's ids; help is offline.help_text",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M0-7",
      "requirement": "INT-M0",
      "given": "Model servers not yet looked at",
      "when": "A question is submitted",
      "then": "The box never waits for the brain: it's looked for off the screen's thread, then asked",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M0-8",
      "requirement": "INT-M0",
      "given": "A connection to Chatmon's pipe on Windows",
      "when": "It's accepted",
      "then": "A connection from a process that isn't yours is aborted",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M0-10",
      "requirement": "INT-M0",
      "given": "chatmon ask on Windows with Chatmon running",
      "when": "It runs",
      "then": "Only Chatmon's own process is allowed to come forward when its id is known",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M1B-7",
      "requirement": "INT-M1B",
      "given": "A brain that can read files",
      "when": "It's asked in a chat other brains answered",
      "then": "It gets only its own answers and a summary made from them; a summary made for it is marked as such",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M1B-9",
      "requirement": "INT-M1B",
      "given": "config.toml or Settings with wrong values",
      "when": "Chatmon starts or reloads",
      "then": "Each wrong setting is named and the rest apply; an unreadable file says the defaults are used",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M1B-10",
      "requirement": "INT-M1B",
      "given": "A damaged state or memory file was recovered",
      "when": "Chatmon starts",
      "then": "A bubble says what happened",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M2-1",
      "requirement": "INT-M2",
      "given": "A cut-short bubble, the bigger box, a multi-line question",
      "when": "More is pressed, the box is made bigger and reopened, a question with line breaks is asked",
      "then": "More opens the whole text in the box; the size is remembered; the hint says Shift+Enter; the question keeps its lines",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M5-1",
      "requirement": "INT-M5",
      "given": "A chat's date and 'today 3:04 PM'",
      "when": "They're shown",
      "then": "They follow the locale's clock and dates (localefmt)",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    }
  ],
  "tasks": [
    {
      "id": "TASK-CI",
      "purpose": "Isolate smoke companions from the host desktop; queue considers every ready message; ask box draws while effects play",
      "acceptance": [
        "AC-CI-1",
        "AC-CI-2",
        "AC-CI-3"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/messages.py",
          "action": "modify"
        },
        {
          "path": "chatmon/bubble.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_smoke.py",
          "action": "modify"
        },
        {
          "path": "tests/test_messages.py",
          "action": "modify"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "action": "modify"
        }
      ],
      "status": "implemented",
      "evidence": [
        "RDY-1"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-HARNESS",
      "purpose": "Share the smoke companion fixture (and an in-memory keychain) with the new app test files",
      "acceptance": [
        "AC-CI-1"
      ],
      "depends_on": [
        "TASK-CI"
      ],
      "changes": [
        {
          "path": "tests/app_harness.py",
          "action": "create"
        },
        {
          "path": "tests/test_app_smoke.py",
          "action": "modify"
        }
      ],
      "status": "planned",
      "evidence": [
        "RDY-1"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-ANSWERS",
      "purpose": "Stream partial answers, keep answering after the box closes, busy row and Stop",
      "acceptance": [
        "AC-01-1",
        "AC-01-2",
        "AC-01-3"
      ],
      "depends_on": [
        "TASK-HARNESS"
      ],
      "changes": [
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "chatmon/asking.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_answers.py",
          "action": "create"
        },
        {
          "path": "tests/test_asking.py",
          "action": "modify"
        }
      ],
      "status": "planned",
      "evidence": [
        "RDY-1"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-FAILURES",
      "purpose": "Failure bubble, fallback announced once, first-run brain line, non-blocking brain lookup, untrusted server offer",
      "acceptance": [
        "AC-02-1",
        "AC-02-2",
        "AC-02-3",
        "AC-02-4",
        "AC-M0-7"
      ],
      "depends_on": [
        "TASK-ANSWERS"
      ],
      "changes": [
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_answers.py",
          "action": "modify"
        }
      ],
      "status": "planned",
      "evidence": [
        "RDY-1"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-CONTEXT",
      "purpose": "Own-only history for brains that read files; brain per chat; ask another brain",
      "acceptance": [
        "AC-M1B-7",
        "AC-09-2"
      ],
      "depends_on": [
        "TASK-FAILURES"
      ],
      "changes": [
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "chatmon/asking.py",
          "action": "modify"
        },
        {
          "path": "chatmon/menus.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_answers.py",
          "action": "modify"
        }
      ],
      "status": "planned",
      "evidence": [
        "RDY-1"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-SETTINGS",
      "purpose": "Settings window: key and Test, Accessibility tab, reminders' snooze, battery order; live update interval",
      "acceptance": [
        "AC-03-1",
        "AC-03-2",
        "AC-03-3",
        "AC-03-4",
        "AC-03-5"
      ],
      "depends_on": [
        "TASK-HARNESS"
      ],
      "changes": [
        {
          "path": "chatmon/settingswin.py",
          "action": "modify"
        },
        {
          "path": "chatmon/settings.py",
          "action": "modify"
        },
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "tests/test_settingswin.py",
          "action": "create"
        },
        {
          "path": "tests/test_settings.py",
          "action": "modify"
        }
      ],
      "status": "planned",
      "evidence": [
        "RDY-1"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-STARTUP",
      "purpose": "Per-setting problems with overrides and brains coerced; damaged files said at start",
      "acceptance": [
        "AC-M1B-9",
        "AC-M1B-10"
      ],
      "depends_on": [
        "TASK-SETTINGS"
      ],
      "changes": [
        {
          "path": "chatmon/settings.py",
          "action": "modify"
        },
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_m7.py",
          "action": "create"
        }
      ],
      "status": "planned",
      "evidence": [
        "RDY-1"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-REMINDERS",
      "purpose": "Reminder alerts with Done and snoozes, restored at start, Edit and Repeat in the menu, repeats when adding, pop_due gone",
      "acceptance": [
        "AC-04-1",
        "AC-04-2",
        "AC-04-3",
        "AC-04-4"
      ],
      "depends_on": [
        "TASK-SETTINGS"
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
          "path": "chatmon/menus.py",
          "action": "modify"
        },
        {
          "path": "chatmon/cli.py",
          "action": "modify"
        },
        {
          "path": "chatmon/reminders.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_reminders.py",
          "action": "create"
        },
        {
          "path": "tests/test_reminders.py",
          "action": "modify"
        },
        {
          "path": "tests/test_cli.py",
          "action": "modify"
        }
      ],
      "status": "planned",
      "evidence": [
        "RDY-1"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-FOCUS",
      "purpose": "One 'While you focused' summary at a focus session's end",
      "acceptance": [
        "AC-05-1"
      ],
      "depends_on": [
        "TASK-REMINDERS"
      ],
      "changes": [
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "chatmon/messages.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_reminders.py",
          "action": "modify"
        },
        {
          "path": "tests/test_messages.py",
          "action": "modify"
        }
      ],
      "status": "planned",
      "evidence": [
        "RDY-1"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-MISSED",
      "purpose": "Recent messages menu and bringing back missed bubbles",
      "acceptance": [
        "AC-06-1",
        "AC-06-2"
      ],
      "depends_on": [
        "TASK-HARNESS"
      ],
      "changes": [
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "chatmon/menus.py",
          "action": "modify"
        },
        {
          "path": "chatmon/messages.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_m7.py",
          "action": "modify"
        }
      ],
      "status": "planned",
      "evidence": [
        "RDY-1"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-AGENTS",
      "purpose": "Agent states in the tray and the stage's name, a badge, the agents command, live states in chatmon status",
      "acceptance": [
        "AC-07-1",
        "AC-07-2",
        "AC-07-3"
      ],
      "depends_on": [
        "TASK-COMMANDS"
      ],
      "changes": [
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "chatmon/cli.py",
          "action": "modify"
        },
        {
          "path": "chatmon/events.py",
          "action": "modify"
        },
        {
          "path": "chatmon/winpipe.py",
          "action": "modify"
        },
        {
          "path": "chatmon/commands.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_m7.py",
          "action": "modify"
        },
        {
          "path": "tests/test_cli.py",
          "action": "modify"
        }
      ],
      "status": "planned",
      "evidence": [
        "RDY-1"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-QUICK",
      "purpose": "Clipboard quick actions",
      "acceptance": [
        "AC-08-1"
      ],
      "depends_on": [
        "TASK-HARNESS"
      ],
      "changes": [
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "chatmon/menus.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_m7.py",
          "action": "modify"
        }
      ],
      "status": "planned",
      "evidence": [
        "RDY-1"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-CHATS",
      "purpose": "Chats window with search, light listing, menu of recent chats, backup in Settings, locale dates",
      "acceptance": [
        "AC-09-1",
        "AC-09-3",
        "AC-09-4",
        "AC-M5-1"
      ],
      "depends_on": [
        "TASK-CONTEXT",
        "TASK-SETTINGS"
      ],
      "changes": [
        {
          "path": "chatmon/chats.py",
          "action": "modify"
        },
        {
          "path": "chatmon/chatswin.py",
          "action": "create"
        },
        {
          "path": "chatmon/menus.py",
          "action": "modify"
        },
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "chatmon/settingswin.py",
          "action": "modify"
        },
        {
          "path": "tests/test_chatswin.py",
          "action": "create"
        },
        {
          "path": "tests/test_chats.py",
          "action": "modify"
        }
      ],
      "status": "planned",
      "evidence": [
        "RDY-1"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-KEYS",
      "purpose": "Copy wired; Ctrl+1-9; typed labels after a bubble closed",
      "acceptance": [
        "AC-10-1",
        "AC-10-2",
        "AC-10-3"
      ],
      "depends_on": [
        "TASK-HARNESS"
      ],
      "changes": [
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_m7.py",
          "action": "modify"
        }
      ],
      "status": "planned",
      "evidence": [
        "RDY-1"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-PLATFORM",
      "purpose": "Lock stops drawing, power saving to bubble and box, palette and motion changes applied, sound and other plumbing",
      "acceptance": [
        "AC-11-1",
        "AC-11-2",
        "AC-11-3"
      ],
      "depends_on": [
        "TASK-SETTINGS"
      ],
      "changes": [
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_m7.py",
          "action": "modify"
        }
      ],
      "status": "planned",
      "evidence": [
        "RDY-1"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-NEWCHAT",
      "purpose": "New chat after 15 idle minutes, said, with carry on",
      "acceptance": [
        "AC-12-1"
      ],
      "depends_on": [
        "TASK-COMMANDS"
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
          "path": "tests/test_app_m7.py",
          "action": "modify"
        }
      ],
      "status": "planned",
      "evidence": [
        "RDY-1"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-HELLO",
      "purpose": "A first-unlock hello",
      "acceptance": [
        "AC-13-1"
      ],
      "depends_on": [
        "TASK-REMINDERS"
      ],
      "changes": [
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_m7.py",
          "action": "modify"
        }
      ],
      "status": "planned",
      "evidence": [
        "RDY-1"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-COMMANDS",
      "purpose": "Command table on M5's phrase ids, help from offline.help_text",
      "acceptance": [
        "AC-M0-6"
      ],
      "depends_on": [
        "TASK-HARNESS"
      ],
      "changes": [
        {
          "path": "chatmon/commands.py",
          "action": "modify"
        },
        {
          "path": "tests/test_commands.py",
          "action": "modify"
        }
      ],
      "status": "planned",
      "evidence": [
        "RDY-1"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-IPC",
      "purpose": "Windows connections checked with client_is_me; chatmon ask lets only Chatmon come forward",
      "acceptance": [
        "AC-M0-8",
        "AC-M0-10"
      ],
      "depends_on": [
        "TASK-AGENTS"
      ],
      "changes": [
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "chatmon/cli.py",
          "action": "modify"
        },
        {
          "path": "tests/test_cli.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_m7.py",
          "action": "modify"
        }
      ],
      "status": "planned",
      "evidence": [
        "RDY-1"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-M2NOTES",
      "purpose": "More to show_notes, remembered size, hint, multi-line questions kept",
      "acceptance": [
        "AC-M2-1"
      ],
      "depends_on": [
        "TASK-ANSWERS"
      ],
      "changes": [
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_m7.py",
          "action": "modify"
        }
      ],
      "status": "planned",
      "evidence": [
        "RDY-1"
      ],
      "blocker": null,
      "superseded_by": null
    }
  ],
  "evidence": [
    {
      "id": "RDY-1",
      "acceptance": [
        "AC-CI-1",
        "AC-CI-2",
        "AC-CI-3",
        "AC-01-1",
        "AC-01-2",
        "AC-01-3",
        "AC-02-1",
        "AC-02-2",
        "AC-02-3",
        "AC-02-4",
        "AC-03-1",
        "AC-03-2",
        "AC-03-3",
        "AC-03-4",
        "AC-03-5",
        "AC-04-1",
        "AC-04-2",
        "AC-04-3",
        "AC-04-4",
        "AC-05-1",
        "AC-06-1",
        "AC-06-2",
        "AC-07-1",
        "AC-07-2",
        "AC-07-3",
        "AC-08-1",
        "AC-09-1",
        "AC-09-2",
        "AC-09-3",
        "AC-09-4",
        "AC-10-1",
        "AC-10-2",
        "AC-10-3",
        "AC-11-1",
        "AC-11-2",
        "AC-11-3",
        "AC-12-1",
        "AC-13-1",
        "AC-M0-6",
        "AC-M0-7",
        "AC-M0-8",
        "AC-M0-10",
        "AC-M1B-7",
        "AC-M1B-9",
        "AC-M1B-10",
        "AC-M2-1",
        "AC-M5-1"
      ],
      "kind": "readiness",
      "status": "pass",
      "command": [],
      "method": "Requirements review of M7-01..M7-13, the CI finding and every integration note addressed to M7, against the assessment, the roadmap's owner decisions, ownership, contracts and rules, and pyproject.toml: clarity, conflicts and decisions, missing failure behavior, scope, terminology, coverage and order (readiness.md).",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m7/readiness.md",
        "sha256": "6f13b69f5528bc3675080db55211c70346c4c8f860c4efc7725bad721a6c5436"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        }
      ],
      "scope_sha256": "82c0af6633dd7bdbeb48a10a4a7e8ca1c3699b61980268eab0218d2a76ee0c12",
      "red": null,
      "reason": null
    }
  ],
  "checkpoint": null
}
```
