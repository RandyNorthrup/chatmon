import json
import time
from datetime import date, datetime, timedelta

import pytest

from chatmon import localefmt
from chatmon.reminders import (
    LONGEST,
    BreakTracker,
    ReminderBook,
    describe,
    describe_repeat,
    explain,
    next_time,
    parse_command,
    parse_when,
    seconds_in,
    snooze_choices,
)

NOW = datetime(2026, 10, 31, 14, 0, 0)


@pytest.fixture(autouse=True)
def plain_english():
    """What's written here is checked in plain English, whatever the machine's locale (test_localefmt.py has the rest)."""
    localefmt.set_locale(None)
    yield
    localefmt.set_locale()


def zone(name):
    """A real time zone, with its daylight-saving rules (on Windows, from the tzdata package)."""
    zoneinfo = pytest.importorskip("zoneinfo")
    try:
        return zoneinfo.ZoneInfo(name)
    except zoneinfo.ZoneInfoNotFoundError:
        pytest.skip("no time-zone database here (pip install tzdata)")


@pytest.mark.parametrize(
    "text, seconds",
    [
        ("20m", 1200),
        ("20 minutes", 1200),
        ("1 hour and 30 minutes", 5400),
        ("1h30m", 5400),
        ("half an hour", 1800),
        ("an hour", 3600),
        ("90 secs", 90),
        ("2 days", 172800),
    ],
)
def test_seconds_in(text, seconds):
    assert seconds_in(text) == seconds


def test_months_are_not_minutes():
    assert seconds_in("5 months") == 0


@pytest.mark.parametrize(
    "text, due, what",
    [
        ("remind me in 20m to stretch", NOW + timedelta(minutes=20), "stretch"),
        ("remind me to call Sam in 2 hours", NOW + timedelta(hours=2), "call Sam"),
        ("remind me at 3pm to call Sam", NOW.replace(hour=15), "call Sam"),
        ("remind me at 15:30 about the build", NOW.replace(hour=15, minute=30), "the build"),
        ("remind me at 9am to water plants", NOW.replace(hour=9) + timedelta(days=1), "water plants"),
        ("remind me tomorrow at 8:15 am that it's trash day", NOW.replace(hour=8, minute=15) + timedelta(days=1), "it's trash day"),
        ("remind me at noon to eat", NOW.replace(hour=12) + timedelta(days=1), "eat"),
        ("Remind me tomorrow to renew the domain", (NOW + timedelta(days=1)).replace(hour=9), "renew the domain"),
    ],
)
def test_reminders(text, due, what):
    cmd = parse_command(text, NOW)
    assert cmd.kind == "reminder"
    assert cmd.due == due
    assert cmd.text == what


def test_reminder_without_a_time_is_unclear():
    assert parse_command("remind me to buy milk", NOW).kind == "unclear"


def test_plain_numbers_are_not_times():
    assert parse_when("buy 3 apples", NOW) is None


def test_timers():
    cmd = parse_command("timer 10 min for the pasta", NOW)
    assert (cmd.kind, cmd.due, cmd.text) == ("timer", NOW + timedelta(minutes=10), "the pasta")
    assert parse_command("set a timer for 5", NOW).due == NOW + timedelta(minutes=5)
    assert parse_command("timer", NOW) is None


def test_focus():
    assert parse_command("focus", NOW).minutes is None
    assert parse_command("focus 50", NOW).minutes == 50
    assert parse_command("start a focus session for 1 hour", NOW).minutes == 60


def test_questions_are_not_commands():
    assert parse_command("what is a closure in python?", NOW) is None
    assert parse_command("focused reading tips?", NOW) is None


def test_book_pops_due_in_order_and_round_trips():
    book = ReminderBook()
    b = book.add(200, "second")
    a = book.add(100, "first")
    book.add(900, "later", "focus")
    assert [r.text for r in book.pop_due(250)] == ["first", "second"]
    assert book.focus().text == "later"
    again = ReminderBook.from_list(book.to_list() + [{"bad": 1}])
    assert [r.text for r in again.upcoming()] == ["later"]
    assert not again.cancel(a.id) and not again.cancel(b.id)


def test_describe():
    now = NOW.timestamp()
    assert describe(now + 300, now) == "in 5 min"
    assert describe(now + 2 * 3600, now) == "at 4:00 PM"
    assert describe((NOW + timedelta(hours=20)).timestamp(), now) == "tomorrow at 10:00 AM"


def test_breaks():
    t = BreakTracker(60, now=0)
    assert not t.due(3599)
    assert t.due(3600)
    t.snooze(3600, 10)
    assert not t.due(3601) and t.due(3600 + 600)
    t.away(4000)
    assert not t.due(5000)
    t.back(4000 + 301)  # five minutes away counts as a break
    assert t.active_since == 4301 and not t.due(4400)


def test_short_time_away_is_not_a_break():
    t = BreakTracker(60, now=0)
    t.away(100)
    t.back(200)
    assert t.active_since == 0


def test_breaks_off():
    assert not BreakTracker(0, now=0).due(10**9)


def test_nothing_further_ahead_than_ten_years():
    """Windows can't show a date past the year 3000; much further, it can't even be worked out."""
    assert parse_when("in 400000 days to retire", NOW) is None
    assert parse_when("in 99999999999 days to retire", NOW) is None
    assert parse_command("timer 99999999999 days", NOW) is None
    assert parse_when("in 3650 days to check the time capsule", NOW) is not None


def test_a_reminder_saved_before_the_limit_still_shows():
    assert describe(1e18, NOW.timestamp()) == "a long way off"


# -- days, dates and hours (M5-02)

WEDNESDAY = datetime(2026, 10, 28, 10, 0)  # a Wednesday morning


@pytest.mark.parametrize(
    "text, due, what",
    [
        ("remind me friday at 3pm to call Sam", datetime(2026, 10, 30, 15, 0), "call Sam"),
        ("remind me to call Sam on Friday at 3pm", datetime(2026, 10, 30, 15, 0), "call Sam"),
        ("remind me wednesday at 4pm to x", datetime(2026, 10, 28, 16, 0), "x"),  # later today
        ("remind me wednesday at 9am to water plants", datetime(2026, 11, 4, 9, 0), "water plants"),  # today's has gone
        ("remind me next wed to pay rent", datetime(2026, 11, 4, 9, 0), "pay rent"),
        ("remind me next mon to pay rent", datetime(2026, 11, 2, 9, 0), "pay rent"),
        ("remind me on thursday to x", datetime(2026, 10, 29, 9, 0), "x"),
        ("remind me friday at 3 to x", datetime(2026, 10, 30, 15, 0), "x"),  # a bare hour on a day to come: in the day
        ("remind me dec 3 to renew the domain", datetime(2026, 12, 3, 9, 0), "renew the domain"),
        ("remind me on the 3rd of december at 9:30am to x", datetime(2026, 12, 3, 9, 30), "x"),
        ("remind me oct 1 to x", datetime(2027, 10, 1, 9, 0), "x"),  # this year's has gone
        ("remind me on 2026-12-03 at 15:30 to deploy", datetime(2026, 12, 3, 15, 30), "deploy"),
        ("remind me 2027-01-15 to file taxes", datetime(2027, 1, 15, 9, 0), "file taxes"),
        ("remind me tonight at 8 to x", datetime(2026, 10, 28, 20, 0), "x"),
        ("remind me tomorrow morning to x", datetime(2026, 10, 29, 9, 0), "x"),
        ("remind me to call Sam at 3 in the afternoon", datetime(2026, 10, 28, 15, 0), "call Sam"),
        ("remind me in 2 days at 3pm to x", datetime(2026, 10, 30, 15, 0), "x"),
        ("remind me to prepare for tomorrow's meeting at 3pm", datetime(2026, 10, 28, 15, 0), "prepare for tomorrow's meeting"),
        ("remind me to put on sun cream at 2pm", datetime(2026, 10, 28, 14, 0), "put on sun cream"),
        ("remind me on sun at 2pm to x", datetime(2026, 11, 1, 14, 0), "x"),
        ("remind me to water every plant at 9am", datetime(2026, 10, 29, 9, 0), "water every plant"),
        ("remind me to take 1/2 a pill at 9pm", datetime(2026, 10, 28, 21, 0), "take 1/2 a pill"),
        ("remind me to march at 4pm", datetime(2026, 10, 28, 16, 0), "march"),
    ],
)
def test_days_and_dates(text, due, what):
    cmd = parse_command(text, WEDNESDAY)
    assert (cmd.kind, cmd.due, cmd.text, cmd.repeat, cmd.ambiguous) == ("reminder", due, what, None, "")


@pytest.mark.parametrize(
    "said_at, text, due",
    [
        (datetime(2026, 10, 28, 14, 0), "remind me at 3 to x", datetime(2026, 10, 28, 15, 0)),  # 3 PM comes first
        (datetime(2026, 10, 28, 16, 0), "remind me at 3 to x", datetime(2026, 10, 29, 3, 0)),  # both gone today: 3 AM
        (datetime(2026, 10, 28, 1, 0), "remind me at 3 to x", datetime(2026, 10, 28, 3, 0)),
        (datetime(2026, 10, 28, 14, 0), "remind me at 1 to x", datetime(2026, 10, 29, 1, 0)),
        (datetime(2026, 10, 28, 11, 0), "remind me at 12 to x", datetime(2026, 10, 28, 12, 0)),
        (datetime(2026, 10, 28, 13, 0), "remind me at 12 to x", datetime(2026, 10, 29, 0, 0)),
        (datetime(2026, 10, 28, 14, 0), "remind me at 3:30 to x", datetime(2026, 10, 28, 15, 30)),
        (datetime(2026, 10, 28, 14, 0), "remind me at 03:30 to x", datetime(2026, 10, 29, 3, 30)),  # a leading zero: 24-hour
        (datetime(2026, 10, 28, 14, 0), "remind me at 15 to x", datetime(2026, 10, 28, 15, 0)),
    ],
)
def test_a_bare_hour_is_whichever_of_am_and_pm_comes_next(said_at, text, due):
    assert parse_command(text, said_at).due == due


@pytest.mark.parametrize(
    "text, words",
    [
        ("remind me friday tomorrow to x", "friday tomorrow"),
        ("remind me tomorrow at 3pm next mon to x", "tomorrow at 3pm next mon"),
        ("remind me at 3pm next week to x", "at 3pm next week"),
        ("remind me on 3/4 to pay rent", "on 3/4"),
        ("remind me every 2 hours to drink water", "every 2 hours"),
        ("remind me in 3 months to x", "in 3 months"),
        ("remind me in 2 hours at 3pm to x", "in 2 hours at 3pm"),
        ("remind me every monday tomorrow to x", "every monday tomorrow"),
        ("remind me on feb 30 to x", "on feb 30"),
        ("remind me today at 9am to x", "today at 9am"),  # gone already
        ("remind me on 2025-01-01 to x", "on 2025-01-01"),
        ("remind me at 3pm and at 5pm to x", "at 3pm at 5pm"),
        ("remind me at 25:00 to x", "at 25:00"),
    ],
)
def test_time_words_that_cant_all_be_placed_are_ambiguous(text, words):
    when = parse_when(text.removeprefix("remind me "), WEDNESDAY)
    assert (when.due, when.ambiguous) == (None, words)
    cmd = parse_command(text, WEDNESDAY)
    assert (cmd.kind, cmd.due, cmd.ambiguous) == ("unclear", None, words)


def test_what_to_say_about_an_unclear_reminder():
    assert explain(parse_command("remind me to buy milk", WEDNESDAY)).startswith("When should I remind you?")
    vague = explain(parse_command("remind me friday tomorrow to x", WEDNESDAY))
    assert '"friday tomorrow"' in vague and "*friday at 3pm*" in vague
    slashed = explain(parse_command("remind me on 3/4 to pay rent", WEDNESDAY), markdown=False)
    assert "either order" in slashed and "apr 3" in slashed and "*" not in slashed


# -- daylight saving, with a real zone's rules (M5-02)


def test_in_is_real_time_across_daylight_saving():
    ny = zone("America/New_York")
    spring = datetime(2026, 3, 8, 1, 30, tzinfo=ny)  # half an hour before the clock jumps to 3:00
    due = parse_command("remind me in 2 hours to stretch", spring).due
    assert due.timestamp() - spring.timestamp() == 7200
    assert (due.hour, due.minute) == (4, 30)
    autumn = datetime(2026, 11, 1, 0, 30, tzinfo=ny)  # the night the clock goes back from 2:00 to 1:00
    due = parse_command("remind me in 2 hours to stretch", autumn).due
    assert due.timestamp() - autumn.timestamp() == 7200
    assert (due.hour, due.minute, due.fold) == (1, 30, 1)  # the second 1:30
    assert parse_command("timer 90 min", spring).due.timestamp() - spring.timestamp() == 5400


def test_wall_clock_times_stay_on_the_wall_across_daylight_saving():
    ny = zone("America/New_York")
    saturday = datetime(2026, 3, 7, 10, 0, tzinfo=ny)
    due = parse_command("remind me tomorrow at 9am to x", saturday).due
    assert (due.date(), due.hour, due.minute) == (date(2026, 3, 8), 9, 0)
    assert due.timestamp() - saturday.timestamp() == 22 * 3600  # the night was an hour short
    gap = parse_command("remind me tomorrow at 2:30am to x", saturday).due
    assert (gap.hour, gap.minute) == (3, 30)  # there's no 2:30 that night: the moment it would have been
    first = datetime(2026, 11, 1, 1, 10, tzinfo=ny)  # the first 1:10 of the night the clock goes back
    assert parse_command("remind me at 1:30 to x", first).due.timestamp() - first.timestamp() == 20 * 60


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="the computer's own zone can be changed in a test only on Unix (time.tzset)")
def test_the_apps_own_local_time_is_real_time_across_daylight_saving(monkeypatch):
    """The app passes datetime.now(): naive, in the computer's own zone."""
    zone("America/New_York")
    monkeypatch.setenv("TZ", "America/New_York")
    time.tzset()
    try:
        spring = datetime(2026, 3, 8, 1, 30)
        due = parse_command("remind me in 2 hours to stretch", spring).due
        assert due.tzinfo is None and due == datetime(2026, 3, 8, 4, 30)
        assert due.timestamp() - spring.timestamp() == 7200
        assert parse_command("remind me tomorrow at 9am", datetime(2026, 3, 7, 10, 0)).due == datetime(2026, 3, 8, 9, 0)
    finally:
        monkeypatch.undo()
        time.tzset()


# -- repeating reminders (M5-03)


@pytest.mark.parametrize(
    "text, due, rule, what",
    [
        ("remind me every day at 9 to stand up", datetime(2026, 10, 29, 9, 0), "daily@09:00", "stand up"),
        ("remind me daily at 6pm to walk", datetime(2026, 10, 28, 18, 0), "daily@18:00", "walk"),
        ("remind me every weekday at 9 to stand up", datetime(2026, 10, 29, 9, 0), "weekdays@09:00", "stand up"),
        ("remind me every monday at 9 to take out the bins", datetime(2026, 11, 2, 9, 0), "mon@09:00", "take out the bins"),
        ("remind me every friday to send the report", datetime(2026, 10, 30, 9, 0), "fri@09:00", "send the report"),
        ("remind me every morning to stretch", datetime(2026, 10, 29, 9, 0), "daily@09:00", "stretch"),
        ("remind me on weekdays at 5:30pm to stop working", datetime(2026, 10, 28, 17, 30), "weekdays@17:30", "stop working"),
    ],
)
def test_repeating_reminders(text, due, rule, what):
    cmd = parse_command(text, WEDNESDAY)
    assert (cmd.kind, cmd.due, cmd.repeat, cmd.text) == ("reminder", due, rule, what)


def test_next_time_is_after_and_on_one_of_the_rules_days():
    friday = datetime(2026, 10, 30, 10, 0).timestamp()
    assert datetime.fromtimestamp(next_time("weekdays@09:00", friday)) == datetime(2026, 11, 2, 9, 0)  # no weekend
    assert datetime.fromtimestamp(next_time("fri@10:00", friday)) == datetime(2026, 11, 6, 10, 0)  # strictly after
    assert datetime.fromtimestamp(next_time("daily@10:01", friday)) == datetime(2026, 10, 30, 10, 1)
    with pytest.raises(ValueError):
        next_time("sometimes", friday)


def test_a_repeating_reminder_moves_on_when_done():
    book = ReminderBook()
    tuesday = datetime(2026, 10, 27, 9, 0).timestamp()
    r = book.add(tuesday, "stand up", repeat="weekdays@09:00")
    assert book.fire(tuesday + 60) == [r]
    friday = datetime(2026, 10, 30, 12, 0).timestamp()  # not done until Friday: still once, and still fired
    assert book.due(friday) == [r] and r.fired
    assert book.acknowledge(r.id, now=friday)
    assert datetime.fromtimestamp(r.due) == datetime(2026, 11, 2, 9, 0) and not r.fired
    assert book.get(r.id) is r


def test_a_daily_reminder_keeps_its_hour_across_daylight_saving():
    ny = zone("America/New_York")
    book = ReminderBook(tz=ny)
    saturday = datetime(2026, 3, 7, 9, 0, tzinfo=ny).timestamp()
    r = book.add(saturday, "pills", repeat="daily@09:00")
    book.fire(saturday)
    book.acknowledge(r.id, now=saturday + 60)
    assert datetime.fromtimestamp(r.due, ny) == datetime(2026, 3, 8, 9, 0, tzinfo=ny)
    assert r.due - saturday == 23 * 3600


def test_the_old_pop_due_moves_a_repeating_reminder_on_and_takes_a_one_off_out():
    book = ReminderBook()
    t = datetime(2026, 10, 28, 9, 0).timestamp()
    rep = book.add(t, "stand up", repeat="daily@09:00")
    book.add(t + 1, "once")
    assert [(f.text, f.due) for f in book.pop_due(t + 60)] == [("stand up", t), ("once", t + 1)]
    assert book.items == [rep] and datetime.fromtimestamp(rep.due) == datetime(2026, 10, 29, 9, 0)


# -- a fired reminder stays until it's seen to (M5-01)


def test_a_fired_reminder_stays_until_done_or_snoozed():
    book = ReminderBook()
    r = book.add(100, "call Sam")
    later = book.add(900, "later")
    assert book.due(50) == [] and book.fire(50) == []
    assert book.fire(150) == [r]
    assert book.fire(160) == []  # told about once
    assert book.due(170) == [r] and r.fired  # and still there, marked fired
    assert book.upcoming() == [r, later]
    assert book.snooze(r.id, 500) and not r.fired and book.due(400) == []
    assert book.due(600) == [r]
    assert book.acknowledge(r.id) and book.get(r.id) is None
    assert not book.acknowledge(r.id) and not book.snooze("nope", 1)
    assert book.upcoming() == [later]


def test_unacknowledged_reminders_come_back_at_start():
    book = ReminderBook()
    r = book.add(100, "call Sam")
    book.add(10**9, "later")
    book.fire(200)
    again = ReminderBook.from_list(json.loads(json.dumps(book.to_list())))  # as state.json keeps it
    assert again.fire(300) == []  # told about before the restart: not news again...
    assert [(x.id, x.text, x.fired) for x in again.due(300)] == [(r.id, "call Sam", True)]  # ...but still there to show


def test_reminders_saved_before_repeats_read_back_unchanged():
    saved = [
        {"due": 1800000000.0, "text": "call Sam", "kind": "reminder", "id": "ab12cd34"},
        {"due": 1800000600.0, "text": "pasta", "kind": "timer", "id": "ef56ab78"},
    ]
    book = ReminderBook.from_list(saved)
    assert book.to_list() == saved
    assert [(r.repeat, r.fired) for r in book.items] == [(None, False), (None, False)]


def test_broken_saved_reminders_are_skipped():
    book = ReminderBook.from_list([{"due": "nan", "text": "x"}, {"due": 5, "text": "ok", "repeat": "every day", "fired": "yes"}, "junk", None, {"text": "no due"}])
    assert [(r.text, r.repeat, r.fired) for r in book.items] == [("ok", None, False)]


# -- snoozing and editing (M5-04)


def test_snooze_offers_its_own_setting_then_5_15_60_minutes_and_tomorrow_morning():
    now = datetime(2026, 10, 28, 16, 20).timestamp()
    choices = snooze_choices(now)
    assert [label for label, _ in choices] == ["10 min", "5 min", "15 min", "1 hour", "Tomorrow at 9:00 AM"]
    assert [until - now for _, until in choices[:4]] == [600, 300, 900, 3600]
    assert datetime.fromtimestamp(choices[4][1]) == datetime(2026, 10, 29, 9, 0)
    assert [label for label, _ in snooze_choices(now, minutes=15)] == ["15 min", "5 min", "1 hour", "Tomorrow at 9:00 AM"]
    assert snooze_choices(now, minutes=120)[0] == ("2 hours", now + 7200)


def test_snoozing_until_tomorrow_morning_keeps_9_am_across_daylight_saving():
    ny = zone("America/New_York")
    evening = datetime(2026, 3, 7, 22, 0, tzinfo=ny).timestamp()
    label, until = snooze_choices(evening, tz=ny)[-1]
    assert label == "Tomorrow at 9:00 AM"
    assert datetime.fromtimestamp(until, ny) == datetime(2026, 3, 8, 9, 0, tzinfo=ny)
    assert until - evening == 10 * 3600


def test_a_reminder_can_be_edited():
    book = ReminderBook()
    r = book.add(100, "call Sam")
    book.fire(200)
    assert book.update(r.id, text="  call Sam back ")
    assert r.text == "call Sam back" and r.fired  # new words alone leave it fired
    assert book.update(r.id, when=5000) and r.due == 5000 and not r.fired
    assert book.update(r.id, repeat="mon@09:00") and r.repeat == "mon@09:00"
    assert book.update(r.id, repeat=None) and r.repeat is None
    assert book.update(r.id) and (r.text, r.due) == ("call Sam back", 5000)
    assert not book.update("nope", text="x")
    for bad in ({"text": "  "}, {"when": float("nan")}, {"repeat": "every day"}, {"text": "fine", "when": float("inf")}):
        with pytest.raises(ValueError):
            book.update(r.id, **bad)
    assert (r.text, r.due, r.repeat) == ("call Sam back", 5000, None)  # a refused edit changes nothing
    with pytest.raises(ValueError):
        book.snooze(r.id, float("inf"))
    with pytest.raises(ValueError):
        book.add(1, "x", repeat="sometimes")


def test_describe_one_already_due_and_one_that_repeats():
    now = NOW.timestamp()
    assert describe(now - 2 * 3600, now) == "was due at 12:00 PM"
    assert describe((NOW - timedelta(days=3)).timestamp(), now) == "was due on Wed Oct 28 at 2:00 PM"
    assert describe_repeat("daily@09:00") == "every day at 9:00 AM"
    assert describe_repeat("weekdays@17:30") == "every weekday at 5:30 PM"
    assert describe_repeat("mon@09:00") == "every Monday at 9:00 AM"


def test_parsed_times_are_always_ahead_and_never_too_far():
    for text in ("remind me in 3650 days to x", "remind me dec 31 to x", "remind me every sunday at midnight to x", "remind me at midnight"):
        cmd = parse_command(text, WEDNESDAY)
        assert 0 < cmd.due.timestamp() - WEDNESDAY.timestamp() <= LONGEST
    assert parse_command("remind me on 2040-01-01 to x", WEDNESDAY).kind == "unclear"  # past ten years
