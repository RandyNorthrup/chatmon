"""Times and dates written the person's own way: "3:04 PM" or "15:04", "Friday, December 25, 2026" or
"Freitag, 25. Dezember 2026".

Formats come from Qt's `QLocale` (the system's, or whatever `QLocale.setDefault` chose) whenever Qt is already
loaded, which it is in the running app. Where it isn't, such as `chatmon` on the command line, or a test of a pure
parser, they fall back to plain English: a command doesn't load Qt just to write a time. Qt's "C" locale (no
locale set at all, as on a bare server) also gets plain English, rather than its 24-hour, year-first look.

The plain English never goes through `strftime`'s `%a` or `%B`: Qt sets the C library's locale from the system as
it starts, so those would give a German month inside an English sentence.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import date, datetime, time

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")

_SYSTEM = object()  # follow Qt's default locale whenever Qt is loaded
_chosen: object = _SYSTEM


def set_locale(locale: object = _SYSTEM) -> None:
    """Which locale to write in: a `QLocale`, None for plain English, or nothing to follow Qt's default again.
    Tests pin one, so what they expect doesn't depend on the machine they run on."""
    global _chosen
    _chosen = locale


def _locale():
    """The QLocale to write in, or None for plain English."""
    if _chosen is None:
        return None
    qtcore = sys.modules.get("PyQt6.QtCore")
    if _chosen is _SYSTEM:
        if qtcore is None:
            return None
        locale = qtcore.QLocale()
    else:
        locale = _chosen
    if qtcore is not None and locale.language() == qtcore.QLocale.Language.C:
        return None
    return locale


def language() -> str:
    """The language to answer in, as "en", "de_DE" or the like: Qt's when it's loaded, otherwise the
    environment's (LANGUAGE, LC_ALL, LC_MESSAGES, LANG), otherwise English."""
    if _chosen is None:
        return "en"
    locale = _locale()
    if locale is not None:
        return locale.name()
    if _chosen is not _SYSTEM:  # a pinned locale with no language of its own ("C")
        return "en"
    for name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(name, "").split(":")[0]
        code = re.match(r"[A-Za-z]{2,3}(?:_[A-Za-z]{2})?", value)
        if code and code.group(0).upper() not in ("C", "POSIX"):
            return code.group(0)
    return "en"


def _qtime(when: datetime | time):
    return sys.modules["PyQt6.QtCore"].QTime(when.hour, when.minute)


def _qdate(day: date):
    return sys.modules["PyQt6.QtCore"].QDate(day.year, day.month, day.day)


def time_of_day(when: datetime | time) -> str:
    """"3:04 PM", "15:04": hours and minutes, the locale's short way."""
    locale = _locale()
    if locale is None:
        return f"{(when.hour % 12) or 12}:{when.minute:02d} {'AM' if when.hour < 12 else 'PM'}"
    return locale.toString(_qtime(when), type(locale).FormatType.ShortFormat)


def long_date(day: date) -> str:
    """"Friday, December 25, 2026", "Freitag, 25. Dezember 2026"."""
    locale = _locale()
    if locale is None:
        return f"{WEEKDAYS[day.weekday()]}, {MONTHS[day.month - 1]} {day.day}, {day.year}"
    return locale.toString(_qdate(day), type(locale).FormatType.LongFormat)


# A year in a long-date pattern, with the separators and quoted words around it ("yyyy", ", yyyy", " 'de' yyyy",
# "yyyy年"): taken out for a date this year or next, where the year goes without saying.
_YEAR = re.compile(r"[\s,./-]*(?:'[^']*'\s*)?y+(?:\s*'[^']*')?[年년]?[\s,./-]*")


def _short_pattern(long_pattern: str) -> str | None:
    """The locale's long-date pattern without its year, and with short day and month names: "dddd, MMMM d, yyyy"
    becomes "ddd, MMM d", and "dddd d MMMM yyyy" becomes "ddd d MMM". None if what's left isn't a date."""
    pattern = _YEAR.sub(" ", long_pattern).strip(" ,/-")
    pattern = re.sub(r"(?<!d)dddd(?!d)", "ddd", pattern)
    pattern = re.sub(r"(?<!M)MMMM(?!M)", "MMM", pattern)
    pattern = re.sub(r"\s+", " ", pattern)
    return pattern if "d" in pattern and "M" in pattern else None


def short_day(day: date) -> str:
    """A day without its year, short: "Fri Dec 25" in plain English, "Fri, Dec 25" or "Fr., 25. Dez." in a locale."""
    locale = _locale()
    if locale is None:
        return f"{WEEKDAYS[day.weekday()][:3]} {MONTHS[day.month - 1][:3]} {day.day}"
    formats = type(locale).FormatType
    pattern = _short_pattern(locale.dateFormat(formats.LongFormat))
    if pattern is None:
        return locale.toString(_qdate(day), formats.ShortFormat)
    return locale.toString(_qdate(day), pattern)


def date_and_time(when: datetime) -> str:
    """"Friday, December 25, 2026, 3:04 PM": a moment worth its whole date, such as when a chat began."""
    return f"{long_date(when.date())}, {time_of_day(when)}"
