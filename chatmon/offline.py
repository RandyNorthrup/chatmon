"""What your chatmon answers by itself, with no AI and no network: sums, unit conversions, the time and date,
counting the days, coins, dice and random picks, and passwords. Pure functions (no Qt, no state); the app
keeps notes, the stopwatch and reminders, and these parse what's asked of them.

Each is recognized only from a clear way of asking for it, so a question that merely mentions a timer or a
note still goes to the AI. Nothing here is ever sent anywhere, or kept in a chat.

The fixed phrases ("time", "notes", "breaks off"…) and the help that lists them are data, one file per language in
`phrases/`: English always, and the person's own language beside it when there's a file for it. Sums, units, dice,
"days until …" and reminders' times are still read in English.
"""

from __future__ import annotations

import ast
import functools
import json
import math
import operator
import re
import secrets
import string
import warnings
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from . import localefmt

# -- the calculator: arithmetic only, from a parsed tree (never eval)

_MAX_EXPRESSION = 200  # characters
_MAX_NODES = 80
_MAX_EXPONENT = 10_000
_MAX_DIGITS = 400  # of a whole-number result
_TOO_MANY_DIGITS = 10**_MAX_DIGITS  # the first whole number with more
_BINARY = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_NAMES = {"pi": math.pi, "π": math.pi, "e": math.e, "tau": math.tau}
_FUNCTIONS = {
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan, "asin": math.asin, "acos": math.acos,
    "atan": math.atan, "log": math.log, "ln": math.log, "log10": math.log10, "log2": math.log2, "exp": math.exp,
    "abs": abs, "round": round, "floor": math.floor, "ceil": math.ceil, "factorial": None,
}
_MATH_TEXT = re.compile(r"[\d\s.+\-*/%^()×÷,πa-z]+", re.I)


class _NotMath(Exception):
    pass


def _number(node: ast.AST, budget: list[int]) -> float | int:
    budget[0] -= 1
    if budget[0] < 0:
        raise _NotMath
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.Name) and node.id in _NAMES:
        return _NAMES[node.id]
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_number(node.operand, budget))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        left, right = _number(node.left, budget), _number(node.right, budget)
        if isinstance(node.op, ast.Pow):
            if abs(right) > _MAX_EXPONENT or (isinstance(left, int) and isinstance(right, int) and right > 0 and abs(left) > 1 and right * math.log10(abs(left)) > _MAX_DIGITS):
                raise OverflowError
        return _BINARY[type(node.op)](left, right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS and not node.keywords and 1 <= len(node.args) <= 2:
        args = [_number(a, budget) for a in node.args]
        if node.func.id == "factorial":
            if len(args) != 1 or args[0] != int(args[0]) or not 0 <= args[0] <= 170:
                raise ValueError
            return math.factorial(int(args[0]))
        if len(args) == 2 and (node.func.id != "round" or not isinstance(args[1], int) or abs(args[1]) > _MAX_DIGITS):
            raise ValueError  # round(1, -10**300) would work out 10**(10**300)
        return _FUNCTIONS[node.func.id](*args)
    raise _NotMath


def calculate(expression: str) -> float | int | None:
    """The value of a sum ("2 + 3 * 4", "2^10", "sqrt(2)", "15% of 80"), or None if it isn't one.
    ValueError for a sum that can't be worked out (1/0, sqrt(-1)); OverflowError for one too big."""
    text = expression.strip().rstrip("=?").strip()
    if not text or len(text) > _MAX_EXPRESSION or not _MATH_TEXT.fullmatch(text):
        return None
    m = re.fullmatch(r"(.+?)\s*%\s*of\s+(.+)", text, re.I)
    if m:
        part, whole = calculate(m.group(1)), calculate(m.group(2))
        return None if part is None or whole is None else _checked(part * whole / 100)
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)  # 1,000,000
    text = text.replace("^", "**").replace("×", "*").replace("÷", "/").replace("π", "pi")
    text = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"(\1/100)", text)  # 20% on its own: a fifth
    try:
        # What's typed isn't Python: Python's own warnings about it ("invalid decimal literal" for "1or 2") mean
        # nothing to anyone, so they're not printed.
        with warnings.catch_warnings(action="ignore", category=SyntaxWarning):
            tree = ast.parse(text, mode="eval")
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return None
    if not any(isinstance(n, (ast.BinOp, ast.Call, ast.UnaryOp)) for n in ast.walk(tree.body)) and not isinstance(tree.body, ast.Constant):
        return None
    if isinstance(tree.body, ast.Name):  # a lone word ("e") isn't a sum anyone asks for
        return None
    try:
        value = _number(tree.body, [_MAX_NODES])
    except _NotMath:
        return None
    except ZeroDivisionError:
        raise ValueError("can't divide by zero") from None
    except (ValueError, TypeError):
        raise ValueError("that can't be worked out") from None
    return _checked(value)


def _checked(value: float | int | complex) -> float | int:
    """A result fit to show: real, finite, and a whole number of at most _MAX_DIGITS digits."""
    if isinstance(value, complex):  # (-8) ** 0.5
        raise ValueError("that has no real answer")
    if isinstance(value, float) and (math.isinf(value) or math.isnan(value)):
        raise OverflowError
    if isinstance(value, int) and abs(value) >= _TOO_MANY_DIGITS:  # 10**400, and products of big numbers too
        raise OverflowError
    return value


def show_number(value: float | int) -> str:
    if isinstance(value, int) or (isinstance(value, float) and value.is_integer() and abs(value) < 1e15):
        return f"{int(value):,}"
    text = f"{value:.10g}"
    return text if "e" in text else text.rstrip("0").rstrip(".")


# -- unit conversions

_UNITS: dict[str, tuple[str, float]] = {}  # name: (kind, how many of the kind's base unit)


def _units(kind: str, base: float, *names: str) -> None:
    for name in names:
        _UNITS[name] = (kind, base)


_units("length", 0.001, "mm", "millimeter", "millimeters", "millimetre", "millimetres")
_units("length", 0.01, "cm", "centimeter", "centimeters", "centimetre", "centimetres")
_units("length", 1, "m", "meter", "meters", "metre", "metres")
_units("length", 1000, "km", "kilometer", "kilometers", "kilometre", "kilometres")
_units("length", 0.0254, "in", "inch", "inches", '"')
_units("length", 0.3048, "ft", "foot", "feet", "'")
_units("length", 0.9144, "yd", "yard", "yards")
_units("length", 1609.344, "mi", "mile", "miles")
_units("length", 1852, "nmi", "nautical mile", "nautical miles")
_units("mass", 0.001, "mg", "milligram", "milligrams")
_units("mass", 1, "g", "gram", "grams")
_units("mass", 1000, "kg", "kilo", "kilos", "kilogram", "kilograms")
_units("mass", 28.349523125, "oz", "ounce", "ounces")
_units("mass", 453.59237, "lb", "lbs", "pound", "pounds")
_units("mass", 6350.29318, "st", "stone", "stones")
_units("mass", 1_000_000, "t", "tonne", "tonnes", "metric ton", "metric tons")
_units("volume", 1, "ml", "milliliter", "milliliters", "millilitre", "millilitres")
_units("volume", 1000, "l", "liter", "liters", "litre", "litres")
_units("volume", 4.92892159375, "tsp", "teaspoon", "teaspoons")
_units("volume", 14.78676478125, "tbsp", "tablespoon", "tablespoons")
_units("volume", 236.5882365, "cup", "cups")
_units("volume", 29.5735295625, "fl oz", "fluid ounce", "fluid ounces")
_units("volume", 473.176473, "pt", "pint", "pints")
_units("volume", 946.352946, "qt", "quart", "quarts")
_units("volume", 3785.411784, "gal", "gallon", "gallons")
_units("speed", 1, "m/s", "meters per second", "metres per second")
_units("speed", 1 / 3.6, "km/h", "kmh", "kph", "kilometers per hour", "kilometres per hour")
_units("speed", 0.44704, "mph", "miles per hour")
_units("speed", 1852 / 3600, "kn", "knot", "knots")
_units("data", 1, "b", "byte", "bytes")
_units("data", 1e3, "kb", "kilobyte", "kilobytes")
_units("data", 1e6, "mb", "megabyte", "megabytes")
_units("data", 1e9, "gb", "gigabyte", "gigabytes")
_units("data", 1e12, "tb", "terabyte", "terabytes")
_units("data", 2**10, "kib", "kibibyte", "kibibytes")
_units("data", 2**20, "mib", "mebibyte", "mebibytes")
_units("data", 2**30, "gib", "gibibyte", "gibibytes")
_units("data", 2**40, "tib", "tebibyte", "tebibytes")
_units("time", 1, "s", "sec", "secs", "second", "seconds")
_units("time", 60, "min", "mins", "minute", "minutes")
_units("time", 3600, "h", "hr", "hrs", "hour", "hours")
_units("time", 86400, "day", "days")
_units("time", 604800, "wk", "week", "weeks")
_TEMPERATURES = {
    "c": "°C", "°c": "°C", "celsius": "°C", "centigrade": "°C",
    "f": "°F", "°f": "°F", "fahrenheit": "°F",
    "k": "K", "kelvin": "K", "kelvins": "K",
}
_UNIT_WORDS = r"[a-z°/'\"]+(?: [a-z°/'\"]+)?"  # one word, or two ("fl oz"): no runs of spaces to backtrack over
_CONVERT = re.compile(
    rf"^(?:convert |how many (?P<target_first>{_UNIT_WORDS}) (?:is|are|in) )?"
    rf"(?P<amount>-?\d[\d,]{{0,20}}(?:\.\d{{1,10}})?) ?(?P<from>{_UNIT_WORDS})"
    rf"(?: (?:in|to|into|as) (?P<to>{_UNIT_WORDS}))? ?\??$",
    re.I,
)


def _to_kelvin(value: float, unit: str) -> float:
    return {"°C": value + 273.15, "°F": (value - 32) * 5 / 9 + 273.15, "K": value}[unit]


def _from_kelvin(value: float, unit: str) -> float:
    return {"°C": value - 273.15, "°F": (value - 273.15) * 9 / 5 + 32, "K": value}[unit]


def convert(text: str) -> str | None:
    """"5 km in miles" → "5 km = **3.107 mi**"; None if it isn't a conversion between units it knows."""
    text = " ".join(text.split())
    if len(text) > 80:  # a conversion is short; anything longer is for the AI, and never a slow match
        return None
    m = _CONVERT.match(text)
    if not m:
        return None
    target = (m.group("to") or m.group("target_first") or "").strip().lower()
    source = m.group("from").strip().lower()
    if not target:
        return None
    amount = float(m.group("amount").replace(",", ""))
    if source in _TEMPERATURES and target in _TEMPERATURES:
        a, b = _TEMPERATURES[source], _TEMPERATURES[target]
        result = _from_kelvin(_to_kelvin(amount, a), b)
        return f"{show_number(amount)} {a} = **{show_number(round(result, 2))} {b}**"
    if source not in _UNITS or target not in _UNITS:
        return None
    (kind_a, base_a), (kind_b, base_b) = _UNITS[source], _UNITS[target]
    if kind_a != kind_b:
        return f"{source} is a {kind_a} and {target} a {kind_b}: one can't be turned into the other."
    result = amount * base_a / base_b
    shown = show_number(float(f"{result:.4g}")) if abs(result) < 1e15 else f"{result:.4g}"
    return f"{show_number(amount)} {source} = **{shown} {target}**"


# -- the time and the date, and counting the days

_HOLIDAYS = {"christmas": (12, 25), "christmas eve": (12, 24), "new year": (1, 1), "new year's": (1, 1), "new years": (1, 1),
             "halloween": (10, 31), "valentine's day": (2, 14), "valentines day": (2, 14), "new year's eve": (12, 31)}
_MONTHS = {m.lower(): i for i, m in enumerate(localefmt.MONTHS, 1)}
_MONTHS.update({name[:3]: i for name, i in list(_MONTHS.items())})
_MONTHS["sept"] = 9


def _day(d: date) -> str:
    return localefmt.long_date(d)


def _parse_date(text: str, today: date) -> tuple[date, str] | None:
    """"christmas", "dec 25", "25 december", "2026-12-25": the next such day, and how to call it."""
    t = text.strip().lower().rstrip("?.!").removeprefix("the ").strip()
    if t in _HOLIDAYS:
        month, day = _HOLIDAYS[t]
        name = t.title().replace("'S", "'s")
    elif m := re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", t):
        try:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
        return d, _day(d)
    elif (m := re.fullmatch(r"([a-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?", t)) and m.group(1) in _MONTHS:
        month, day, name = _MONTHS[m.group(1)], int(m.group(2)), ""
    elif (m := re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]+)", t)) and m.group(2) in _MONTHS:
        month, day, name = _MONTHS[m.group(2)], int(m.group(1)), ""
    else:
        return None
    for year in (today.year, today.year + 1):
        try:
            d = date(year, month, day)
        except ValueError:
            return None
        if d >= today:
            return d, name or _day(d)
    return None


def when(text: str, now: datetime) -> str | None:
    """The time, the date, the week, or days until a day."""
    t = " ".join(text.lower().strip().rstrip("?.!").split())
    asked = phrases().command(t)
    if asked == "time":
        return f"It's **{localefmt.time_of_day(now)}**."
    if asked == "date":
        return f"Today is **{_day(now.date())}**."
    if asked == "week":
        return f"It's week **{now.isocalendar().week}** of {now.isocalendar().year}."
    m = re.fullmatch(r"(?:how many )?days (?:until|till|til|to|before) (.+)", t)
    if m:
        found = _parse_date(m.group(1), now.date())
        if found is None:
            return None
        d, name = found
        days = (d - now.date()).days
        if days == 0:
            return f"{name} is **today**!"
        return f"**{days} day{'s' if days != 1 else ''}** until {name}" + (f" ({localefmt.short_day(d)})." if name != _day(d) else ".")
    return None


# -- chance

_RANDOM = secrets.SystemRandom()


def chance(text: str, rng=_RANDOM) -> str | None:
    """Coins, dice, a number, or one of several: fair (the system's own randomness)."""
    t = " ".join(text.lower().strip().rstrip("?.!").split())
    if phrases().command(t) == "coin":
        return f"🪙 **{rng.choice(['Heads', 'Tails'])}**"
    m = re.fullmatch(r"roll(?: an?| the)?(?: (\d{1,3}))?\s*(?:dice|die|d(\d{1,4}))?(?:\s*([+-])\s*(\d{1,4}))?", t)
    if m and (t.startswith("roll ") or t == "roll"):
        count, sides = int(m.group(1) or 1), int(m.group(2) or 6)
        if not (1 <= count <= 100 and 2 <= sides <= 1000):
            return "I can roll 1 to 100 dice, of 2 to 1000 sides."
        rolls = [rng.randint(1, sides) for _ in range(count)]
        bonus = (int(m.group(4)) * (1 if m.group(3) == "+" else -1)) if m.group(4) else 0
        total = sum(rolls) + bonus
        shown = " + ".join(map(str, rolls)) + (f" {m.group(3)} {m.group(4)}" if bonus else "")
        return f"🎲 **{total}**" + (f"  ({shown})" if count > 1 or bonus else "")
    m = re.fullmatch(r"(?:pick |give me |choose )?(?:a )?random number(?: (?:between|from) (-?\d{1,18}) (?:and|to|-) (-?\d{1,18}))?", t) or re.fullmatch(
        r"(?:pick|choose) a number (?:between |from )?(-?\d{1,18}) ?(?:and|to|-) ?(-?\d{1,18})", t
    )
    if m:
        low, high = (int(m.group(1)), int(m.group(2))) if m.group(1) else (1, 100)
        low, high = min(low, high), max(low, high)
        return f"**{rng.randint(low, high)}**  (from {low} to {high})"
    # "pick one: pizza, tacos or sushi": short options, asked plainly (a question about choosing is the AI's).
    m = re.fullmatch(r"(?:pick|choose) (?:one(?: of| from)?|between|from|one for me|for me)\s*:?\s+(.+)", text.strip(), re.I)
    if m and "?" not in text and not phrases().asks(m.group(1)):
        options = [o.strip(" .!") for o in re.split(r",|\bor\b|\band\b", m.group(1)) if o.strip(" .!")]
        if 2 <= len(options) <= 20 and all(len(o) <= 40 and len(o.split()) <= 5 for o in options):
            return f"**{rng.choice(options)}**"
    return None


# -- passwords

_SYMBOLS = "!#$%&*+-=?@^_~"


def password(text: str) -> str | None:
    """A strong password, made here (the system's own randomness), shown once and kept nowhere."""
    t = " ".join(text.lower().strip().rstrip("?.!").split())
    m = re.fullmatch(r"(?:generate |make |give me |new |create )?(?:a |an )?(?:strong |random |new )?password(?: of)?(?: (\d{1,3}))?(?: char(?:acter)?s?)?(?: long)?", t)
    if not m:
        return None
    length = int(m.group(1) or 20)
    if not 8 <= length <= 128:
        return "A password of 8 to 128 characters, please."
    pool = string.ascii_letters + string.digits + _SYMBOLS
    while True:
        made = "".join(secrets.choice(pool) for _ in range(length))
        if all(any(c in group for c in made) for group in (string.ascii_lowercase, string.ascii_uppercase, string.digits, _SYMBOLS)):
            break
    return f"`{made}`\n\nMade here, from your system's own randomness. I don't keep it anywhere: copy it now."


# -- the phrases, one file per language

PHRASES = Path(__file__).resolve().parent / "phrases"
_LANGUAGE_NAME = re.compile(r"[A-Za-z]{2,3}(?:_[A-Za-z0-9]{2,4})?")  # "en", "pt_BR": a file name, never a path


def normal(text: str) -> str:
    """A phrase as commands are matched: lower case, single spaces, straight apostrophes, and no full stop,
    question mark or exclamation mark around it."""
    return " ".join(text.casefold().replace("’", "'").split()).strip(" ?!.")


def _template(template: str) -> tuple[re.Pattern, bool] | None:
    """A pattern for a template with one {n} (a number) or one {text} (the rest of what's typed), and whether
    it's {text}: "delete note {n}" matches "delete note 2", "note: {text}" matches "note: buy milk" and
    "note:buy milk". None for a template without exactly one."""
    pieces = re.split(r"(\{n\}|\{text\})", " ".join(template.split()))
    holes = [p for p in pieces if p in ("{n}", "{text}")]
    if len(holes) != 1 or not "".join(p for p in pieces if p not in holes).strip():
        return None
    out = []
    for piece in pieces:
        if piece == "{n}":
            out.append(r"(\d{1,9})")
        elif piece == "{text}":
            out[-1:] = [out[-1].rstrip()] if out else []
            out.append(r"\s*(.+)")
        else:
            out.append(re.escape(piece).replace("\\ ", " "))
    return re.compile("".join(out), re.I | re.S), holes[0] == "{text}"


def _read(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: not a phrase file")
    return data


def _strings(value: object) -> list[str]:
    return [v for v in value if isinstance(v, str) and v.strip()] if isinstance(value, list) else []


def _table(data: dict, key: str) -> dict[str, list[str]]:
    table = data.get(key)
    return {k: _strings(v) for k, v in table.items() if isinstance(k, str)} if isinstance(table, dict) else {}


@dataclass(frozen=True)
class HelpSection:
    id: str
    name: str
    examples: tuple[str, ...]
    after: str = ""  # said right after the examples


@dataclass(frozen=True)
class Phrases:
    """The phrases understood and the help shown, for one language (`language`, "en" when there's no file for
    the one asked for). English phrases are always understood besides that language's."""

    language: str
    commands: Mapping[str, str]  # a phrase, as normal() gives it: its command
    templates: tuple[tuple[str, re.Pattern, bool], ...]  # (command, pattern, whether what it takes is text)
    question_words: frozenset[str]  # a sentence starting with one asks something
    remind_me_questions: frozenset[str]  # "remind me" and then one of these asks the AI something
    title: str
    sections: tuple[HelpSection, ...]
    footer: str

    def command(self, text: str) -> str | None:
        """The command a whole phrase asks for ("what time is it?" is "time"), or None."""
        return self.commands.get(normal(text))

    def template(self, text: str) -> tuple[str, str] | None:
        """(command, what it takes) for a phrase that fits a template: ("delete note", "2"), ("note", "buy milk")."""
        t = " ".join(text.split())
        for command, pattern, takes_text in self.templates:
            m = pattern.fullmatch(t if takes_text else t.rstrip(" ?!."))
            if m:
                return command, m.group(1).strip()
        return None

    def asks(self, text: str) -> bool:
        """Whether a sentence starts by asking something: "should I use …", "how do …"."""
        first = re.match(r"\w+", text.strip().casefold())
        return bool(first) and first.group(0) in self.question_words

    def help(self) -> str:
        """What Chatmon does without any AI, as Markdown, in this language."""
        lines = [f"- **{s.name}:** " + " · ".join(f"*{e}*" for e in s.examples) + s.after for s in self.sections]
        return f"{self.title}\n\n" + "\n".join(lines) + f"\n\n{self.footer}\n"


def _candidates(language: str) -> list[str]:
    """The files that may hold a language, most particular first: "pt_BR" is pt_BR.json, then pt.json."""
    code = language.replace("-", "_").split(".")[0]
    names = [code, code.split("_")[0]]
    return [n for n in dict.fromkeys(names) if _LANGUAGE_NAME.fullmatch(n) and n.lower() != "en"]


def load_phrases(language: str = "en", folder: Path = PHRASES) -> Phrases:
    """The phrases for `language`: its own file's, with English's always understood too, and English help where
    the language's leaves something out. A language file that's missing or broken counts as not there; the
    English one is part of Chatmon, so its absence raises (OSError, ValueError)."""
    english = _read(folder / "en.json")
    own: dict = {}
    found = "en"
    for name in _candidates(language):
        try:
            own = _read(folder / f"{name}.json")
        except (OSError, ValueError):
            continue
        found = name
        break
    known = _table(english, "commands")
    commands: dict[str, str] = {}
    for source in (_table(own, "commands"), known):  # English last: its phrases always mean what they mean in English
        for command, said in source.items():
            if command in known:
                commands.update({normal(s): command for s in said})
    templates = []
    english_templates = _table(english, "templates")
    for source in (english_templates, _table(own, "templates")):
        for command, said in source.items():
            for s in said:
                compiled = _template(s) if command in english_templates else None
                if compiled:
                    templates.append((command, *compiled))
    words = {key: frozenset(w.casefold() for w in _strings(english.get(key)) + _strings(own.get(key))) for key in ("question_words", "remind_me_questions")}
    help_en = english.get("help") if isinstance(english.get("help"), dict) else {}
    help_own = own.get("help") if isinstance(own.get("help"), dict) else {}
    translated = {s["id"]: s for s in help_own.get("sections", []) if isinstance(s, dict) and isinstance(s.get("id"), str)}
    sections = []
    for section in help_en.get("sections", []):
        mine = translated.get(section["id"], {})
        name = mine.get("name") if isinstance(mine.get("name"), str) else section["name"]
        examples = tuple(_strings(mine.get("examples")) or _strings(section.get("examples")))
        after = mine.get("after") if isinstance(mine.get("after"), str) else section.get("after", "")
        sections.append(HelpSection(section["id"], name, examples, after))

    def said(key: str) -> str:
        return help_own[key] if isinstance(help_own.get(key), str) else str(help_en.get(key, ""))

    return Phrases(found, commands, tuple(templates), words["question_words"], words["remind_me_questions"], said("title"), tuple(sections), said("footer"))


@functools.lru_cache(maxsize=8)
def _phrases(language: str) -> Phrases:
    return load_phrases(language)


def phrases(language: str | None = None) -> Phrases:
    """The phrases for `language`, or for the person's own (localefmt.language()) when None. Read once each."""
    return _phrases(language or localefmt.language())


def command(text: str, language: str | None = None) -> str | None:
    """Which fixed command a phrase asks for ("help", "status", "agents", "breaks off"…), or None."""
    return phrases(language).command(text)


def help_text(language: str | None = None) -> str:
    """Everything Chatmon does without any AI, as Markdown, in the person's language (English where there's no
    translation)."""
    return phrases(language).help()


# -- telling what's for the AI


def reminder_or_question(rest: str) -> bool:
    """"remind me how decorators work" is a question for the AI, not a reminder without a time."""
    first = re.match(r"\w+", rest.strip().casefold())
    return "?" in rest or (bool(first) and first.group(0) in phrases().remind_me_questions)


@dataclass
class Asked:
    """Something about notes, the stopwatch or reminders: what (`kind`) and with what (`arg`)."""

    kind: str
    arg: str = ""


_KEPT = ("notes", "clear notes", "stopwatch", "stop stopwatch", "reminders", "clear reminders")


def parse_kept(text: str) -> Asked | None:
    """Notes, the stopwatch and reminders, which the app keeps."""
    book = phrases()
    found = book.template(text)
    # Only "note: ..." (or "add a note: ..."), and never something asked: "Note: I use Python 3.12. Why does
    # asyncio fail?" is a question for the AI, and mustn't be kept in a file instead.
    if found and not (found[0] == "note" and ("?" in found[1] or book.asks(found[1]) or reminder_or_question(found[1]))):
        return Asked(*found)
    kind = book.command(text)
    return Asked(kind) if kind in _KEPT else None


# -- AI agents at a glance

_STATE_ORDER = {"needs-you": 0, "working": 1}


def span(seconds: float) -> str:
    """How long something has gone on: "under a minute", "5 min", "1 h 5 min", "3 days"."""
    s = int(max(0, seconds))
    if s < 60:
        return "under a minute"
    if s < 3600:
        return f"{s // 60} min"
    if s < 86400:
        hours, minutes = divmod(s // 60, 60)
        return f"{hours} h {minutes} min" if minutes else f"{hours} h"
    days = s // 86400
    return f"{days} day{'s' if days != 1 else ''}"


def agents_report(agents: Mapping[str, tuple[str, float]], now: float, label: Callable[[str], str] | None = None, markdown: bool = True) -> str:
    """How the AI agents stand, for the *agents* command (Markdown) and `chatmon status` (plain): `agents` maps
    each agent's name to (state, since), as the app keeps them, `since` on the same clock as `now`. The ones
    that need you come first, longest waiting first; then the ones working."""
    label = label or (lambda name: name[:1].upper() + name[1:])
    if not agents:
        return "No AI agent is working or waiting for you."
    lines = []
    for name, (state, since) in sorted(agents.items(), key=lambda item: (_STATE_ORDER.get(item[1][0], 2), item[1][1], item[0])):
        who = f"**{label(name)}**" if markdown else label(name)
        if state == "needs-you":
            line = f"{who} needs you (waiting {span(now - since)})"
        elif state == "working":
            line = f"{who} is working ({span(now - since)} so far)"
        else:
            line = f"{who}: {state}"
        lines.append(f"- {line}" if markdown else line)
    return "\n".join(lines)


def answer(text: str, now: datetime) -> str | None:
    """What Chatmon can answer by itself, without any AI: Markdown, or None to leave it for the AI."""
    t = text.strip()
    for found in (when(t, now), chance(t), password(t), convert(t)):
        if found:
            return found
    m = re.fullmatch(r"(?:calc(?:ulate)?|compute|what(?:'s| is)|evaluate|=)\s*(.+)", t, re.I)
    expression = m.group(1) if m else t
    try:
        value = calculate(expression)
    except OverflowError:
        return "That's too big a number for me."
    except ValueError as exc:
        return f"Hmm: {exc}." if m or re.search(r"\d", expression) else None
    if value is None:
        return None
    if not m and not re.search(r"\d\s*[-+*/^%×÷]|[a-z]\(|\)", expression):  # a bare "42" isn't asking for anything
        return None
    return f"{expression.strip().rstrip('=?').strip()} = **{show_number(value)}**"
