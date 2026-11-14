# M5: Reminders, offline answers and locale

Milestone M5 of the [improvement roadmap](ROADMAP.md), items M5-01 to M5-08 of the [assessment](ASSESSMENT.md).
Branch `wave1/m5`, from `improve/assessment-fixes` at `5346385`. The ledger at the end owns every requirement,
task, state and receipt. Reports, logs and the drill spec are in [reports/m5/](reports/m5/).

## Rationale

### Scope

The work is reminders that wait to be seen and repeat, parsing that reads days and dates honestly, locale-aware
times and dates, offline phrases as per-language data, property tests for the two parsers, and a formatter for
the agents command.

M5 owns these files:

- `chatmon/reminders.py`
- `chatmon/offline.py`
- `chatmon/context.py`
- the new `chatmon/localefmt.py`
- the new `chatmon/phrases/`

`context.py` has no M5 finding and is unchanged. Every change needed in a file M5 doesn't own is under
[Integration notes](#integration-notes).

Every finding was re-checked against `5346385` before it was changed, and all of them are real. The evidence is in
[reports/m5/findings-recheck.log](reports/m5/findings-recheck.log), and the decisions on the requirements' gaps
are in [reports/m5/readiness.md](reports/m5/readiness.md).

### Design

**The reminder book (M5-01, M5-03, M5-04).** It keeps the roadmap's contract:

| Call | What it does |
|---|---|
| `due(now)` | Lists fired, unacknowledged reminders without removing them. |
| `acknowledge(id)` | Done: a one-off reminder goes; a repeating one moves on to its next time. |
| `snooze(id, until)` | Puts it off to a given moment. |
| `update(id, text=None, when=None)` | Changes its words or its time. |

Additions to the contract:

- `fire(now)` lists only what came due since the last look, so the app alerts once. `due(now)` is what the app shows
  again at start.
- `Reminder.fired` and `Reminder.repeat` are saved only when set, so a book saved by an earlier version reads back
  and saves byte-for-byte the same.
- `update` also takes `repeat`.
- `pop_due` stays, because today's `app.py` calls it. It now moves a repeating reminder on instead of losing it.

**Reading when (M5-02, M5-03).** `parse_when` takes the time words out of a phrase one kind at a time, each with
its own small reader. The kinds, in order:

1. a repeat ("every monday");
2. "in …";
3. a day: today, tonight, tomorrow, an ISO date, "dec 3" or "3rd of december", or a weekday with "next" or "this";
4. a part of the day;
5. a clock time.

Time words still left after that, or words that conflict, give an ambiguous result instead of a guess. "in …" is
real seconds from the epoch. Everything else is wall-clock time in the zone of `now`:

- A naive `now` (what the app passes) is in the computer's zone.
- A zoneinfo `now` (the tests) is in that zone.
- A time a spring-forward change skips becomes the moment it would have been.

The rules for "next mon", a bare hour on a day still to come, and what counts as ambiguous are in
[readiness.md](reports/m5/readiness.md).

**Locale (M5-05).** `localefmt.py` writes times and dates:

- through Qt's default `QLocale` when Qt is already loaded;
- in plain English when it isn't, or in Qt's "C" locale.

It reuses no `strftime` names, because Qt sets the C library's locale from the system as it starts.

**Phrases (M5-06).** `chatmon/phrases/en.json` holds:

- the fixed phrases of every offline command: `offline.py`'s, and the ones in `app.py`'s `_local`, which M0 is
  moving to a command table;
- the templates with a number or text;
- the question words;
- the help, as sections.

`load_phrases` merges a language's own file with English. English is always understood and wins on a conflict, and
its help fills in what a translation leaves out. A missing or broken translation counts as not there. `parse_kept`,
`when`, `chance` and `reminder_or_question` read the data, and give the same answers as before. `help_text()` is
`app.py`'s `HELP_ALL` with two more reminder examples and an "AI agents" line.

**Agents (M5-08).** `agents_report` turns the app's own `{source: (state, since)}` into lines: needs-you first,
longest waiting first, then the agents still working, each with how long. It has a Markdown form for the *agents*
command and a plain form for `chatmon status`.

**Property tests (M5-07).** `tests/test_parser_properties.py` uses a named, derandomized Hypothesis profile with no
example database, 150 examples, a 1 s deadline, and only `too_slow` suppressed. It covers two properties:

- **The calculator** raises only `ValueError` or `OverflowError`, takes under 0.5 s, gives a whole-number result of
  at most `_MAX_DIGITS` digits, and `answer()` never raises.
- **`parse_when`** gives `now < due ≤ now + LONGEST` in five zones. "in N" is exactly N seconds. A 24-hour time
  stays on the wall clock unless that day skips it.

They run in about 2 s. A one-off randomized run of 3,000 examples each, not committed, found nothing more.

### Defects found on the way, and fixed

- `10**400` was answered with 401 digits. The old check, `bit_length() > 400 * 3.33`, let through numbers up to
  about 10^401. The bound is now exact: `abs(value) >= 10**400`.
- "1e308 % of 1e308" was answered with infinity: the "% of" path skipped the result checks. It now goes through
  them too.
- Python's own `SyntaxWarning` ("invalid decimal literal" for "1or 2") was printed while reading a sum. That's noise
  for the person, and an error under the `filterwarnings = error` setting M6A plans. The calculator now reads
  without it.
- A red drill found a test gap: the restart test called `due()`, which marks a reminder fired, before checking
  that the saved `fired` flag was read. The test now checks `fire()` first.

### Reuse

These were extended in place:

- The book, the parser, `seconds_in`, `LONGEST` and the regex style in `reminders.py`.
- The calculator, the `_parse_date` holidays and `Asked` in `offline.py`.
- The month and weekday names now come from `localefmt.MONTHS` and `localefmt.WEEKDAYS`, one list for parsing and
  for plain English.

New code has a responsibility of its own. `localefmt` has formatting and no parsing. The phrase loader is in
`offline.py`, beside the commands it serves. It isn't in a new module, because a `phrases.py` would share its name
with the data folder.

### Non-goals

- Translating the grammars: reminders' time words, units, sums, dice and "days until" stay English. Only English
  ships, and the owner chose plumbing plus locale formats.
- Wiring anything into `app.py`, `cli.py`, `settings.py`, `settingswin.py` or `chats.py`. Those belong to M0, M1B
  and M7, and are listed in the integration notes.
- Intervals such as "every 2 hours", and "every weekend". These are answered as ambiguous, and the person is told
  which repeats work.

## Verification

Run on Windows 11 with Python 3.14.10, PyQt6 6.11.0, pytest 9.2.0, Hypothesis 6.170.15, tzdata 2026.6 and ruff
0.17.4. The observation is in [reports/m5/context.log](reports/m5/context.log).

| Check | Command | Result |
|---|---|---|
| M5 tests | `python -m pytest -q -p no:cacheprovider tests/test_reminders.py tests/test_offline.py tests/test_localefmt.py tests/test_parser_properties.py` | 209 passed, 1 skipped ([behavior.log](reports/m5/behavior.log)) |
| Whole suite | `python -m pytest -q -p no:cacheprovider` | 623 passed, 60 skipped ([suite.log](reports/m5/suite.log)). The baseline was 514 passed, 59 skipped. |
| Lint | `ruff check .` | Clean ([ruff.log](reports/m5/ruff.log)) |
| Red drills | `python tests/drills/run.py docs/delivery/reports/m5/drill-spec.json --log docs/delivery/reports/m5/drills.log` | 28 of 28 went green, then red (exit 1, failing in the named test), then green again ([drills.log](reports/m5/drills.log), [drills.json](reports/m5/drills.json)) |

The skipped M5 test is the Unix-only check of the app's own naive local time, which needs `time.tzset`. It runs on
the Linux and macOS CI legs. The zone tests skip only where there's no time-zone database.

## Integration notes

### reminders.py: the API delivered

**The book.** `ReminderBook(items=None, tz=None)` and `ReminderBook.from_list(data, tz=None)` load a book; `tz` is
the wall clock repeats follow, and None means the computer's own zone. `to_list()` saves it.

| Call | Returns | Notes |
|---|---|---|
| `add(due, text, kind="reminder", repeat=None)` | `Reminder` | |
| `due(now)` | `list[Reminder]` | Fired and unacknowledged, oldest first. Marks them fired and keeps them. |
| `fire(now)` | `list[Reminder]` | Just the ones newly due: what to alert about. |
| `acknowledge(id, now=None)` | `bool` | |
| `snooze(id, until)` | `bool` | `ValueError` if `until` isn't finite. |
| `update(id, text=None, when=None, repeat=<keep>)` | `bool` | `ValueError` for blank words, a non-finite time or a bad rule. A refused edit changes nothing. |
| `get(id)` | `Reminder` or None | |

`cancel`, `upcoming`, `focus` and `pop_due` are as before, except that `pop_due` moves a repeating reminder on.

`Reminder` has two new fields: `repeat`, a rule such as `daily@09:00`, `weekdays@09:00` or `mon@09:00`, or None;
and `fired`, a bool.

**Parsing.**

- `parse_command(text, now)` returns `Command` with new fields `repeat` and `ambiguous`. A reminder whose time
  can't be told is kind `"unclear"` with `ambiguous` naming its time words, so today's `app.py` asks "When should I
  remind you?" and doesn't fail.
- `explain(command, markdown=True)` is the message for an unclear reminder. It is specific when `ambiguous` is set.
  `markdown=False` gives plain text for a terminal.
- `parse_when(text, now)` returns `When(due, rest, repeat, ambiguous)` or None. It was a tuple, and nothing outside
  `reminders.py` called it.

**Times.**

- `next_time(rule, after, tz=None)` is the next time a repeat falls, strictly after `after`.
- `describe_repeat(rule)` gives "every Monday at 9:00 AM".
- `describe(due, now, tz=None)` now says "was due at …" for a fired reminder.
- `clock(when)` follows the locale.
- `snooze_choices(now, minutes=DEFAULT_SNOOZE_MINUTES, tz=None)` gives a list of `(label, until)`: the person's own
  snooze first, then 5 min, 15 min, 1 hour and "Tomorrow at 9:00 AM" on the wall clock. `DEFAULT_SNOOZE_MINUTES` is
  10.

### What M7 (and M0) must wire

**The reminder contract (M0 queue, M7-04).**

1. Alerts: in `_check_reminders`, replace `pop_due(now)` with `fire(now)`.
2. The start: right after the book is loaded, call `due(time.time())` and post each reminder as priority
   "reminder", keyed `reminder:<id>`. The M0 queue never drops these. This restores unacknowledged reminders.
3. Save the state after `fire`, `acknowledge`, `snooze` and `update`.
4. A reminder bubble's buttons:
   - **Done** calls `acknowledge(id)`.
   - **Snooze** offers `snooze_choices(time.time(), config["reminders"]["snooze_minutes"])`, then calls
     `snooze(id, until)`.
5. The bubble's menu:
   - **Edit** opens the ask box prefilled. Read what's typed with `parse_when(text, datetime.now())`, then call
     `update(id, text=..., when=when.due.timestamp(), repeat=when.repeat)`.
   - **Repeat** offers rules labelled with `describe_repeat`, or "Never", and calls `update(id, repeat=...)`.
6. Then delete `pop_due` and its test, `test_the_old_pop_due_moves_a_repeating_reminder_on_and_takes_a_one_off_out`.

**Adding reminders.** In `_local`, or M0's command table:

- When adding, pass the repeat: `self.reminders.add(command.due.timestamp(), command.text, command.kind,
  repeat=command.repeat)`. The confirmation can add `describe_repeat(command.repeat)`.
- For `kind == "unclear"`, show `reminders.explain(command)`, after the existing `reminder_or_question` check.
- The `remind` IPC message in `handle()` should pass `repeat=command.repeat` too.

**M0-11, `chatmon remind`.** Parse with `reminders.parse_command("remind me " + text, datetime.now())`. If the kind
isn't `"reminder"`, print `reminders.explain(command, markdown=False)` to stderr and exit 2.

**Settings (M1B owns `settings.py`, M7 the settings window, M7-03).** Add `"reminders": {"snooze_minutes": 10}` to
`DEFAULTS` and to the config template. Reminders use it; breaks keep `[breaks] snooze_minutes`.

**Listing reminders.** Fired ones read "was due at …" through `describe`. Add `describe_repeat(r.repeat)` for a
repeating one.

### localefmt.py: the API delivered

| Function | Gives |
|---|---|
| `time_of_day(dt or time)` | "3:04 PM", "15:04" |
| `long_date(date)` | "Friday, December 25, 2026" |
| `short_day(date)` | "Fri Dec 25" in plain English, "Fri, 25 Dec" in a locale |
| `date_and_time(dt)` | the long date and the time |
| `language()` | "en", "de_DE"… |

`set_locale(locale)` takes a `QLocale`, None for plain English, or no argument to follow Qt's default again. Tests
pin one. `WEEKDAYS` and `MONTHS` are the English names.

- **`chats.py` (M1B or M7):**
  - line 62: `localefmt.date_and_time(datetime.fromtimestamp(self.created))`;
  - line 239: `f"today {localefmt.time_of_day(d)}"`;
  - line 242: `localefmt.short_day(d.date())`.
- **M8:** to pick a UI language, call `QLocale.setDefault(...)`. `localefmt` and the phrase loader follow it.

### offline.py: the API delivered

**Phrases.** `command(text, language=None)` names the fixed command a phrase asks for, or None. Its ids:

| Group | Ids |
|---|---|
| Me | `help`, `status`, `agents`, `hide`, `new chat`, `rename chat`, `settings`, `history`, `what's new`, `check for updates`, `report a problem`, `suggest an idea`, `version` |
| Focus and breaks | `stop focus`, `breaks off`, `breaks on`, `focus alerts off`, `focus alerts on` |
| Answered here | `time`, `date`, `week`, `coin` |
| Kept by the app | `notes`, `clear notes`, `stopwatch`, `stop stopwatch`, `reminders`, `clear reminders` |

Templates give `note`, `delete note` and `cancel reminder`, through `parse_kept` as before.

- `help_text(language=None)` gives the whole help as Markdown, in the person's language, and replaces `app.py`'s
  `HELP_ALL`.
- `phrases(language=None)` gives a `Phrases`, with `.command()`, `.template()`, `.asks()`, `.help()` and
  `.language`.
- Also: `load_phrases(language, folder)`, `normal(text)`, and `PHRASES`, the folder.

**M0-05.** The command table maps these ids to its handlers, in place of `_local`'s word tuples: `offline.command(text)`
then dispatch.

**Agents.** `agents_report(agents, now, label=None, markdown=True)` and `span(seconds)`:

- **M7-07, the *agents* command:** `self._offline(text, offline.agents_report(self.agents, self._now(), pretty))`.
- **M0-12, `chatmon status`:** the same with `markdown=False`.

### Package data and test dependencies (M6A)

- **Package data.** Add `"phrases/*.json"` to `[tool.setuptools.package-data] chatmon`. PyInstaller
  (`collect_data_files`), Nuitka (`--include-package-data`) and the Linux staging in `build.py` already take every
  file in the package. M6A's `test_package_data.py` will see `chatmon/phrases/en.json`.
- **Test dependencies.** Add `hypothesis` and `tzdata` to the test extra and to CI's install line; tzdata is what
  gives Windows a zone database for zoneinfo. Without them, the five property tests and the zone tests skip, each
  with its reason. Optionally, `tests/conftest.py` can load the `chatmon` Hypothesis profile.
- **`.hypothesis/`.** Hypothesis keeps a small cache there, with its own `.gitignore`. Adding `.hypothesis/` to the
  root `.gitignore` would be tidy.

### For the coordinator

- **The drill harness overwrites its spec.** `tests/drills/run.py` writes its JSON summary to
  `log.with_suffix(".json")`. With the suggested `drills.json` spec and `drills.log` log, the summary overwrites the
  spec after the first run. M5's spec is `drill-spec.json`.
- **The shared pipe makes two app tests fail.** `test_events.py::test_send_without_a_running_companion` and
  `test_app_smoke.py::test_a_hook_reaches_it` failed twice in this worktree's full runs. Both times another
  worker's `pytest tests/test_app_smoke.py` was running, and `\\.\pipe\chatmon-<SID>-1` was held. The pipe name
  is per user, so workers sharing a machine share it. Both tests pass on their own, and the full suite passed once
  that run had ended ([suite-interfered.log](reports/m5/suite-interfered.log) has the failing run). The name could
  take a per-run suffix in tests (M1A owns `events.py` and `winpipe.py`).
- **CRLF from Python edits.** On Windows, `Path.write_text` writes CRLF. With `core.autocrlf=true` the index stays
  LF, but the drill harness matches raw bytes, so a multi-line mutation misses a CRLF file.

## Changelog notes

These describe what M5's code does. Items that need M7's wiring before people see them are marked **(M7)**.

- Reminders understand days and dates: "friday at 3pm", "next mon", "dec 3", "2026-12-03 15:30", "tomorrow
  morning", "tonight at 8". "at 3" means whichever 3 o'clock comes next.
- If Chatmon can't tell when you mean ("friday tomorrow", "next week", "on 3/4"), it says so and shows a way to put
  it, instead of guessing.
- "in 2 hours" is two real hours, even across a daylight-saving change, and "tomorrow at 9" stays 9 AM.
- Reminders can repeat: "every day at 9", "every weekday at 9", "every monday at 9". When you press Done, a
  repeating reminder moves on to its next time.
- A reminder that comes due waits until you press Done or snooze it, even across a restart. **(M7)**
- Snooze a reminder for 5 minutes, 15 minutes, an hour, or until tomorrow at 9 AM. Reminders get their own snooze
  setting, and can be edited. **(M7)**
- Times and dates follow your system's settings: 24-hour or 12-hour clock, the order of day and month, and the
  names of days and months.
- *help* lists everything Chatmon does without any AI, in your language when there's a translation (only English
  ships). **(M7)**
- An *agents* command says which AI agents need you and which are working, and for how long. **(M7)**
- A sum whose answer has more than 400 digits is now always "too big".

## README notes

**Offline commands.**

- Add these reminder phrases: "remind me friday at 3pm to call Sam", "remind me dec 3 to renew the domain", and
  "remind me every weekday at 9 to stand up".
- Say that "in …" counts real time, and that unclear dates get a question back.
- Mention snooze choices **(M7)** and the *agents* command **(M7)**.

**Translation.** The offline phrases and help are data in `chatmon/phrases/`, one JSON file per language. English
is always understood. Only English ships; a translation is a new file beside `en.json`.

**Locale.** Times and dates follow the system's regional settings.

```quality-ledger
{
  "schema_version": 1,
  "work": {
    "id": "M5",
    "title": "Reminders, offline answers and locale",
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
        "pytest": "9.2.0",
        "PyQt6": "6.11.0",
        "ruff": "0.17.4",
        "hypothesis": "6.170.15",
        "tzdata": "2026.6"
      }
    }
  },
  "requirements": [
    {
      "id": "M5-01",
      "statement": "A fired reminder stays in the book, marked fired, until it is done or snoozed, and unacknowledged reminders come back at start",
      "priority": "critical",
      "acceptance": [
        "M5-01.A1",
        "M5-01.A2"
      ],
      "superseded_by": null
    },
    {
      "id": "M5-02",
      "statement": "Reminder phrases are read as meant: weekdays, next mon, dec 3, ISO dates, a bare hour's next occurrence, an ambiguous result for leftover date words, and in-spans as epoch plus seconds",
      "priority": "critical",
      "acceptance": [
        "M5-02.A1",
        "M5-02.A2",
        "M5-02.A3",
        "M5-02.A4"
      ],
      "superseded_by": null
    },
    {
      "id": "M5-03",
      "statement": "Reminders repeat (every day, every weekday, every monday at 9) and are rescheduled when they fire and are done",
      "priority": "normal",
      "acceptance": [
        "M5-03.A1"
      ],
      "superseded_by": null
    },
    {
      "id": "M5-04",
      "statement": "Snooze offers 5 min, 15 min, 1 h and tomorrow at 9 AM with the reminder's own snooze, and a reminder's text and time can be edited",
      "priority": "normal",
      "acceptance": [
        "M5-04.A1",
        "M5-04.A2"
      ],
      "superseded_by": null
    },
    {
      "id": "M5-05",
      "statement": "Times and dates are formatted with QLocale, with a plain fallback where Qt isn't loaded",
      "priority": "normal",
      "acceptance": [
        "M5-05.A1"
      ],
      "superseded_by": null
    },
    {
      "id": "M5-06",
      "statement": "The offline commands' phrases are per-language data, English is always accepted, and help lists the commands in the active language",
      "priority": "normal",
      "acceptance": [
        "M5-06.A1",
        "M5-06.A2"
      ],
      "superseded_by": null
    },
    {
      "id": "M5-07",
      "statement": "Hypothesis property tests cover the calculator and parse_when, fast and deterministic",
      "priority": "normal",
      "acceptance": [
        "M5-07.A1",
        "M5-07.A2"
      ],
      "superseded_by": null
    },
    {
      "id": "M5-08",
      "statement": "A pure function formats agent states and durations for an agents command and chatmon status",
      "priority": "normal",
      "acceptance": [
        "M5-08.A1"
      ],
      "superseded_by": null
    }
  ],
  "acceptance": [
    {
      "id": "M5-01.A1",
      "requirement": "M5-01",
      "given": "A reminder whose time has come",
      "when": "due(now) and fire(now) are called, then snooze or acknowledge",
      "then": "It is listed and stays in the book marked fired, fire tells about it once, snooze moves it and clears fired, and only acknowledge removes it",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M5-01.A2",
      "requirement": "M5-01",
      "given": "A book with a fired, unacknowledged reminder, saved to plain JSON and read back, and a list saved before M5",
      "when": "The book is read at start",
      "then": "The fired reminder is listed by due(now) and isn't news to fire(now), and the old list reads back and saves unchanged",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M5-02.A1",
      "requirement": "M5-02",
      "given": "A Wednesday morning",
      "when": "Reminders name weekdays, next mon, dec 3, the 3rd of december, ISO dates, tonight and tomorrow morning",
      "then": "Each is due on that day at the said or usual time, with the time words taken out of its text",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M5-02.A2",
      "requirement": "M5-02",
      "given": "A bare hour of 12 or less with no day",
      "when": "It is said at different times of day",
      "then": "It is due at whichever of h and h+12 comes next, and a leading zero or an hour of 13 or more is the 24-hour clock",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M5-02.A3",
      "requirement": "M5-02",
      "given": "Time words that can't all be placed (two days, next week, on 3/4, every 2 hours, conflicts, gone or impossible days)",
      "when": "The phrase is parsed",
      "then": "The result is ambiguous: no due time, the words named, and parse_command gives kind unclear with them",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M5-02.A4",
      "requirement": "M5-02",
      "given": "A real zone with daylight saving (America/New_York) and the computer's own zone",
      "when": "in-spans and wall-clock times are parsed across a change",
      "then": "An in-span is exactly that many real seconds, and a wall-clock time keeps its hour",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M5-03.A1",
      "requirement": "M5-03",
      "given": "every day, every weekday and every monday at 9",
      "when": "They are parsed, fire, and are acknowledged, also across daylight saving",
      "then": "Each has a repeat rule and first time, and done moves it on to its next time on the wall clock instead of removing it",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M5-04.A1",
      "requirement": "M5-04",
      "given": "A fired reminder",
      "when": "Snooze choices are asked for and one is taken",
      "then": "The choices are the reminder's own snooze, 5 min, 15 min, 1 hour and tomorrow at 9 AM on the wall clock, and snoozing moves it and clears fired",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M5-04.A2",
      "requirement": "M5-04",
      "given": "A reminder",
      "when": "Its text, time or repeat is edited, including with bad values",
      "then": "Good edits apply, bad ones raise ValueError and change nothing, and an unknown id gives False",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M5-05.A1",
      "requirement": "M5-05",
      "given": "Locales en_GB, de_DE, en_US, C, Qt's default, and a process without Qt",
      "when": "Times and dates are written, also by reminders and offline answers",
      "then": "Qt's locale formats them where Qt is loaded, and plain English otherwise and in the C locale",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M5-06.A1",
      "requirement": "M5-06",
      "given": "en.json and a translation file in a folder",
      "when": "Phrases are matched with English, the translation, a missing one and a broken one",
      "then": "Commands come from the data, English is always understood and wins conflicts, and a missing or broken translation leaves English",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M5-06.A2",
      "requirement": "M5-06",
      "given": "The help data",
      "when": "Help is asked for in English and in a translated language",
      "then": "It lists every command, in the active language where translated and English elsewhere, and every example is understood offline",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M5-07.A1",
      "requirement": "M5-07",
      "given": "Generated sums and typed text",
      "when": "The calculator and answer() read them under a derandomized Hypothesis profile",
      "then": "Only ValueError or OverflowError is raised, each takes under 0.5 s, and whole-number results have at most _MAX_DIGITS digits",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M5-07.A2",
      "requirement": "M5-07",
      "given": "Generated moments in five zones with daylight saving, and generated phrases",
      "when": "parse_when reads them",
      "then": "Every due time is after now and at most LONGEST later, in-spans are exact, and 24-hour times keep their wall-clock time",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M5-08.A1",
      "requirement": "M5-08",
      "given": "Agents needing you and working, with since-times",
      "when": "The report is made in Markdown and plain",
      "then": "Needs-you comes first, longest waiting first, then working, each with its duration, and no agents says so",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    }
  ],
  "tasks": [
    {
      "id": "T1-locale",
      "purpose": "Write times and dates through a new localefmt module (QLocale or plain English) and use it in reminders and offline answers",
      "acceptance": [
        "M5-05.A1"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/localefmt.py",
          "action": "create"
        },
        {
          "path": "tests/test_localefmt.py",
          "action": "create"
        },
        {
          "path": "chatmon/reminders.py",
          "action": "modify"
        },
        {
          "path": "chatmon/offline.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-behavior-m5",
        "E-suite",
        "E-red-M5-05-qlocale-unused",
        "E-red-M5-05-loads-qt",
        "E-red-M5-05-c-locale-shown",
        "E-red-M5-05-offline-12-hour"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T2-parse",
      "purpose": "Extend the canonical reminder parser: days, dates, bare hours, ambiguity, epoch in-spans, wall-clock times and repeat phrases",
      "acceptance": [
        "M5-02.A1",
        "M5-02.A2",
        "M5-02.A3",
        "M5-02.A4"
      ],
      "depends_on": [
        "T1-locale"
      ],
      "changes": [
        {
          "path": "chatmon/reminders.py",
          "action": "modify"
        },
        {
          "path": "tests/test_reminders.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-behavior-m5",
        "E-suite",
        "E-red-M5-02-weekday-ignored",
        "E-red-M5-02-bare-hour-am",
        "E-red-M5-02-leftovers-guessed",
        "E-red-M5-02-in-by-wall-clock"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T3-book",
      "purpose": "Extend the canonical ReminderBook: fired state, due/fire/acknowledge/snooze/update, repeat rescheduling, snooze choices and compatible saves",
      "acceptance": [
        "M5-01.A1",
        "M5-01.A2",
        "M5-03.A1",
        "M5-04.A1",
        "M5-04.A2"
      ],
      "depends_on": [
        "T2-parse"
      ],
      "changes": [
        {
          "path": "chatmon/reminders.py",
          "action": "modify"
        },
        {
          "path": "tests/test_reminders.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-behavior-m5",
        "E-suite",
        "E-red-M5-01-removed-when-due",
        "E-red-M5-01-fired-not-saved",
        "E-red-M5-01-old-saves-change",
        "E-red-M5-03-every-not-read",
        "E-red-M5-03-done-repeat-removed",
        "E-red-M5-03-repeat-by-real-days",
        "E-red-M5-04-no-hour-snooze",
        "E-red-M5-04-tomorrow-by-real-day",
        "E-red-M5-04-snooze-stays-fired",
        "E-red-M5-04-blank-edit-accepted"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T4-phrases",
      "purpose": "Move offline phrases and help into chatmon/phrases/en.json with a loader that merges a language with English",
      "acceptance": [
        "M5-06.A1",
        "M5-06.A2"
      ],
      "depends_on": [
        "T1-locale"
      ],
      "changes": [
        {
          "path": "chatmon/phrases/en.json",
          "action": "create"
        },
        {
          "path": "chatmon/offline.py",
          "action": "modify"
        },
        {
          "path": "tests/test_offline.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-behavior-m5",
        "E-suite",
        "E-red-M5-06-english-dropped",
        "E-red-M5-06-help-not-translated",
        "E-red-M5-06-broken-file-raises",
        "E-red-M5-06-phrases-not-normalized"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T5-agents",
      "purpose": "Add agents_report and span to offline.py for the agents command and chatmon status",
      "acceptance": [
        "M5-08.A1"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/offline.py",
          "action": "modify"
        },
        {
          "path": "tests/test_offline.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-behavior-m5",
        "E-suite",
        "E-red-M5-08-working-first",
        "E-red-M5-08-span-off-by-one"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T6-properties",
      "purpose": "Add deterministic Hypothesis property tests for the calculator and parse_when, and fix what they found in the calculator",
      "acceptance": [
        "M5-07.A1",
        "M5-07.A2"
      ],
      "depends_on": [
        "T2-parse",
        "T4-phrases"
      ],
      "changes": [
        {
          "path": "tests/test_parser_properties.py",
          "action": "create"
        },
        {
          "path": "chatmon/offline.py",
          "action": "modify"
        },
        {
          "path": "chatmon/reminders.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-behavior-m5",
        "E-suite",
        "E-red-M5-07-401-digits",
        "E-red-M5-07-type-error-escapes",
        "E-red-M5-07-past-longest",
        "E-red-M5-07-in-by-wall-clock"
      ],
      "blocker": null,
      "superseded_by": null
    }
  ],
  "evidence": [
    {
      "id": "E-readiness",
      "acceptance": [
        "M5-01.A1",
        "M5-01.A2",
        "M5-02.A1",
        "M5-02.A2",
        "M5-02.A3",
        "M5-02.A4",
        "M5-03.A1",
        "M5-04.A1",
        "M5-04.A2",
        "M5-05.A1",
        "M5-06.A1",
        "M5-06.A2",
        "M5-07.A1",
        "M5-07.A2",
        "M5-08.A1"
      ],
      "kind": "readiness",
      "status": "pass",
      "command": [],
      "method": "Requirements review of M5-01..M5-08 against the assessment, the roadmap's owner decisions, file ownership and reminder contract, and pyproject.toml: findings re-checked on 5346385 (findings-recheck.log), ambiguities resolved with recorded decisions, failure behaviour, terminology, scope and coverage (readiness.md).",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m5/readiness.md",
        "sha256": "483577eb308a12add8223458a2134740aa43612301c065379971b560af24c51a"
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
      "scope_sha256": "ac4cdc210a7c5810f7c2e290fdbe91d872e83b497977a96614b66837709d2f11",
      "red": null,
      "reason": null
    },
    {
      "id": "E-behavior-m5",
      "acceptance": [
        "M5-01.A1",
        "M5-01.A2",
        "M5-02.A1",
        "M5-02.A2",
        "M5-02.A3",
        "M5-02.A4",
        "M5-03.A1",
        "M5-04.A1",
        "M5-04.A2",
        "M5-05.A1",
        "M5-06.A1",
        "M5-06.A2",
        "M5-07.A1",
        "M5-07.A2",
        "M5-08.A1"
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
        "-rs",
        "tests/test_reminders.py",
        "tests/test_offline.py",
        "tests/test_localefmt.py",
        "tests/test_parser_properties.py"
      ],
      "method": "Ran M5's four test modules, which exercise every M5 acceptance criterion: 209 passed, 1 skipped (the Unix-only time.tzset check of the app's naive local time). Real Qt locales, real zoneinfo zones (tzdata), a subprocess without Qt, Hypothesis under the derandomized chatmon profile.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/behavior.log",
        "sha256": "275d03dde0d49a0326b4d6cbb95152588ad762b59a7b562fd5525fe0fa28afb4"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/phrases/en.json",
          "sha256": "03c9900891775478e4810607d004bb88c055417af0a3e714a8fe7a39dd2d05ea"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "c0f5d57588cd79ac8f825afb729a17b2079d7618163eaad587d418164ffa93c1"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "e598820b921a97c21ea9e531943362f2de50681d310dde8d1556768963c8b552"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "a4924383b46b88e2781817b2223027fe0674c9495981d87eef6ad419edbfecc7"
        }
      ],
      "scope_sha256": "ac4cdc210a7c5810f7c2e290fdbe91d872e83b497977a96614b66837709d2f11",
      "red": null,
      "reason": null
    },
    {
      "id": "E-suite",
      "acceptance": [
        "M5-01.A1",
        "M5-01.A2",
        "M5-02.A1",
        "M5-02.A2",
        "M5-02.A3",
        "M5-02.A4",
        "M5-03.A1",
        "M5-04.A1",
        "M5-04.A2",
        "M5-05.A1",
        "M5-06.A1",
        "M5-06.A2",
        "M5-07.A1",
        "M5-07.A2",
        "M5-08.A1"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider"
      ],
      "method": "Ran the whole suite on the final source: every test in the repository, M5's included, with no other worker's companion holding the shared per-user pipe.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/suite.log",
        "sha256": "06f65a113da1555b5c9610d99749be43d41a8e4a6e1483b768d6182deb563da6"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/phrases/en.json",
          "sha256": "03c9900891775478e4810607d004bb88c055417af0a3e714a8fe7a39dd2d05ea"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "c0f5d57588cd79ac8f825afb729a17b2079d7618163eaad587d418164ffa93c1"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "e598820b921a97c21ea9e531943362f2de50681d310dde8d1556768963c8b552"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "a4924383b46b88e2781817b2223027fe0674c9495981d87eef6ad419edbfecc7"
        }
      ],
      "scope_sha256": "ac4cdc210a7c5810f7c2e290fdbe91d872e83b497977a96614b66837709d2f11",
      "red": null,
      "reason": null
    },
    {
      "id": "E-red-M5-01-removed-when-due",
      "acceptance": [
        "M5-01.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-01-removed-when-due in a temporary copy (tests/drills/run.py): green, then chatmon/reminders.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "a4924383b46b88e2781817b2223027fe0674c9495981d87eef6ad419edbfecc7"
        }
      ],
      "scope_sha256": "39bccffaecf19b59eaf7ab449be326ba831555399cb63ac4f317305f8c71ba60",
      "red": {
        "mutation": "'        for r in due:\\n            r.fired = True\\n        return due' -> '        self.items = [r for r in self.items if r.due > now]\\n        return due'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_fired_reminder_stays_until_done_or_snoozed",
        "observed_diagnostic": "______________ test_a_fired_reminder_stays_until_done_or_snoozed ______________",
        "before": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "dd06a3b7883bdcacf78ca8257af04d202c079e9dd7c51d217cef5f23e7081b97"
          }
        ],
        "after": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-01-fired-not-saved",
      "acceptance": [
        "M5-01.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-01-fired-not-saved in a temporary copy (tests/drills/run.py): green, then chatmon/reminders.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "a4924383b46b88e2781817b2223027fe0674c9495981d87eef6ad419edbfecc7"
        }
      ],
      "scope_sha256": "39bccffaecf19b59eaf7ab449be326ba831555399cb63ac4f317305f8c71ba60",
      "red": {
        "mutation": "'reminder.fired = entry.get(\"fired\") is True' -> 'reminder.fired = False'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_unacknowledged_reminders_come_back_at_start",
        "observed_diagnostic": "______________ test_unacknowledged_reminders_come_back_at_start _______________",
        "before": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "77faefc2c17241e5eda9fde11927107cb5370e020c03bb95be736361919e199c"
          }
        ],
        "after": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-01-old-saves-change",
      "acceptance": [
        "M5-01.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-01-old-saves-change in a temporary copy (tests/drills/run.py): green, then chatmon/reminders.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "a4924383b46b88e2781817b2223027fe0674c9495981d87eef6ad419edbfecc7"
        }
      ],
      "scope_sha256": "39bccffaecf19b59eaf7ab449be326ba831555399cb63ac4f317305f8c71ba60",
      "red": {
        "mutation": "'if k not in _LATER_FIELDS or v != _LATER_FIELDS[k]' -> 'if k'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_reminders_saved_before_repeats_read_back_unchanged",
        "observed_diagnostic": "___________ test_reminders_saved_before_repeats_read_back_unchanged ___________",
        "before": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "c3c50df7c6eb70106bf64513ff2ce76c2671d2939d6836406dc3317bc2661a69"
          }
        ],
        "after": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-02-weekday-ignored",
      "acceptance": [
        "M5-02.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-02-weekday-ignored in a temporary copy (tests/drills/run.py): green, then chatmon/reminders.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "a4924383b46b88e2781817b2223027fe0674c9495981d87eef6ad419edbfecc7"
        }
      ],
      "scope_sha256": "539b36f7d65087960a917cce9174b18eaaabc8a05ed12fcf5f9e57de8da8b5eb",
      "red": {
        "mutation": "'return \"weekday\", _DAYS[m.group(\"day\").lower()], (m.group(\"which\") or \"\").lower() == \"next\"' -> 'return \"day\", now.date(), False'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_days_and_dates",
        "observed_diagnostic": "___ test_days_and_dates[remind me friday at 3pm to call Sam-due0-call Sam] ____",
        "before": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "bb29c30fc5b964a1d6a341b0e22f68ae5edc55451e308c78ab759e00d9eebdaa"
          }
        ],
        "after": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-02-bare-hour-am",
      "acceptance": [
        "M5-02.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-02-bare-hour-am in a temporary copy (tests/drills/run.py): green, then chatmon/reminders.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "a4924383b46b88e2781817b2223027fe0674c9495981d87eef6ad419edbfecc7"
        }
      ],
      "scope_sha256": "539b36f7d65087960a917cce9174b18eaaabc8a05ed12fcf5f9e57de8da8b5eb",
      "red": {
        "mutation": "'hours = (h, (h + 12) % 24) if' -> 'hours = (h,) if'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_bare_hour_is_whichever_of_am_and_pm_comes_next",
        "observed_diagnostic": "_ test_a_bare_hour_is_whichever_of_am_and_pm_comes_next[said_at0-remind me at 3 to x-due0] _",
        "before": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "c3f76464b37a60217f8c5b4725051622fa5071a8a93c467564334efb03181104"
          }
        ],
        "after": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-02-leftovers-guessed",
      "acceptance": [
        "M5-02.A3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-02-leftovers-guessed in a temporary copy (tests/drills/run.py): green, then chatmon/reminders.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "a4924383b46b88e2781817b2223027fe0674c9495981d87eef6ad419edbfecc7"
        }
      ],
      "scope_sha256": "539b36f7d65087960a917cce9174b18eaaabc8a05ed12fcf5f9e57de8da8b5eb",
      "red": {
        "mutation": "'if bad or leftovers or (seconds and timed)' -> 'if bad or (seconds and timed)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_time_words_that_cant_all_be_placed_are_ambiguous",
        "observed_diagnostic": "_ test_time_words_that_cant_all_be_placed_are_ambiguous[remind me friday tomorrow to x-friday tomorrow] _",
        "before": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "8483d8d26fb789e22f22bd4d6e51540db1b031e8b9d8a4e425592e9e69b16cd1"
          }
        ],
        "after": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-02-in-by-wall-clock",
      "acceptance": [
        "M5-02.A4"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-02-in-by-wall-clock in a temporary copy (tests/drills/run.py): green, then chatmon/reminders.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "a4924383b46b88e2781817b2223027fe0674c9495981d87eef6ad419edbfecc7"
        }
      ],
      "scope_sha256": "539b36f7d65087960a917cce9174b18eaaabc8a05ed12fcf5f9e57de8da8b5eb",
      "red": {
        "mutation": "'return _at(start + seconds, now), None' -> 'return now + timedelta(seconds=seconds), None'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_in_is_real_time_across_daylight_saving",
        "observed_diagnostic": "_________________ test_in_is_real_time_across_daylight_saving _________________",
        "before": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "b387b62b9a1d042acd4694b50c2da5dabb18a80f87c8294254c804f5ad606e63"
          }
        ],
        "after": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-03-every-not-read",
      "acceptance": [
        "M5-03.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-03-every-not-read in a temporary copy (tests/drills/run.py): green, then chatmon/reminders.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "a4924383b46b88e2781817b2223027fe0674c9495981d87eef6ad419edbfecc7"
        }
      ],
      "scope_sha256": "39bccffaecf19b59eaf7ab449be326ba831555399cb63ac4f317305f8c71ba60",
      "red": {
        "mutation": "'every = words.take(_EVERY_RE)' -> 'every = None'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_repeating_reminders",
        "observed_diagnostic": "_ test_repeating_reminders[remind me every day at 9 to stand up-due0-daily@09:00-stand up] _",
        "before": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "08f75c3b8b9e19a9e3cae902e178f8db7f12744206898a4cc60498eda4baa047"
          }
        ],
        "after": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-03-done-repeat-removed",
      "acceptance": [
        "M5-03.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-03-done-repeat-removed in a temporary copy (tests/drills/run.py): green, then chatmon/reminders.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "a4924383b46b88e2781817b2223027fe0674c9495981d87eef6ad419edbfecc7"
        }
      ],
      "scope_sha256": "39bccffaecf19b59eaf7ab449be326ba831555399cb63ac4f317305f8c71ba60",
      "red": {
        "mutation": "'        if r.repeat:\\n            r.due = next_time(r.repeat, max(' -> '        if False:\\n            r.due = next_time(r.repeat, max('",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_repeating_reminder_moves_on_when_done",
        "observed_diagnostic": "________________ test_a_repeating_reminder_moves_on_when_done _________________",
        "before": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "64da78ba91963396af8fd418a399efd2ff9f46718c93635bbd2866d639e7cf8c"
          }
        ],
        "after": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-03-repeat-by-real-days",
      "acceptance": [
        "M5-03.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-03-repeat-by-real-days in a temporary copy (tests/drills/run.py): green, then chatmon/reminders.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "a4924383b46b88e2781817b2223027fe0674c9495981d87eef6ad419edbfecc7"
        }
      ],
      "scope_sha256": "39bccffaecf19b59eaf7ab449be326ba831555399cb63ac4f317305f8c71ba60",
      "red": {
        "mutation": "'moment = _on_wall(day, hour, minute, start).timestamp()' -> 'moment = start.replace(hour=hour, minute=minute, second=0, microsecond=0).timestamp() + k * DAY'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_daily_reminder_keeps_its_hour_across_daylight_saving",
        "observed_diagnostic": "_________ test_a_daily_reminder_keeps_its_hour_across_daylight_saving _________",
        "before": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "772c9794bd0257f1a9370422fbcb9adeec0bac357cc9df6fdb0ebdc2903297aa"
          }
        ],
        "after": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-04-no-hour-snooze",
      "acceptance": [
        "M5-04.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-04-no-hour-snooze in a temporary copy (tests/drills/run.py): green, then chatmon/reminders.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "a4924383b46b88e2781817b2223027fe0674c9495981d87eef6ad419edbfecc7"
        }
      ],
      "scope_sha256": "39bccffaecf19b59eaf7ab449be326ba831555399cb63ac4f317305f8c71ba60",
      "red": {
        "mutation": "'_SNOOZES = (5, 15, 60)' -> '_SNOOZES = (5, 15)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_snooze_offers_its_own_setting_then_5_15_60_minutes_and_tomorrow_morning",
        "observed_diagnostic": "_ test_snooze_offers_its_own_setting_then_5_15_60_minutes_and_tomorrow_morning _",
        "before": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "01b583d5ab1f36473430e1ecd660b18a50ff17ed1713fdee2888b7a181d35f55"
          }
        ],
        "after": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-04-tomorrow-by-real-day",
      "acceptance": [
        "M5-04.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-04-tomorrow-by-real-day in a temporary copy (tests/drills/run.py): green, then chatmon/reminders.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "a4924383b46b88e2781817b2223027fe0674c9495981d87eef6ad419edbfecc7"
        }
      ],
      "scope_sha256": "39bccffaecf19b59eaf7ab449be326ba831555399cb63ac4f317305f8c71ba60",
      "red": {
        "mutation": "'tomorrow = _on_wall(today.date() + timedelta(days=1), DEFAULT_HOUR, 0, today)' -> 'tomorrow = _at(_on_wall(today.date(), DEFAULT_HOUR, 0, today).timestamp() + DAY, today)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_snoozing_until_tomorrow_morning_keeps_9_am_across_daylight_saving",
        "observed_diagnostic": "___ test_snoozing_until_tomorrow_morning_keeps_9_am_across_daylight_saving ____",
        "before": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "9a2877c57d3cabf2b67f60b1de6deefae391e7e34682eecb84005e28983f5d96"
          }
        ],
        "after": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-04-snooze-stays-fired",
      "acceptance": [
        "M5-04.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-04-snooze-stays-fired in a temporary copy (tests/drills/run.py): green, then chatmon/reminders.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "a4924383b46b88e2781817b2223027fe0674c9495981d87eef6ad419edbfecc7"
        }
      ],
      "scope_sha256": "39bccffaecf19b59eaf7ab449be326ba831555399cb63ac4f317305f8c71ba60",
      "red": {
        "mutation": "'r.due, r.fired = until, False' -> 'r.due = until'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_fired_reminder_stays_until_done_or_snoozed",
        "observed_diagnostic": "______________ test_a_fired_reminder_stays_until_done_or_snoozed ______________",
        "before": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "b7265b21aef3ec77e2a67bcf76f98698ee8307bced2f9fbdb880cea27a3da222"
          }
        ],
        "after": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-04-blank-edit-accepted",
      "acceptance": [
        "M5-04.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-04-blank-edit-accepted in a temporary copy (tests/drills/run.py): green, then chatmon/reminders.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "a4924383b46b88e2781817b2223027fe0674c9495981d87eef6ad419edbfecc7"
        }
      ],
      "scope_sha256": "39bccffaecf19b59eaf7ab449be326ba831555399cb63ac4f317305f8c71ba60",
      "red": {
        "mutation": "'if text is not None and not text.strip():' -> 'if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_reminder_can_be_edited",
        "observed_diagnostic": "________________________ test_a_reminder_can_be_edited ________________________",
        "before": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "2eb27276c327394af79ba80b4730157b55f726fdeabce52de942de3acc76d1cb"
          }
        ],
        "after": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-05-qlocale-unused",
      "acceptance": [
        "M5-05.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-05-qlocale-unused in a temporary copy (tests/drills/run.py): green, then chatmon/localefmt.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        }
      ],
      "scope_sha256": "d007eb82aa5ea09ee3fc25e26feff4a709e363e39aeb545e1a7960ac2279503d",
      "red": {
        "mutation": "'    locale = _locale()\\n    if locale is None:\\n        return f\"{(when.hour % 12)' -> '    locale = _locale()\\n    if True:\\n        return f\"{(when.hour % 12)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_british_english_writes_24_hour_times_and_day_first_dates",
        "observed_diagnostic": "________ test_british_english_writes_24_hour_times_and_day_first_dates ________",
        "before": [
          {
            "path": "chatmon/localefmt.py",
            "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/localefmt.py",
            "sha256": "3ff452740d0382d55f9a56a45f47b5ddebb4669655a5caf37b2e35915cd16adc"
          }
        ],
        "after": [
          {
            "path": "chatmon/localefmt.py",
            "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-05-loads-qt",
      "acceptance": [
        "M5-05.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-05-loads-qt in a temporary copy (tests/drills/run.py): green, then chatmon/localefmt.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        }
      ],
      "scope_sha256": "d007eb82aa5ea09ee3fc25e26feff4a709e363e39aeb545e1a7960ac2279503d",
      "red": {
        "mutation": "'        if qtcore is None:\\n            return None\\n' -> '        if qtcore is None:\\n            from PyQt6 import QtCore as qtcore\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_without_qt_it_writes_plain_english_and_reads_the_language_from_the_environment",
        "observed_diagnostic": "_ test_without_qt_it_writes_plain_english_and_reads_the_language_from_the_environment _",
        "before": [
          {
            "path": "chatmon/localefmt.py",
            "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/localefmt.py",
            "sha256": "be1994e864895fff24ba87b0abec15fd276e72394b31fb20fe16feca2697becd"
          }
        ],
        "after": [
          {
            "path": "chatmon/localefmt.py",
            "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-05-c-locale-shown",
      "acceptance": [
        "M5-05.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-05-c-locale-shown in a temporary copy (tests/drills/run.py): green, then chatmon/localefmt.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        }
      ],
      "scope_sha256": "d007eb82aa5ea09ee3fc25e26feff4a709e363e39aeb545e1a7960ac2279503d",
      "red": {
        "mutation": "'if qtcore is not None and locale.language() == qtcore.QLocale.Language.C:' -> 'if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_no_locale_at_all_is_plain_english_not_qts_c_look",
        "observed_diagnostic": "____________ test_no_locale_at_all_is_plain_english_not_qts_c_look ____________",
        "before": [
          {
            "path": "chatmon/localefmt.py",
            "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/localefmt.py",
            "sha256": "c38b455529723d64b278d4a223a889531fd193f81c7a5cc563a47bd05c0d8319"
          }
        ],
        "after": [
          {
            "path": "chatmon/localefmt.py",
            "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-05-offline-12-hour",
      "acceptance": [
        "M5-05.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-05-offline-12-hour in a temporary copy (tests/drills/run.py): green, then chatmon/offline.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        }
      ],
      "scope_sha256": "d007eb82aa5ea09ee3fc25e26feff4a709e363e39aeb545e1a7960ac2279503d",
      "red": {
        "mutation": "'return f\"It\\'s **{localefmt.time_of_day(now)}**.\"' -> 'return f\"It\\'s **{(now.hour % 12) or 12}:{now.minute:02d} {\\'AM\\' if now.hour < 12 else \\'PM\\'}**.\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_reminders_and_offline_answers_write_times_the_locales_way",
        "observed_diagnostic": "_______ test_reminders_and_offline_answers_write_times_the_locales_way ________",
        "before": [
          {
            "path": "chatmon/offline.py",
            "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/offline.py",
            "sha256": "87ec4ea63a291baa5e9bc4da2a9ea2f12d35566b2f850efd185f4333c43e463f"
          }
        ],
        "after": [
          {
            "path": "chatmon/offline.py",
            "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-06-english-dropped",
      "acceptance": [
        "M5-06.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-06-english-dropped in a temporary copy (tests/drills/run.py): green, then chatmon/offline.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/phrases/en.json",
          "sha256": "03c9900891775478e4810607d004bb88c055417af0a3e714a8fe7a39dd2d05ea"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "c0f5d57588cd79ac8f825afb729a17b2079d7618163eaad587d418164ffa93c1"
        }
      ],
      "scope_sha256": "4b5ab447295623c5b95e2db49758e5260f1b30d53100454938b67702a4348156",
      "red": {
        "mutation": "'for source in (_table(own, \"commands\"), known):' -> 'for source in (_table(own, \"commands\") or known,):'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_another_languages_phrases_and_help_with_english_always_understood",
        "observed_diagnostic": "___ test_another_languages_phrases_and_help_with_english_always_understood ____",
        "before": [
          {
            "path": "chatmon/offline.py",
            "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/offline.py",
            "sha256": "bf527085b4aea8765524fd973b483282ef3725166932a2bd5cc470dc7880dc44"
          }
        ],
        "after": [
          {
            "path": "chatmon/offline.py",
            "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-06-help-not-translated",
      "acceptance": [
        "M5-06.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-06-help-not-translated in a temporary copy (tests/drills/run.py): green, then chatmon/offline.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/phrases/en.json",
          "sha256": "03c9900891775478e4810607d004bb88c055417af0a3e714a8fe7a39dd2d05ea"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "c0f5d57588cd79ac8f825afb729a17b2079d7618163eaad587d418164ffa93c1"
        }
      ],
      "scope_sha256": "4b5ab447295623c5b95e2db49758e5260f1b30d53100454938b67702a4348156",
      "red": {
        "mutation": "'name = mine.get(\"name\") if isinstance(mine.get(\"name\"), str) else section[\"name\"]' -> 'name = section[\"name\"]'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_another_languages_phrases_and_help_with_english_always_understood",
        "observed_diagnostic": "___ test_another_languages_phrases_and_help_with_english_always_understood ____",
        "before": [
          {
            "path": "chatmon/offline.py",
            "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/offline.py",
            "sha256": "bcc149a8fe42c11aa20bb7e80eb80a7e3c2c2d64aa823fcf6f57ff03a48608cf"
          }
        ],
        "after": [
          {
            "path": "chatmon/offline.py",
            "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-06-broken-file-raises",
      "acceptance": [
        "M5-06.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-06-broken-file-raises in a temporary copy (tests/drills/run.py): green, then chatmon/offline.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/phrases/en.json",
          "sha256": "03c9900891775478e4810607d004bb88c055417af0a3e714a8fe7a39dd2d05ea"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "c0f5d57588cd79ac8f825afb729a17b2079d7618163eaad587d418164ffa93c1"
        }
      ],
      "scope_sha256": "4b5ab447295623c5b95e2db49758e5260f1b30d53100454938b67702a4348156",
      "red": {
        "mutation": "'        except (OSError, ValueError):\\n            continue' -> '        except OSError:\\n            continue'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_missing_or_broken_translation_leaves_english",
        "observed_diagnostic": "_____________ test_a_missing_or_broken_translation_leaves_english _____________",
        "before": [
          {
            "path": "chatmon/offline.py",
            "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/offline.py",
            "sha256": "9b53f687446aad5f109532f145a633e04ed791f4d760f745ab9f96963ad512c0"
          }
        ],
        "after": [
          {
            "path": "chatmon/offline.py",
            "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-06-phrases-not-normalized",
      "acceptance": [
        "M5-06.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-06-phrases-not-normalized in a temporary copy (tests/drills/run.py): green, then chatmon/offline.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/phrases/en.json",
          "sha256": "03c9900891775478e4810607d004bb88c055417af0a3e714a8fe7a39dd2d05ea"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "c0f5d57588cd79ac8f825afb729a17b2079d7618163eaad587d418164ffa93c1"
        }
      ],
      "scope_sha256": "4b5ab447295623c5b95e2db49758e5260f1b30d53100454938b67702a4348156",
      "red": {
        "mutation": "'return self.commands.get(normal(text))' -> 'return self.commands.get(text)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_fixed_commands_are_read_from_the_phrase_data",
        "observed_diagnostic": "__ test_fixed_commands_are_read_from_the_phrase_data[What can you do?-help] ___",
        "before": [
          {
            "path": "chatmon/offline.py",
            "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/offline.py",
            "sha256": "0d1ebce62f23bdf7c1d1bcf98fe2edf381118dfa4da79616791ef9b8db806324"
          }
        ],
        "after": [
          {
            "path": "chatmon/offline.py",
            "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-07-401-digits",
      "acceptance": [
        "M5-07.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-07-401-digits in a temporary copy (tests/drills/run.py): green, then chatmon/offline.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/phrases/en.json",
          "sha256": "03c9900891775478e4810607d004bb88c055417af0a3e714a8fe7a39dd2d05ea"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "c0f5d57588cd79ac8f825afb729a17b2079d7618163eaad587d418164ffa93c1"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "e598820b921a97c21ea9e531943362f2de50681d310dde8d1556768963c8b552"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "a4924383b46b88e2781817b2223027fe0674c9495981d87eef6ad419edbfecc7"
        }
      ],
      "scope_sha256": "de21efa2658565ee8e553a9525477fad6ae2a46c06f2ce51e415982054e27f26",
      "red": {
        "mutation": "'abs(value) >= _TOO_MANY_DIGITS' -> 'abs(value) >= _TOO_MANY_DIGITS * 10'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_sum_is_answered_or_refused_quickly_and_never_too_long",
        "observed_diagnostic": "________ test_a_sum_is_answered_or_refused_quickly_and_never_too_long _________",
        "before": [
          {
            "path": "chatmon/offline.py",
            "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/offline.py",
            "sha256": "df41cab1669cff3a6069a188a88ee129c8943c2c0ade139668fc718b0598e03f"
          }
        ],
        "after": [
          {
            "path": "chatmon/offline.py",
            "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-07-type-error-escapes",
      "acceptance": [
        "M5-07.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-07-type-error-escapes in a temporary copy (tests/drills/run.py): green, then chatmon/offline.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/phrases/en.json",
          "sha256": "03c9900891775478e4810607d004bb88c055417af0a3e714a8fe7a39dd2d05ea"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "c0f5d57588cd79ac8f825afb729a17b2079d7618163eaad587d418164ffa93c1"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "e598820b921a97c21ea9e531943362f2de50681d310dde8d1556768963c8b552"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "a4924383b46b88e2781817b2223027fe0674c9495981d87eef6ad419edbfecc7"
        }
      ],
      "scope_sha256": "de21efa2658565ee8e553a9525477fad6ae2a46c06f2ce51e415982054e27f26",
      "red": {
        "mutation": "'    except (ValueError, TypeError):\\n        raise ValueError(\"that can\\'t be worked out\")' -> '    except ValueError:\\n        raise ValueError(\"that can\\'t be worked out\")'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_sum_is_answered_or_refused_quickly_and_never_too_long",
        "observed_diagnostic": "________ test_a_sum_is_answered_or_refused_quickly_and_never_too_long _________",
        "before": [
          {
            "path": "chatmon/offline.py",
            "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/offline.py",
            "sha256": "4e0176a4c8e745928680ee879ed1b3af699f82bcef8d07ae20842f7d25d60479"
          }
        ],
        "after": [
          {
            "path": "chatmon/offline.py",
            "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-07-past-longest",
      "acceptance": [
        "M5-07.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-07-past-longest in a temporary copy (tests/drills/run.py): green, then chatmon/reminders.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/phrases/en.json",
          "sha256": "03c9900891775478e4810607d004bb88c055417af0a3e714a8fe7a39dd2d05ea"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "c0f5d57588cd79ac8f825afb729a17b2079d7618163eaad587d418164ffa93c1"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "e598820b921a97c21ea9e531943362f2de50681d310dde8d1556768963c8b552"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "a4924383b46b88e2781817b2223027fe0674c9495981d87eef6ad419edbfecc7"
        }
      ],
      "scope_sha256": "de21efa2658565ee8e553a9525477fad6ae2a46c06f2ce51e415982054e27f26",
      "red": {
        "mutation": "'if due is None or not 0 < due.timestamp() - now.timestamp() <= LONGEST:' -> 'if due is None:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_reminders_time_is_always_ahead_and_never_too_far",
        "observed_diagnostic": "___________ test_a_reminders_time_is_always_ahead_and_never_too_far ___________",
        "before": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "54be9cf2ccee9351ee0f5279e4444f920d1229a366603f0a3436af4a7f1bff87"
          }
        ],
        "after": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-07-in-by-wall-clock",
      "acceptance": [
        "M5-07.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-07-in-by-wall-clock in a temporary copy (tests/drills/run.py): green, then chatmon/reminders.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/localefmt.py",
          "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
        },
        {
          "path": "chatmon/phrases/en.json",
          "sha256": "03c9900891775478e4810607d004bb88c055417af0a3e714a8fe7a39dd2d05ea"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
          "path": "tests/test_localefmt.py",
          "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "c0f5d57588cd79ac8f825afb729a17b2079d7618163eaad587d418164ffa93c1"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "e598820b921a97c21ea9e531943362f2de50681d310dde8d1556768963c8b552"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "a4924383b46b88e2781817b2223027fe0674c9495981d87eef6ad419edbfecc7"
        }
      ],
      "scope_sha256": "de21efa2658565ee8e553a9525477fad6ae2a46c06f2ce51e415982054e27f26",
      "red": {
        "mutation": "'return _at(start + seconds, now), None' -> 'return now + timedelta(seconds=seconds), None'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_in_is_that_many_seconds_of_real_time",
        "observed_diagnostic": "__________________ test_in_is_that_many_seconds_of_real_time __________________",
        "before": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "b387b62b9a1d042acd4694b50c2da5dabb18a80f87c8294254c804f5ad606e63"
          }
        ],
        "after": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-08-working-first",
      "acceptance": [
        "M5-08.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-08-working-first in a temporary copy (tests/drills/run.py): green, then chatmon/offline.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
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
          "path": "tests/test_offline.py",
          "sha256": "c0f5d57588cd79ac8f825afb729a17b2079d7618163eaad587d418164ffa93c1"
        }
      ],
      "scope_sha256": "bc194f5be934ed6c766115393200fa6895b62f8408f29073cdf5d96c8e57e0f3",
      "red": {
        "mutation": "'_STATE_ORDER = {\"needs-you\": 0, \"working\": 1}' -> '_STATE_ORDER = {\"needs-you\": 1, \"working\": 0}'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_agents_at_a_glance",
        "observed_diagnostic": "___________________________ test_agents_at_a_glance ___________________________",
        "before": [
          {
            "path": "chatmon/offline.py",
            "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/offline.py",
            "sha256": "d4bda42ec18b1a9d6b2edcf01df01dd599b38a168e3c9b9ec070e57ce3e8b59a"
          }
        ],
        "after": [
          {
            "path": "chatmon/offline.py",
            "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M5-08-span-off-by-one",
      "acceptance": [
        "M5-08.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m5/drill-spec.json",
        "--log",
        "docs/delivery/reports/m5/drills.log",
        "--python",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
      ],
      "method": "Red drill M5-08-span-off-by-one in a temporary copy (tests/drills/run.py): green, then chatmon/offline.py mutated once and the named test failed with pytest's tests-failed exit, then the original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "PyQt6": "6.11.0",
          "ruff": "0.17.4",
          "hypothesis": "6.170.15",
          "tzdata": "2026.6"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m5/drills.log",
        "sha256": "c7fb46177010b318d16da11fe52fe2440a3b29089b27ba099b53946e4bee81c0"
      },
      "inputs": [
        {
          "path": "chatmon/offline.py",
          "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
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
          "path": "tests/test_offline.py",
          "sha256": "c0f5d57588cd79ac8f825afb729a17b2079d7618163eaad587d418164ffa93c1"
        }
      ],
      "scope_sha256": "bc194f5be934ed6c766115393200fa6895b62f8408f29073cdf5d96c8e57e0f3",
      "red": {
        "mutation": "'    if s < 3600:\\n        return f\"{s // 60} min\"' -> '    if s <= 3600:\\n        return f\"{s // 60} min\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_spans",
        "observed_diagnostic": "____________________________ test_spans[3600-1 h] _____________________________",
        "before": [
          {
            "path": "chatmon/offline.py",
            "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/offline.py",
            "sha256": "be9f70a90e1b468f147050b57764abcf9060746aac73a3a51ea8a6753ef9a9e4"
          }
        ],
        "after": [
          {
            "path": "chatmon/offline.py",
            "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
          }
        ]
      },
      "reason": null
    }
  ],
  "checkpoint": {
    "scope_sha256": "ac4cdc210a7c5810f7c2e290fdbe91d872e83b497977a96614b66837709d2f11",
    "inputs": [
      {
        "path": "chatmon/localefmt.py",
        "sha256": "63ae9268fce086a90995f6e49ade895524767f93981f56c05f6375de6a4974af"
      },
      {
        "path": "chatmon/offline.py",
        "sha256": "db3de0ad74819c9543c74e46be50479fb3fd40e1ff3bc886dc6215c3bed98ed1"
      },
      {
        "path": "chatmon/phrases/en.json",
        "sha256": "03c9900891775478e4810607d004bb88c055417af0a3e714a8fe7a39dd2d05ea"
      },
      {
        "path": "chatmon/reminders.py",
        "sha256": "7bbf2d4f8ab6dcf40e002bb15c348d47613db49c307aa5524f6e5c526b0638c0"
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
        "path": "tests/test_localefmt.py",
        "sha256": "d7ee1f223fdaf0051522b0fb024e3a66e3d706e2e53142e861a3f0401fdd0a5d"
      },
      {
        "path": "tests/test_offline.py",
        "sha256": "c0f5d57588cd79ac8f825afb729a17b2079d7618163eaad587d418164ffa93c1"
      },
      {
        "path": "tests/test_parser_properties.py",
        "sha256": "e598820b921a97c21ea9e531943362f2de50681d310dde8d1556768963c8b552"
      },
      {
        "path": "tests/test_reminders.py",
        "sha256": "a4924383b46b88e2781817b2223027fe0674c9495981d87eef6ad419edbfecc7"
      }
    ],
    "environment": {
      "platform": "windows",
      "tools": {
        "python": "3.14.10",
        "pytest": "9.2.0",
        "PyQt6": "6.11.0",
        "ruff": "0.17.4",
        "hypothesis": "6.170.15",
        "tzdata": "2026.6"
      }
    },
    "verified_tasks": [
      "T1-locale",
      "T2-parse",
      "T3-book",
      "T4-phrases",
      "T5-agents",
      "T6-properties"
    ],
    "pending_operations": [],
    "next_action": "Hand back to the coordinator: merge wave1/m5, then M6A adds the phrases/*.json package-data glob and the hypothesis/tzdata test dependencies, and M7 wires the reminder contract, explain(), help_text(), command() and agents_report() into app.py, cli.py and the settings.",
    "source_revision": "ec26a84"
  }
}
```
