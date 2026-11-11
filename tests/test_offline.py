"""What Chatmon answers without any AI, and, as much, what it leaves for the AI: a question that only
mentions a timer, a note or a sum is never taken for one."""

import random
import time
from datetime import datetime

import pytest

from chatmon import offline

NOW = datetime(2026, 11, 11, 15, 4)  # a Wednesday


@pytest.mark.parametrize(
    "question",
    [
        "what is love",
        "what is e",
        "what is the capital of France?",
        "how do I set a timer in python",
        "explain 2+2 in binary",
        "choose rust or go for the backend",
        "choose between rust or go?",
        "roll back the last migration",
        "password manager recommendations",
        "is 5 km far to walk",
        "what's the time complexity of quicksort",
        "days until my code compiles",
        "42",
        "-5",
        "max(1, 2)",
        "__import__('os').system('echo hi')",
        "().__class__.__bases__",
        "2 days to go",
        "remind me what a monad is",
    ],
)
def test_questions_for_the_ai_are_left_for_it(question):
    assert offline.answer(question, NOW) is None
    assert offline.parse_kept(question) is None


@pytest.mark.parametrize(
    "asked, shown",
    [
        ("2+2*3", "= **8**"),
        ("what is 12*7", "= **84**"),
        ("calc 2^10", "= **1,024**"),
        ("15% of 80", "= **12**"),
        ("sqrt(16) + 1", "= **5**"),
        ("(1+2)*3", "= **9**"),
        ("1,000 + 1", "= **1,001**"),
        ("what is 0.1+0.2", "= **0.3**"),
        ("10 / 4", "= **2.5**"),
        ("3 × 4 ÷ 2", "= **6**"),
    ],
)
def test_sums(asked, shown):
    assert offline.answer(asked, NOW).endswith(shown)


@pytest.mark.parametrize(
    "asked",
    ["9**99999", "10**300*10**300*10**300*10**300*10**300", "exp(1000)", "2**2**2**2**2**2", "factorial(170)*factorial(170)*factorial(170)"],
)
def test_sums_too_big_are_refused_at_once(asked):
    started = time.perf_counter()
    assert offline.answer(asked, NOW) == "That's too big a number for me."
    assert time.perf_counter() - started < 0.5


def test_sums_that_cant_be_done_say_so():
    assert offline.answer("1/0", NOW) == "Hmm: can't divide by zero."
    assert "can't be worked out" in offline.answer("sqrt(-1)", NOW)
    assert "can't be worked out" in offline.answer("factorial(200)", NOW)


def test_the_calculator_never_runs_anything():
    for sneaky in ("__import__('os')", "open('/etc/passwd')", "(lambda: 1)()", "[1]*10**9", "'a'*10**9", "x", "sum(range(10**12))"):
        assert offline.calculate(sneaky) is None
    assert offline.calculate("1+" * 300 + "1") is None  # far too long to be a sum anyone typed


@pytest.mark.parametrize(
    "asked, shown",
    [
        ("5 km in miles", "5 km = **3.107 miles**"),
        ("70 f to c", "70 °F = **21.11 °C**"),
        ("-40 c to f", "-40 °C = **-40 °F**"),
        ("3 cups to ml", "3 cups = **709.8 ml**"),
        ("2 gb in mib", "2 gb = **1,907 mib**"),
        ("90 minutes in hours", "90 minutes = **1.5 hours**"),
        ("convert 10 lb to kg", "10 lb = **4.536 kg**"),
        ("60 mph to km/h", "60 mph = **96.56 km/h**"),
    ],
)
def test_units(asked, shown):
    assert offline.answer(asked, NOW) == shown


def test_units_of_different_kinds_dont_mix():
    assert "can't be turned into" in offline.answer("1 kg to cm", NOW)


def test_the_time_the_date_and_counting_days():
    assert offline.answer("time", NOW) == "It's **3:04 PM**."
    assert offline.answer("What day is it?", NOW) == "Today is **Wednesday, November 11, 2026**."
    assert offline.answer("what week is it", NOW) == "It's week **46** of 2026."
    assert offline.answer("days until christmas", NOW) == "**44 days** until Christmas (Fri Dec 25)."
    assert offline.answer("days until 2027-01-01", NOW) == "**51 days** until Friday, January 1, 2027."
    assert offline.answer("how many days until 11 november", NOW) == "Wednesday, November 11, 2026 is **today**!"
    assert offline.answer("days until jan 5", NOW).startswith("**55 days**")  # next year's


def test_chance_is_fair_and_bounded():
    rng = random.Random(7)
    assert offline.chance("flip a coin", rng) in ("🪙 **Heads**", "🪙 **Tails**")
    two = offline.chance("roll 2d6+3", rng)
    total = int(two.split("**")[1])
    assert 5 <= total <= 15 and "+ 3" in two
    assert offline.chance("roll 500d6", rng).startswith("I can roll")
    for _ in range(50):
        n = int(offline.chance("random number between 10 and 1", rng).split("**")[1])
        assert 1 <= n <= 10
    assert offline.chance("pick one: tacos, sushi or pizza", rng) in ("**tacos**", "**sushi**", "**pizza**")


def test_passwords_are_strong_and_never_the_same():
    a, b = offline.password("password"), offline.password("generate a password 32 characters long")
    pa, pb = a.split("`")[1], b.split("`")[1]
    assert len(pa) == 20 and len(pb) == 32 and pa != pb
    assert any(c.islower() for c in pa) and any(c.isupper() for c in pa) and any(c.isdigit() for c in pa) and any(c in offline._SYMBOLS for c in pa)
    assert "keep it anywhere" in a
    assert offline.password("password 4") == "A password of 8 to 128 characters, please."


@pytest.mark.parametrize(
    "asked, kind, arg",
    [
        ("note: buy milk", "note", "buy milk"),
        ("Add a note: call the dentist", "note", "call the dentist"),
        ("take a note: idea for a game", "note", "idea for a game"),
        ("notes", "notes", ""),
        ("delete note 2", "delete note", "2"),
        ("clear notes", "clear notes", ""),
        ("stopwatch", "stopwatch", ""),
        ("stop the stopwatch", "stop stopwatch", ""),
        ("reminders", "reminders", ""),
        ("cancel reminder 3", "cancel reminder", "3"),
        ("clear reminders", "clear reminders", ""),
    ],
)
def test_what_chatmon_keeps_is_asked_for_plainly(asked, kind, arg):
    found = offline.parse_kept(asked)
    assert (found.kind, found.arg) == (kind, arg)


def test_a_reminder_without_a_time_or_a_question_for_the_ai():
    assert offline.reminder_or_question("how decorators work")
    assert offline.reminder_or_question("what a monad is")
    assert offline.reminder_or_question("to stretch?")
    assert not offline.reminder_or_question("to stretch")
    assert not offline.reminder_or_question("call Sam")


@pytest.mark.parametrize(
    "question",
    [
        "Note: I use Python 3.12. Why does asyncio.run fail inside Jupyter?",
        "note, my AWS key is AKIAEXAMPLE can you check its format",
        "write down the steps to rotate my SSH keys",
        "jot down a plan for my week",
        "note: how do I rotate my keys",
        "pick one: should I use postgres or mysql for this",
    ],
)
def test_questions_are_never_kept_as_notes_or_picked_at_random(question):
    assert offline.parse_kept(question) is None and offline.answer(question, NOW) is None


@pytest.mark.parametrize("asked", ["round(1, -10**300)", "round(1, -10**8)", "round(2.5, 10**9)"])
def test_round_cant_be_made_to_work_forever(asked):
    started = time.perf_counter()
    assert "can't be worked out" in offline.answer(asked, NOW)
    assert time.perf_counter() - started < 0.2
    assert offline.answer("round(3.14159, 2)", NOW).endswith("= **3.14**")


def test_pasted_text_with_runs_of_spaces_is_never_slow():
    for text in ("1 a in " + " " * 5000 + "!", "5 " + "km " * 3000 + "in miles", "1" + " " * 30000 + "kg"):
        started = time.perf_counter()
        assert offline.answer(text, NOW) is None
        assert time.perf_counter() - started < 0.2
    assert offline.answer("  5   km   in   miles ", NOW) == "5 km = **3.107 miles**"


def test_no_complex_numbers_and_no_huge_random_ranges():
    assert offline.answer("(-8)**0.5", NOW) == "Hmm: that has no real answer."
    assert offline.answer("random number between 1 and " + "9" * 5000, NOW) is None
