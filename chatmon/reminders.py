"""Reminders, timers, focus sessions and break nudges, and the plain-English ways people ask for them: "remind me
in 20m to stretch", "remind me friday at 3pm to call Sam", "remind me every weekday at 9 to stand up", "timer 10 min".

Times are worked out in two ways, on purpose:

- "in 2 hours" is two hours of real time: the moment now plus 7,200 seconds, whatever the wall clock does in
  between. A daylight-saving change meanwhile moves the clock, not the reminder.
- "at 3pm", "friday", "dec 3" and "every monday at 9" are times on the wall clock: 3 PM is 3 PM on that day,
  on either side of a change.

`now` is a datetime: naive for the computer's own time zone (what the app passes), or aware, with a zone that knows
its daylight-saving rules (zoneinfo).

Words for a day or a time that can't all be placed ("friday tomorrow", "next week", "on 3/4", "feb 30") make an
*ambiguous* result rather than a guess: a reminder at the wrong time is worse than a question.
"""

from __future__ import annotations

import math
import re
import time as _time
import uuid
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, time, timedelta, tzinfo

from . import localefmt

_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "ten": 10,
    "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "half an": 0.5, "half a": 0.5,
}
# Ten years: the furthest ahead a reminder, timer or focus may be. Much further, the date can't be shown
# (Windows' clock stops at the year 3000) or even worked out.
LONGEST = 10 * 366 * 24 * 3600
DAY = 86400
_NUMBER = r"\d+(?:\.\d+)?"
_WORD = r"half an?|an?|one|two|three|four|five|ten|fifteen|twenty|thirty|forty|fifty"
_UNIT = r"seconds?|secs?|minutes?|mins?|hours?|hrs?|hr|days?|weeks?|wks?|[smhdw]"
# A word amount needs a space before its unit, so "and" is never "an d(ay)".
_PART = rf"(?:(?<![\d.]){_NUMBER}\s*|(?<![a-z])(?:{_WORD})\s+)(?:{_UNIT})(?![a-z])"
_PART_RE = re.compile(rf"(?:(?<![\d.])(?P<number>{_NUMBER})\s*|(?<![a-z])(?P<word>{_WORD})\s+)(?P<unit>{_UNIT})(?![a-z])", re.I)
_DURATIONS = rf"{_PART}(?:\s*(?:,|and)?\s*{_PART})*"
_IN_RE = re.compile(rf"\bin\s+(?P<d>{_DURATIONS})", re.I)
_LEADING_RE = re.compile(rf"^\s*(?:for\s+)?(?P<d>{_DURATIONS}|\d+)", re.I)
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": DAY, "w": 7 * DAY}

# -- the words for days and times

_B, _E = r"(?<![\w'])", r"(?![\w'])"  # word edges, where "tomorrow's meeting" isn't "tomorrow"
_FULL_DAYS = {name.lower(): i for i, name in enumerate(localefmt.WEEKDAYS)}
_SHORT_DAYS = {"mon": 0, "tue": 1, "tues": 1, "wed": 2, "thu": 3, "thur": 3, "thurs": 3, "fri": 4, "sat": 5, "sun": 6}
_DAYS = {**_FULL_DAYS, **_SHORT_DAYS}
_SHY = {"wed", "sat", "sun"}  # words of their own too ("put on sun cream"): days only as "on sun at 2pm", "next sat"
_SHY_AFTER_TEXT = r"\s*(?:$|[,.;!?]|(?:at|by|to|for|that|about|morning|afternoon|evening|night)\b|\d)"
_SHY_AFTER = re.compile(_SHY_AFTER_TEXT, re.I)
_SHORT_NAMES = "|".join([*(d for d in _SHORT_DAYS if d not in _SHY), *(f"{d}(?={_SHY_AFTER_TEXT})" for d in sorted(_SHY))])
_DAY_WORDS = "|".join(sorted(_DAYS, key=len, reverse=True))
_MONTH_NUMBERS = {name.lower(): i for i, name in enumerate(localefmt.MONTHS, 1)}
_MONTH_NUMBERS.update({name[:3]: i for name, i in list(_MONTH_NUMBERS.items())})
_MONTH_NUMBERS["sept"] = 9
_MONTH_WORDS = "|".join(sorted(_MONTH_NUMBERS, key=len, reverse=True))
_RULE_CODES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

# What part of the day a word means: its usual hour, and whether an hour said with it is AM or PM.
_DAY_PARTS = {"morning": (9, "a"), "afternoon": (15, "p"), "evening": (18, "p"), "night": (20, "p")}
DEFAULT_HOUR = 9  # a day without a time: "tomorrow", "friday", "every day"

_EVERY_RE = re.compile(
    rf"{_B}(?:(?P<daily>daily|(?:every|each)\s+day)"
    rf"|(?P<weekdays>(?:every|each)\s+weekday|(?:on\s+)?weekdays)"
    rf"|(?:every|each)\s+(?P<part>morning|afternoon|evening|night)"
    rf"|(?:every|each)\s+(?P<day>{_DAY_WORDS})s?){_E}",
    re.I,
)
_REL_RE = re.compile(rf"{_B}(?:on\s+)?(?:the\s+)?(?P<rel>day\s+after\s+tomorrow|tomorrow|today|tonight){_E}", re.I)
_ISO_RE = re.compile(rf"{_B}(?:on\s+)?(?P<y>\d{{4}})-(?P<m>\d{{1,2}})-(?P<d>\d{{1,2}}){_E}", re.I)
_MONTHDAY_RE = re.compile(
    rf"{_B}(?:on\s+)?(?:the\s+)?(?:(?P<m1>{_MONTH_WORDS})\.?\s+(?P<d1>\d{{1,2}})(?:st|nd|rd|th)?"
    rf"|(?P<d2>\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?(?P<m2>{_MONTH_WORDS})\.?)(?:,?\s+(?P<y>\d{{4}}))?{_E}",
    re.I,
)
_WEEKDAY_RE = re.compile(rf"{_B}(?:(?P<on>on)\s+)?(?:(?P<which>this|next|coming)\s+)?(?P<day>{_DAY_WORDS}){_E}", re.I)
_DAY_PART_RE = re.compile(rf"{_B}(?:(?P<this>this)\s+|in\s+the\s+|at\s+)?(?P<part>morning|afternoon|evening|night){_E}", re.I)
_CLOCK_RE = re.compile(
    r"(?<![\w:./-])(?P<at>(?:at|by)\s+)?"
    r"(?:(?P<word>noon|midday|midnight)|(?P<h>\d{1,2})(?::(?P<min>\d{2}))?\s*(?P<ap>[ap]\.?m\.?)?)"
    r"(?![\w:])",
    re.I,
)
# Words about a day or a time that are still there once the rest is understood: a second date ("friday
# tomorrow"), or one this doesn't know how to place ("next week", "every 2 hours", "on 3/4", "in 3 months").
_LEFTOVER_RE = re.compile(
    rf"{_B}(?:(?:{'|'.join(_FULL_DAYS)})s?|(?:on|this|next|every)\s+(?:{_SHORT_NAMES})"
    rf"|today|tonight|tomorrow|yesterday|noon|midday|midnight"
    rf"|(?:next|last|this)\s+(?:week|month|year|weekend)"
    rf"|(?:every|each)\s+(?:\d+(?:\s*(?:{_UNIT}|months?|years?))?|other|second|week|month|year|hour|minute|weekend|fortnight|{_UNIT})"
    rf"|(?:{_MONTH_WORDS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?|\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:{_MONTH_WORDS})"
    rf"|\d{{4}}-\d{{1,2}}-\d{{1,2}}|(?:on|by|until)\s+\d{{1,2}}/\d{{1,2}}(?:/\d{{2,4}})?|\d{{1,2}}/\d{{1,2}}/\d{{2,4}}"
    rf"|(?:at|by)\s+\d{{1,2}}(?::\d{{2}})?(?:\s*[ap]\.?m\.?)?|\d{{1,2}}:\d{{2}}|\d{{1,2}}\s*[ap]\.?m\.?"
    rf"|in\s+(?:a|an|\d+)\s+(?:months?|years?)){_E}",
    re.I,
)


def seconds_in(text: str) -> float:
    """Total seconds in a phrase like "1 hour and 30 minutes" or "1h30m"."""
    total = 0.0
    for m in _PART_RE.finditer(text):
        value = float(m.group("number")) if m.group("number") else _WORDS[" ".join(m.group("word").lower().split())]
        total += value * _UNIT_SECONDS[m.group("unit")[0].lower()]
    return total


def _cut(text: str, m: re.Match) -> str:
    return " ".join((text[: m.start()] + " " + text[m.end() :]).split())


# -- moments: real time and wall-clock time


def _at(seconds: float, like: datetime) -> datetime:
    """The moment `seconds` after the epoch, on the wall clock `like` is on (naive: the computer's own zone)."""
    return datetime.fromtimestamp(seconds, like.tzinfo) if like.tzinfo else datetime.fromtimestamp(seconds)


def _on_wall(day: date, hour: int, minute: int, like: datetime) -> datetime:
    """That day's hour and minute on the wall clock `like` is on. A time a spring-forward change skips becomes
    the moment it would have been (2:30 becomes 3:30); a time an autumn change repeats is its first."""
    wall = datetime.combine(day, time(hour, minute), tzinfo=like.tzinfo)
    return _at(wall.timestamp(), like)


def _local(seconds: float, tz: tzinfo | None) -> datetime:
    return datetime.fromtimestamp(seconds, tz) if tz else datetime.fromtimestamp(seconds)


# -- repeating reminders: "daily@09:00", "weekdays@09:00", "mon@09:00"

_RULE_RE = re.compile(r"(daily|weekdays|mon|tue|wed|thu|fri|sat|sun)@([01]\d|2[0-3]):([0-5]\d)")


def _rule(rule: str) -> tuple[tuple[int, ...], int, int]:
    """A repeat rule's weekdays (Monday is 0), hour and minute. ValueError for anything else."""
    m = _RULE_RE.fullmatch(rule) if isinstance(rule, str) else None
    if not m:
        raise ValueError(f"not a repeat rule: {rule!r}")
    days = {"daily": tuple(range(7)), "weekdays": tuple(range(5))}.get(m.group(1)) or (_RULE_CODES.index(m.group(1)),)
    return days, int(m.group(2)), int(m.group(3))


def next_time(rule: str, after: float, tz: tzinfo | None = None) -> float:
    """When a repeating reminder next falls, strictly after the moment `after`, on the wall clock of `tz` (the
    computer's own zone when None). Within eight days there's always one."""
    days, hour, minute = _rule(rule)
    start = _local(after, tz)
    moments = []
    for k in range(8):
        day = start.date() + timedelta(days=k)
        if day.weekday() in days:
            moment = _on_wall(day, hour, minute, start).timestamp()
            if moment > after:
                moments.append(moment)
    return min(moments)


def describe_repeat(rule: str) -> str:
    """"every day at 9:00 AM", "every weekday at 9:00 AM", "every Monday at 9:00 AM"."""
    days, hour, minute = _rule(rule)
    at = localefmt.time_of_day(time(hour, minute))
    if len(days) == 7:
        return f"every day at {at}"
    if len(days) == 5:
        return f"every weekday at {at}"
    return f"every {localefmt.WEEKDAYS[days[0]]} at {at}"


# -- reading when


@dataclass(frozen=True)
class When:
    """What the time words in a phrase mean. `due` is None when they're ambiguous, and `ambiguous` holds them."""

    due: datetime | None
    rest: str  # the phrase with its time words taken out
    repeat: str | None = None  # a repeat rule, for "every …"
    ambiguous: str = ""


def _hour(h: int, ap: str) -> int:
    """An hour with "a" or "p" said (or meant, by "in the morning" or "tonight")."""
    if ap == "p" and h < 12:
        return h + 12
    if ap == "a" and h == 12:
        return 0
    return h


def _waking(h: int) -> int:
    """A bare hour on a day still to come: during the day, as people mean "friday at 3" (3 PM) or "at 9" (9 AM)."""
    return h + 12 if 1 <= h <= 6 else h


def _a_day(m: re.Match, text: str) -> bool:
    """Whether a weekday's name is meant as one: a short name that's a word of its own too needs "on", "this" or
    "next" before it, and a time or the end after it."""
    if m.group("day").lower() not in _SHY:
        return True
    return bool(m.group("on") or m.group("which")) and bool(_SHY_AFTER.match(text, m.end()))


class _Words:
    """A phrase as it's read: what's left of it, and the time words taken out of it so far."""

    def __init__(self, text: str):
        self.text, self.rest, self.seen = text, text, []

    def take(self, pattern: re.Pattern, wanted=lambda m, rest: True) -> re.Match | None:
        """The first match of `pattern` that's wanted, taken out of what's left."""
        m = next((c for c in pattern.finditer(self.rest) if wanted(c, self.rest)), None)
        if m:
            self.seen.append(m.group(0).strip())
            self.rest = _cut(self.rest, m)
        return m

    def said(self, more: list[str]) -> str:
        """The time words taken out, and `more`, in the order they were said."""
        return " ".join(sorted(self.seen + more, key=lambda w: self.text.lower().find(w.lower())))


def _a_time(m: re.Match, rest: str) -> bool:
    """A number is a time only with "at", minutes, AM or PM: "buy 3 apples" has none."""
    return bool(m.group("at") or m.group("min") or m.group("ap") or m.group("word"))


def _take_in(words: _Words) -> tuple[float | None, bool]:
    """Seconds of "in 2 hours", and whether they're whole days ("in 2 days", which a time of day can go with)."""
    m = words.take(_IN_RE)
    if not m:
        return None, False
    seconds = seconds_in(m.group("d"))
    return seconds, seconds % DAY == 0 and all(p.group("unit")[0].lower() in "dw" for p in _PART_RE.finditer(m.group("d")))


def _take_day(words: _Words, now: datetime) -> tuple | None:
    """The first day said: ("day", date, tonight?), ("monthday", month, day, year or None), or ("weekday", weekday,
    after today?)."""
    if m := words.take(_REL_RE):
        rel = " ".join(m.group("rel").lower().split())
        return "day", now.date() + timedelta(days={"today": 0, "tonight": 0, "tomorrow": 1}.get(rel, 2)), rel == "tonight"
    if m := words.take(_ISO_RE):
        return "monthday", int(m.group("m")), int(m.group("d")), int(m.group("y"))
    if m := words.take(_MONTHDAY_RE):
        month = _MONTH_NUMBERS[(m.group("m1") or m.group("m2")).lower()]
        return "monthday", month, int(m.group("d1") or m.group("d2")), int(m.group("y")) if m.group("y") else None
    if m := words.take(_WEEKDAY_RE, _a_day):
        return "weekday", _DAYS[m.group("day").lower()], (m.group("which") or "").lower() == "next"
    return None


def _take_clock(words: _Words, part: str | None) -> tuple[tuple[int, int, str] | None, bool]:
    """The time of day said, as (hour, minute, how), how being "bare" (an hour of 12 or less with AM or PM not
    said), "midnight" or ""; and whether it's one that can't be (25:00, 13pm)."""
    m = words.take(_CLOCK_RE, _a_time)
    if not m:
        return None, False
    word = (m.group("word") or "").lower()
    if word:
        return ((0, 0, "midnight") if word == "midnight" else (12, 0, "")), False
    h, minute = int(m.group("h")), int(m.group("min") or 0)
    ap = (m.group("ap") or "")[:1].lower()
    if h > 23 or minute > 59 or (ap and not 1 <= h <= 12):
        return None, True
    if ap:
        return (_hour(h, ap), minute, ""), False
    if part and 1 <= h <= 12:
        return (_hour(h, _DAY_PARTS[part][1]), minute, ""), False
    return (h, minute, "bare" if 1 <= h <= 12 and not m.group("h").startswith("0") else ""), False


def parse_when(text: str, now: datetime) -> When | None:
    """When the text means, or None if it says no time at all."""
    words = _Words(text)
    every = words.take(_EVERY_RE)
    seconds, whole_days = _take_in(words)
    if seconds is not None and not 0 < seconds <= LONGEST:
        return None
    dated = _take_day(words, now)
    part = every.group("part").lower() if every and every.group("part") else None
    if m := words.take(_DAY_PART_RE):
        part = m.group("part").lower()
        dated = dated or (("day", now.date(), False) if m.group("this") else None)
    if dated and dated[0] == "day" and dated[2]:  # "tonight"
        part = part or "night"
    clock, bad = _take_clock(words, part)
    leftovers = [m.group(0) for m in _LEFTOVER_RE.finditer(words.rest)]
    if not (words.seen or leftovers or bad):
        return None
    timed = dated is not None or every is not None or (clock is not None and not whole_days)
    if bad or leftovers or (seconds and timed) or (every is not None and dated is not None):
        return When(None, words.rest, ambiguous=words.said(leftovers))
    due, repeat = _resolve(now, every, seconds, dated, part, clock)
    if due is None or not 0 < due.timestamp() - now.timestamp() <= LONGEST:  # a day that's gone, or can't be
        return When(None, words.rest, ambiguous=words.said(leftovers))
    return When(due, words.rest, repeat)


def _resolve(
    now: datetime, every: re.Match | None, seconds: float | None, dated: tuple | None, part: str | None, clock: tuple[int, int, str] | None
) -> tuple[datetime | None, str | None]:
    """The moment the understood words mean (None for a day that's gone or doesn't exist), and the repeat rule."""
    start = now.timestamp()
    if seconds and clock is None:
        return _at(start + seconds, now), None
    if seconds:  # "in 2 days at 3pm": a day, by the wall clock
        dated = ("day", now.date() + timedelta(days=round(seconds / DAY)), False)
    default = (_DAY_PARTS[part][0], 0, "") if part else None
    if every is not None:
        h, minute, how = clock or default or (DEFAULT_HOUR, 0, "")
        h = _waking(h) if how == "bare" else h
        code = "daily" if every.group("daily") or every.group("part") else "weekdays" if every.group("weekdays") else _RULE_CODES[_DAYS[every.group("day").lower()]]
        rule = f"{code}@{h:02d}:{minute:02d}"
        return _at(next_time(rule, start, now.tzinfo), now), rule

    def at(day: date, h: int, minute: int, how: str) -> datetime | None:
        """The day's time, or None if it's gone. A bare hour with no day, or today, is whichever of h and h+12
        comes next; on a day still to come it's during the day (_waking)."""
        if how == "midnight":  # a day's midnight is the end of it ("friday at midnight"); with no day, the next one
            moments = [_on_wall(day + timedelta(days=1) if dated else day, 0, 0, now)]
        else:
            hours = (h, (h + 12) % 24) if how == "bare" and (dated is None or day == now.date()) else ((_waking(h) if how == "bare" else h),)
            moments = [_on_wall(day, hour, minute, now) for hour in hours]
        return min((t for t in moments if t.timestamp() > start), default=None, key=lambda t: t.timestamp())

    h, minute, how = clock or default or (DEFAULT_HOUR, 0, "")
    if dated is None:  # a time with no day: its next one
        return (at(now.date(), h, minute, how) or at(now.date() + timedelta(days=1), h, minute, how)), None
    if dated[0] == "day":
        return at(dated[1], h, minute, how), None
    if dated[0] == "weekday":
        _, weekday, after_today = dated
        first = 1 if after_today else 0
        days = (now.date() + timedelta(days=k) for k in range(first, first + 8))
        return next(filter(None, (at(d, h, minute, how) for d in days if d.weekday() == weekday)), None), None
    _, month, day, year = dated
    if year is not None and not 0 <= year - now.year <= LONGEST // (366 * DAY):
        return None, None  # gone, or further off than a reminder may be (and than some clocks can count)
    for y in [year] if year else range(now.year, now.year + 9):
        try:
            moment = at(date(y, month, day), h, minute, how)
        except ValueError:  # February 30, or the 29th in a year that hasn't one
            continue
        if moment is not None:
            return moment, None
    return None, None


def _what(text: str) -> str:
    text = re.sub(r"^\s*(?:to|that|about|of|:|,)\s+", "", text.strip(), flags=re.I)
    return text.strip(" .!?,:")


@dataclass
class Command:
    kind: str  # "reminder", "timer", "focus", or "unclear" (a reminder whose time is missing or can't be told)
    due: datetime | None = None
    text: str = ""
    minutes: float | None = None
    repeat: str | None = None  # a repeating reminder's rule (see next_time)
    ambiguous: str = ""  # an unclear reminder's time words that couldn't be placed


def parse_command(text: str, now: datetime) -> Command | None:
    """A reminder, timer or focus request typed in the ask box, if it is one."""
    t = text.strip()
    m = re.match(r"^(?:please\s+)?remind me\b[\s,:]*(?P<rest>.*)$", t, re.I | re.S)
    if m:
        when = parse_when(m.group("rest"), now)
        if when is None:
            return Command("unclear", text=_what(m.group("rest")))
        if when.due is None:
            return Command("unclear", text=_what(when.rest), ambiguous=when.ambiguous)
        return Command("reminder", when.due, _what(when.rest) or "Reminder", repeat=when.repeat)
    m = re.match(r"^(?:set\s+(?:a\s+)?)?timer\b\s*(?P<rest>.*)$", t, re.I)
    if m:
        lead = _LEADING_RE.match(m.group("rest"))
        if lead:
            d = lead.group("d")
            secs = float(d) * 60 if d.isdigit() else seconds_in(d)
            if 0 < secs <= LONGEST:
                rest = m.group("rest")[lead.end() :]
                return Command("timer", _at(now.timestamp() + secs, now), _what(re.sub(r"^\s*for\s+", "", rest)) or "Timer")
        return None
    m = re.match(r"^(?:start\s+(?:a\s+)?)?focus(?:\s+(?:session|time|mode))?\b\s*(?P<rest>.*)$", t, re.I)
    if m:
        rest = m.group("rest").strip()
        if not rest:
            return Command("focus")
        lead = _LEADING_RE.match(rest)
        if lead:
            d = lead.group("d")
            minutes = float(d) if d.isdigit() else seconds_in(d) / 60
            if 0 < minutes * 60 <= LONGEST:
                return Command("focus", minutes=minutes)
    return None


def explain(command: Command, markdown: bool = True) -> str:
    """What to say about a reminder whose time is missing or can't be told: Markdown, or plain for a terminal."""
    words = command.ambiguous
    if re.search(r"\d{1,2}/\d{1,2}", words):
        text = (f'I can\'t tell which day "{words}" is: day and month come in either order. '
                "Write the month's name (*apr 3*), or the year first (*2027-04-03*).")
    elif words:
        text = (f'I couldn\'t tell when "{words}" is. Try one day and one time, like *friday at 3pm*, '
                "*dec 3 at 9am*, *in 2 hours* or *every weekday at 9*.")
    else:
        text = "When should I remind you? Try *remind me in 20m to stretch* or *remind me at 3pm to call Sam*."
    return text if markdown else text.replace("*", "")


def clock(when: datetime | time) -> str:
    """"3:04 PM" or "15:04", as the person's locale writes it."""
    return localefmt.time_of_day(when)


def describe(due: float, now: float, tz: tzinfo | None = None) -> str:
    """"in 5 min", "at 3:30 PM", "tomorrow at 9:00 AM", "on Fri Dec 25 at 3:00 PM", "was due at 2:00 PM"..."""
    delta = due - now
    if 0 <= delta < 3600:
        return f"in {max(1, round(delta / 60))} min"
    try:
        d, n = _local(due, tz), _local(now, tz)
    except (OSError, OverflowError, ValueError):  # one saved before there was a limit, past what the clock can show
        return "a long way off"
    if d.date() == n.date():
        said = f"at {clock(d)}"
    elif d.date() == n.date() + timedelta(days=1):
        said = f"tomorrow at {clock(d)}"
    else:
        said = f"on {localefmt.short_day(d.date())} at {clock(d)}"
    return f"was due {said}" if delta < 0 else said


# -- snoozing

DEFAULT_SNOOZE_MINUTES = 10  # a reminder's own snooze, until the person sets theirs
_SNOOZES = (5, 15, 60)  # minutes, besides tomorrow morning


def _minutes_label(minutes: float) -> str:
    if minutes >= 60 and minutes % 60 == 0:
        hours = int(minutes // 60)
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return f"{minutes:g} min"


def snooze_choices(now: float, minutes: float = DEFAULT_SNOOZE_MINUTES, tz: tzinfo | None = None) -> list[tuple[str, float]]:
    """How long a fired reminder can be put off, as (label, until): the person's own snooze first, then 5 min,
    15 min, 1 hour and tomorrow at 9 AM (on the wall clock, so a daylight-saving change doesn't move it)."""
    choices = [(_minutes_label(m), now + m * 60) for m in dict.fromkeys((minutes, *_SNOOZES)) if 0 < m * 60 <= LONGEST]
    today = _local(now, tz)
    tomorrow = _on_wall(today.date() + timedelta(days=1), DEFAULT_HOUR, 0, today)
    choices.append((f"Tomorrow at {clock(tomorrow)}", tomorrow.timestamp()))
    return choices


# -- the book


@dataclass
class Reminder:
    due: float
    text: str
    kind: str = "reminder"  # "reminder", "timer" or "focus"
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    repeat: str | None = None  # a repeat rule (see next_time), for one that comes back
    fired: bool = False  # it came due and hasn't been done or snoozed yet


_LATER_FIELDS = {"repeat": None, "fired": False}  # saved only when set, so a book saved before them reads back the same
_KEEP = object()


class ReminderBook:
    """The reminders, timers and focus sessions set, saved as a list of plain dicts in state.json.

    A reminder that comes due stays in the book, marked fired, until it's acknowledged (done) or snoozed: so
    one that fired while nobody was looking, or just before Chatmon quit, is still there to show. `due(now)`
    lists them; `fire(now)` lists just the ones that came due since the last look. A repeating one moves on to
    its next time when it's acknowledged. `tz` is the wall clock repeats follow: the computer's own when None."""

    def __init__(self, items: list[Reminder] | None = None, tz: tzinfo | None = None):
        self.items: list[Reminder] = list(items or [])
        self.tz = tz

    @classmethod
    def from_list(cls, data: list, tz: tzinfo | None = None) -> ReminderBook:
        items = []
        for entry in data or []:
            try:
                reminder = Reminder(float(entry["due"]), str(entry["text"]), str(entry.get("kind", "reminder")), str(entry.get("id") or uuid.uuid4().hex[:8]))
            except (AttributeError, KeyError, TypeError, ValueError):
                continue
            if not math.isfinite(reminder.due):
                continue
            repeat = entry.get("repeat")
            if isinstance(repeat, str) and _RULE_RE.fullmatch(repeat):
                reminder.repeat = repeat
            reminder.fired = entry.get("fired") is True
            items.append(reminder)
        return cls(items, tz)

    def to_list(self) -> list[dict]:
        return [{k: v for k, v in asdict(r).items() if k not in _LATER_FIELDS or v != _LATER_FIELDS[k]} for r in self.items]

    def get(self, rid: str) -> Reminder | None:
        return next((r for r in self.items if r.id == rid), None)

    def add(self, due: float, text: str, kind: str = "reminder", repeat: str | None = None) -> Reminder:
        if repeat is not None:
            _rule(repeat)
        reminder = Reminder(due, text, kind, repeat=repeat)
        self.items.append(reminder)
        return reminder

    def cancel(self, rid: str) -> bool:
        before = len(self.items)
        self.items = [r for r in self.items if r.id != rid]
        return len(self.items) != before

    def due(self, now: float) -> list[Reminder]:
        """The reminders that have come due and haven't been done or snoozed, oldest first. They stay in the
        book, marked fired."""
        due = sorted((r for r in self.items if r.due <= now), key=lambda r: r.due)
        for r in due:
            r.fired = True
        return due

    def fire(self, now: float) -> list[Reminder]:
        """The reminders that came due since the last look (`due` or `fire`): the ones to tell about now."""
        fresh = [r for r in self.items if r.due <= now and not r.fired]
        self.due(now)
        return sorted(fresh, key=lambda r: r.due)

    def acknowledge(self, rid: str, now: float | None = None) -> bool:
        """Done with it: a one-off reminder goes, a repeating one moves on to its next time after now."""
        r = self.get(rid)
        if r is None:
            return False
        if r.repeat:
            r.due = next_time(r.repeat, max(_time.time() if now is None else now, r.due), self.tz)
            r.fired = False
        else:
            self.items.remove(r)
        return True

    def snooze(self, rid: str, until: float) -> bool:
        """Put it off until the moment `until` (see snooze_choices). A repeating one's later times stay as they were."""
        if not math.isfinite(until):
            raise ValueError("a snooze needs a time")
        r = self.get(rid)
        if r is None:
            return False
        r.due, r.fired = until, False
        return True

    def update(self, rid: str, text: str | None = None, when: float | None = None, repeat: object = _KEEP) -> bool:
        """Change what a reminder says, when it's due (a moment), or how it repeats (a rule, or None for never)."""
        r = self.get(rid)
        if r is None:
            return False
        if text is not None and not text.strip():
            raise ValueError("a reminder needs some words")
        if when is not None and not math.isfinite(when):
            raise ValueError("a reminder needs a time")
        if repeat is not _KEEP and repeat is not None:
            _rule(repeat)
        if text is not None:
            r.text = text.strip()
        if when is not None:
            r.due, r.fired = when, False
        if repeat is not _KEEP:
            r.repeat = repeat
        return True

    def pop_due(self, now: float) -> list[Reminder]:
        """The reminders due, taken out of the book: what the app used before `due` and `acknowledge`. A
        repeating one stays, moved on to its next time, and a copy of the one that fired is returned."""
        due = sorted((r for r in self.items if r.due <= now), key=lambda r: r.due)
        fired = [replace(r) for r in due]
        for r in due:
            if r.repeat:
                r.due, r.fired = next_time(r.repeat, now, self.tz), False
            else:
                self.items.remove(r)
        return fired

    def upcoming(self) -> list[Reminder]:
        return sorted(self.items, key=lambda r: r.due)

    def focus(self) -> Reminder | None:
        return next((r for r in self.items if r.kind == "focus"), None)


class BreakTracker:
    """Counts time at the screen and says when a break is due. Time away
    (locked screen, suspend) of five minutes or more counts as a break."""

    AWAY_IS_A_BREAK = 300

    def __init__(self, every_minutes: float, now: float):
        self.every = every_minutes * 60
        self.active_since = now
        self.snoozed_until = 0.0
        self.away_since: float | None = None

    def away(self, now: float) -> None:
        if self.away_since is None:
            self.away_since = now

    def back(self, now: float) -> None:
        if self.away_since is not None and now - self.away_since >= self.AWAY_IS_A_BREAK:
            self.took_break(now)
        self.away_since = None

    def took_break(self, now: float) -> None:
        self.active_since = now
        self.snoozed_until = 0.0

    def snooze(self, now: float, minutes: float) -> None:
        self.snoozed_until = now + minutes * 60

    def minutes_on(self, now: float) -> int:
        return int((now - self.active_since) // 60)

    def due(self, now: float) -> bool:
        return (
            self.every > 0
            and self.away_since is None
            and now - self.active_since >= self.every
            and now >= self.snoozed_until
        )
