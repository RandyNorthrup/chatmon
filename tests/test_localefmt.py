"""Times and dates in the person's own way of writing them (localefmt.py): Qt's locale when Qt is loaded, plain
English where it isn't, and the replies of reminders and offline answers written through it."""

import os
import subprocess
import sys
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from PyQt6.QtCore import QLocale

from chatmon import localefmt, reminders

ROOT = Path(__file__).resolve().parent.parent
XMAS = date(2026, 12, 25)  # a Friday
TEA = datetime(2026, 12, 25, 15, 4)


@contextmanager
def pinned(locale):
    localefmt.set_locale(locale)
    try:
        yield
    finally:
        localefmt.set_locale()


def locale(language, country):
    return QLocale(language, country)


GB = locale(QLocale.Language.English, QLocale.Country.UnitedKingdom)
US = locale(QLocale.Language.English, QLocale.Country.UnitedStates)
DE = locale(QLocale.Language.German, QLocale.Country.Germany)


def test_british_english_writes_24_hour_times_and_day_first_dates():
    with pinned(GB):
        assert localefmt.time_of_day(TEA) == "15:04"
        assert localefmt.long_date(XMAS) == "Friday, 25 December 2026"
        assert localefmt.short_day(XMAS) == "Fri, 25 Dec"


def test_german_writes_german_names():
    with pinned(DE):
        assert localefmt.time_of_day(TEA) == "15:04"
        assert localefmt.long_date(XMAS) == "Freitag, 25. Dezember 2026"
        assert localefmt.short_day(XMAS) == "Fr., 25. Dez."
        assert localefmt.date_and_time(TEA) == "Freitag, 25. Dezember 2026, 15:04"
        assert localefmt.language() == "de_DE"


def test_us_english_keeps_12_hour_times():
    with pinned(US):
        # Qt's own data puts a narrow no-break space before "PM", as the US convention now has it.
        assert localefmt.time_of_day(TEA).replace(" ", " ") == "3:04 PM"
        assert localefmt.short_day(XMAS) == "Fri, Dec 25"


def test_no_locale_at_all_is_plain_english_not_qts_c_look():
    with pinned(QLocale.c()):
        assert localefmt.time_of_day(TEA) == "3:04 PM"
        assert localefmt.long_date(XMAS) == "Friday, December 25, 2026"
        assert localefmt.language() == "en"
    with pinned(None):
        assert localefmt.short_day(XMAS) == "Fri Dec 25"
        assert localefmt.language() == "en"


def test_left_alone_it_follows_qts_default_locale():
    before = QLocale()
    QLocale.setDefault(DE)
    try:
        assert localefmt.long_date(XMAS) == "Freitag, 25. Dezember 2026"
    finally:
        QLocale.setDefault(before)


def test_without_qt_it_writes_plain_english_and_reads_the_language_from_the_environment():
    """The command line doesn't load Qt to write a time; nor does a parser's test."""
    script = (
        "import sys\n"
        "from datetime import date, datetime\n"
        "from chatmon import localefmt\n"
        "print(localefmt.time_of_day(datetime(2026, 12, 25, 15, 4)))\n"
        "print(localefmt.long_date(date(2026, 12, 25)))\n"
        "print(localefmt.short_day(date(2026, 12, 25)))\n"
        "print(localefmt.language())\n"
        "print('PyQt6.QtCore' in sys.modules)\n"
    )
    env = {k: v for k, v in os.environ.items() if k not in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")}
    env.update(PYTHONPATH=str(ROOT), LANG="pt_BR.UTF-8")
    out = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env, capture_output=True, text=True, timeout=60, check=True)
    assert out.stdout.splitlines() == ["3:04 PM", "Friday, December 25, 2026", "Fri Dec 25", "pt_BR", "False"]


def test_reminders_write_times_the_locales_way():
    now = datetime(2026, 12, 23, 9, 0)
    with pinned(GB):
        assert reminders.describe(datetime(2026, 12, 23, 16, 30).timestamp(), now.timestamp()) == "at 16:30"
        assert reminders.describe(TEA.timestamp(), now.timestamp()) == "on Fri, 25 Dec at 15:04"
    with pinned(DE):
        assert reminders.describe_repeat("mon@09:00") == "every Monday at 09:00"
