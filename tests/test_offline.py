"""What Chatmon answers without any AI, and, as much, what it leaves for the AI: a question that only
mentions a timer, a note or a sum is never taken for one."""

import json
import random
import shutil
import time
import warnings
from datetime import datetime

import pytest

from chatmon import localefmt, memory, offline, reminders

NOW = datetime(2026, 11, 11, 15, 4)  # a Wednesday


@pytest.fixture(autouse=True)
def plain_english():
    """What's written here is checked in plain English, whatever the machine's locale (test_localefmt.py has the rest)."""
    localefmt.set_locale(None)
    yield
    localefmt.set_locale()


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


def test_a_whole_number_answer_has_at_most_400_digits():
    assert offline.calculate("10**399") == 10**399  # 400 digits
    for too_big in ("10**400", "10**399 * 10", "1e308 % of 1e308"):
        with pytest.raises(OverflowError):
            offline.calculate(too_big)


# -- the phrases are data, one file per language (M5-06)

EXPECTED_HELP = """\
**Without any AI** (nothing leaves your computer, and none of it goes in a chat):

- **Reminders and timers:** *remind me in 20m to stretch* · *remind me friday at 3pm to call Sam* · *remind me every weekday at 9 to stand up* · *timer 10 min for the pasta* · *reminders* · *cancel reminder 2* · *clear reminders*
- **Focus and breaks:** *focus 50* · *stop focus* · *breaks off* · *breaks on* · *focus alerts off* · *focus alerts on*
- **Notes:** *note: buy milk* · *notes* · *delete note 2* · *clear notes*
- **Stopwatch:** *stopwatch* · *stop stopwatch*
- **Sums:** *2 + 2 * 3* · *15% of 80* · *sqrt(2)* · *calc 2^10*
- **Units:** *5 km in miles* · *70 f to c* · *3 cups to ml* · *2 GB in MiB*
- **Time and days:** *time* · *date* · *what week is it* · *days until Christmas* · *days until 2027-01-01*
- **Chance:** *flip a coin* · *roll 2d6* · *random number between 1 and 10* · *pick one: tacos, sushi or pizza*
- **Passwords:** *password* · *password 32*
- **Your computer:** *status* (battery, disks, reminders, the brain in use)
- **AI agents:** *agents* (which are working, and which need you)
- **Me:** *settings* · *hide* · *new chat* · *rename chat* · *history* · *what's new* · *check for updates* · *report a problem* · *version*
- **Memory:** *remember that I use Arch* · *what do you remember* · *forget that I use Arch* · *forget everything*. What you ask me to remember goes with every question, to whichever AI you ask: that's what it's for.

Anything else goes to the AI you picked, under **Brain** in my menu.
"""


def test_help_lists_everything_done_without_any_ai():
    assert offline.help_text("en") == EXPECTED_HELP


def test_the_help_follows_the_persons_language_and_is_english_when_theres_no_translation():
    from PyQt6.QtCore import QLocale

    localefmt.set_locale(QLocale(QLocale.Language.German, QLocale.Country.Germany))
    assert offline.phrases().language == "en"  # only English ships
    assert offline.help_text() == EXPECTED_HELP
    assert offline.answer("what time is it", NOW) == "It's **15:04**."  # and its times are still German's


def test_every_example_in_the_help_is_understood_without_any_ai():
    examples = [e for s in offline.phrases("en").sections for e in s.examples]
    assert len(examples) >= 50  # guards the loop below against an empty help
    for e in examples:
        reminder = reminders.parse_command(e, NOW)
        understood = offline.command(e, "en") or offline.parse_kept(e) or offline.answer(e, NOW) or memory.command(e) or (reminder and reminder.kind != "unclear")
        assert understood, e


@pytest.mark.parametrize(
    "said, command",
    [
        ("What can you do?", "help"),
        ("How’s my computer", "status"),
        ("  GO   away! ", "hide"),
        ("/new", "new chat"),
        ("stop break reminders", "breaks off"),
        ("focus notifications on", "focus alerts on"),
        ("Release notes.", "what's new"),
        ("what are my agents doing?", "agents"),
        ("report a bug", "report a problem"),
        ("which version", "version"),
        ("what is love", None),
    ],
)
def test_fixed_commands_are_read_from_the_phrase_data(said, command):
    assert offline.command(said, "en") == command


def test_a_phrase_means_one_command_only():
    data = json.loads((offline.PHRASES / "en.json").read_text(encoding="utf-8"))
    said = [offline.normal(p) for phrases in data["commands"].values() for p in phrases]
    assert len(said) > 100 and len(said) == len(set(said))


def test_another_languages_phrases_and_help_with_english_always_understood(tmp_path):
    shutil.copy(offline.PHRASES / "en.json", tmp_path / "en.json")
    (tmp_path / "fr.json").write_text(json.dumps({
        "commands": {"help": ["aide", "Que sais-tu faire"], "notes": ["mes notes"], "made up": ["bidule"], "hide": ["help"]},
        "templates": {"note": ["note : {text}"], "delete note": ["supprimer la note {n}"], "nonsense": ["x {n}"], "clear notes": ["{n} {text}"]},
        "question_words": ["pourquoi"],
        "help": {
            "title": "**Sans IA** :",
            "sections": [{"id": "notes", "name": "Notes", "examples": ["note : acheter du lait", "mes notes"]}, {"id": "me", "name": "Moi"}],
            "footer": "Le reste va à l'IA.",
        },
    }), encoding="utf-8")
    fr = offline.load_phrases("fr_CA", tmp_path)
    assert fr.language == "fr"
    assert fr.command("Aide") == fr.command("que sais-tu faire ?") == "help"
    assert fr.command("help") == "help"  # English is always understood, and means what it means in English
    assert fr.command("mes notes") == "notes" and fr.command("bidule") is None
    assert fr.template("supprimer la note 3") == fr.template("delete note 3") == ("delete note", "3")
    assert fr.template("note : acheter du lait") == ("note", "acheter du lait")
    assert fr.template("x 3") is None
    assert fr.asks("pourquoi pas") and fr.asks("why not")
    shown = fr.help()
    assert shown.startswith("**Sans IA** :\n\n") and shown.endswith("\n\nLe reste va à l'IA.\n")
    assert "- **Notes:** *note : acheter du lait* · *mes notes*\n" in shown
    assert "- **Moi:** *settings* · *hide* · *new chat*" in shown  # named in French, its examples English's
    assert "- **Sums:** *2 + 2 * 3*" in shown  # not translated: English


def test_a_missing_or_broken_translation_leaves_english(tmp_path):
    shutil.copy(offline.PHRASES / "en.json", tmp_path / "en.json")
    (tmp_path / "de.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "es.json").write_text("[1, 2]", encoding="utf-8")
    english = offline.load_phrases("en", tmp_path)
    for language in ("de_DE", "es", "pt_BR", "../en", "en_GB", ""):
        book = offline.load_phrases(language, tmp_path)
        assert book.language == "en" and book.command("help") == "help"
        assert book.help() == english.help() == EXPECTED_HELP
    (tmp_path / "en.json").unlink()
    with pytest.raises(OSError):
        offline.load_phrases("en", tmp_path)  # English is part of Chatmon: without it, something's broken


# -- AI agents at a glance (M5-08)


def test_agents_at_a_glance():
    agents = {"claude": ("needs-you", 1000.0), "codex": ("working", 400.0), "gemini": ("needs-you", 700.0), "muse": ("working", 3500.0)}
    assert offline.agents_report(agents, 3600.0) == (
        "- **Gemini** needs you (waiting 48 min)\n"
        "- **Claude** needs you (waiting 43 min)\n"
        "- **Codex** is working (53 min so far)\n"
        "- **Muse** is working (1 min so far)"
    )
    plain = offline.agents_report({"claude": ("needs-you", 0.0)}, 4000.0, label={"claude": "Claude Code"}.get, markdown=False)
    assert plain == "Claude Code needs you (waiting 1 h 6 min)"
    assert offline.agents_report({}, 0) == "No AI agent is working or waiting for you."
    assert offline.agents_report({"x": ("thinking", 0.0)}, 10) == "- **X**: thinking"


@pytest.mark.parametrize(
    "seconds, said",
    [(-5, "under a minute"), (59, "under a minute"), (60, "1 min"), (3599, "59 min"), (3600, "1 h"), (3660, "1 h 1 min"),
     (86399, "23 h 59 min"), (86400, "1 day"), (3 * 86400 + 5, "3 days")],
)
def test_spans(seconds, said):
    assert offline.span(seconds) == said


def test_the_calculator_reads_what_is_typed_without_pythons_own_warnings():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert offline.calculate("1or 2") is None and offline.answer("3if 4", NOW) is None
    assert [str(w.message) for w in caught] == []
