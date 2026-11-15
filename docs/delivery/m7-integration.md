# M7: integration

The work unit for items M7-01 to M7-13 of [ASSESSMENT.md](ASSESSMENT.md#m7-integration-apppy-settingswinpy-clipy-wiring-after-wave-1),
and for every integration note the merged wave-1 plans address to M7 or "the app": [M0](m0-app-core.md#integration-notes),
[M1A](m1a-security-updates.md#integration-notes), [M1B](m1b-brains-and-stored-data.md#integration-notes),
[M2](m2-bubbles-askbox.md#integration-notes) and [M5](m5-reminders-offline-locale.md#integration-notes). Ordered and
bounded by [ROADMAP.md](ROADMAP.md). Branch `wave2/m7`, from `improve/assessment-fixes` at `4827b0c`, with `81af7c7`,
then M3 (`25dd7cd`), M4B (`c6ca786`), M6A (`8b4c9fc`: stricter pytest, mypy) and M4A (`d352359`) merged as the
coordinator said they were ready, M4B's toast fix (`b401cc7`), and M8's phase A (`0de0af1`, the translation layer):
wave 1 is complete, and nothing of M7 waits on it. Reports, logs, the drills'
generator (`drills_m7.py`) and the ledger's (`ledger.py`, `receipt.py`) are in [reports/m7](reports/m7/).

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
What needed M3's, M4A's or M4B's APIs was built up to one call and finished as each branch was merged (see
[Wave 1's APIs, all wired](#wave-1s-apis-all-wired)). No new runtime dependencies.

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
- **Focus (M7-05).** At a session's end the plain bubbles it held become one "While you focused" bubble after "Focus
  session done!" (`MessageQueue.take`); stopped by you, they're in the "Focus stopped" bubble itself (two plain
  bubbles in a row would replace each other). Ones with buttons stay queued and follow.
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
- **Platform (M7-11).** Lock from logind and Hyprland stops drawing (Windows says what can be seen itself); the
  power saver reaches the bubble and the box; a palette or light/dark change sets the styles again at once, and
  reduced motion (system or Settings) reaches the box and the stage. From M3: the agents badge (`set_badge`),
  `set_reduced_motion`, `follow_pointer_screen` from the "Follow me to another monitor" setting, and on the Wayland
  overlay `set_hosting(False)` while a screen reader runs (or the setting says so), the penguin's own menu still
  drawn on the stage there, as M3 advises. From M4B: `_cue` decides and `sound.play` plays (the player configured
  with the settings and the same quiet rule); the hotkey (`hotkey.register`, default Ctrl+Alt+Space, Ctrl+Shift+Space
  on macOS) toggles the box, a problem said once for that hotkey; on Windows a toast (`wintoast.show`, a reminder's
  with Done and its snooze) before the balloon, the balloon too if Windows refuses the toast after taking it (its
  `failed`; after a toast's final `dismissed` nothing more is news), and every toast cleared at quit; `wintoast.register_app_id` at start
  for a pip or source install; Magnifier sent to each bubble (`wincaret.place`, option on by default). From M4A:
  the Desk's `settings_changed` applies reduced motion and contrast at once (the 30-second look is gone) and
  `screen_reader_changed` looks again for a screen reader (and moves the ask box); Windows' lock watcher passes
  WM_SETTINGCHANGE on (`settings=`); on macOS `WorkspaceWatcher` says the Mac or its displays sleep (nothing drawn),
  accessibility changed, and Low Power Mode (read once at start too); on Linux `SessionWatcher(..., seen=, parent=)`
  and `PowerProfile(..., parent=)`; reading aloud goes through `a11y.announce` (UI Automation on Windows first), with
  Linux's `sysnotify.Notifier` as the fallback and for held alerts (urgent, except when Do Not Disturb is why it
  waits, as urgent shows through GNOME's); and macOS's speech fallback is a setting, off by default.
- **New chat after 15 minutes (M7-12).** Not while a question is on its way. The empty box says "New chat · carry on
  with the last one"; *carry on* goes back to it.
- **Hello (M7-13).** The first unlock each day (and the first start of the day): one bubble with today's reminders,
  agents waiting and updates pending, if there are any.
- **Language (M8's notes for M7).** `language = ""` in the defaults and the template (`i18n.SETTING`). The Companion
  calls `i18n.setup(config["language"] or None)` right after reading its settings, before the stage or any widget
  is made, so the command table (`commands.Table()`, built afterwards) takes that language's phrases too. `chatmon`
  calls `i18n.setup` before printing, reading the setting from the state file's Settings or `config.toml` without
  writing either. Settings' General tab offers "System default" and each of `i18n.available()` by
  `QLocale(code).nativeLanguageName()`, applied at the next start. The three strings this adds go through `_()`
  and the template was regenerated (`packaging/extract_strings.py`).
- **Left to M8's phase B.** M7 doesn't wrap the strings it wrote before M8 merged, nor make M8's listed fix-ups in
  M7-owned files (the system prompt's `label_en`, `updates`' flags in place of English text, `agents.status_words()`,
  the brain and reason templates, `keychain.where()` in sentences, the transcript's `**You:**`/`Attached:` with
  `richtext.TURN`, `winfiles.Dropped.problem`): phase B wraps every user-facing string in the eight files at once,
  with whole-sentence templates, and these go with it. The new M7 strings that are sentences built from pieces are
  listed for it under Integration notes.

### Changes outside M7's files

| File | Change | Asked for by |
|---|---|---|
| `chatmon/bubble.py` | `Effects.playing`; the ask box draws while effects play (CI finding) | Coordinator, 2026-11-14 |
| `chatmon/chats.py` | `ChatBook.listing`; dates through `localefmt` | M0 note 5; M5 (localefmt) |
| `chatmon/events.py`, `chatmon/winpipe.py` | `events.request`; `winpipe.deliver(..., reply=None)` | M0 note 4 |
| `chatmon/reminders.py` | `pop_due` deleted | M5 (step 6) |
| `tests/test_reminders.py` | `pop_due`'s test deleted | M5 (step 6) |
| `tests/test_bubble_styles.py` | the coarse-clock test | Coordinator, 2026-11-14 |
| `chatmon/bubble.py` | `SpeechBubble.timed_out` (went by itself, not closed): missed messages | M7-06 |
| `chatmon/penguin.py` | `Stage.bubble_rect()`: where the bubble is, for Magnifier | M4B's note (wincaret) |
| `chatmon/phrases/en.json` | the *carry on* command's phrases | M7-12 (a translatable phrase, as M5's data wants) |
| `tests/test_settings.py` | nonsense for the new numeric settings; battery order; the new choices | M1B's file; the settings M7 adds |
| `tests/test_commands.py` | the table on M5's ids | M0's file; M0's note 6 |
| `chatmon/locale/chatmon.pot` | regenerated for the language list's three strings | M8 (tests/test_i18n.py checks it's current) |
| `chatmon/chats.py` | merged with M8's own change to the same lines (its wrapped strings kept, `ChatBook.listing` added back) | Merge of `0de0af1` |
| `tests/test_wintoast.py` | two tests accept a CI runner's Windows refusing toasts by its own setting (said, with why) or expiring one before Chatmon hides it | Coordinator: "include test_wintoast in your Windows-CI look" |

### Wave 1's APIs, all wired

M3, M4A and M4B are merged and wired; nothing of M7 waits on another milestone. M0-06's battery and disk readings
already run off the screen's thread (`Background`), which M4A's notes allow.

## Verification

- Gates: `python -m pytest -q -p no:cacheprovider` (the whole suite, one run at a time) and `ruff check .` before every
  commit; logs in [reports/m7](reports/m7/).
- Every acceptance criterion has behavior tests in the project's style (real Qt objects, offscreen) and at least one
  red drill in [drill-spec.json](reports/m7/drill-spec.json), run by `tests/drills/run.py` in a temporary copy.
- The smoke companion fixture moves to `tests/app_harness.py` (`make_companion`), shared by the new app test files.
  Every test companion gets the desktop's readings from the test, never the computer's: its own desk (the CI
  finding), an in-memory keychain (M1B's note 14), `hotkey.register` and `sound.play` stood in for (a test never
  takes a shortcut from the desktop or plays a sound), no toast in Action Center, and a pointer far from the stage
  (M3's stage pauses a bubble under the pointer, and the offscreen cursor stays wherever an earlier test left it: a
  full run once failed `test_a_bubble_that_went_by_while_you_were_away…` that way).
- Three full runs failed M4B's `test_hotkey.py::test_windows_registers_it_on_a_message_only_window_and_hears_it`,
  which passed alone: a test of M7's that replaced the state's settings dropped the harness's empty hotkey, and the
  reload registered the default Ctrl+Alt+Space for real, leaving hotkey.py's window for the rest of the run. The
  harness now stands in for `hotkey.register`, `unregister` and `sound.play` whatever a test does to the settings;
  `tests/test_app_m7.py` and `tests/test_hotkey.py` run together pass.
- M6A's rules apply from its merge: warnings are errors (but ResourceWarning, none of them M7's), 120 s per test, and
  mypy on Windows, Linux and macOS, where new modules are checked: `chatswin.py`, and the changed `chats.py` and
  `asking.py`, pass ([final-mypy.log](reports/m7/final-mypy.log)); `app.py`, `settingswin.py`, `cli.py`, `menus.py`,
  `messages.py`, `commands.py`, `settings.py` stay on M6A's exemption list, for M6B-02.
- Windows CI's `test_wintoast.py` failures (run 43645270996) were the runner's Windows, not the code: it refused a
  toast though the user's setting is on (the test's oracle reads only the registry; the log doesn't show which of
  Windows' reasons), and it said a toast timed out before Chatmon hid it. The two tests now accept Windows refusing by
  its own setting (and say `why_not` otherwise) and its expiry before the hiding; the next Windows CI run either
  passes or names the reason.
- Results on the final source (`41cd4fd`): the whole suite, 1208 passed and 145 skipped
  ([final-pytest.log](reports/m7/final-pytest.log); 959 and 101 on the base before M7, with M3, M4A, M4B, M6A and
  M8's tests since); ruff clean ([final-ruff.log](reports/m7/final-ruff.log)); mypy clean on win32, linux and darwin,
  with M4A's `winuia.py` exempted by the coordinator (`cac0047`) ([final-mypy.log](reports/m7/final-mypy.log)); the
  string template current. 81 red drills, every one green, red and green again, in one run
  ([drills.log](reports/m7/drills.log), [drills-results.json](reports/m7/drills-results.json)) with TEMP pointed at an
  empty folder: in an earlier run two baselines timed out (120 s) inside M1B's `brains.remove_stale_folders()`, which
  lists `%TEMP%` (34,507 entries on this machine, with several workers' drill copies) the first time an `Asker` is
  made. The CI fix's first drills are in [drills-ci.log](reports/m7/drills-ci.log) (run again in the full set).
  Closure validation: [validate-closure.txt](reports/m7/validate-closure.txt).

## Integration notes

APIs M7 adds or changes, for the milestones after it (M8, M6B) and the consolidation:

- `events.request(message, timeout=2.0) -> dict | None` and `events.reply_line(reply)`: a message the companion answers
  (`{"type": "status"}` gives `pid`, `version` and `agents`, the plain agents report). `winpipe.deliver(..., reply)`.
  `Companion.handle()` returns the reply to send (None for most messages).
- `chats.ChatBook.listing(limit) -> list[chats.Listed]` (id, title, updated, pinned), cached per file.
- `commands.Table(phrases=None)` reads `offline.phrases()`; `commands.PHRASES` and `HELP_ALL` are gone (help is
  `offline.help_text()`). `commands.COMMANDS` is keyed by the phrase data's ids; `reminder_line(r, now)`.
- `messages.Message.cue`; `MessageQueue.add()` returns the plain bubbles it dropped; `MessageQueue.take(which)`.
- `asking.Question.partial`, `started`, `before`; `asking.typed(text)` (a question's lines as hard breaks).
- `settings.read_config()` (config, per-setting problems, unreadable); `settings.CHOICES`; new keys `hotkey`,
  `follow_screen`, `[reminders] snooze_minutes`, `[accessibility] text_scale, bubble_time, reduced_motion,
  accessible_ask_box, magnifier_follows`, `[sound] enabled, volume, cues`.
- `chatswin.ChatsWindow(book)` with `refresh(current, kept)` and signals; `SettingsWindow` gains `test_requested`,
  `remove_key`, `backup_requested`, `restore_requested`, `show_tab`, `show_test`, `show_key_status`.
- `tests/app_harness.py`: `make_companion(tmp_path, monkeypatch)` (its own desk, keychain in memory, no hotkey, no
  sound, no toasts in Action Center), `PretendBrain(c, monkeypatch, kind, tools_off, name, label)`, `PretendDesk`,
  `spin`, `until`, `NoToasts`. A test file's `companion` fixture yields from `make_companion`.

For others:

- **M8 (translation, phase B).** M7's strings in `app.py`, `settingswin.py`, `chatswin.py`, `menus.py`, `commands.py`
  and `cli.py` aren't wrapped yet (only the language list's are); *carry on* is phrase data. Pieces to make whole
  sentences: `_hello`'s "{agents} is/are waiting for you" and "{n} system update(s)", the failure bubble's
  "Ask {brain}", the snooze button's "Snooze {length}", `reminder_line`'s "{kind} {when}: {text} ({repeat})", the
  Chats window's and the chats menu's "{title} · {when} (this one)", the tray tooltip's "Chatmon\n{states}", and
  `_key_status`'s sentences around `keychain.where()`. The phase-B fix-ups in M8's table are left to phase B.
- **M6A (CI).** Windows CI's smoke failures were the runner's "quiet" desktop leaking into tests: fixed in the
  harness. Pending on Linux and macOS: the POSIX branch of `events.request`, `test_a_locked_session_stops_drawing…`
  (runs everywhere, platform faked), and the Settings and Chats windows' tests with other fonts.
- **M1B.** `brains.remove_stale_folders()` lists `%TEMP%` on the screen's thread the first time an `Asker` is made, as
  Chatmon starts: with tens of thousands of entries there it took over two minutes under load here. Worth a thread,
  or a look only at names Chatmon makes.
- **M4B.** `sound.CommandPlayer.close()` reaps Linux players at quit, but the module's players are private
  (`sound._sounds._players`): a public `sound.close()` would let the app call it. Not called: a player runs in a
  session of its own and finishes by itself as Chatmon exits.
- **M6B.** `chatmon.winuia` (M4A's) failed mypy on all three platforms until the coordinator exempted it (`cac0047`).
  M7's own new module (`chatswin.py`) and changed checked modules pass.
- **Coordinator.** `set_hosting(False)` and the penguin's menu kept on the stage are untried on a real Wayland
  compositor (none here): try the ask box with Orca running on Hyprland or KDE before release. Showing the
  desktop's own wording for the hotkey on Wayland (`Hotkey.bound`) in Settings needs the module's `Hotkey` object,
  which `hotkey.register` keeps private: a follow-up.

## Changelog notes

- Answers appear as they're written, with who is answering, the seconds so far, and **Stop**. Closing the ask box no
  longer throws the answer away: it finishes, stays in the chat, and a bubble says "<brain> answered" with **Read**.
- When a question fails, a bubble offers **Try again**, **Ask <another brain>** and **Settings**. If the brain you
  picked can't answer, Chatmon says once which brain answers instead. After you name your chatmon, it says which
  brain will answer, or how to set one up. A model server running here that isn't yours is offered once, never
  used without asking.
- Settings: an API brain's key can be saved in your system's keychain from the AI tab, and **Test** asks the brain
  "Say OK" and shows how long it took or what went wrong. A new **Accessibility** tab: text size, how long bubbles
  stay (up to "until I close them"), sounds and their volume, the hotkey, less movement, the ask box as its own
  window for screen readers, reading aloud, and (Windows) Magnifier following bubbles. Reminders have their own
  snooze setting. Changing how often to look for system updates applies at once. "Almost empty" stays below "low".
  **Back up** and **Bring back** are under Chats.
- Reminders wait until you press **Done** or snooze them (your own length, or **Later**: 5 minutes to tomorrow
  morning), and come back after a restart. Each reminder in the menu can be edited, made to repeat, or cancelled.
- A focus session ends with one "While you focused" bubble for what waited.
- **Recent messages** in the menu shows bubbles again, and a click on your chatmon brings back one that went by while
  you were away.
- The tray's tooltip and the chatmon's name for screen readers say what each AI agent is doing; the tray icon gets a
  dot, and the chatmon a badge, while one needs you. *agents* says it in the box, and `chatmon status` prints what
  your agents are doing now.
- **Clipboard** in the menu: Explain, Summarize, Translate or Fix what you copied; it's read only when you choose one.
- A **Chats** window lists every chat with search; the menu keeps the newest. **Ask another brain** asks the last
  question again; each chat remembers which brain it was having.
- **Copy** under answers and code blocks works; Ctrl+1 to Ctrl+9 press a bubble's buttons while you type, and a
  button's label typed soon after its bubble went still presses it.
- Sounds for needs-you, reminders and focus done (others when you turn them on), never during Do Not Disturb, Focus,
  a full-screen app or a focus session. A hotkey (Ctrl+Alt+Space; Ctrl+Shift+Space on macOS) opens the ask box.
  Windows shows toasts instead of balloons. Your chatmon can follow you to another monitor (Windows, macOS, X11).
- Locked, asleep or with the displays off, nothing is drawn (Linux and macOS too now); in power-saving mode (and
  macOS's Low Power Mode) the bubbles and the ask box hold still; high contrast, dark mode and reduced motion apply
  the moment they change. On Linux an alert waiting under Do Not Disturb no longer shows through it. On macOS,
  announcements can be spoken in macOS's own voice while Chatmon is in the background (a setting, off by default).
- After 15 minutes the ask box opens on a new chat and says so: *carry on* goes back to the last one.
- Settings can choose the language Chatmon speaks (from its next start), and the `chatmon` command follows it.
- The first unlock of the day says what's waiting: today's reminders, agents waiting for you, updates.
- Settings that are wrong are named one by one, and a damaged file Chatmon recovered is said at start.
- **Security (Windows):** each connection to Chatmon is checked to come from your own processes, and `chatmon ask`
  lets only Chatmon itself come to the front.
- **Fix (Windows):** the ask box moves again when new words arrive (Windows' clock is coarse); newer news of the
  bubble showing is never stuck behind another.

## README notes

- "Using it": the menu gains **Clipboard** and **Recent messages**; **Chats** lists the newest chats and **All chats…**
  (a window with search); each reminder has Edit, Repeat and Cancel; the hotkey (Ctrl+Alt+Space, Ctrl+Shift+Space on
  macOS) opens the ask box; Ctrl+1 to Ctrl+9 press a bubble's buttons.
- The ask box: answers appear as they come, with **Stop**; closing the box doesn't stop an answer; *carry on* after a
  new chat goes back to the last one.
- Brains: save an API key in Settings (your keychain, never the settings file), **Test** a brain, **Ask another
  brain**; Automatic asks before using a model server that isn't yours.
- Settings: the Accessibility tab; reminders' own snooze; Back up and Bring back; the Language (System default, or a
  translation Chatmon has), from the next start; `language = "de"` in `config.toml` does the same.
- Sounds: alerts only by default (needs-you, reminders, focus done), never during Do Not Disturb, Focus, full screen
  or a focus session; one switch for all.
- AI agents: `chatmon status` shows what your agents are doing now (from the running Chatmon).
- Privacy: the clipboard is read only when you choose a Clipboard action (or paste); keys never leave the keychain
  for state, the settings file or a backup.
- Windows, pip or source installs: Chatmon registers its name for notifications under
  `HKCU\Software\Classes\AppUserModelId\RandyNorthrup.Chatmon` (the installer's Start menu shortcut does this for
  installed copies).
- "How it's put together": `chatmon/chatswin.py` (the Chats window); `tests/app_harness.py` (the companion the app's
  tests share).

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
        "AC-11-3",
        "AC-11-4",
        "AC-11-5",
        "AC-11-6",
        "AC-11-7"
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
      "id": "INT-M8",
      "statement": "M8's notes for M7: the language setting, chosen at start and in the command line, offered in Settings",
      "priority": "normal",
      "acceptance": [
        "AC-M8-1"
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
      "then": "It plays only when sound is on, the cue is on, and it isn't Do Not Disturb, Focus, full screen or a focus session; the player (sound.py) is told the settings and asks the same",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-11-4",
      "requirement": "M7-11",
      "given": "A hotkey in Settings, and an alert under a full-screen app on Windows",
      "when": "The hotkey is pressed, or the alert comes",
      "then": "The hotkey opens the ask box (and closes it; a problem said once); Windows shows a toast, a reminder's with Done and a snooze, and the balloon only when there's no toast",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-11-5",
      "requirement": "M7-11",
      "given": "The Wayland overlay with a screen reader running, or the setting on; Follow me in Settings",
      "when": "Chatmon looks",
      "then": "The ask box is a window of its own (the penguin's menu stays the stage's); the stage follows the pointer to another monitor where it can",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-11-6",
      "requirement": "M7-11",
      "given": "Windows' Magnifier running and the option on",
      "when": "A bubble shows, and closes",
      "then": "Magnifier is sent to the bubble's rectangle in the stage window's pixels, and let go when it closes; not with the option off",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-11-7",
      "requirement": "M7-11",
      "given": "M4A's platform readings: the Desk's change signals, macOS's workspace, Linux's notifications",
      "when": "Reduced motion or contrast changes, a screen reader starts, the Mac or its displays sleep, Low Power Mode changes, an alert waits under Do Not Disturb",
      "then": "Each applies at once (no 30-second look): drawing stops while asleep, power saving follows, and a held alert isn't urgent when Do Not Disturb is why it waits",
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
      "id": "AC-M8-1",
      "requirement": "INT-M8",
      "given": "A language chosen in Settings or the settings file",
      "when": "Chatmon or the chatmon command starts",
      "then": "It's set up before any window is built or anything printed (the command line reading it without writing anything); Settings offers System default and each shipped language by its own name",
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
        },
        {
          "path": "tests/test_wintoast.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "RDY-1",
        "BEH-SUITE",
        "RED-CI-01-host-desk-read",
        "RED-CI-02-queue-best-only",
        "RED-CI-03-wake-best-only",
        "RED-CI-04-askbox-wakes-by-strength",
        "RED-CI-05-askbox-frame-stops-at-zero"
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
      "status": "verified",
      "evidence": [
        "RDY-1",
        "BEH-SUITE",
        "RED-CI-01-host-desk-read"
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
      "status": "verified",
      "evidence": [
        "RDY-1",
        "BEH-SUITE",
        "RED-M7-01-only-newest-piece",
        "RED-M7-01-closing-drops",
        "RED-M7-01-answered-unsaid",
        "RED-M7-01-stop-loses-what-came",
        "RED-M7-01-no-busy"
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
      "status": "verified",
      "evidence": [
        "RDY-1",
        "BEH-SUITE",
        "RED-M7-02-no-next-brain",
        "RED-M7-02-fallback-every-time",
        "RED-M7-02-welcome-without-brain",
        "RED-M7-02-server-not-kept",
        "RED-M0-07-waits-for-brain"
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
      "status": "verified",
      "evidence": [
        "RDY-1",
        "BEH-SUITE",
        "RED-M7-09-answer-not-by",
        "RED-M7-09-chat-brain-ignored",
        "RED-M1B-07-files-brain-sees-all"
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
      "status": "verified",
      "evidence": [
        "RDY-1",
        "BEH-SUITE",
        "RED-M7-03-key-not-saved",
        "RED-M7-03-key-not-handed-back",
        "RED-M7-03-test-without-typed-key",
        "RED-M7-03-text-scale-unapplied",
        "RED-M7-03-cues-not-handed-back",
        "RED-M7-03-snooze-from-breaks",
        "RED-M7-03-interval-needs-restart",
        "RED-M7-03-battery-order-window",
        "RED-M7-03-battery-order-file"
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
      "status": "verified",
      "evidence": [
        "RDY-1",
        "BEH-SUITE",
        "RED-M1B-09-overrides-unchecked",
        "RED-M1B-10-damage-unsaid"
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
      "status": "verified",
      "evidence": [
        "RDY-1",
        "BEH-SUITE",
        "RED-M7-04-done-keeps-it",
        "RED-M7-04-later-missing",
        "RED-M7-04-not-restored",
        "RED-M7-04-focus-held-forever",
        "RED-M7-04-edit-ignores-time",
        "RED-M7-04-repeat-dropped",
        "RED-M7-04-cli-no-explanation"
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
      "status": "verified",
      "evidence": [
        "RDY-1",
        "BEH-SUITE",
        "RED-M7-05-no-summary"
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
          "path": "chatmon/bubble.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_m7.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "RDY-1",
        "BEH-SUITE",
        "RED-M7-06-not-recent",
        "RED-M7-06-click-ignores-missed",
        "RED-M7-06-dropped-not-missed"
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
      "status": "verified",
      "evidence": [
        "RDY-1",
        "BEH-SUITE",
        "RED-M7-07-no-tooltip",
        "RED-M7-07-no-badge",
        "RED-M7-07-agents-command-is-help",
        "RED-M7-07-no-reply",
        "RED-M7-07-cli-ignores-live",
        "RED-M7-07-no-stage-badge"
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
      "status": "verified",
      "evidence": [
        "RDY-1",
        "BEH-SUITE",
        "RED-M7-08-text-not-attached"
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
        }
      ],
      "status": "verified",
      "evidence": [
        "RDY-1",
        "BEH-SUITE",
        "RED-M7-09-no-search-inside",
        "RED-M7-09-no-all-chats",
        "RED-M7-09-restore-not-reread",
        "RED-M7-09-listing-rereads",
        "RED-M5-chat-times-12h"
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
      "status": "verified",
      "evidence": [
        "RDY-1",
        "BEH-SUITE",
        "RED-M7-10-copy-unwired",
        "RED-M7-10-ctrl-number-ignored",
        "RED-M7-10-expired-unanswerable"
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
      "status": "verified",
      "evidence": [
        "RDY-1",
        "BEH-SUITE",
        "RED-M7-11-lock-keeps-drawing",
        "RED-M7-11-box-ignores-saver",
        "RED-M7-11-palette-ignored",
        "RED-M7-11-sound-in-quiet",
        "RED-M7-11-player-never-quiet"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-STAGE-M4B",
      "purpose": "M3's stage (badge, reduced motion, follow, hosting) and M4B's hotkey, sound player, toasts and Magnifier, wired in",
      "acceptance": [
        "AC-07-1",
        "AC-11-3",
        "AC-11-4",
        "AC-11-5",
        "AC-11-6"
      ],
      "depends_on": [
        "TASK-PLATFORM",
        "TASK-AGENTS"
      ],
      "changes": [
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "chatmon/settings.py",
          "action": "modify"
        },
        {
          "path": "chatmon/settingswin.py",
          "action": "modify"
        },
        {
          "path": "chatmon/penguin.py",
          "action": "modify"
        },
        {
          "path": "tests/app_harness.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_m7.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "RDY-1",
        "BEH-SUITE",
        "RED-M7-07-no-tooltip",
        "RED-M7-07-no-badge",
        "RED-M7-11-sound-in-quiet",
        "RED-M7-07-no-stage-badge",
        "RED-M7-11-player-never-quiet",
        "RED-M7-11-hotkey-unregistered",
        "RED-M7-11-balloon-not-toast",
        "RED-M7-11-refused-toast-unsaid",
        "RED-M7-11-box-always-hosted",
        "RED-M7-11-follow-ignored",
        "RED-M7-11-magnifier-not-placed"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-M4A",
      "purpose": "M4A's Desk signals, macOS's workspace watcher, Linux's session, power and notifications, a11y.announce, the speech fallback",
      "acceptance": [
        "AC-11-7"
      ],
      "depends_on": [
        "TASK-STAGE-M4B"
      ],
      "changes": [
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "chatmon/settings.py",
          "action": "modify"
        },
        {
          "path": "chatmon/settingswin.py",
          "action": "modify"
        },
        {
          "path": "tests/app_harness.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_m7.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_smoke.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "RDY-1",
        "BEH-SUITE",
        "RED-M4A-desk-changes-unheard",
        "RED-M4A-reader-not-looked-again",
        "RED-M4A-mac-sleep-unheard",
        "RED-M4A-low-power-not-read",
        "RED-M4A-urgent-through-dnd"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "TASK-I18N",
      "purpose": "M8's language setting wired: settings, i18n.setup in the app and the CLI, the Settings window's list",
      "acceptance": [
        "AC-M8-1"
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
          "path": "chatmon/cli.py",
          "action": "modify"
        },
        {
          "path": "chatmon/settings.py",
          "action": "modify"
        },
        {
          "path": "chatmon/settingswin.py",
          "action": "modify"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "action": "modify"
        },
        {
          "path": "tests/app_harness.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_m7.py",
          "action": "modify"
        },
        {
          "path": "tests/test_cli.py",
          "action": "modify"
        },
        {
          "path": "tests/test_settingswin.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "RDY-1",
        "BEH-SUITE",
        "RED-M8-app-language-ignored",
        "RED-M8-cli-language-ignored",
        "RED-M8-window-language-dropped"
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
          "path": "chatmon/phrases/en.json",
          "action": "modify"
        },
        {
          "path": "tests/test_app_m7.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "RDY-1",
        "BEH-SUITE",
        "RED-M7-12-carry-on-forgotten",
        "RED-M7-12-drops-question"
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
      "status": "verified",
      "evidence": [
        "RDY-1",
        "BEH-SUITE",
        "RED-M7-13-hello-every-unlock"
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
      "status": "verified",
      "evidence": [
        "RDY-1",
        "BEH-SUITE",
        "RED-M0-06-table-unfiltered"
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
      "status": "verified",
      "evidence": [
        "RDY-1",
        "BEH-SUITE",
        "RED-M0-08-connections-unchecked",
        "RED-M0-10-any-process-forward"
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
      "status": "verified",
      "evidence": [
        "RDY-1",
        "BEH-SUITE",
        "RED-M2-more-unwired"
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
        "AC-11-4",
        "AC-11-5",
        "AC-11-6",
        "AC-11-7",
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
        "AC-M8-1",
        "AC-M5-1"
      ],
      "kind": "readiness",
      "status": "pass",
      "command": [],
      "method": "Requirements review of M7-01..M7-13, the CI finding and every integration note addressed to M7 (readiness.md), re-read against the merged M3 and M4B notes.",
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
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
      "scope_sha256": "e0bed30be8b7760b1f38fc3d3659feb5e96f882502608e71901632acb6c06022",
      "red": null,
      "reason": null
    },
    {
      "id": "BEH-SUITE",
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
        "AC-11-4",
        "AC-11-5",
        "AC-11-6",
        "AC-11-7",
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
        "AC-M8-1",
        "AC-M5-1"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider"
      ],
      "method": "The whole suite on the final source (real Qt objects, offscreen), which runs every criterion's tests; the log names each failure, and had none.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/final-pytest.log",
        "sha256": "cf444f3d74a56446be989a8ba8959452890ff608320746e9cb8e55600b4c94c5"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "3c036d7ab8cf9483ce526519528ed903dc2d2d44cdf32f4a93ae69c3e8708f0a"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "291cd461529db851480828ecb52398b5cd9b3d3c02fe874e7a57ffabaf440ab3"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "da3d7845b19bb1888001e93d1f13b5319288d0e36d5e66a2dc277e700a9bc4b9"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "a849300cbe173d5996052e021575090bd77ed05f0b31c4ef0ea4252ec458b8f2"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "7371614c5f0315d19f805df16694d5ca4f8b599cc6127b891c4a3f836d50b149"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "c9748102e3e1063b9e769e535af9cea8ec905abae66ff988fb109b5f1d496562"
        },
        {
          "path": "chatmon/phrases/en.json",
          "sha256": "0ad5d23950aa11252a58caf94e713d198fb4deb500aa67fb60f7f191085a1da8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "a4c6d141f6f6b4ec78449cc5adbaafbf99418c6a421ba9341722aa81b4079a50"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "f7e4fdafc15b570e5ad1bc93db79659d4e109392355b4a3781a14d8039d4975f"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_answers.py",
          "sha256": "324749f6668263eec4508df65370296e91d712da9e8acebc25ac0b5c362da433"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "025c386f89a3ee0d9fcd403ffcf000e644e238338c98ae6fde08693256e0890d"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a75812ca8e75ee2390fc2456d64fd4d4d1744a3a56b9c03a8edf5c586dd41b98"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_chatswin.py",
          "sha256": "8854160e3c08385f0e4bf4d7ca024e50c5822caefdbafa351fd546966d2f0373"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "e4527c1b87ccc4b30b1dfda7913927b99e2e29df0484ce0497419932e46df1d5"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "e0bed30be8b7760b1f38fc3d3659feb5e96f882502608e71901632acb6c06022",
      "red": null,
      "reason": null
    },
    {
      "id": "RED-CI-01-host-desk-read",
      "acceptance": [
        "AC-CI-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_smoke.py::test_the_computer_the_tests_run_on_holds_nothing_back"
      ],
      "method": "Red drill CI-01-host-desk-read through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "7cba23fc33f4752c905eedff1ce3a44cb97a32c336df75f0e660d05c867b2fa7",
      "red": {
        "mutation": "CI-01-host-desk-read: in tests/app_harness.py, '    c.desk = PretendDesk()' became \"    pass  # the computer's own desk, as before\"",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_computer_the_tests_run_on_holds_nothing_back",
        "observed_diagnostic": "____________ test_the_computer_the_tests_run_on_holds_nothing_back ____________",
        "before": [
          {
            "path": "tests/app_harness.py",
            "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
          }
        ],
        "mutated": [
          {
            "path": "tests/app_harness.py",
            "sha256": "6b190bc3cc76ad13c50615c78a619bfa711aa408773cf7fbf3d3ed11762db4f9"
          }
        ],
        "after": [
          {
            "path": "tests/app_harness.py",
            "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-CI-02-queue-best-only",
      "acceptance": [
        "AC-CI-2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_messages.py::test_newer_news_of_whats_showing_isnt_stuck_behind_what_cant_take_over",
        "tests/test_messages.py::test_what_you_did_shows_at_once_even_while_something_from_the_background_waits_for_the_minimum"
      ],
      "method": "Red drill CI-02-queue-best-only through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "65e6105a4fa372892ce8815d26cb0b9105625a3f2d7ae8efe8c055eb073e1256",
      "red": {
        "mutation": "CI-02-queue-best-only: in chatmon/messages.py, 'best = next((m for m in self._ready() if self._takes_over(m, now)), None)' became 'best = next((m for m in self._ready()[:1] if self._takes_over(m, now)), None)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_newer_news_of_whats_showing_isnt_stuck_behind_what_cant_take_over",
        "observed_diagnostic": "___ test_newer_news_of_whats_showing_isnt_stuck_behind_what_cant_take_over ____",
        "before": [
          {
            "path": "chatmon/messages.py",
            "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/messages.py",
            "sha256": "97bcb0886353ce0725c1b6c90288ad155f846e36369eaca789a187e801981cc8"
          }
        ],
        "after": [
          {
            "path": "chatmon/messages.py",
            "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-CI-03-wake-best-only",
      "acceptance": [
        "AC-CI-2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_messages.py::test_newer_news_of_whats_showing_isnt_stuck_behind_what_cant_take_over"
      ],
      "method": "Red drill CI-03-wake-best-only through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "65e6105a4fa372892ce8815d26cb0b9105625a3f2d7ae8efe8c055eb073e1256",
      "red": {
        "mutation": "CI-03-wake-best-only: in chatmon/messages.py, 'times = [at for m in self._ready() if' became 'times = [at for m in self._ready()[:1] if'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_newer_news_of_whats_showing_isnt_stuck_behind_what_cant_take_over",
        "observed_diagnostic": "___ test_newer_news_of_whats_showing_isnt_stuck_behind_what_cant_take_over ____",
        "before": [
          {
            "path": "chatmon/messages.py",
            "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/messages.py",
            "sha256": "738ab7dd6e479b811aa4998965b16c5122d517c8416331e4be32c1a1765fc9b9"
          }
        ],
        "after": [
          {
            "path": "chatmon/messages.py",
            "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-CI-04-askbox-wakes-by-strength",
      "acceptance": [
        "AC-CI-3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_bubble_styles.py::test_new_words_wake_the_ask_box_on_a_clock_that_hasnt_moved_since"
      ],
      "method": "Red drill CI-04-askbox-wakes-by-strength through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "65e6105a4fa372892ce8815d26cb0b9105625a3f2d7ae8efe8c055eb073e1256",
      "red": {
        "mutation": "CI-04-askbox-wakes-by-strength: in chatmon/bubble.py, '        if drawn_here and self._moving(time.monotonic()):' became '        if drawn_here and self.effects(time.monotonic()) > 0.0:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "new words: it moves again",
        "observed_diagnostic": ">       assert box._frames.isActive() and box.anim_key(now) != -1, \"new words: it moves again\"",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "fc60ebfa58ebd48c40101b3e68c4ed0bedc382a405cabcbdf72e2bd5cc4114ff"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-CI-05-askbox-frame-stops-at-zero",
      "acceptance": [
        "AC-CI-3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_bubble_styles.py::test_new_words_wake_the_ask_box_on_a_clock_that_hasnt_moved_since"
      ],
      "method": "Red drill CI-05-askbox-frame-stops-at-zero through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "65e6105a4fa372892ce8815d26cb0b9105625a3f2d7ae8efe8c055eb073e1256",
      "red": {
        "mutation": "CI-05-askbox-frame-stops-at-zero: in chatmon/bubble.py, '        if not self._moving(time.monotonic()):' became '        if self.effects(time.monotonic()) <= 0.0:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "a frame drawn at strength 0 is the start of the rise",
        "observed_diagnostic": ">       assert box._frames.isActive(), \"a frame drawn at strength 0 is the start of the rise, not the end of it\"",
        "before": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "60f29925d53fd13062906b789855d4561cb75adaaf764802a6408933bbb16a1c"
          }
        ],
        "after": [
          {
            "path": "chatmon/bubble.py",
            "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-01-only-newest-piece",
      "acceptance": [
        "AC-01-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_answers.py::test_an_answer_shows_as_it_streams_in_and_survives_the_box_being_drawn_again"
      ],
      "method": "Red drill M7-01-only-newest-piece through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "3c036d7ab8cf9483ce526519528ed903dc2d2d44cdf32f4a93ae69c3e8708f0a"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_answers.py",
          "sha256": "324749f6668263eec4508df65370296e91d712da9e8acebc25ac0b5c362da433"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a75812ca8e75ee2390fc2456d64fd4d4d1744a3a56b9c03a8edf5c586dd41b98"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "307d24f97f367c690cf893e3a8e6c312107423f212104b718efb656239c5bf1f",
      "red": {
        "mutation": "M7-01-only-newest-piece: in chatmon/app.py, 'first, q.partial = not q.partial, q.partial + text' became 'first, q.partial = not q.partial, text'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_an_answer_shows_as_it_streams_in_and_survives_the_box_being_drawn_again",
        "observed_diagnostic": "_ test_an_answer_shows_as_it_streams_in_and_survives_the_box_being_drawn_again _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "4492a81cc158d83773502230aad75696f2491ca8089bd27c12ad8c64f9473813"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-01-closing-drops",
      "acceptance": [
        "AC-01-2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_answers.py::test_closing_the_box_lets_the_answer_finish_and_a_bubble_says_it_came"
      ],
      "method": "Red drill M7-01-closing-drops through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "3c036d7ab8cf9483ce526519528ed903dc2d2d44cdf32f4a93ae69c3e8708f0a"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_answers.py",
          "sha256": "324749f6668263eec4508df65370296e91d712da9e8acebc25ac0b5c362da433"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a75812ca8e75ee2390fc2456d64fd4d4d1744a3a56b9c03a8edf5c586dd41b98"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "307d24f97f367c690cf893e3a8e6c312107423f212104b718efb656239c5bf1f",
      "red": {
        "mutation": "M7-01-closing-drops: in chatmon/app.py, '        # A question on its way carries on: its answer is kept in the chat, and a bubble says it came (_answered).' became '        self.asker.cancel()\\r\\n        self.questions.drop()'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_closing_the_box_lets_the_answer_finish_and_a_bubble_says_it_came",
        "observed_diagnostic": "____ test_closing_the_box_lets_the_answer_finish_and_a_bubble_says_it_came ____",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "c83fbb3aaa4cce17d0c9e96d3584e0e97dcb50f25ddfa7918851fb828d803af7"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-01-answered-unsaid",
      "acceptance": [
        "AC-01-2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_answers.py::test_closing_the_box_lets_the_answer_finish_and_a_bubble_says_it_came"
      ],
      "method": "Red drill M7-01-answered-unsaid through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "3c036d7ab8cf9483ce526519528ed903dc2d2d44cdf32f4a93ae69c3e8708f0a"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_answers.py",
          "sha256": "324749f6668263eec4508df65370296e91d712da9e8acebc25ac0b5c362da433"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a75812ca8e75ee2390fc2456d64fd4d4d1744a3a56b9c03a8edf5c586dd41b98"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "307d24f97f367c690cf893e3a8e6c312107423f212104b718efb656239c5bf1f",
      "red": {
        "mutation": "M7-01-answered-unsaid: in chatmon/app.py, 'self.say(f\"{label or \\'The AI\\'} answered\", buttons=[(\"Read\", self._read_answer)]' became 'self._read_aloud(f\"{label or \\'The AI\\'} answered\", buttons=[(\"Read\", self._read_answer)]'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_closing_the_box_lets_the_answer_finish_and_a_bubble_says_it_came",
        "observed_diagnostic": "____ test_closing_the_box_lets_the_answer_finish_and_a_bubble_says_it_came ____",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "14ff2e590c8ead4e3c5e84e7e4e8636e48c974b897f1bfe1b53d19eb9a304e22"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-01-stop-loses-what-came",
      "acceptance": [
        "AC-01-3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_answers.py::test_the_box_says_who_is_answering_and_stop_ends_it"
      ],
      "method": "Red drill M7-01-stop-loses-what-came through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "3c036d7ab8cf9483ce526519528ed903dc2d2d44cdf32f4a93ae69c3e8708f0a"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_answers.py",
          "sha256": "324749f6668263eec4508df65370296e91d712da9e8acebc25ac0b5c362da433"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a75812ca8e75ee2390fc2456d64fd4d4d1744a3a56b9c03a8edf5c586dd41b98"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "307d24f97f367c690cf893e3a8e6c312107423f212104b718efb656239c5bf1f",
      "red": {
        "mutation": "M7-01-stop-loses-what-came: in chatmon/app.py, '        if q.partial.strip():\\r\\n' became '        if False:\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_box_says_who_is_answering_and_stop_ends_it",
        "observed_diagnostic": "_____________ test_the_box_says_who_is_answering_and_stop_ends_it _____________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "0ebb02ea8d96180872bde37256ab31da207306560621bccb7a96515796d94928"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-01-no-busy",
      "acceptance": [
        "AC-01-3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_answers.py::test_the_box_says_who_is_answering_and_stop_ends_it"
      ],
      "method": "Red drill M7-01-no-busy through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "3c036d7ab8cf9483ce526519528ed903dc2d2d44cdf32f4a93ae69c3e8708f0a"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_answers.py",
          "sha256": "324749f6668263eec4508df65370296e91d712da9e8acebc25ac0b5c362da433"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a75812ca8e75ee2390fc2456d64fd4d4d1744a3a56b9c03a8edf5c586dd41b98"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "307d24f97f367c690cf893e3a8e6c312107423f212104b718efb656239c5bf1f",
      "red": {
        "mutation": "M7-01-no-busy: in chatmon/app.py, '        self.ask_box.set_busy(brain.label, q.started)\\r\\n' became '\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_box_says_who_is_answering_and_stop_ends_it",
        "observed_diagnostic": "_____________ test_the_box_says_who_is_answering_and_stop_ends_it _____________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "6db21788c16295f4547f58741ac7c5c93cbd561283e8c5cc34b2d6ab731abd6a"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-02-no-next-brain",
      "acceptance": [
        "AC-02-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_answers.py::test_a_failed_question_offers_to_try_again_ask_the_next_brain_or_open_settings"
      ],
      "method": "Red drill M7-02-no-next-brain through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "3c036d7ab8cf9483ce526519528ed903dc2d2d44cdf32f4a93ae69c3e8708f0a"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_answers.py",
          "sha256": "324749f6668263eec4508df65370296e91d712da9e8acebc25ac0b5c362da433"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a75812ca8e75ee2390fc2456d64fd4d4d1744a3a56b9c03a8edf5c586dd41b98"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "eff80296798f27b428ad17a3140777d79bc11e5ed9764f97c05ecc69b17c564e",
      "red": {
        "mutation": "M7-02-no-next-brain: in chatmon/app.py, '        if other is not None:\\r\\n            buttons.append' became '        if False:\\r\\n            buttons.append'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_failed_question_offers_to_try_again_ask_the_next_brain_or_open_settings",
        "observed_diagnostic": "_ test_a_failed_question_offers_to_try_again_ask_the_next_brain_or_open_settings _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "827ad8b65d89f89c7be32ad1df178e93e4dfd23858fcd9482d7f28935cb3a4eb"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-02-fallback-every-time",
      "acceptance": [
        "AC-02-2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_answers.py::test_a_brain_picked_that_cant_answer_is_announced_once_for_that_pick"
      ],
      "method": "Red drill M7-02-fallback-every-time through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "3c036d7ab8cf9483ce526519528ed903dc2d2d44cdf32f4a93ae69c3e8708f0a"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_answers.py",
          "sha256": "324749f6668263eec4508df65370296e91d712da9e8acebc25ac0b5c362da433"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a75812ca8e75ee2390fc2456d64fd4d4d1744a3a56b9c03a8edf5c586dd41b98"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "eff80296798f27b428ad17a3140777d79bc11e5ed9764f97c05ecc69b17c564e",
      "red": {
        "mutation": "M7-02-fallback-every-time: in chatmon/app.py, '        if self._fallback_told == picked:\\r\\n' became '        if False:\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_brain_picked_that_cant_answer_is_announced_once_for_that_pick",
        "observed_diagnostic": "____ test_a_brain_picked_that_cant_answer_is_announced_once_for_that_pick _____",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "008764c276b0264ea87863721bd5f6ca9fa19200a75876995e63bf259ea9b029"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-02-welcome-without-brain",
      "acceptance": [
        "AC-02-3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_answers.py::test_after_naming_it_says_which_brain_will_answer_or_how_to_set_one_up"
      ],
      "method": "Red drill M7-02-welcome-without-brain through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "3c036d7ab8cf9483ce526519528ed903dc2d2d44cdf32f4a93ae69c3e8708f0a"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_answers.py",
          "sha256": "324749f6668263eec4508df65370296e91d712da9e8acebc25ac0b5c362da433"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a75812ca8e75ee2390fc2456d64fd4d4d1744a3a56b9c03a8edf5c586dd41b98"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "eff80296798f27b428ad17a3140777d79bc11e5ed9764f97c05ecc69b17c564e",
      "red": {
        "mutation": "M7-02-welcome-without-brain: in chatmon/app.py, 'line = f\"Your questions go to **{brain.label}**; **Brain** in my menu picks another.\"' became 'line = \"\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_after_naming_it_says_which_brain_will_answer_or_how_to_set_one_up",
        "observed_diagnostic": "___ test_after_naming_it_says_which_brain_will_answer_or_how_to_set_one_up ____",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "951f2151535c327990af069ab4ca24a8e378b69610b79ba314bd3d63957b8bf5"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-02-server-not-kept",
      "acceptance": [
        "AC-02-4"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_answers.py::test_a_model_server_that_isnt_yours_is_offered_once_and_kept_once_confirmed"
      ],
      "method": "Red drill M7-02-server-not-kept through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "3c036d7ab8cf9483ce526519528ed903dc2d2d44cdf32f4a93ae69c3e8708f0a"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_answers.py",
          "sha256": "324749f6668263eec4508df65370296e91d712da9e8acebc25ac0b5c362da433"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a75812ca8e75ee2390fc2456d64fd4d4d1744a3a56b9c03a8edf5c586dd41b98"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "eff80296798f27b428ad17a3140777d79bc11e5ed9764f97c05ecc69b17c564e",
      "red": {
        "mutation": "M7-02-server-not-kept: in chatmon/app.py, '        self.state.set(\"trusted_servers\", brains.confirmed_servers())\\r\\n' became '\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_model_server_that_isnt_yours_is_offered_once_and_kept_once_confirmed",
        "observed_diagnostic": "_ test_a_model_server_that_isnt_yours_is_offered_once_and_kept_once_confirmed _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "46c93fbae63b7f811f4be24fee6df7450cfe3ad3e0b8c724e09eb35e2b62e060"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-03-key-not-saved",
      "acceptance": [
        "AC-03-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_a_key_saved_in_settings_goes_to_the_keychain_only"
      ],
      "method": "Red drill M7-03-key-not-saved through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "0ef46abd49148651a55d9cbc783fadaebb0f4a4ab4c870c609ebfa176e6aa7be",
      "red": {
        "mutation": "M7-03-key-not-saved: in chatmon/app.py, '            problem = keychain.set(name, key)\\r\\n' became '            problem = None\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_key_saved_in_settings_goes_to_the_keychain_only",
        "observed_diagnostic": "___________ test_a_key_saved_in_settings_goes_to_the_keychain_only ____________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "72dfbc0f9ffe8c22e942a15916b2fbfcd93a6aefa89f6004f8c8c32537a341e6"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-03-key-not-handed-back",
      "acceptance": [
        "AC-03-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_settingswin.py::test_the_key_field_shows_only_for_an_api_brain_and_a_key_typed_is_handed_back_once"
      ],
      "method": "Red drill M7-03-key-not-handed-back through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "0ef46abd49148651a55d9cbc783fadaebb0f4a4ab4c870c609ebfa176e6aa7be",
      "red": {
        "mutation": "M7-03-key-not-handed-back: in chatmon/settingswin.py, '\"api_key\": (self._brain_name(), key) if key and self._brain_name() in self._keys else None,' became '\"api_key\": None,'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_key_field_shows_only_for_an_api_brain_and_a_key_typed_is_handed_back_once",
        "observed_diagnostic": "_ test_the_key_field_shows_only_for_an_api_brain_and_a_key_typed_is_handed_back_once _",
        "before": [
          {
            "path": "chatmon/settingswin.py",
            "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/settingswin.py",
            "sha256": "69d7dab72865a0e7830bda699c48d317159f3486c742891e473d58b3c731282c"
          }
        ],
        "after": [
          {
            "path": "chatmon/settingswin.py",
            "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-03-test-without-typed-key",
      "acceptance": [
        "AC-03-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_settingswin.py::test_test_and_remove_key_ask_the_companion"
      ],
      "method": "Red drill M7-03-test-without-typed-key through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "0ef46abd49148651a55d9cbc783fadaebb0f4a4ab4c870c609ebfa176e6aa7be",
      "red": {
        "mutation": "M7-03-test-without-typed-key: in chatmon/settingswin.py, 'self.test_requested.emit(name, self.key.text().strip() if name in self._keys else \"\")' became 'self.test_requested.emit(name, \"\")'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_test_and_remove_key_ask_the_companion",
        "observed_diagnostic": "_________________ test_test_and_remove_key_ask_the_companion __________________",
        "before": [
          {
            "path": "chatmon/settingswin.py",
            "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/settingswin.py",
            "sha256": "3d8072cc0797d5608eb825c9b5c56ee1a2ecdda959fa9db223dbdc22a13b2094"
          }
        ],
        "after": [
          {
            "path": "chatmon/settingswin.py",
            "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-03-text-scale-unapplied",
      "acceptance": [
        "AC-03-2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_text_size_and_how_long_bubbles_stay_apply_at_once"
      ],
      "method": "Red drill M7-03-text-scale-unapplied through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "0ef46abd49148651a55d9cbc783fadaebb0f4a4ab4c870c609ebfa176e6aa7be",
      "red": {
        "mutation": "M7-03-text-scale-unapplied: in chatmon/app.py, '        self.stage.bubble.set_text_scale(scale)\\r\\n' became '\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_text_size_and_how_long_bubbles_stay_apply_at_once",
        "observed_diagnostic": "___________ test_text_size_and_how_long_bubbles_stay_apply_at_once ____________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "04bff04b3c930746b59296cf519f16cb48f0ce4b04129bf4d04871af6a99df96"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-03-cues-not-handed-back",
      "acceptance": [
        "AC-03-2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_settingswin.py::test_the_accessibility_tab_hands_back_what_was_set"
      ],
      "method": "Red drill M7-03-cues-not-handed-back through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "0ef46abd49148651a55d9cbc783fadaebb0f4a4ab4c870c609ebfa176e6aa7be",
      "red": {
        "mutation": "M7-03-cues-not-handed-back: in chatmon/settingswin.py, '\"cues\": {name: box.isChecked() for name, box in self.cues.items()},' became '\"cues\": {},'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_accessibility_tab_hands_back_what_was_set",
        "observed_diagnostic": "_____________ test_the_accessibility_tab_hands_back_what_was_set ______________",
        "before": [
          {
            "path": "chatmon/settingswin.py",
            "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/settingswin.py",
            "sha256": "d5a1c046d8d3b9bf2850dada7d377a059da40a1a554dc26e5676da9164bbdc9a"
          }
        ],
        "after": [
          {
            "path": "chatmon/settingswin.py",
            "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-03-snooze-from-breaks",
      "acceptance": [
        "AC-03-3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_reminders.py::test_reminders_snooze_by_their_own_setting_not_the_breaks"
      ],
      "method": "Red drill M7-03-snooze-from-breaks through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "0ef46abd49148651a55d9cbc783fadaebb0f4a4ab4c870c609ebfa176e6aa7be",
      "red": {
        "mutation": "M7-03-snooze-from-breaks: in chatmon/app.py, '        return float(self.config[\"reminders\"][\"snooze_minutes\"])' became '        return float(self.config[\"breaks\"][\"snooze_minutes\"])'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_reminders_snooze_by_their_own_setting_not_the_breaks",
        "observed_diagnostic": "__________ test_reminders_snooze_by_their_own_setting_not_the_breaks __________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "97aff18cb248d9848601e546ab416935755c0520e6659e788798cf676e6c59e0"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-03-interval-needs-restart",
      "acceptance": [
        "AC-03-4"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_the_update_check_interval_applies_without_a_restart"
      ],
      "method": "Red drill M7-03-interval-needs-restart through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "0ef46abd49148651a55d9cbc783fadaebb0f4a4ab4c870c609ebfa176e6aa7be",
      "red": {
        "mutation": "M7-03-interval-needs-restart: in chatmon/app.py, '        self._updates_timer.setInterval(' became '        (lambda ms: None)('",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_update_check_interval_applies_without_a_restart",
        "observed_diagnostic": "__________ test_the_update_check_interval_applies_without_a_restart ___________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "72a1a20391f3daaf777787c84315e4a3300be15517683422ce9d1f23143f4356"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-03-battery-order-window",
      "acceptance": [
        "AC-03-5"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_settingswin.py::test_reminders_have_their_own_snooze_and_almost_empty_stays_below_low"
      ],
      "method": "Red drill M7-03-battery-order-window through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "0ef46abd49148651a55d9cbc783fadaebb0f4a4ab4c870c609ebfa176e6aa7be",
      "red": {
        "mutation": "M7-03-battery-order-window: in chatmon/settingswin.py, 'self.battery_critical.setMaximum(max(1, low - 1) if low else 50)' became 'self.battery_critical.setMaximum(50)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_reminders_have_their_own_snooze_and_almost_empty_stays_below_low",
        "observed_diagnostic": "____ test_reminders_have_their_own_snooze_and_almost_empty_stays_below_low ____",
        "before": [
          {
            "path": "chatmon/settingswin.py",
            "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/settingswin.py",
            "sha256": "013da72845928c09da535b4e70102b018d4fa2f51342a09d574c6a90945f6d3b"
          }
        ],
        "after": [
          {
            "path": "chatmon/settingswin.py",
            "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-03-battery-order-file",
      "acceptance": [
        "AC-03-5"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_settings.py::test_almost_empty_stays_below_low_in_the_settings_file"
      ],
      "method": "Red drill M7-03-battery-order-file through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "0ef46abd49148651a55d9cbc783fadaebb0f4a4ab4c870c609ebfa176e6aa7be",
      "red": {
        "mutation": "M7-03-battery-order-file: in chatmon/settings.py, '0 < heads_up.get(\"battery_low\", 0) <= heads_up.get(\"battery_critical\", 0)' became 'False'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_almost_empty_stays_below_low_in_the_settings_file",
        "observed_diagnostic": "___________ test_almost_empty_stays_below_low_in_the_settings_file ____________",
        "before": [
          {
            "path": "chatmon/settings.py",
            "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/settings.py",
            "sha256": "0660ae380f0c2c2f853b403f3f3ed1ae59307e04fc569faa1ca67ae3b6f8b0a5"
          }
        ],
        "after": [
          {
            "path": "chatmon/settings.py",
            "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-04-done-keeps-it",
      "acceptance": [
        "AC-04-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_reminders.py::test_a_reminder_that_comes_due_waits_until_done_or_snoozed"
      ],
      "method": "Red drill M7-04-done-keeps-it through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "a4c6d141f6f6b4ec78449cc5adbaafbf99418c6a421ba9341722aa81b4079a50"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "025c386f89a3ee0d9fcd403ffcf000e644e238338c98ae6fde08693256e0890d"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "e4527c1b87ccc4b30b1dfda7913927b99e2e29df0484ce0497419932e46df1d5"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "22d8327c7456f03af9cec85507b61665ca1b274e40ccaf339c354005ae04df23",
      "red": {
        "mutation": "M7-04-done-keeps-it: in chatmon/app.py, '        if self.reminders.acknowledge(rid, time.time()):' became '        if self.reminders.get(rid):'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_reminder_that_comes_due_waits_until_done_or_snoozed",
        "observed_diagnostic": "_________ test_a_reminder_that_comes_due_waits_until_done_or_snoozed __________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "5632a3ed148ac86fc5b6c6fd2d20de595bd0aabdfdc4b8e8f333f7cc9a3b2d4f"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-04-later-missing",
      "acceptance": [
        "AC-04-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_reminders.py::test_a_repeating_reminder_moves_on_when_done_and_later_offers_every_snooze"
      ],
      "method": "Red drill M7-04-later-missing through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "a4c6d141f6f6b4ec78449cc5adbaafbf99418c6a421ba9341722aa81b4079a50"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "025c386f89a3ee0d9fcd403ffcf000e644e238338c98ae6fde08693256e0890d"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "e4527c1b87ccc4b30b1dfda7913927b99e2e29df0484ce0497419932e46df1d5"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "22d8327c7456f03af9cec85507b61665ca1b274e40ccaf339c354005ae04df23",
      "red": {
        "mutation": "M7-04-later-missing: in chatmon/app.py, '            (\"Later…\", partial(self._offer_snoozes, r.id)),\\r\\n' became '\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_repeating_reminder_moves_on_when_done_and_later_offers_every_snooze",
        "observed_diagnostic": "_ test_a_repeating_reminder_moves_on_when_done_and_later_offers_every_snooze __",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "b35fbe39d6dd84d4e617d2ef33a007d294ce498c98fad87ea39e2de01355f73d"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-04-not-restored",
      "acceptance": [
        "AC-04-2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_reminders.py::test_reminders_fired_and_not_done_come_back_at_the_next_start"
      ],
      "method": "Red drill M7-04-not-restored through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "a4c6d141f6f6b4ec78449cc5adbaafbf99418c6a421ba9341722aa81b4079a50"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "025c386f89a3ee0d9fcd403ffcf000e644e238338c98ae6fde08693256e0890d"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "e4527c1b87ccc4b30b1dfda7913927b99e2e29df0484ce0497419932e46df1d5"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "22d8327c7456f03af9cec85507b61665ca1b274e40ccaf339c354005ae04df23",
      "red": {
        "mutation": "M7-04-not-restored: in chatmon/app.py, '        self._show_due_reminders()  # fired and not yet done or snoozed' became '        pass  # fired and not yet done or snoozed'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_reminders_fired_and_not_done_come_back_at_the_next_start",
        "observed_diagnostic": "________ test_reminders_fired_and_not_done_come_back_at_the_next_start ________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "3f1d3fbbd24495846eb1613c4879f6449ffea0bab7975d9a61661cd087c9eb1b"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-04-focus-held-forever",
      "acceptance": [
        "AC-04-2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_reminders.py::test_reminders_fired_and_not_done_come_back_at_the_next_start"
      ],
      "method": "Red drill M7-04-focus-held-forever through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "a4c6d141f6f6b4ec78449cc5adbaafbf99418c6a421ba9341722aa81b4079a50"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "025c386f89a3ee0d9fcd403ffcf000e644e238338c98ae6fde08693256e0890d"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "e4527c1b87ccc4b30b1dfda7913927b99e2e29df0484ce0497419932e46df1d5"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "22d8327c7456f03af9cec85507b61665ca1b274e40ccaf339c354005ae04df23",
      "red": {
        "mutation": "M7-04-focus-held-forever: in chatmon/app.py, '        for r in [r for r in due if r.kind == \"focus\"]:\\r\\n' became '        for r in []:\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_reminders_fired_and_not_done_come_back_at_the_next_start",
        "observed_diagnostic": "________ test_reminders_fired_and_not_done_come_back_at_the_next_start ________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "f5b14b39b24ddf1463182cb5203b6d583700dc6ffee22d83377d9b1e4929432f"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-04-edit-ignores-time",
      "acceptance": [
        "AC-04-3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_reminders.py::test_each_reminder_in_the_menu_can_be_changed_repeated_or_cancelled"
      ],
      "method": "Red drill M7-04-edit-ignores-time through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "a4c6d141f6f6b4ec78449cc5adbaafbf99418c6a421ba9341722aa81b4079a50"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "025c386f89a3ee0d9fcd403ffcf000e644e238338c98ae6fde08693256e0890d"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "e4527c1b87ccc4b30b1dfda7913927b99e2e29df0484ce0497419932e46df1d5"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "22d8327c7456f03af9cec85507b61665ca1b274e40ccaf339c354005ae04df23",
      "red": {
        "mutation": "M7-04-edit-ignores-time: in chatmon/app.py, '            changes[\"when\"] = when.due.timestamp()\\r\\n' became '            pass\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_each_reminder_in_the_menu_can_be_changed_repeated_or_cancelled",
        "observed_diagnostic": "_____ test_each_reminder_in_the_menu_can_be_changed_repeated_or_cancelled _____",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "4ed540f95658fdeed50762f6f5f1c8badef2a86cafcbf87aa1e92b0356d47856"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-04-repeat-dropped",
      "acceptance": [
        "AC-04-4"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_reminders.py::test_adding_a_reminder_keeps_its_repeat_and_explains_an_unclear_time"
      ],
      "method": "Red drill M7-04-repeat-dropped through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "a4c6d141f6f6b4ec78449cc5adbaafbf99418c6a421ba9341722aa81b4079a50"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "025c386f89a3ee0d9fcd403ffcf000e644e238338c98ae6fde08693256e0890d"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "e4527c1b87ccc4b30b1dfda7913927b99e2e29df0484ce0497419932e46df1d5"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "22d8327c7456f03af9cec85507b61665ca1b274e40ccaf339c354005ae04df23",
      "red": {
        "mutation": "M7-04-repeat-dropped: in chatmon/commands.py, 'command.kind, repeat=command.repeat)' became 'command.kind, repeat=None)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_adding_a_reminder_keeps_its_repeat_and_explains_an_unclear_time",
        "observed_diagnostic": "____ test_adding_a_reminder_keeps_its_repeat_and_explains_an_unclear_time _____",
        "before": [
          {
            "path": "chatmon/commands.py",
            "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/commands.py",
            "sha256": "e5a31788e61cca2b3ad5f9316207cd55b5cfa9e303f0db29364e2d8ea1632098"
          }
        ],
        "after": [
          {
            "path": "chatmon/commands.py",
            "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-04-cli-no-explanation",
      "acceptance": [
        "AC-04-4"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_cli.py::test_a_reminder_it_cant_read_says_so_and_exits_2"
      ],
      "method": "Red drill M7-04-cli-no-explanation through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "a4c6d141f6f6b4ec78449cc5adbaafbf99418c6a421ba9341722aa81b4079a50"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "025c386f89a3ee0d9fcd403ffcf000e644e238338c98ae6fde08693256e0890d"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "e4527c1b87ccc4b30b1dfda7913927b99e2e29df0484ce0497419932e46df1d5"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "22d8327c7456f03af9cec85507b61665ca1b274e40ccaf339c354005ae04df23",
      "red": {
        "mutation": "M7-04-cli-no-explanation: in chatmon/cli.py, 'why = reminders.explain(command, markdown=False) if command is not None and command.kind == \"unclear\" else \"\"' became 'why = \"\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_reminder_it_cant_read_says_so_and_exits_2",
        "observed_diagnostic": "______________ test_a_reminder_it_cant_read_says_so_and_exits_2 _______________",
        "before": [
          {
            "path": "chatmon/cli.py",
            "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/cli.py",
            "sha256": "b5169748ae3a1aa86996d1c2dcfbb8177bed9f8b59f50df02b04c9c700ad5b77"
          }
        ],
        "after": [
          {
            "path": "chatmon/cli.py",
            "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-05-no-summary",
      "acceptance": [
        "AC-05-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_smoke.py::test_a_focus_session_holds_what_comes_on_its_own_until_its_over_then_sums_it_up"
      ],
      "method": "Red drill M7-05-no-summary through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "a4c6d141f6f6b4ec78449cc5adbaafbf99418c6a421ba9341722aa81b4079a50"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "025c386f89a3ee0d9fcd403ffcf000e644e238338c98ae6fde08693256e0890d"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "e4527c1b87ccc4b30b1dfda7913927b99e2e29df0484ce0497419932e46df1d5"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "3676da33ed511c55a37a5e3cb679bc02e85bd32025a3b1592322e62fca7c865e",
      "red": {
        "mutation": "M7-05-no-summary: in chatmon/app.py, '        return self.messages.take(lambda m: m in held and not m.buttons)' became '        return []'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_focus_session_holds_what_comes_on_its_own_until_its_over_then_sums_it_up",
        "observed_diagnostic": "_ test_a_focus_session_holds_what_comes_on_its_own_until_its_over_then_sums_it_up _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "dbfe63fff9b2daacc2fa462697c5a8647bbe9e1c06e7ce57fc3e9b4fd6b94a47"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-06-not-recent",
      "acceptance": [
        "AC-06-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_recent_messages_are_in_the_menu_and_show_again"
      ],
      "method": "Red drill M7-06-not-recent through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "d5c2f4228a737c833bac1cc19ac3b5386bde65b6bf57f60d4f2ace4b1c09b7d1",
      "red": {
        "mutation": "M7-06-not-recent: in chatmon/app.py, '        self._recent.append((time.time(), message))\\r\\n' became '\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_recent_messages_are_in_the_menu_and_show_again",
        "observed_diagnostic": "_____________ test_recent_messages_are_in_the_menu_and_show_again _____________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "ea4c1a2fd9e474df3a8e9b95689a0eaf1e31dc6106fca91f11c93fe913582f43"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-06-click-ignores-missed",
      "acceptance": [
        "AC-06-2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_a_bubble_that_went_by_while_you_were_away_comes_back_with_a_click"
      ],
      "method": "Red drill M7-06-click-ignores-missed through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "d5c2f4228a737c833bac1cc19ac3b5386bde65b6bf57f60d4f2ace4b1c09b7d1",
      "red": {
        "mutation": "M7-06-click-ignores-missed: in chatmon/app.py, '        elif self._missed and not self.stage.message_visible():' became '        elif False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_bubble_that_went_by_while_you_were_away_comes_back_with_a_click",
        "observed_diagnostic": "___ test_a_bubble_that_went_by_while_you_were_away_comes_back_with_a_click ____",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "d4f5b3eafcdcf0d5440289e2cfd123b93dd3473ad727488d67c526e030059fd6"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-06-dropped-not-missed",
      "acceptance": [
        "AC-06-2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_plain_bubbles_the_queue_dropped_count_as_missed"
      ],
      "method": "Red drill M7-06-dropped-not-missed through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "d5c2f4228a737c833bac1cc19ac3b5386bde65b6bf57f60d4f2ace4b1c09b7d1",
      "red": {
        "mutation": "M7-06-dropped-not-missed: in chatmon/app.py, 'self._missed += [m for m in self.messages.add(message) if m is not message]' became 'self.messages.add(message)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_plain_bubbles_the_queue_dropped_count_as_missed",
        "observed_diagnostic": "____________ test_plain_bubbles_the_queue_dropped_count_as_missed _____________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "5d06aef3b4232a80ad13d65b993dafbf13471d2a63a8dc2c265b7921d3e93dff"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-07-no-tooltip",
      "acceptance": [
        "AC-07-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_the_tray_and_the_stage_name_what_each_agent_is_doing_with_a_badge_while_one_needs_you"
      ],
      "method": "Red drill M7-07-no-tooltip through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "a849300cbe173d5996052e021575090bd77ed05f0b31c4ef0ea4252ec458b8f2"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "c9748102e3e1063b9e769e535af9cea8ec905abae66ff988fb109b5f1d496562"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "f7e4fdafc15b570e5ad1bc93db79659d4e109392355b4a3781a14d8039d4975f"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "f6a09bac042388d63b21af89e8d297a6cd2fc57d83356d90a1bd633bd8e178ed",
      "red": {
        "mutation": "M7-07-no-tooltip: in chatmon/app.py, '        self.tray.setToolTip(f\"Chatmon\\\\n{states}\" if states else \"Chatmon\")' became '        self.tray.setToolTip(\"Chatmon\")'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_tray_and_the_stage_name_what_each_agent_is_doing_with_a_badge_while_one_needs_you",
        "observed_diagnostic": "_ test_the_tray_and_the_stage_name_what_each_agent_is_doing_with_a_badge_while_one_needs_you _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "40d5d878e983f1de12753c85b695cfeb8fdd341c96252d39ed1c83b0e9df93a5"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-07-no-badge",
      "acceptance": [
        "AC-07-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_the_tray_and_the_stage_name_what_each_agent_is_doing_with_a_badge_while_one_needs_you"
      ],
      "method": "Red drill M7-07-no-badge through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "a849300cbe173d5996052e021575090bd77ed05f0b31c4ef0ea4252ec458b8f2"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "c9748102e3e1063b9e769e535af9cea8ec905abae66ff988fb109b5f1d496562"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "f7e4fdafc15b570e5ad1bc93db79659d4e109392355b4a3781a14d8039d4975f"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "f6a09bac042388d63b21af89e8d297a6cd2fc57d83356d90a1bd633bd8e178ed",
      "red": {
        "mutation": "M7-07-no-badge: in chatmon/app.py, '            return QIcon(_with_badge(frame.pixmap) if self._tray_badge else frame.pixmap)' became '            return QIcon(frame.pixmap)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_tray_and_the_stage_name_what_each_agent_is_doing_with_a_badge_while_one_needs_you",
        "observed_diagnostic": "_ test_the_tray_and_the_stage_name_what_each_agent_is_doing_with_a_badge_while_one_needs_you _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "46e4a721182d184bb964b29b914d1d59100edd711e63665f5e0603ca5243ed74"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-07-agents-command-is-help",
      "acceptance": [
        "AC-07-2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_the_agents_command_says_how_each_stands"
      ],
      "method": "Red drill M7-07-agents-command-is-help through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "a849300cbe173d5996052e021575090bd77ed05f0b31c4ef0ea4252ec458b8f2"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "f7e4fdafc15b570e5ad1bc93db79659d4e109392355b4a3781a14d8039d4975f"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "f59b52b9b7db883584ed637009d9fc8cd3ef093fa3573516a6a8d0ec6aa33c12",
      "red": {
        "mutation": "M7-07-agents-command-is-help: in chatmon/commands.py, '\"agents\": _agents,' became '\"agents\": _help,'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_agents_command_says_how_each_stands",
        "observed_diagnostic": "________________ test_the_agents_command_says_how_each_stands _________________",
        "before": [
          {
            "path": "chatmon/commands.py",
            "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/commands.py",
            "sha256": "5e73cb1c34bde96d7e0a025d677c12371b4879a307ad670fb5e7eecff7a7b4f2"
          }
        ],
        "after": [
          {
            "path": "chatmon/commands.py",
            "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-07-no-reply",
      "acceptance": [
        "AC-07-3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_chatmon_status_hears_the_live_states_from_the_running_chatmon"
      ],
      "method": "Red drill M7-07-no-reply through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "a849300cbe173d5996052e021575090bd77ed05f0b31c4ef0ea4252ec458b8f2"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "f7e4fdafc15b570e5ad1bc93db79659d4e109392355b4a3781a14d8039d4975f"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "f59b52b9b7db883584ed637009d9fc8cd3ef093fa3573516a6a8d0ec6aa33c12",
      "red": {
        "mutation": "M7-07-no-reply: in chatmon/app.py, '                            sock.write(events.reply_line(reply))' became '                            pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_chatmon_status_hears_the_live_states_from_the_running_chatmon",
        "observed_diagnostic": "_____ test_chatmon_status_hears_the_live_states_from_the_running_chatmon ______",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "082e005039090dfa6fffcd270fd2642f36d75e9adc1eddcc2735222f3313cb27"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-07-cli-ignores-live",
      "acceptance": [
        "AC-07-3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_cli.py::test_status_says_whether_its_running_the_brain_reminders_and_agents"
      ],
      "method": "Red drill M7-07-cli-ignores-live through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "a849300cbe173d5996052e021575090bd77ed05f0b31c4ef0ea4252ec458b8f2"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "f7e4fdafc15b570e5ad1bc93db79659d4e109392355b4a3781a14d8039d4975f"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "f59b52b9b7db883584ed637009d9fc8cd3ef093fa3573516a6a8d0ec6aa33c12",
      "red": {
        "mutation": "M7-07-cli-ignores-live: in chatmon/cli.py, '    if live is not None:\\r\\n' became '    if False:\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_status_says_whether_its_running_the_brain_reminders_and_agents",
        "observed_diagnostic": "_____ test_status_says_whether_its_running_the_brain_reminders_and_agents _____",
        "before": [
          {
            "path": "chatmon/cli.py",
            "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/cli.py",
            "sha256": "97591d410682545599966e258131360223d9b86be25bd49970869b803c6f565e"
          }
        ],
        "after": [
          {
            "path": "chatmon/cli.py",
            "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-08-text-not-attached",
      "acceptance": [
        "AC-08-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_quick_actions_attach_the_clipboard_only_when_chosen_and_type_the_prompt"
      ],
      "method": "Red drill M7-08-text-not-attached through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "a8a9358207bbf3ff9dad8d13168c71a28cb43d91544cbb75658db9c04d717f08",
      "red": {
        "mutation": "M7-08-text-not-attached: in chatmon/app.py, '            self._attach(lambda: attachments.from_text(payload))  # attached, however short' became '            pass  # attached, however short'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_quick_actions_attach_the_clipboard_only_when_chosen_and_type_the_prompt",
        "observed_diagnostic": "_ test_quick_actions_attach_the_clipboard_only_when_chosen_and_type_the_prompt _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "92715392d1c3570af1fe01a9b837ee4a8eef1870fede858e64721758e1f0ae94"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-09-no-search-inside",
      "acceptance": [
        "AC-09-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_chatswin.py::test_the_window_lists_every_chat_and_searches_titles_then_words_inside"
      ],
      "method": "Red drill M7-09-no-search-inside through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "3c036d7ab8cf9483ce526519528ed903dc2d2d44cdf32f4a93ae69c3e8708f0a"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "291cd461529db851480828ecb52398b5cd9b3d3c02fe874e7a57ffabaf440ab3"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "da3d7845b19bb1888001e93d1f13b5319288d0e36d5e66a2dc277e700a9bc4b9"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_answers.py",
          "sha256": "324749f6668263eec4508df65370296e91d712da9e8acebc25ac0b5c362da433"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a75812ca8e75ee2390fc2456d64fd4d4d1744a3a56b9c03a8edf5c586dd41b98"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_chatswin.py",
          "sha256": "8854160e3c08385f0e4bf4d7ca024e50c5822caefdbafa351fd546966d2f0373"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "16614abf8935b828ba3c463a243fe5f36b2e397edf7b420d6611be2e2c1430f7",
      "red": {
        "mutation": "M7-09-no-search-inside: in chatmon/chatswin.py, '                inside.add(listed.id)\\n' became '                pass\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_window_lists_every_chat_and_searches_titles_then_words_inside",
        "observed_diagnostic": "___ test_the_window_lists_every_chat_and_searches_titles_then_words_inside ____",
        "before": [
          {
            "path": "chatmon/chatswin.py",
            "sha256": "da3d7845b19bb1888001e93d1f13b5319288d0e36d5e66a2dc277e700a9bc4b9"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/chatswin.py",
            "sha256": "3bb69b67be5f931647b2f6a850a91be8ce477c24ec9626ec901a4dee5cb58b0f"
          }
        ],
        "after": [
          {
            "path": "chatmon/chatswin.py",
            "sha256": "da3d7845b19bb1888001e93d1f13b5319288d0e36d5e66a2dc277e700a9bc4b9"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-09-no-all-chats",
      "acceptance": [
        "AC-09-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_smoke.py::test_the_menu_lists_the_newest_chats_and_all_chats_opens_the_window"
      ],
      "method": "Red drill M7-09-no-all-chats through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "3c036d7ab8cf9483ce526519528ed903dc2d2d44cdf32f4a93ae69c3e8708f0a"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "291cd461529db851480828ecb52398b5cd9b3d3c02fe874e7a57ffabaf440ab3"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "da3d7845b19bb1888001e93d1f13b5319288d0e36d5e66a2dc277e700a9bc4b9"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_answers.py",
          "sha256": "324749f6668263eec4508df65370296e91d712da9e8acebc25ac0b5c362da433"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a75812ca8e75ee2390fc2456d64fd4d4d1744a3a56b9c03a8edf5c586dd41b98"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_chatswin.py",
          "sha256": "8854160e3c08385f0e4bf4d7ca024e50c5822caefdbafa351fd546966d2f0373"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "16614abf8935b828ba3c463a243fe5f36b2e397edf7b420d6611be2e2c1430f7",
      "red": {
        "mutation": "M7-09-no-all-chats: in chatmon/menus.py, '    sub.addAction(\"All chats…\", c.open_chats)\\r\\n' became '\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_menu_lists_the_newest_chats_and_all_chats_opens_the_window",
        "observed_diagnostic": "_____ test_the_menu_lists_the_newest_chats_and_all_chats_opens_the_window _____",
        "before": [
          {
            "path": "chatmon/menus.py",
            "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/menus.py",
            "sha256": "317e3dc1e2e3d404384558857dd05f981149d83c37d0a71f9c3c3f5db14090d3"
          }
        ],
        "after": [
          {
            "path": "chatmon/menus.py",
            "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-09-answer-not-by",
      "acceptance": [
        "AC-09-2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_answers.py::test_a_chat_keeps_its_brain_and_another_brain_can_answer_the_last_question"
      ],
      "method": "Red drill M7-09-answer-not-by through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "3c036d7ab8cf9483ce526519528ed903dc2d2d44cdf32f4a93ae69c3e8708f0a"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_answers.py",
          "sha256": "324749f6668263eec4508df65370296e91d712da9e8acebc25ac0b5c362da433"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a75812ca8e75ee2390fc2456d64fd4d4d1744a3a56b9c03a8edf5c586dd41b98"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "17abeed3258d72fdc41913b91fd22939dd27f1a12ae09745c31bbd10ea66cde6",
      "red": {
        "mutation": "M7-09-answer-not-by: in chatmon/app.py, 'self.chat.add(chats.Message(\"assistant\", answer, brain=label, by=name))' became 'self.chat.add(chats.Message(\"assistant\", answer, brain=label))'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_chat_keeps_its_brain_and_another_brain_can_answer_the_last_question",
        "observed_diagnostic": "_ test_a_chat_keeps_its_brain_and_another_brain_can_answer_the_last_question __",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "683edea0c09f262fa8a239c5f263cd2129a540087d3bdeb609e938cd5eeb9230"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-09-chat-brain-ignored",
      "acceptance": [
        "AC-09-2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_answers.py::test_carrying_a_chat_on_asks_its_own_brain_before_the_one_picked"
      ],
      "method": "Red drill M7-09-chat-brain-ignored through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "3c036d7ab8cf9483ce526519528ed903dc2d2d44cdf32f4a93ae69c3e8708f0a"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_answers.py",
          "sha256": "324749f6668263eec4508df65370296e91d712da9e8acebc25ac0b5c362da433"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a75812ca8e75ee2390fc2456d64fd4d4d1744a3a56b9c03a8edf5c586dd41b98"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "17abeed3258d72fdc41913b91fd22939dd27f1a12ae09745c31bbd10ea66cde6",
      "red": {
        "mutation": "M7-09-chat-brain-ignored: in chatmon/app.py, 'picked, prefer = self.config[\"ai\"][\"brain\"], self.state.get(\"brain\"), self.chat.brain or None' became 'picked, prefer = self.config[\"ai\"][\"brain\"], self.state.get(\"brain\"), None'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_carrying_a_chat_on_asks_its_own_brain_before_the_one_picked",
        "observed_diagnostic": "______ test_carrying_a_chat_on_asks_its_own_brain_before_the_one_picked _______",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "e6af7676a558a866befd1c74ffc4f32285dd382b8669ca1a3d325bf559dc1d20"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-09-restore-not-reread",
      "acceptance": [
        "AC-09-3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_back_up_and_bring_back_from_settings"
      ],
      "method": "Red drill M7-09-restore-not-reread through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "3c036d7ab8cf9483ce526519528ed903dc2d2d44cdf32f4a93ae69c3e8708f0a"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "291cd461529db851480828ecb52398b5cd9b3d3c02fe874e7a57ffabaf440ab3"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "da3d7845b19bb1888001e93d1f13b5319288d0e36d5e66a2dc277e700a9bc4b9"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_answers.py",
          "sha256": "324749f6668263eec4508df65370296e91d712da9e8acebc25ac0b5c362da433"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a75812ca8e75ee2390fc2456d64fd4d4d1744a3a56b9c03a8edf5c586dd41b98"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_chatswin.py",
          "sha256": "8854160e3c08385f0e4bf4d7ca024e50c5822caefdbafa351fd546966d2f0373"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "16614abf8935b828ba3c463a243fe5f36b2e397edf7b420d6611be2e2c1430f7",
      "red": {
        "mutation": "M7-09-restore-not-reread: in chatmon/app.py, '        self.reminders = reminders.ReminderBook.from_list(self.state.get(\"reminders\", []))\\r\\n        self._sync_focus_hold()\\r\\n        self.reload(quietly=True)' became '        self.reload(quietly=True)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_back_up_and_bring_back_from_settings",
        "observed_diagnostic": "__________________ test_back_up_and_bring_back_from_settings __________________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "e6e8ade23fda3a403dcfdf6d7926eab4d3fe5ca6cb8c87aa57a022998e1bed3c"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-09-listing-rereads",
      "acceptance": [
        "AC-09-4"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_chatswin.py::test_the_listing_reads_each_file_once_while_it_doesnt_change"
      ],
      "method": "Red drill M7-09-listing-rereads through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "3c036d7ab8cf9483ce526519528ed903dc2d2d44cdf32f4a93ae69c3e8708f0a"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "291cd461529db851480828ecb52398b5cd9b3d3c02fe874e7a57ffabaf440ab3"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "da3d7845b19bb1888001e93d1f13b5319288d0e36d5e66a2dc277e700a9bc4b9"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_answers.py",
          "sha256": "324749f6668263eec4508df65370296e91d712da9e8acebc25ac0b5c362da433"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a75812ca8e75ee2390fc2456d64fd4d4d1744a3a56b9c03a8edf5c586dd41b98"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_chatswin.py",
          "sha256": "8854160e3c08385f0e4bf4d7ca024e50c5822caefdbafa351fd546966d2f0373"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "16614abf8935b828ba3c463a243fe5f36b2e397edf7b420d6611be2e2c1430f7",
      "red": {
        "mutation": "M7-09-listing-rereads: in chatmon/chats.py, '            if seen is None or seen[:2] != (info.st_mtime_ns, info.st_size):' became '            if True:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_listing_reads_each_file_once_while_it_doesnt_change",
        "observed_diagnostic": "________ test_the_listing_reads_each_file_once_while_it_doesnt_change _________",
        "before": [
          {
            "path": "chatmon/chats.py",
            "sha256": "291cd461529db851480828ecb52398b5cd9b3d3c02fe874e7a57ffabaf440ab3"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/chats.py",
            "sha256": "d069dc6f73a09a85815384b6763d1010d3ccfecf4d7ecd41402ca63a381a6673"
          }
        ],
        "after": [
          {
            "path": "chatmon/chats.py",
            "sha256": "291cd461529db851480828ecb52398b5cd9b3d3c02fe874e7a57ffabaf440ab3"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-10-copy-unwired",
      "acceptance": [
        "AC-10-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_copy_puts_an_answer_on_the_clipboard"
      ],
      "method": "Red drill M7-10-copy-unwired through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "961a8ac0ad536540bc05978c2e04678753fbba4954735701de3d95d28756240a",
      "red": {
        "mutation": "M7-10-copy-unwired: in chatmon/app.py, '        self.ask_box.copy_requested.connect(self._copy)\\r\\n' became '\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_copy_puts_an_answer_on_the_clipboard",
        "observed_diagnostic": "__________________ test_copy_puts_an_answer_on_the_clipboard __________________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "a2076212c473e84573181af7df69db55c1c8d7fdbf8e80f7518edd9064855a9a"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-10-ctrl-number-ignored",
      "acceptance": [
        "AC-10-2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_ctrl_and_a_number_press_a_bubbles_buttons_while_the_box_is_open"
      ],
      "method": "Red drill M7-10-ctrl-number-ignored through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "961a8ac0ad536540bc05978c2e04678753fbba4954735701de3d95d28756240a",
      "red": {
        "mutation": "M7-10-ctrl-number-ignored: in chatmon/app.py, '                return self._press_bubble_button(key - Qt.Key.Key_1.value)' became '                return False'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_ctrl_and_a_number_press_a_bubbles_buttons_while_the_box_is_open",
        "observed_diagnostic": "____ test_ctrl_and_a_number_press_a_bubbles_buttons_while_the_box_is_open _____",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "d93bd6ee0afeb2010bdb7b96871c212087d559ceb80a839f2787530d7d6bf118"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-10-expired-unanswerable",
      "acceptance": [
        "AC-10-3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_a_buttons_label_typed_after_its_bubble_went_is_answerable_for_a_while"
      ],
      "method": "Red drill M7-10-expired-unanswerable through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "961a8ac0ad536540bc05978c2e04678753fbba4954735701de3d95d28756240a",
      "red": {
        "mutation": "M7-10-expired-unanswerable: in chatmon/app.py, '            self._answerable = (now, list(message.buttons))\\r\\n' became '            pass\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_buttons_label_typed_after_its_bubble_went_is_answerable_for_a_while",
        "observed_diagnostic": "_ test_a_buttons_label_typed_after_its_bubble_went_is_answerable_for_a_while __",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "45bc0a9fd5e50d8ff2215f2a20842de105702205fc46ff03c7253b430cc4789b"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-11-lock-keeps-drawing",
      "acceptance": [
        "AC-11-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_a_locked_session_stops_drawing_and_the_power_saver_reaches_the_bubble_and_box"
      ],
      "method": "Red drill M7-11-lock-keeps-drawing through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "8ca7e7dd770fba4542d1289ecb43c42f76240e07e087403347485831dc619293",
      "red": {
        "mutation": "M7-11-lock-keeps-drawing: in chatmon/app.py, '            self.stage.set_drawing(not locked)  # nothing is drawn while nobody can see it' became '            pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_locked_session_stops_drawing_and_the_power_saver_reaches_the_bubble_and_box",
        "observed_diagnostic": "_ test_a_locked_session_stops_drawing_and_the_power_saver_reaches_the_bubble_and_box _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "ac7136af403ef0fc6907bccd45b45832e6a3e01cede7cb42b5e27531596899c7"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-11-box-ignores-saver",
      "acceptance": [
        "AC-11-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_a_locked_session_stops_drawing_and_the_power_saver_reaches_the_bubble_and_box"
      ],
      "method": "Red drill M7-11-box-ignores-saver through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "8ca7e7dd770fba4542d1289ecb43c42f76240e07e087403347485831dc619293",
      "red": {
        "mutation": "M7-11-box-ignores-saver: in chatmon/app.py, '        self.ask_box.set_power_saving(on)\\r\\n' became '\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_locked_session_stops_drawing_and_the_power_saver_reaches_the_bubble_and_box",
        "observed_diagnostic": "_ test_a_locked_session_stops_drawing_and_the_power_saver_reaches_the_bubble_and_box _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "6a8407f4ed0fbd3f6c82d69220f25d33b004664b8adfd49c1abf6097586c852c"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-11-palette-ignored",
      "acceptance": [
        "AC-11-2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_the_desktops_colours_and_reduced_motion_apply_at_once"
      ],
      "method": "Red drill M7-11-palette-ignored through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "8ca7e7dd770fba4542d1289ecb43c42f76240e07e087403347485831dc619293",
      "red": {
        "mutation": "M7-11-palette-ignored: in chatmon/app.py, '            QTimer.singleShot(0, self._palette_changed)\\r\\n' became '            pass\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_desktops_colours_and_reduced_motion_apply_at_once",
        "observed_diagnostic": "_________ test_the_desktops_colours_and_reduced_motion_apply_at_once __________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "b477243a0c7d8df77d1983ecff735b0d363413f8cf90e0fcf9bad608934b00e3"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-11-sound-in-quiet",
      "acceptance": [
        "AC-11-3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_sounds_play_for_alerts_only_unless_turned_on_and_never_in_quiet_or_focus"
      ],
      "method": "Red drill M7-11-sound-in-quiet through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "a849300cbe173d5996052e021575090bd77ed05f0b31c4ef0ea4252ec458b8f2"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "c9748102e3e1063b9e769e535af9cea8ec905abae66ff988fb109b5f1d496562"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "f7e4fdafc15b570e5ad1bc93db79659d4e109392355b4a3781a14d8039d4975f"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "f6a09bac042388d63b21af89e8d297a6cd2fc57d83356d90a1bd633bd8e178ed",
      "red": {
        "mutation": "M7-11-sound-in-quiet: in chatmon/app.py, '        if self._quiet or self.reminders.focus() is not None:\\r\\n            return False\\r\\n        return self._play(name)' became '        return self._play(name)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_sounds_play_for_alerts_only_unless_turned_on_and_never_in_quiet_or_focus",
        "observed_diagnostic": "_ test_sounds_play_for_alerts_only_unless_turned_on_and_never_in_quiet_or_focus _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "ae94f9ee46fcf56110550cb01df9e046bb0c3e08fd54b029f52b1467d97516ce"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-12-carry-on-forgotten",
      "acceptance": [
        "AC-12-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_after_a_while_the_box_opens_on_a_new_chat_and_carry_on_goes_back"
      ],
      "method": "Red drill M7-12-carry-on-forgotten through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/phrases/en.json",
          "sha256": "0ad5d23950aa11252a58caf94e713d198fb4deb500aa67fb60f7f191085a1da8"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "55f740ed553717b7a599bd7495bf3fd1bbf380872509c8747fc2e6d9ac41a376",
      "red": {
        "mutation": "M7-12-carry-on-forgotten: in chatmon/app.py, '            self._set_aside = set_aside\\r\\n' became '            pass\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_after_a_while_the_box_opens_on_a_new_chat_and_carry_on_goes_back",
        "observed_diagnostic": "____ test_after_a_while_the_box_opens_on_a_new_chat_and_carry_on_goes_back ____",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "b8e5d4b7028e9627390820e8c174de5e6ca69bfeee36f0486434d86481c65091"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-12-drops-question",
      "acceptance": [
        "AC-12-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_after_a_while_the_box_opens_on_a_new_chat_and_carry_on_goes_back"
      ],
      "method": "Red drill M7-12-drops-question through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/phrases/en.json",
          "sha256": "0ad5d23950aa11252a58caf94e713d198fb4deb500aa67fb60f7f191085a1da8"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "55f740ed553717b7a599bd7495bf3fd1bbf380872509c8747fc2e6d9ac41a376",
      "red": {
        "mutation": "M7-12-drops-question: in chatmon/app.py, 'and bool(self.chat.messages) and self.questions.current is None and' became 'and bool(self.chat.messages) and'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_after_a_while_the_box_opens_on_a_new_chat_and_carry_on_goes_back",
        "observed_diagnostic": "____ test_after_a_while_the_box_opens_on_a_new_chat_and_carry_on_goes_back ____",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "14a5e63f430ec4924e77ae33ef12cf65850487f812beea4f4e3ba3da288734c4"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-13-hello-every-unlock",
      "acceptance": [
        "AC-13-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_the_first_unlock_of_the_day_names_reminders_agents_and_updates_once"
      ],
      "method": "Red drill M7-13-hello-every-unlock through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "a4c6d141f6f6b4ec78449cc5adbaafbf99418c6a421ba9341722aa81b4079a50"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "025c386f89a3ee0d9fcd403ffcf000e644e238338c98ae6fde08693256e0890d"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "e4527c1b87ccc4b30b1dfda7913927b99e2e29df0484ce0497419932e46df1d5"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "e24af9ea07eba1aff8b14d717c1aa8187d93cd0573b1fa6ecf93b9c3d027a6e6",
      "red": {
        "mutation": "M7-13-hello-every-unlock: in chatmon/app.py, '        if self.state.get(\"hello_day\") == today.isoformat():\\r\\n            return False\\r\\n' became ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_first_unlock_of_the_day_names_reminders_agents_and_updates_once",
        "observed_diagnostic": "__ test_the_first_unlock_of_the_day_names_reminders_agents_and_updates_once ___",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "bc4bb22cc3215d38c4413ce45a8fe916219d2e54d2301192ddbf0cdeef612ece"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M0-06-table-unfiltered",
      "acceptance": [
        "AC-M0-6"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_commands.py::test_a_phrase_is_found_as_typed_give_or_take_case_and_punctuation"
      ],
      "method": "Red drill M0-06-table-unfiltered through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "93de17910e21bb29fc63323a47f45a253ca7871bb88e5b98d8b4f66182886d92",
      "red": {
        "mutation": "M0-06-table-unfiltered: in chatmon/commands.py, '        return command if command in COMMANDS else None' became '        return command'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_phrase_is_found_as_typed_give_or_take_case_and_punctuation",
        "observed_diagnostic": "______ test_a_phrase_is_found_as_typed_give_or_take_case_and_punctuation ______",
        "before": [
          {
            "path": "chatmon/commands.py",
            "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/commands.py",
            "sha256": "37e8bcc3a22ca14f6baa695c96a975a474420d820da5a5c96e9fdf837a321311"
          }
        ],
        "after": [
          {
            "path": "chatmon/commands.py",
            "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M0-07-waits-for-brain",
      "acceptance": [
        "AC-M0-7"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_answers.py::test_asking_never_waits_on_the_screens_thread_to_find_the_brain"
      ],
      "method": "Red drill M0-07-waits-for-brain through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "3c036d7ab8cf9483ce526519528ed903dc2d2d44cdf32f4a93ae69c3e8708f0a"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_answers.py",
          "sha256": "324749f6668263eec4508df65370296e91d712da9e8acebc25ac0b5c362da433"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a75812ca8e75ee2390fc2456d64fd4d4d1744a3a56b9c03a8edf5c586dd41b98"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "eff80296798f27b428ad17a3140777d79bc11e5ed9764f97c05ecc69b17c564e",
      "red": {
        "mutation": "M0-07-waits-for-brain: in chatmon/app.py, 'quick = brains.choose(self.brains, configured, picked, wait=False, prefer=prefer)' became 'quick = brains.choose(self.brains, configured, picked, wait=True, prefer=prefer)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_asking_never_waits_on_the_screens_thread_to_find_the_brain",
        "observed_diagnostic": "_______ test_asking_never_waits_on_the_screens_thread_to_find_the_brain _______",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "0007b5fad0fda55187d92b48ea2aacbd027cb3b1ed4c94b3d87c8dad4535f2d3"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M0-08-connections-unchecked",
      "acceptance": [
        "AC-M0-8"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_on_windows_each_connection_is_checked_to_be_yours"
      ],
      "method": "Red drill M0-08-connections-unchecked through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "a849300cbe173d5996052e021575090bd77ed05f0b31c4ef0ea4252ec458b8f2"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "f7e4fdafc15b570e5ad1bc93db79659d4e109392355b4a3781a14d8039d4975f"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "a7807b0373c8be02bf8fa18b0e20b3a34756e3a290628ee7bcc1e22fb6e738b5",
      "red": {
        "mutation": "M0-08-connections-unchecked: in chatmon/app.py, '            if sys.platform == \"win32\" and not _client_is_me(sock):' became '            if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_on_windows_each_connection_is_checked_to_be_yours",
        "observed_diagnostic": "___________ test_on_windows_each_connection_is_checked_to_be_yours ____________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "51d77c6dd8febb0bb6f4184cf46f9a787111a56e2f024de8d60819a16ee38be2"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M0-10-any-process-forward",
      "acceptance": [
        "AC-M0-10"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_cli.py::test_on_windows_ask_lets_only_chatmon_come_forward_before_sending"
      ],
      "method": "Red drill M0-10-any-process-forward through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "a849300cbe173d5996052e021575090bd77ed05f0b31c4ef0ea4252ec458b8f2"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "f7e4fdafc15b570e5ad1bc93db79659d4e109392355b4a3781a14d8039d4975f"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "a7807b0373c8be02bf8fa18b0e20b3a34756e3a290628ee7bcc1e22fb6e738b5",
      "red": {
        "mutation": "M0-10-any-process-forward: in chatmon/cli.py, '    target = pid if isinstance(pid, int) and not isinstance(pid, bool) and pid > 0 else ASFW_ANY' became '    target = ASFW_ANY'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_on_windows_ask_lets_only_chatmon_come_forward_before_sending",
        "observed_diagnostic": "______ test_on_windows_ask_lets_only_chatmon_come_forward_before_sending ______",
        "before": [
          {
            "path": "chatmon/cli.py",
            "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/cli.py",
            "sha256": "ab6c6f06f3a9e8ebfa3b4f04891447920d0689215445cb162a462787c75773e3"
          }
        ],
        "after": [
          {
            "path": "chatmon/cli.py",
            "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M1B-07-files-brain-sees-all",
      "acceptance": [
        "AC-M1B-7"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_answers.py::test_a_brain_that_reads_files_gets_only_its_own_answers_and_summaries"
      ],
      "method": "Red drill M1B-07-files-brain-sees-all through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "3c036d7ab8cf9483ce526519528ed903dc2d2d44cdf32f4a93ae69c3e8708f0a"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_answers.py",
          "sha256": "324749f6668263eec4508df65370296e91d712da9e8acebc25ac0b5c362da433"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a75812ca8e75ee2390fc2456d64fd4d4d1744a3a56b9c03a8edf5c586dd41b98"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "17abeed3258d72fdc41913b91fd22939dd27f1a12ae09745c31bbd10ea66cde6",
      "red": {
        "mutation": "M1B-07-files-brain-sees-all: in chatmon/app.py, 'pairs = chat.history(brain.label, name=brain.name, own_only=guard, before=q.before)' became 'pairs = chat.history(brain.label, name=brain.name, own_only=False, before=q.before)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_brain_that_reads_files_gets_only_its_own_answers_and_summaries",
        "observed_diagnostic": "____ test_a_brain_that_reads_files_gets_only_its_own_answers_and_summaries ____",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "9788ec757c01e402f5a89e7dfe2a847fb9822df1b9af7688d375976683f58a55"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M1B-09-overrides-unchecked",
      "acceptance": [
        "AC-M1B-9"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_wrong_settings_are_named_one_by_one_and_the_rest_apply"
      ],
      "method": "Red drill M1B-09-overrides-unchecked through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "605ac613971236ed701063a0454a668eeff01688e58967fa82908232449704ab",
      "red": {
        "mutation": "M1B-09-overrides-unchecked: in chatmon/app.py, '            config, more = coerce(merge(config, overrides))' became '            config, more = merge(config, overrides), []'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_wrong_settings_are_named_one_by_one_and_the_rest_apply",
        "observed_diagnostic": "_________ test_wrong_settings_are_named_one_by_one_and_the_rest_apply _________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "cfd3890d65b9bfc1052160b57d769513adc579201f1da077e55dc52d291aef31"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M1B-10-damage-unsaid",
      "acceptance": [
        "AC-M1B-10"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_a_damaged_file_recovered_at_start_is_said"
      ],
      "method": "Red drill M1B-10-damage-unsaid through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "605ac613971236ed701063a0454a668eeff01688e58967fa82908232449704ab",
      "red": {
        "mutation": "M1B-10-damage-unsaid: in chatmon/app.py, '        for problem in (self.state.problem, self.memory.problem):' became '        for problem in ():'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_damaged_file_recovered_at_start_is_said",
        "observed_diagnostic": "_______________ test_a_damaged_file_recovered_at_start_is_said ________________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "14ee37b380ac04cdd50935f53706080fab0daa2ad27c24a709ef5ced9a9321d0"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M2-more-unwired",
      "acceptance": [
        "AC-M2-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_more_opens_the_whole_text_and_the_box_remembers_its_size_and_says_shift_enter"
      ],
      "method": "Red drill M2-more-unwired through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "3c036d7ab8cf9483ce526519528ed903dc2d2d44cdf32f4a93ae69c3e8708f0a"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_answers.py",
          "sha256": "324749f6668263eec4508df65370296e91d712da9e8acebc25ac0b5c362da433"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a75812ca8e75ee2390fc2456d64fd4d4d1744a3a56b9c03a8edf5c586dd41b98"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "68f1743ac49a26862709bb05dd2f3183c5fd849cb79380d9bf4180b374101814",
      "red": {
        "mutation": "M2-more-unwired: in chatmon/app.py, '        self.stage.bubble.on_more = self._show_more' became '        pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_more_opens_the_whole_text_and_the_box_remembers_its_size_and_says_shift_enter",
        "observed_diagnostic": "_ test_more_opens_the_whole_text_and_the_box_remembers_its_size_and_says_shift_enter _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "54c19c2a0b96df7fa24f7d11dc97632cb8b490103e9aa1ff9564bf2c4ff4588d"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M5-chat-times-12h",
      "acceptance": [
        "AC-M5-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_chatswin.py::test_chat_times_follow_the_locale"
      ],
      "method": "Red drill M5-chat-times-12h through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "3c036d7ab8cf9483ce526519528ed903dc2d2d44cdf32f4a93ae69c3e8708f0a"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "291cd461529db851480828ecb52398b5cd9b3d3c02fe874e7a57ffabaf440ab3"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "da3d7845b19bb1888001e93d1f13b5319288d0e36d5e66a2dc277e700a9bc4b9"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_answers.py",
          "sha256": "324749f6668263eec4508df65370296e91d712da9e8acebc25ac0b5c362da433"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_asking.py",
          "sha256": "a75812ca8e75ee2390fc2456d64fd4d4d1744a3a56b9c03a8edf5c586dd41b98"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_chatswin.py",
          "sha256": "8854160e3c08385f0e4bf4d7ca024e50c5822caefdbafa351fd546966d2f0373"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "16614abf8935b828ba3c463a243fe5f36b2e397edf7b420d6611be2e2c1430f7",
      "red": {
        "mutation": "M5-chat-times-12h: in chatmon/chats.py, '        return _(\"today {time}\").format(time=localefmt.time_of_day(d))' became '        return f\"today {(d.hour % 12) or 12}:{d.minute:02d} {\\'AM\\' if d.hour < 12 else \\'PM\\'}\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_chat_times_follow_the_locale",
        "observed_diagnostic": "______________________ test_chat_times_follow_the_locale ______________________",
        "before": [
          {
            "path": "chatmon/chats.py",
            "sha256": "291cd461529db851480828ecb52398b5cd9b3d3c02fe874e7a57ffabaf440ab3"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/chats.py",
            "sha256": "159886b7c605dff9861b178c625dd03e081475c420a251fd0c70964adcc78f27"
          }
        ],
        "after": [
          {
            "path": "chatmon/chats.py",
            "sha256": "291cd461529db851480828ecb52398b5cd9b3d3c02fe874e7a57ffabaf440ab3"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-07-no-stage-badge",
      "acceptance": [
        "AC-07-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_the_tray_and_the_stage_name_what_each_agent_is_doing_with_a_badge_while_one_needs_you"
      ],
      "method": "Red drill M7-07-no-stage-badge through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "a849300cbe173d5996052e021575090bd77ed05f0b31c4ef0ea4252ec458b8f2"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "c9748102e3e1063b9e769e535af9cea8ec905abae66ff988fb109b5f1d496562"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "f7e4fdafc15b570e5ad1bc93db79659d4e109392355b4a3781a14d8039d4975f"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "f6a09bac042388d63b21af89e8d297a6cd2fc57d83356d90a1bd633bd8e178ed",
      "red": {
        "mutation": "M7-07-no-stage-badge: in chatmon/app.py, '        self.stage.set_badge(sum(1 for state, _ in self.agents.values() if state == \"working\"), waiting)\\r\\n' became '\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_tray_and_the_stage_name_what_each_agent_is_doing_with_a_badge_while_one_needs_you",
        "observed_diagnostic": "_ test_the_tray_and_the_stage_name_what_each_agent_is_doing_with_a_badge_while_one_needs_you _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "117c1c76ef436b9a7e440e10a97d2e369185bfa8ca3f88a3b6909885d37681c3"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-11-player-never-quiet",
      "acceptance": [
        "AC-11-3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_the_player_is_told_the_settings_and_asks_whether_its_a_time_for_quiet"
      ],
      "method": "Red drill M7-11-player-never-quiet through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "a849300cbe173d5996052e021575090bd77ed05f0b31c4ef0ea4252ec458b8f2"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "c9748102e3e1063b9e769e535af9cea8ec905abae66ff988fb109b5f1d496562"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "f7e4fdafc15b570e5ad1bc93db79659d4e109392355b4a3781a14d8039d4975f"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "f6a09bac042388d63b21af89e8d297a6cd2fc57d83356d90a1bd633bd8e178ed",
      "red": {
        "mutation": "M7-11-player-never-quiet: in chatmon/app.py, 'quiet=lambda: self._quiet or self.reminders.focus() is not None)' became 'quiet=lambda: False)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_player_is_told_the_settings_and_asks_whether_its_a_time_for_quiet",
        "observed_diagnostic": "_ test_the_player_is_told_the_settings_and_asks_whether_its_a_time_for_quiet __",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "a2c81e89efa9bc189407e77a89297dca23743b87b1c489e065593517135d8b86"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-11-hotkey-unregistered",
      "acceptance": [
        "AC-11-4"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_the_hotkey_is_registered_from_settings_toggles_the_box_and_a_problem_is_said_once"
      ],
      "method": "Red drill M7-11-hotkey-unregistered through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "a849300cbe173d5996052e021575090bd77ed05f0b31c4ef0ea4252ec458b8f2"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "c9748102e3e1063b9e769e535af9cea8ec905abae66ff988fb109b5f1d496562"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "f7e4fdafc15b570e5ad1bc93db79659d4e109392355b4a3781a14d8039d4975f"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "f6a09bac042388d63b21af89e8d297a6cd2fc57d83356d90a1bd633bd8e178ed",
      "red": {
        "mutation": "M7-11-hotkey-unregistered: in chatmon/app.py, '        error = hotkey.register(sequence, self._hotkey_pressed, failed=self._hotkey_failed)' became '        error = None'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_hotkey_is_registered_from_settings_toggles_the_box_and_a_problem_is_said_once",
        "observed_diagnostic": "_ test_the_hotkey_is_registered_from_settings_toggles_the_box_and_a_problem_is_said_once _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "48c43d73516c121c2264012281c0d3acb190abedd9eb67a499006e8e43da75aa"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-11-balloon-not-toast",
      "acceptance": [
        "AC-11-4"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_on_windows_an_alert_under_a_full_screen_app_is_a_toast_with_the_reminders_buttons"
      ],
      "method": "Red drill M7-11-balloon-not-toast through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "a849300cbe173d5996052e021575090bd77ed05f0b31c4ef0ea4252ec458b8f2"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "c9748102e3e1063b9e769e535af9cea8ec905abae66ff988fb109b5f1d496562"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "f7e4fdafc15b570e5ad1bc93db79659d4e109392355b4a3781a14d8039d4975f"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "f6a09bac042388d63b21af89e8d297a6cd2fc57d83356d90a1bd633bd8e178ed",
      "red": {
        "mutation": "M7-11-balloon-not-toast: in chatmon/app.py, '            if tag is None:  # no toast here' became '            if True:  # no toast here'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_on_windows_an_alert_under_a_full_screen_app_is_a_toast_with_the_reminders_buttons",
        "observed_diagnostic": "_ test_on_windows_an_alert_under_a_full_screen_app_is_a_toast_with_the_reminders_buttons _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "ee60aebe017787e90c504d6c732efc535699d29543e0106cc52ef50710db93ff"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-11-refused-toast-unsaid",
      "acceptance": [
        "AC-11-4"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_on_windows_an_alert_under_a_full_screen_app_is_a_toast_with_the_reminders_buttons"
      ],
      "method": "Red drill M7-11-refused-toast-unsaid through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "a849300cbe173d5996052e021575090bd77ed05f0b31c4ef0ea4252ec458b8f2"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "c9748102e3e1063b9e769e535af9cea8ec905abae66ff988fb109b5f1d496562"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "f7e4fdafc15b570e5ad1bc93db79659d4e109392355b4a3781a14d8039d4975f"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "f6a09bac042388d63b21af89e8d297a6cd2fc57d83356d90a1bd633bd8e178ed",
      "red": {
        "mutation": "M7-11-refused-toast-unsaid: in chatmon/app.py, '            self._balloon(*notice)\\r\\n' became '            pass\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_on_windows_an_alert_under_a_full_screen_app_is_a_toast_with_the_reminders_buttons",
        "observed_diagnostic": "_ test_on_windows_an_alert_under_a_full_screen_app_is_a_toast_with_the_reminders_buttons _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "a60fdd4f9e335c17216f3b3c813f115e4e6a4e7405a8191cedf6fe00a16a42e1"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-11-box-always-hosted",
      "acceptance": [
        "AC-11-5"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_the_ask_box_is_a_window_with_a_screen_reader_where_the_overlay_draws_it"
      ],
      "method": "Red drill M7-11-box-always-hosted through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "a849300cbe173d5996052e021575090bd77ed05f0b31c4ef0ea4252ec458b8f2"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "c9748102e3e1063b9e769e535af9cea8ec905abae66ff988fb109b5f1d496562"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "f7e4fdafc15b570e5ad1bc93db79659d4e109392355b4a3781a14d8039d4975f"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "f6a09bac042388d63b21af89e8d297a6cd2fc57d83356d90a1bd633bd8e178ed",
      "red": {
        "mutation": "M7-11-box-always-hosted: in chatmon/app.py, '            self.stage.set_hosting(not self._ask_box_as_window())' became '            pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_ask_box_is_a_window_with_a_screen_reader_where_the_overlay_draws_it",
        "observed_diagnostic": "_ test_the_ask_box_is_a_window_with_a_screen_reader_where_the_overlay_draws_it _",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "67f8cc0bfda6ae83e972673590698fb47d3822c783245becf4b16b03d50539ab"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-11-follow-ignored",
      "acceptance": [
        "AC-11-5"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_follow_me_across_monitors_is_a_setting"
      ],
      "method": "Red drill M7-11-follow-ignored through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "a849300cbe173d5996052e021575090bd77ed05f0b31c4ef0ea4252ec458b8f2"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "c9748102e3e1063b9e769e535af9cea8ec905abae66ff988fb109b5f1d496562"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "f7e4fdafc15b570e5ad1bc93db79659d4e109392355b4a3781a14d8039d4975f"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "f6a09bac042388d63b21af89e8d297a6cd2fc57d83356d90a1bd633bd8e178ed",
      "red": {
        "mutation": "M7-11-follow-ignored: in chatmon/app.py, '        self.stage.follow_pointer_screen(bool(self.config[\"follow_screen\"]))' became '        self.stage.follow_pointer_screen(False)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_follow_me_across_monitors_is_a_setting",
        "observed_diagnostic": "_________________ test_follow_me_across_monitors_is_a_setting _________________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "0307e34f91a4f6ed5592fd29b46dd8302ba98528b16e8cd9e1bd7346da03fa03"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M4A-desk-changes-unheard",
      "acceptance": [
        "AC-11-7"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_reduced_motion_contrast_and_screen_readers_are_heard_as_they_change"
      ],
      "method": "Red drill M4A-desk-changes-unheard through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "a849300cbe173d5996052e021575090bd77ed05f0b31c4ef0ea4252ec458b8f2"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "c9748102e3e1063b9e769e535af9cea8ec905abae66ff988fb109b5f1d496562"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "f7e4fdafc15b570e5ad1bc93db79659d4e109392355b4a3781a14d8039d4975f"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "93bfcd2364148f956db06931d38244d62a8b79e69e618c6241dff0a1e8d85e6f",
      "red": {
        "mutation": "M4A-desk-changes-unheard: in chatmon/app.py, '        desk.settings_changed.connect(self._check_accessibility)\\r\\n' became '\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_reduced_motion_contrast_and_screen_readers_are_heard_as_they_change",
        "observed_diagnostic": "__ test_reduced_motion_contrast_and_screen_readers_are_heard_as_they_change ___",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "fdca77b85ea327ba9ef5ee0bcabec08c5ad6edac21821c07a44a483395d913df"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M4A-reader-not-looked-again",
      "acceptance": [
        "AC-11-7"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_reduced_motion_contrast_and_screen_readers_are_heard_as_they_change"
      ],
      "method": "Red drill M4A-reader-not-looked-again through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "a849300cbe173d5996052e021575090bd77ed05f0b31c4ef0ea4252ec458b8f2"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "c9748102e3e1063b9e769e535af9cea8ec905abae66ff988fb109b5f1d496562"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "f7e4fdafc15b570e5ad1bc93db79659d4e109392355b4a3781a14d8039d4975f"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "93bfcd2364148f956db06931d38244d62a8b79e69e618c6241dff0a1e8d85e6f",
      "red": {
        "mutation": "M4A-reader-not-looked-again: in chatmon/app.py, '        self._reader_seen = float(\"-inf\")\\r\\n        self._check_hosting()' became '        self._check_hosting()'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_reduced_motion_contrast_and_screen_readers_are_heard_as_they_change",
        "observed_diagnostic": "__ test_reduced_motion_contrast_and_screen_readers_are_heard_as_they_change ___",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "0fdf9600e749c4ffba927bfcad46ae3d8ed41b69f9345f5ee18599b6fdd08e45"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M4A-mac-sleep-unheard",
      "acceptance": [
        "AC-11-7"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_on_macos_sleep_sleeping_displays_and_low_power_mode_are_heard"
      ],
      "method": "Red drill M4A-mac-sleep-unheard through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "a849300cbe173d5996052e021575090bd77ed05f0b31c4ef0ea4252ec458b8f2"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "c9748102e3e1063b9e769e535af9cea8ec905abae66ff988fb109b5f1d496562"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "f7e4fdafc15b570e5ad1bc93db79659d4e109392355b4a3781a14d8039d4975f"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "93bfcd2364148f956db06931d38244d62a8b79e69e618c6241dff0a1e8d85e6f",
      "red": {
        "mutation": "M4A-mac-sleep-unheard: in chatmon/app.py, '            watcher.slept.connect(self._sleeping)\\r\\n' became '\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_on_macos_sleep_sleeping_displays_and_low_power_mode_are_heard",
        "observed_diagnostic": "_____ test_on_macos_sleep_sleeping_displays_and_low_power_mode_are_heard ______",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "7e43f6ef20f1a739e17694259ed965a0909be6b997cc8f49bac95aac4e6da417"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M4A-low-power-not-read",
      "acceptance": [
        "AC-11-7"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_on_macos_sleep_sleeping_displays_and_low_power_mode_are_heard"
      ],
      "method": "Red drill M4A-low-power-not-read through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "a849300cbe173d5996052e021575090bd77ed05f0b31c4ef0ea4252ec458b8f2"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "c9748102e3e1063b9e769e535af9cea8ec905abae66ff988fb109b5f1d496562"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "f7e4fdafc15b570e5ad1bc93db79659d4e109392355b4a3781a14d8039d4975f"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "93bfcd2364148f956db06931d38244d62a8b79e69e618c6241dff0a1e8d85e6f",
      "red": {
        "mutation": "M4A-low-power-not-read: in chatmon/app.py, '            self._power_saving(bool(macnative.low_power_mode()))\\r\\n' became '\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_on_macos_sleep_sleeping_displays_and_low_power_mode_are_heard",
        "observed_diagnostic": "_____ test_on_macos_sleep_sleeping_displays_and_low_power_mode_are_heard ______",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "726b83136c08361644d5ebc16a87395d572a41a34a5881a032391ed4139a6817"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M4A-urgent-through-dnd",
      "acceptance": [
        "AC-11-7"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_on_linux_a_held_alert_is_urgent_unless_do_not_disturb_is_why_it_waits"
      ],
      "method": "Red drill M4A-urgent-through-dnd through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "a849300cbe173d5996052e021575090bd77ed05f0b31c4ef0ea4252ec458b8f2"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "c9748102e3e1063b9e769e535af9cea8ec905abae66ff988fb109b5f1d496562"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "f7e4fdafc15b570e5ad1bc93db79659d4e109392355b4a3781a14d8039d4975f"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "93bfcd2364148f956db06931d38244d62a8b79e69e618c6241dff0a1e8d85e6f",
      "red": {
        "mutation": "M4A-urgent-through-dnd: in chatmon/app.py, 'urgency = sysnotify.URGENCY_NORMAL if self._quiet == \"Do Not Disturb\" else sysnotify.URGENCY_CRITICAL' became 'urgency = sysnotify.URGENCY_CRITICAL'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_on_linux_a_held_alert_is_urgent_unless_do_not_disturb_is_why_it_waits",
        "observed_diagnostic": "_ test_on_linux_a_held_alert_is_urgent_unless_do_not_disturb_is_why_it_waits __",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "7eec721f64c3ef6528a13e89261ecb402007f4d2c74b7cfdd3c2e8204ca4ed83"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M8-app-language-ignored",
      "acceptance": [
        "AC-M8-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_chatmon_starts_in_the_language_set_before_any_window"
      ],
      "method": "Red drill M8-app-language-ignored through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "7371614c5f0315d19f805df16694d5ca4f8b599cc6127b891c4a3f836d50b149"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "7d5fd3ca98ea9dec977f7dc5c353522500406a8bbd61e5c272518c9f21fb39df",
      "red": {
        "mutation": "M8-app-language-ignored: in chatmon/app.py, '        i18n.setup(self.config.get(i18n.SETTING) or None)' became '        i18n.setup(None)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_chatmon_starts_in_the_language_set_before_any_window",
        "observed_diagnostic": "__________ test_chatmon_starts_in_the_language_set_before_any_window __________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "f06aef6a45bf1b61f051d38ac5afadada73b0bdeec5a1512f26cb81dd2ac181b"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M8-cli-language-ignored",
      "acceptance": [
        "AC-M8-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_cli.py::test_the_command_line_speaks_the_language_chosen_without_writing_anything"
      ],
      "method": "Red drill M8-cli-language-ignored through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "7371614c5f0315d19f805df16694d5ca4f8b599cc6127b891c4a3f836d50b149"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "7d5fd3ca98ea9dec977f7dc5c353522500406a8bbd61e5c272518c9f21fb39df",
      "red": {
        "mutation": "M8-cli-language-ignored: in chatmon/cli.py, '    i18n.setup(_language_setting())' became '    i18n.setup(None)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_command_line_speaks_the_language_chosen_without_writing_anything",
        "observed_diagnostic": "__ test_the_command_line_speaks_the_language_chosen_without_writing_anything __",
        "before": [
          {
            "path": "chatmon/cli.py",
            "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/cli.py",
            "sha256": "ce0396752396b8b2ccc1e2d66cd31fae29c90cdc66cccde6c6c4489fca75c0f0"
          }
        ],
        "after": [
          {
            "path": "chatmon/cli.py",
            "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M8-window-language-dropped",
      "acceptance": [
        "AC-M8-1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_settingswin.py::test_the_language_is_the_systems_or_one_chatmon_has_and_applies_at_the_next_start"
      ],
      "method": "Red drill M8-window-language-dropped through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "7371614c5f0315d19f805df16694d5ca4f8b599cc6127b891c4a3f836d50b149"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "7d5fd3ca98ea9dec977f7dc5c353522500406a8bbd61e5c272518c9f21fb39df",
      "red": {
        "mutation": "M8-window-language-dropped: in chatmon/settingswin.py, '            \"language\": self.language.currentData(),\\r\\n' became ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_language_is_the_systems_or_one_chatmon_has_and_applies_at_the_next_start",
        "observed_diagnostic": "_ test_the_language_is_the_systems_or_one_chatmon_has_and_applies_at_the_next_start _",
        "before": [
          {
            "path": "chatmon/settingswin.py",
            "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/settingswin.py",
            "sha256": "d1cb999d37045e5ce5af3f3154fd4254675631e1ea6f34b1fea105f2e3eb7cf9"
          }
        ],
        "after": [
          {
            "path": "chatmon/settingswin.py",
            "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "RED-M7-11-magnifier-not-placed",
      "acceptance": [
        "AC-11-6"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_on_windows_magnifier_goes_to_each_bubble_and_lets_go_when_it_closes"
      ],
      "method": "Red drill M7-11-magnifier-not-placed through tests/drills/run.py in a temporary copy: green, the defect put in, the named tests failing for that reason, the file's bytes put back and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m7/drills.log",
        "sha256": "a8961d72a440adab5b5e4922edb05c928ac545ceaca5d46f0820c925b5acb7a6"
      },
      "inputs": [
        {
          "path": "chatmon/app.py",
          "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "a849300cbe173d5996052e021575090bd77ed05f0b31c4ef0ea4252ec458b8f2"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "c9748102e3e1063b9e769e535af9cea8ec905abae66ff988fb109b5f1d496562"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "f7e4fdafc15b570e5ad1bc93db79659d4e109392355b4a3781a14d8039d4975f"
        },
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
          "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
        },
        {
          "path": "tests/test_commands.py",
          "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
        },
        {
          "path": "tests/test_messages.py",
          "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
        },
        {
          "path": "tests/test_settingswin.py",
          "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
        },
        {
          "path": "tests/test_wintoast.py",
          "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
        }
      ],
      "scope_sha256": "f6a09bac042388d63b21af89e8d297a6cd2fc57d83356d90a1bd633bd8e178ed",
      "red": {
        "mutation": "M7-11-magnifier-not-placed: in chatmon/app.py, '        wincaret.place(self.stage.native_window(),' became '        (lambda *a: None)(self.stage.native_window(),'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_on_windows_magnifier_goes_to_each_bubble_and_lets_go_when_it_closes",
        "observed_diagnostic": "__ test_on_windows_magnifier_goes_to_each_bubble_and_lets_go_when_it_closes ___",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "ea588eec6e42bcad3369c3492dbe9449ec21672970d6e7931a2297ed4ae2faed"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
          }
        ]
      },
      "reason": null
    }
  ],
  "checkpoint": {
    "scope_sha256": "e0bed30be8b7760b1f38fc3d3659feb5e96f882502608e71901632acb6c06022",
    "inputs": [
      {
        "path": "chatmon/app.py",
        "sha256": "7919c507bb867b8a7e8665166d0287d8a0017914447055d57c20b2332af1c532"
      },
      {
        "path": "chatmon/asking.py",
        "sha256": "3c036d7ab8cf9483ce526519528ed903dc2d2d44cdf32f4a93ae69c3e8708f0a"
      },
      {
        "path": "chatmon/bubble.py",
        "sha256": "66eac8bcda569245877da20212cbc834a0aa79b444a19ad9e88b5f867443c0af"
      },
      {
        "path": "chatmon/chats.py",
        "sha256": "291cd461529db851480828ecb52398b5cd9b3d3c02fe874e7a57ffabaf440ab3"
      },
      {
        "path": "chatmon/chatswin.py",
        "sha256": "da3d7845b19bb1888001e93d1f13b5319288d0e36d5e66a2dc277e700a9bc4b9"
      },
      {
        "path": "chatmon/cli.py",
        "sha256": "744861f8602695e86cf80752a3ba28736dc989b252a492579936693ffe270815"
      },
      {
        "path": "chatmon/commands.py",
        "sha256": "f214e1ecc38b856a5aeb37ff519769b3770f1018ce954715ebb4fa5b0a9e8d90"
      },
      {
        "path": "chatmon/events.py",
        "sha256": "a849300cbe173d5996052e021575090bd77ed05f0b31c4ef0ea4252ec458b8f2"
      },
      {
        "path": "chatmon/locale/chatmon.pot",
        "sha256": "7371614c5f0315d19f805df16694d5ca4f8b599cc6127b891c4a3f836d50b149"
      },
      {
        "path": "chatmon/menus.py",
        "sha256": "306f037e46cd090cf587b626e71626a9fe0ef200069086b5313ccd5984eb9e51"
      },
      {
        "path": "chatmon/messages.py",
        "sha256": "1ae28121c8d19526f62a66e36dfaccaa84ae653ae94af5aca32082d33e97287d"
      },
      {
        "path": "chatmon/penguin.py",
        "sha256": "c9748102e3e1063b9e769e535af9cea8ec905abae66ff988fb109b5f1d496562"
      },
      {
        "path": "chatmon/phrases/en.json",
        "sha256": "0ad5d23950aa11252a58caf94e713d198fb4deb500aa67fb60f7f191085a1da8"
      },
      {
        "path": "chatmon/reminders.py",
        "sha256": "a4c6d141f6f6b4ec78449cc5adbaafbf99418c6a421ba9341722aa81b4079a50"
      },
      {
        "path": "chatmon/settings.py",
        "sha256": "9d7b99d1f7c725b799b6a690de4303c2abe745a2e8c8f8e72f6d53e4c8c3f65f"
      },
      {
        "path": "chatmon/settingswin.py",
        "sha256": "1f120463c15a359663f923a5500bc05642da3b86f49cf404b1605b692314575c"
      },
      {
        "path": "chatmon/winpipe.py",
        "sha256": "f7e4fdafc15b570e5ad1bc93db79659d4e109392355b4a3781a14d8039d4975f"
      },
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
        "sha256": "0ab2f7fe3fdeb1864856d09bda90df0de23cb5a87877ea427560f358ca9bac4b"
      },
      {
        "path": "tests/app_harness.py",
        "sha256": "2548c17bc5391f3485f07735bf49a8c6b9eb01ab99099fff81813fe1a8fa78bd"
      },
      {
        "path": "tests/conftest.py",
        "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
      },
      {
        "path": "tests/drills/run.py",
        "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
      },
      {
        "path": "tests/test_app_answers.py",
        "sha256": "324749f6668263eec4508df65370296e91d712da9e8acebc25ac0b5c362da433"
      },
      {
        "path": "tests/test_app_m7.py",
        "sha256": "9e337c0cc0d40f03051445accc98805b77d45154b6104c1099449cd40f9cfb20"
      },
      {
        "path": "tests/test_app_reminders.py",
        "sha256": "025c386f89a3ee0d9fcd403ffcf000e644e238338c98ae6fde08693256e0890d"
      },
      {
        "path": "tests/test_app_smoke.py",
        "sha256": "06d7b95c1f4389b3561b5386b9c1c46f710fbe679455ce0796ff558a04c8cc25"
      },
      {
        "path": "tests/test_asking.py",
        "sha256": "a75812ca8e75ee2390fc2456d64fd4d4d1744a3a56b9c03a8edf5c586dd41b98"
      },
      {
        "path": "tests/test_bubble_styles.py",
        "sha256": "cf518260b3712784afcc637eab674e4d399e0411ced3a5af38e1d5cf2e4cf8ab"
      },
      {
        "path": "tests/test_chatswin.py",
        "sha256": "8854160e3c08385f0e4bf4d7ca024e50c5822caefdbafa351fd546966d2f0373"
      },
      {
        "path": "tests/test_cli.py",
        "sha256": "5feb6584bfffd558430543c3364c37a6cc6957e9ff061cfe2e0b559a59f58756"
      },
      {
        "path": "tests/test_commands.py",
        "sha256": "26ef2c7258c42a71deb3857b12b1254a9f1f4389f2a46d524dc11b54386b5123"
      },
      {
        "path": "tests/test_messages.py",
        "sha256": "bcab5a8a3aad45a68e577e13ce4e08dd434e4c71ddfb42a3932b25a54c5ecbad"
      },
      {
        "path": "tests/test_reminders.py",
        "sha256": "e4527c1b87ccc4b30b1dfda7913927b99e2e29df0484ce0497419932e46df1d5"
      },
      {
        "path": "tests/test_settings.py",
        "sha256": "6e216304e491a8967266b248e4acf41cef7e124906d52d0bf71afc2d82c2df60"
      },
      {
        "path": "tests/test_settingswin.py",
        "sha256": "066f1d944ad08853a53eddcf019aaee790126b32348474784684db75b14a0819"
      },
      {
        "path": "tests/test_wintoast.py",
        "sha256": "7f5706e98b335c2536d5c7266486576b59698d2ac8070daec32540ea5209765f"
      }
    ],
    "environment": {
      "platform": "windows",
      "tools": {
        "PyQt6": "6.11.0",
        "pytest": "9.2.0",
        "python": "3.14.10",
        "ruff": "0.17.4"
      }
    },
    "verified_tasks": [
      "TASK-AGENTS",
      "TASK-ANSWERS",
      "TASK-CHATS",
      "TASK-CI",
      "TASK-COMMANDS",
      "TASK-CONTEXT",
      "TASK-FAILURES",
      "TASK-FOCUS",
      "TASK-HARNESS",
      "TASK-HELLO",
      "TASK-I18N",
      "TASK-IPC",
      "TASK-KEYS",
      "TASK-M2NOTES",
      "TASK-M4A",
      "TASK-MISSED",
      "TASK-NEWCHAT",
      "TASK-PLATFORM",
      "TASK-QUICK",
      "TASK-REMINDERS",
      "TASK-SETTINGS",
      "TASK-STAGE-M4B",
      "TASK-STARTUP"
    ],
    "pending_operations": [
      {
        "id": "CI-ALL-PLATFORMS",
        "description": "The coordinator's CI run of the feature branch with wave2/m7 merged: Windows (the smoke and ask-box fixes), Linux and macOS (POSIX events.request, the windows' tests with other fonts)",
        "next_action": "Observe the outcome (the coordinator's CI run or merge), then re-run the affected checks."
      },
      {
        "id": "WAYLAND-HOSTING",
        "description": "set_hosting(False) with a screen reader on a real Wayland compositor (Hyprland or KDE): the ask box as a window, the penguin's menu kept on the stage",
        "next_action": "Observe the outcome (the coordinator's CI run or merge), then re-run the affected checks."
      }
    ],
    "next_action": "Wire M4A's sleep and live accessibility events once it is merged into improve/assessment-fixes; read the Linux and macOS CI results.",
    "source_revision": "41cd4fd0a7301c8dd764d02ed7250fefde300b99"
  }
}
```
