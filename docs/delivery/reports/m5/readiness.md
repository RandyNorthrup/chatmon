# M5 readiness review: reminders, offline answers and locale

Reviewed 2026-11-14 against `docs/delivery/ASSESSMENT.md` (M5-01 to M5-08), the roadmap's owner decisions, file
ownership and the M0/M5 reminder contract (`docs/delivery/ROADMAP.md`), and `pyproject.toml` (ruff, pytest). This
reviews the requirements, not the code. A first draft of the code was written while scanning, before this review
was saved. Each decision below was then checked against that draft, and the draft was changed where the two
disagreed.

## Findings re-checked

Every M5 finding without a ✓ was re-checked before any change. The re-check ran the code at `5346385`, and its
output is in `findings-recheck.log`.

| ID | Real? | Evidence |
|---|---|---|
| M5-01 ✓ | Yes | `pop_due(200)` returns the reminder and leaves the book empty. |
| M5-02 | Yes, all three | "friday at 3pm" said on a Wednesday is due that Wednesday at 15:00, with "friday" left in the text. "at 3" said at 2 PM gives 03:00 the next day. "in 2 hours" at 01:30 on New York's spring-forward day gives 1.0 real hours. |
| M5-03 | Yes | "every monday at 9" makes a one-off reminder at the next 9:00, with the text "every monday to …". |
| M5-04 | Yes | `app.py` snoozes by `[breaks] snooze_minutes`, and the book has no snooze or edit. |
| M5-05 | Yes | `reminders.clock`, `offline._clock` and `chats.py:239` write 12-hour English. `offline._day` and `chats.py:62/242` use `strftime` `%a %b %A %B`, which follow the C library's locale. Qt sets that locale from the system as it starts, so a German desktop gets a German month in an English sentence. |
| M5-06 | Yes | The phrases are in code: in `offline.py` (`when`, `chance`, `parse_kept`) and in `app.py` (`_local`, `HELP_ALL`). |
| M5-07 | Yes | No Hypothesis tests exist, and Hypothesis isn't a test dependency. |
| M5-08 | Yes | There's no *agents* command. The app keeps `self.agents: {source: (state, since)}` on the monotonic clock. |

`context.py` is M5's file, but no finding names it, so it stays unchanged.

## Ambiguities and the decisions taken

1. **When a fired reminder comes back (M5-01).** The contract's `due(now)` returns fired, unacknowledged reminders
   without removing them. Called on every tick, it would make the app alert about the same reminder again and
   again. Decisions:
   - `fire(now)` returns only the reminders that came due since the last look. It is what the app alerts about.
   - `due(now)` lists every fired, unacknowledged reminder. It is what the app shows again at start.
   - `fired` is saved, so a restart doesn't tell about a reminder twice.
2. **Rescheduled "when they fire" against staying fired until done (M5-03 against M5-01).** These conflict for a
   repeating reminder. Decision: a fired repeating reminder stays fired, listed once however many of its times
   pass, and moves on to its next time when it's acknowledged. The old `pop_due` path, which the app uses until M7,
   moves it on at once when it fires, so a repeat isn't lost before M7.
3. **"next mon" (M5-02).** English is split on this. Decision: "next <day>" is the first such day after today,
   never today. "<day>", "on <day>" and "this <day>" are the first such day from today, today only if the time is
   still ahead.
4. **A bare hour (M5-02).** The finding says h or h+12, whichever comes next. That settles a time with no day, or
   one today. For a day still to come, both are ahead and "next" doesn't decide. Decision: there, hours 1 to 6 are
   PM and 7 to 12 keep their reading, so "friday at 3" is 3 PM and "friday at 9" is 9 AM. h:mm without AM or PM
   follows the same rule. A leading zero ("03:30") or an hour of 13 or more is the 24-hour clock.
5. **What "ambiguous" covers (M5-02).** Decision: an ambiguous result has no due time and names the time words.
   It covers:
   - leftover date words (a second day, "next week", "every 2 hours", "in 3 months");
   - a numeric date ("on 3/4"), whose day/month order depends on the locale;
   - time words that conflict ("in 2 hours at 3pm", "every monday tomorrow");
   - days that are gone or can't exist ("today at 9am" said at 10, "feb 30", "on 2025-01-01");
   - a date past ten years.

   An "in …" span past ten years keeps its existing result: no time at all. `parse_command` returns these as kind
   "unclear" with `ambiguous` set, so today's `app.py`, which has no case for a new kind, asks "When should I
   remind you?" instead of failing. `explain()` gives the specific message for M7.
6. **Real time against wall time (M5-02, M5-03, M5-04).** "in …" is the epoch plus seconds. Days, dates, clock
   times, repeats and "tomorrow at 9 AM" are wall-clock times in the zone `now` is in:
   - A naive `now` (what the app passes) is in the computer's zone.
   - An aware `now` with a zoneinfo zone is in that zone (the tests use real zones).
   - A wall time a spring-forward change skips becomes the moment it would have been (2:30 becomes 3:30).
   - A wall time an autumn change repeats is its first.
7. **"Reminders have their own snooze setting" (M5-04).** The settings and their window belong to M1B (`settings.py`)
   and M7 (`settingswin.py`). Decision: M5 gives `snooze_choices(now, minutes)` and `DEFAULT_SNOOZE_MINUTES = 10`,
   the same as today's break snooze, so nothing changes until the setting exists. The `[reminders] snooze_minutes`
   key is an integration note.
8. **Which locale (M5-05).** Decisions:
   - Qt's default `QLocale` when Qt is loaded, so M8 can choose a language with `QLocale.setDefault`.
   - Plain English when Qt isn't loaded: the CLI, and pure parsers.
   - Plain English in Qt's "C" locale, whose 24-hour, year-first look reads as broken.
   - `chats.py` belongs to M1B, so its three places are an integration note.
9. **What "phrases" are (M5-06).** Decision: the data holds:
   - the fixed phrases of every offline command, including `_local`'s, which M0 is moving to a command table;
   - the templates with a number or text ("delete note {n}", "note: {text}");
   - the words that make a sentence a question;
   - the help, as sections.

   The grammars stay English in code: reminders' times, units, sums, dice and "days until". Translating those is
   out of M5's scope, since only English ships. On a conflict, English phrases win, so English always means what
   it means. A missing or broken translation is ignored. A missing `en.json` raises, as a missing sprite manifest
   does, because it means a broken package.
10. **The agents report (M5-08).** Its input is the app's own `{source: (state, since)}`, with `now` on the same
    clock. It has a Markdown form for the *agents* command and a plain form for `chatmon status`.
11. **Property tests (M5-07).** CI installs only `PyQt6 psutil pytest` today. Decisions:
    - The property module skips with a reason when Hypothesis is missing.
    - Its zone tests skip when no zone database exists (Windows without `tzdata`).
    - Adding both to the test dependencies is an integration note for M6A.
    - The profile is derandomized, with no example database, 150 examples, a 1 s deadline, and only the `too_slow`
      health check suppressed.

## Failure behaviour

| Input | Result |
|---|---|
| A repeat rule that isn't one | `ValueError` |
| An empty edit text | `ValueError` |
| A non-finite time to snooze or edit to | `ValueError` |
| A refused edit | Changes nothing |
| An unknown id | `False` |
| A broken saved entry | Skipped |
| An unknown saved repeat | Dropped, keeping the reminder |
| A broken translation file | English only |
| A language name that isn't a file name ("../en") | Ignored |
| A calculator input | Answers, or raises only `ValueError` or `OverflowError` |

## Terminology

| Term | Meaning |
|---|---|
| Fired | Came due, and not yet done or snoozed. |
| Acknowledged | Done. A one-off reminder goes; a repeating one moves on. |
| Snoozed | Put off to a given moment, which clears fired. |
| Rule | `daily@HH:MM`, `weekdays@HH:MM` or `mon@HH:MM` … `sun@HH:MM`. |
| Ambiguous | Time words with no due time. |

## Scope and ownership

- **Changed:** `chatmon/reminders.py`, `chatmon/offline.py`, new `chatmon/localefmt.py`, new
  `chatmon/phrases/en.json`, and their tests.
- **Unchanged:** `chatmon/context.py`.
- **Not touched:** `app.py` (M0, then M7), `cli.py` (M0), `settings.py` and `chats.py` (M1B), `settingswin.py`,
  `pyproject.toml` (M6A), `README.md`, `changelog.md`, `__init__.py`. Each needed change elsewhere is an
  integration note in the plan.
- **No new runtime dependency.** Hypothesis and tzdata are test-only, as the roadmap allows.

## Coverage

Every requirement has at least one acceptance criterion with behavior and red proof. Each criterion has one owning
task, and the task dependencies follow the imports:

- `localefmt` comes first.
- The parser comes before the book, which uses `next_time`.
- The phrases come before the property tests.

The plan's ledger holds the mapping.

## Result

The requirements are ready to verify, with the decisions above. No owner decision is needed: each choice follows
the assessment's "Done when" or the roadmap's contracts. Where those are silent (points 2, 3 and 4 above), the
choice keeps today's behavior or follows common usage, and is recorded.
