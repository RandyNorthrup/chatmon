"""Property tests for the parsers (Hypothesis): whatever is typed, the calculator answers or says it can't, and
quickly; and a reminder's time is always ahead of now and never past the longest, in zones with daylight saving.

They run the same examples every time (a derandomized profile, no example database), a modest number of them, each
within a deadline: fast enough for every test run, and never a failure that can't be repeated.
"""

import math
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest

pytest.importorskip("hypothesis", reason="the property tests need Hypothesis (pip install hypothesis)")

from hypothesis import HealthCheck, example, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from chatmon import offline  # noqa: E402
from chatmon.reminders import LONGEST, parse_when  # noqa: E402

settings.register_profile(
    "chatmon",
    max_examples=150,
    deadline=timedelta(seconds=1),
    derandomize=True,
    database=None,  # nothing written into the working tree
    print_blob=False,
    # Generating nested sums is the slow part, not the code under test; on a busy machine it trips this check.
    suppress_health_check=[HealthCheck.too_slow],
)
PROFILE = settings(settings.get_profile("chatmon"))
NOW = datetime(2026, 11, 11, 15, 4)

# -- the calculator

_ATOMS = st.one_of(
    st.integers(-10**6, 10**6).map(str),
    st.integers(0, 10**30).map(str),
    st.floats(allow_nan=False, allow_infinity=False).map(repr),
    st.sampled_from(["pi", "e", "tau", "π", "1e308", "1e309", "0", "0.5", "999", "1,000"]),
)
_FUNCTIONS = ["sqrt", "sin", "log", "ln", "exp", "factorial", "round", "floor", "ceil", "abs", "log10", "acos"]
_OPERATORS = ["+", "-", "*", "/", "//", "%", "**", "^", "×", "÷"]
SUMS = st.recursive(
    _ATOMS,
    lambda inner: st.one_of(
        st.tuples(inner, st.sampled_from(_OPERATORS), inner).map(" ".join),
        st.tuples(st.sampled_from(_FUNCTIONS), inner).map(lambda t: f"{t[0]}({t[1]})"),
        st.tuples(inner, inner).map(lambda t: f"round({t[0]}, {t[1]})"),
        inner.map(lambda x: f"({x})"),
        inner.map(lambda x: f"-{x}"),
        st.tuples(inner, inner).map(lambda t: f"{t[0]}% of {t[1]}"),
    ),
    max_leaves=12,
)
TYPED = st.text(alphabet="0123456789 .+-*/%^()×÷,πpiesqrtlogfacorund", max_size=120)


def _calculates_or_says_it_cant(text: str) -> None:
    started = time.perf_counter()
    try:
        value = offline.calculate(text)
    except (ValueError, OverflowError):  # can't be worked out, or too big: what it may say
        value = None
    assert time.perf_counter() - started < 0.5
    if value is not None:
        assert type(value) in (int, float)
        if isinstance(value, int):
            assert len(str(abs(value))) <= offline._MAX_DIGITS
        else:
            assert math.isfinite(value)
    assert offline.answer(text, NOW) is None or isinstance(offline.answer(text, NOW), str)  # and never raises


@PROFILE
@given(SUMS)
@example("10**400")
@example("10**399 * 10")
@example("1e308 % of 1e308")
@example("9**99999")
@example("2**2**2**2**2**2")
@example("factorial(170)*factorial(170)*factorial(170)")
@example("round(1, -10**300)")
def test_a_sum_is_answered_or_refused_quickly_and_never_too_long(text):
    _calculates_or_says_it_cant(text)


@PROFILE
@given(TYPED)
def test_whatever_is_typed_the_calculator_answers_or_refuses_quickly(text):
    _calculates_or_says_it_cant(text)


# -- when a reminder is due, in zones whose clocks change


def _zones() -> dict[str, ZoneInfo]:
    names = ("America/New_York", "Europe/London", "Australia/Lord_Howe", "America/Santiago", "Asia/Kolkata")
    try:
        return {name: ZoneInfo(name) for name in names}
    except ZoneInfoNotFoundError:
        return {}


ZONES = _zones()
needs_zones = pytest.mark.skipif(not ZONES, reason="no time-zone database here (pip install tzdata)")
ZONE_NAMES = st.sampled_from(sorted(ZONES) or ["UTC"])
WALLS = st.datetimes(min_value=datetime(2000, 1, 1), max_value=datetime(2040, 12, 31))
_DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_UNITS = {"seconds": 1, "minutes": 60, "hours": 3600, "days": 86400, "weeks": 7 * 86400}
_PIECES = st.one_of(
    st.sampled_from(["today", "tonight", "tomorrow", "day after tomorrow", "dec 3", "3rd of march", "feb 29", "2027-03-14",
                     "march 31st", "nov 1", "next mon", "on sun", "this saturday", "friday", "next week", "on 3/4"]),
    st.builds(lambda h, m, ap: f"at {h}" + (f":{m:02d}" if m is not None else "") + ap,
              st.integers(0, 25), st.none() | st.integers(0, 61), st.sampled_from(["", "am", "pm", " p.m."])),
    st.sampled_from(["at noon", "at midnight", "in the morning", "this evening", "at 2:30", "at 1:30", "at 0:30"]),
    st.builds(lambda n, unit: f"in {n} {unit}", st.integers(0, 6000), st.sampled_from(sorted(_UNITS))),
    st.sampled_from(["every day", "daily", "every weekday", "every monday", "every sunday", "every morning", "on weekdays"]),
    st.sampled_from(["to call Sam", "buy milk", "that it's trash day", "about the 3 apples"]),
)
PHRASES = st.lists(_PIECES, min_size=1, max_size=4).map(" ".join)
HOURS_24 = st.integers(0, 23).filter(lambda h: not 10 <= h <= 12)  # 00-09 with their zero, and 13-23


def _real(zone_name: str, wall: datetime) -> datetime:
    """A moment that happens in the zone: a wall time a spring-forward change skips becomes the one after it."""
    tz = ZONES[zone_name]
    return datetime.fromtimestamp(wall.replace(tzinfo=tz).timestamp(), tz)


@needs_zones
@PROFILE
@given(ZONE_NAMES, WALLS, PHRASES)
@example("America/New_York", datetime(2026, 3, 8, 1, 30), "in 2 hours")
@example("America/New_York", datetime(2026, 11, 1, 1, 10), "at 1:30")
@example("America/New_York", datetime(2026, 3, 7, 23, 0), "tomorrow at 2:30am")
@example("America/Santiago", datetime(2026, 9, 5, 23, 30), "at midnight")  # Santiago skips its midnight in September
@example("Australia/Lord_Howe", datetime(2026, 10, 4, 1, 50), "in 30 minutes")  # a half-hour change
@example("Europe/London", datetime(2026, 10, 25, 1, 59), "every day at 1:30")
@example("Asia/Kolkata", datetime(2040, 12, 31, 23, 59), "in 3650 days")
def test_a_reminders_time_is_always_ahead_and_never_too_far(zone_name, wall, text):
    now = _real(zone_name, wall)
    when = parse_when(text, now)
    if when is not None and when.due is not None:
        assert when.due.tzinfo is now.tzinfo
        assert 0 < when.due.timestamp() - now.timestamp() <= LONGEST


@needs_zones
@PROFILE
@given(ZONE_NAMES, WALLS, st.integers(1, 6000), st.sampled_from(sorted(_UNITS)))
@example("America/New_York", datetime(2026, 3, 8, 1, 30), 2, "hours")
@example("America/New_York", datetime(2026, 10, 31, 12, 0), 1, "days")  # a day of 25 hours: still 24 of them
def test_in_is_that_many_seconds_of_real_time(zone_name, wall, n, unit):
    now = _real(zone_name, wall)
    when = parse_when(f"in {n} {unit}", now)
    seconds = n * _UNITS[unit]
    if seconds > LONGEST:
        assert when is None
    else:
        assert abs(when.due.timestamp() - now.timestamp() - seconds) < 1e-3


@needs_zones
@PROFILE
@given(ZONE_NAMES, WALLS, HOURS_24, st.integers(0, 59), st.sampled_from(["", "every ", "on "]), st.sampled_from(_DAY_NAMES))
@example("America/New_York", datetime(2026, 3, 7, 10, 0), 2, 30, "on ", "sunday")
@example("America/New_York", datetime(2026, 10, 31, 23, 0), 1, 30, "every ", "sunday")
def test_a_wall_clock_time_is_kept_on_the_wall(zone_name, wall, hour, minute, how, day):
    """"at 09:30", "on friday at 21:30", "every friday at 09:30": that time on the clock, unless the clock skips it
    that day, and on that day of the week. (10:00 to 12:59 are left out: written so, they're a bare hour, whichever
    of AM and PM comes next.)"""
    now = _real(zone_name, wall)
    text = f"{how}{day} at {hour:02d}:{minute:02d}" if how else f"at {hour:02d}:{minute:02d}"
    when = parse_when(text, now)
    due = when.due
    assert 0 < due.timestamp() - now.timestamp() <= 8 * 86400
    asked = due.replace(hour=hour, minute=minute, fold=0)
    skipped = _real(zone_name, asked.replace(tzinfo=None)).replace(tzinfo=None) != asked.replace(tzinfo=None)
    assert (due.hour, due.minute) == (hour, minute) or skipped
    if how:
        assert asked.weekday() == _DAY_NAMES.index(day)
        assert (when.repeat is not None) == (how == "every ")
