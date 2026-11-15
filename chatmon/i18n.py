"""Every word Chatmon shows, in the person's language when Chatmon has a translation for it, and otherwise in
English, the language it's written in.

Marking a string:

- `_("Couldn't start {program}.").format(program=name)`: a whole sentence, with named placeholders, never pieced
  together from fragments, so a translator can put the words in their language's order.
- `ngettext("{n} reminder", "{n} reminders", n).format(n=n)`: a sentence that changes with a number. Languages
  have from one to six plural forms, so never `"s" if n != 1`.
- `join(items)`: "tacos, sushi and pizza", a list in a sentence.
- `N_("…")`: a string in a table built as its module is imported. The language is chosen after the modules load,
  so it's translated where it's shown: `_(TABLE[key])`.

Not marked: anything written to a log, config keys, command-line flags, protocol strings, model and product names,
the offline commands' phrases (per-language data in phrases/), and anything sent to a brain.

A translation is one gettext .po file in chatmon/locale/, named for its language ("de.po", "pt_BR.po"), made from
the template there, chatmon.pot (packaging/extract_strings.py writes it). Chatmon reads the .po file itself and
hands it to the standard library's gettext for the lookups and plural rules: no build step, no new dependency.
An entry that's fuzzy, empty, or uses a placeholder its English doesn't have is left out, so English shows in its
place: a slip in a translation never stops a sentence being shown. A file that can't be read at all counts as not
there.

`setup()` chooses the language once, as Chatmon starts and before any window is built: the person's own choice
(the `language` setting), or else the first of the system's preferred languages that has a translation; English
when none has. It loads Qt's own translation of its buttons and dialogs for that language, and `localefmt` and the
offline phrases follow the choice. A language the person chose also becomes Qt's default locale, so times and
dates follow it; otherwise they keep the system's regional format.
"""

from __future__ import annotations

import gettext
import io
import logging
import os
import re
import string
import struct
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from . import localefmt

logger = logging.getLogger(__name__)

LOCALE = Path(__file__).resolve().parent / "locale"
SOURCE = "en"  # the language the strings are written in: always there, and never a file
SETTING = "language"  # config.toml's key: a language code, such as "de" or "pt_BR"; empty follows the system

_catalog: gettext.NullTranslations = gettext.NullTranslations()
_language = SOURCE
_qt_translator: Any = None  # the QTranslator holding Qt's own words, while it's installed
_default_before: Any = None  # Qt's default QLocale before a chosen language replaced it


def _(message: str) -> str:
    """`message` in the chosen language, or as it is when there's no translation for it."""
    return _catalog.gettext(message)


def ngettext(singular: str, plural: str, n: int) -> str:
    """The form of a sentence for the number `n`, in the chosen language (English: `singular` for 1, `plural`
    otherwise). The number goes in through a placeholder: `ngettext("{n} day", "{n} days", n).format(n=n)`."""
    return _catalog.ngettext(singular, plural, n)


def N_(message: str) -> str:  # gettext's own name for it, which translators' tools know
    """Marks `message` for the template and gives it back untranslated: for a table built at import, before the
    language is chosen. Translate it where it's shown, with `_()`."""
    return message


def join(items: Iterable[str]) -> str:
    """"tacos", "tacos and sushi", "tacos, sushi and pizza": a list in a sentence, as the language writes one."""
    listed = list(items)
    if not listed:
        return ""
    text = listed[0]
    for item in listed[1:-1]:
        # Translators: a list of three or more, up to its last item: "tacos, sushi" in "tacos, sushi and pizza".
        text = _("{list}, {item}").format(list=text, item=item)
    if len(listed) > 1:
        # Translators: a list's last item: "tacos and sushi", "tacos, sushi and pizza".
        text = _("{list} and {last}").format(list=text, last=listed[-1])
    return text


def either(items: Iterable[str]) -> str:
    """"Yes", "Yes or No", "Yes or No or Later": choices in a sentence, any one of them."""
    listed = list(items)
    text = listed[0] if listed else ""
    for item in listed[1:]:
        # Translators: one more choice: "“Yes” or “No”", "“Yes” or “No” or “Later”".
        text = _("{choices} or {choice}").format(choices=text, choice=item)
    return text


def language() -> str:
    """The language chosen by `setup`, as "en", "de" or "pt_BR"; English before it's called."""
    return _language


def available(folder: Path = LOCALE) -> list[str]:
    """The languages Chatmon can be shown in: English, then one for each translation, as "de" or "pt_BR"."""
    found = sorted(p.stem for p in folder.glob("*.po") if _TAG.fullmatch(p.stem))
    return [SOURCE, *(code for code in found if code != SOURCE)]


# -- choosing the language

# A language tag as systems and people write one: "de", "pt_BR", "pt-BR", "zh-Hant-TW", "de_DE.UTF-8@euro". Only
# the letters and digits it matches ever become part of a file's name.
_TAG = re.compile(r"([A-Za-z]{2,3})(?:[-_]([A-Za-z]{4}))?(?:[-_]([A-Za-z]{2}|\d{3}))?")


def candidates(tag: str) -> list[str]:
    """The names a translation of `tag` may have, most particular first: "pt-BR" may be pt_BR.po, then pt.po, and
    "zh-Hant-TW" zh_TW.po, zh_Hant.po, then zh.po. Nothing for what isn't a language tag ("C", "POSIX", "")."""
    found = _TAG.match(tag.strip())
    if found is None or found.group(0).upper() in ("C", "POSIX") or tag.strip()[found.end():][:1] not in ("", ".", "@", "-", "_"):
        return []  # not a tag, or a word that starts like one ("klingon")
    lang, script, region = found.group(1).lower(), found.group(2), found.group(3)
    names = [f"{lang}_{region.upper()}"] if region else []
    if script:
        names.append(f"{lang}_{script.title()}")
    return [*names, lang]


def _environment() -> list[str]:
    """The preferred languages a Unix desktop gives programs, as gettext reads them."""
    for name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(name, "")
        if value:
            return value.split(":") if name == "LANGUAGE" else [value]
    return []


def _windows() -> list[str]:
    """The display languages chosen in Windows' settings, most preferred first: what Qt's uiLanguages() reads
    there, for when Qt isn't loaded (the command line)."""
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes

    mui_language_name = 0x8
    count, size = wintypes.ULONG(0), wintypes.ULONG(0)
    preferred = ctypes.windll.kernel32.GetUserPreferredUILanguages
    if not preferred(mui_language_name, ctypes.byref(count), None, ctypes.byref(size)) or not size.value:
        return []
    names = ctypes.create_unicode_buffer(size.value)
    if not preferred(mui_language_name, ctypes.byref(count), names, ctypes.byref(size)):
        return []
    return [name for name in ctypes.wstring_at(names, size.value).split("\0") if name]


def preferred() -> list[str]:
    """The system's preferred languages, most preferred first: Qt's when it's loaded, otherwise Windows' own, or
    the environment's (LANGUAGE, LC_ALL, LC_MESSAGES, LANG) elsewhere."""
    qtcore = sys.modules.get("PyQt6.QtCore")
    if qtcore is not None:
        return list(qtcore.QLocale.system().uiLanguages())
    return _windows() if sys.platform == "win32" else _environment()


def choose(wanted: list[str], folder: Path = LOCALE) -> tuple[str, gettext.NullTranslations]:
    """The first language in `wanted` that has a translation which reads, with its catalog; English, with none,
    when an English one comes first or none has."""
    for tag in wanted:
        for code in candidates(tag):
            path = folder / f"{code}.po"
            if path.is_file():
                try:
                    return code, load_catalog(path)
                except (OSError, UnicodeDecodeError, CatalogError) as exc:
                    logger.debug("couldn't read the translation %s: %s", path, exc)
                    continue  # a translation that can't be read counts as not there
            if code == SOURCE:
                return SOURCE, gettext.NullTranslations()
    return SOURCE, gettext.NullTranslations()


def setup(choice: str | None = None, folder: Path = LOCALE) -> str:
    """Choose the language every string is shown in, and return it ("en", "de", "pt_BR").

    `choice` is the person's own (the `language` setting), or None or "" to follow the system's preferred
    languages. Call it once, after the QApplication exists and before any window is built: strings already shown
    stay as they were. Calling it again replaces the earlier choice."""
    global _catalog, _language, _default_before
    reset()
    _language, _catalog = choose([choice] if choice else preferred(), folder)
    localefmt.follow(_language)
    qtcore = sys.modules.get("PyQt6.QtCore")
    if qtcore is None:
        return _language
    asked = candidates(choice) if choice else []
    if asked:
        # The person's choice of language decides times and dates too, unless it's the system's own language
        # already: English chosen on a British system keeps its day-month dates.
        wanted = qtcore.QLocale(asked[0])
        if wanted.language() != qtcore.QLocale.system().language():
            _default_before = qtcore.QLocale()
            qtcore.QLocale.setDefault(wanted)
    _install_qt_translation(qtcore, _language)
    return _language


def _install_qt_translation(qtcore: Any, code: str) -> None:
    """Qt's own words (its dialogs' buttons, a text field's menu) in the chosen language, from the translations
    Qt ships, when there's an application to give them to. English is Qt's own language: nothing to load."""
    global _qt_translator
    app = qtcore.QCoreApplication.instance()
    if app is None or code == SOURCE:
        return
    translator = qtcore.QTranslator()
    folder = qtcore.QLibraryInfo.path(qtcore.QLibraryInfo.LibraryPath.TranslationsPath)
    if translator.load(qtcore.QLocale(code), "qtbase", "_", folder) and app.installTranslator(translator):
        _qt_translator = translator


def reset() -> None:
    """Back to English, as before `setup`: Qt's translation taken out, Qt's default locale as it was, and
    `localefmt` and the offline phrases following the system again."""
    global _catalog, _language, _qt_translator, _default_before
    _catalog, _language = gettext.NullTranslations(), SOURCE
    localefmt.follow(None)
    qtcore = sys.modules.get("PyQt6.QtCore")
    if qtcore is None:
        return
    app = qtcore.QCoreApplication.instance()
    if _qt_translator is not None and app is not None:
        app.removeTranslator(_qt_translator)
    _qt_translator = None
    if _default_before is not None:
        qtcore.QLocale.setDefault(_default_before)
        _default_before = None


# -- reading a .po file


class CatalogError(ValueError):
    """A .po file that can't be read: its line number and what's wrong there."""


_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "a": "\a", "b": "\b", "f": "\f", "v": "\v"}
_ESCAPE = re.compile(r"\\(.)")
_STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')
_KEYWORD = re.compile(r"(msgctxt|msgid_plural|msgid|msgstr(?:\[(\d+)\])?)\s+(\".*\")$")


def _unquote(token: str, line: int) -> str:
    """A .po string's text: C's quoting, with its backslash escapes."""
    found = _STRING.fullmatch(token)
    if found is None:
        raise CatalogError(f"line {line}: not a quoted string, or a quote in it isn't escaped")

    def escape(char: re.Match[str]) -> str:
        if char.group(1) not in _ESCAPES:
            raise CatalogError(f"line {line}: unknown escape {char.group(0)}")
        return _ESCAPES[char.group(1)]

    return _ESCAPE.sub(escape, found.group(1))


class _Entry:
    def __init__(self) -> None:
        self.fields: dict[str, str] = {}  # "msgctxt", "msgid", "msgid_plural", "msgstr", "msgstr[0]"…
        self.fuzzy = False
        self.last: str | None = None  # the field a continuation line adds to


def read_po(text: str) -> dict[str, str]:
    """A .po file's translations, keyed the way gettext's .mo files key them: the English, "context\\x04English"
    for a string with a context, and "singular\\0plural" for a plural, whose forms are joined by "\\0" too.

    The header (the entry for "") is kept, and so is every entry with a translation; fuzzy, obsolete and empty
    ones are left out, and so is one whose translation names a placeholder its English doesn't. A line that isn't
    .po raises CatalogError."""
    entries: list[_Entry] = []
    entry = _Entry()
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#~"):
            if entry.fields:
                entries.append(entry)
                entry = _Entry()
            continue
        if line.startswith("#"):
            if entry.fields and entry.last is not None and entry.last.startswith("msgstr"):
                entries.append(entry)  # comments start the next entry
                entry = _Entry()
            if line.startswith("#,") and "fuzzy" in (flag.strip() for flag in line[2:].split(",")):
                entry.fuzzy = True
            continue
        if line.startswith('"'):
            if entry.last is None:
                raise CatalogError(f"line {number}: a string with no msgid or msgstr before it")
            entry.fields[entry.last] += _unquote(line, number)
            continue
        found = _KEYWORD.match(line)
        if found is None:
            raise CatalogError(f"line {number}: not a line of a .po file")
        keyword = found.group(1)
        if keyword in ("msgctxt", "msgid") and entry.last is not None and entry.last.startswith("msgstr"):
            entries.append(entry)  # an entry with no blank line before it
            entry = _Entry()
        if keyword in entry.fields:
            raise CatalogError(f"line {number}: {keyword} twice in one entry")
        entry.fields[keyword] = _unquote(found.group(3), number)
        entry.last = keyword
    if entry.fields:
        entries.append(entry)

    catalog: dict[str, str] = {}
    for e in entries:
        key, value = _translation(e)
        if key is not None and value is not None:
            catalog[key] = value
    return catalog


def _placeholders(text: str) -> set[str] | None:
    """The names of a brace-format string's placeholders, or None when it isn't one."""
    try:
        return {name for _literal, name, _spec, _conversion in string.Formatter().parse(text) if name is not None}
    except ValueError:
        return None


def _translation(e: _Entry) -> tuple[str | None, str | None]:
    """An entry's .mo key and value, or (None, None) when it's left out."""
    if "msgid" not in e.fields:
        raise CatalogError("an entry with no msgid")
    msgid = e.fields["msgid"]
    if msgid == "":
        return "", e.fields.get("msgstr", "")  # the header, fuzzy or not: its Plural-Forms are needed
    if e.fuzzy:
        return None, None
    plural = e.fields.get("msgid_plural")
    if plural is None:
        forms = [e.fields.get("msgstr", "")]
        key = msgid
    else:
        indices = sorted(int(k[7:-1]) for k in e.fields if k.startswith("msgstr["))
        if not indices or indices != list(range(len(indices))):
            return None, None
        forms = [e.fields[f"msgstr[{i}]"] for i in indices]
        key = f"{msgid}\0{plural}"
    if not all(forms):
        return None, None
    english = _placeholders(msgid)
    if plural is not None:
        other = _placeholders(plural)
        english = None if english is None or other is None else english | other
    if english is not None:
        for form in forms:
            names = _placeholders(form)
            if names is None or not names <= english:
                return None, None  # .format() would raise, or show a hole
    if "msgctxt" in e.fields:
        key = f"{e.fields['msgctxt']}\x04{key}"
    return key, "\0".join(forms)


_PLURAL_FORMS = re.compile(r"^Plural-Forms:[^\n]*$", re.MULTILINE | re.IGNORECASE)


def _mo(catalog: dict[str, str]) -> bytes:
    """`catalog` (from read_po) as the bytes of a GNU .mo file, in UTF-8, for gettext.GNUTranslations to read.
    The header keeps only the file's Plural-Forms: the text was read as UTF-8, whatever it claims."""
    plural_forms = _PLURAL_FORMS.search(catalog.get("", ""))
    header = "Content-Type: text/plain; charset=UTF-8\n" + (plural_forms.group(0) + "\n" if plural_forms else "")
    pairs = sorted((k.encode("utf-8"), v.encode("utf-8")) for k, v in {**catalog, "": header}.items())
    count = len(pairs)
    keys_at = 7 * 4
    values_at = keys_at + count * 8
    data_at = values_at + count * 8
    keys, values, data = [], [], bytearray()
    for key, _value in pairs:
        keys.append((len(key), data_at + len(data)))
        data += key + b"\0"
    for _key, value in pairs:
        values.append((len(value), data_at + len(data)))
        data += value + b"\0"
    out = struct.pack("<7I", 0x950412DE, 0, count, keys_at, values_at, 0, 0)
    out += b"".join(struct.pack("<2I", *k) for k in keys) + b"".join(struct.pack("<2I", *v) for v in values)
    return out + bytes(data)


def load_catalog(path: Path) -> gettext.GNUTranslations:
    """A .po file, ready to translate with. CatalogError when it can't be read as one, or its Plural-Forms
    isn't a formula gettext accepts; OSError and UnicodeDecodeError when it can't be read at all."""
    catalog = read_po(path.read_text(encoding="utf-8"))
    try:
        return gettext.GNUTranslations(io.BytesIO(_mo(catalog)))
    except (ValueError, SyntaxError, RecursionError) as exc:  # gettext checks the Plural-Forms formula
        raise CatalogError(f"{path.name}: {exc}") from None
