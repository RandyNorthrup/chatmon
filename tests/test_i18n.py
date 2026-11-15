"""Translation (M8-01): every string Chatmon shows goes through gettext, a translation is one .po file, the
language follows the person's choice and then the system's, Qt's own words follow it, a slip in a translation
shows English rather than nothing, and the template can't fall behind the code.

Only English ships, so every catalog here is a throwaway one written in the test's own folder."""

import importlib.util
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from chatmon import i18n, localefmt, offline

REPO = Path(__file__).resolve().parent.parent

HEADER = """\
msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\\n"
"""


def catalog(folder: Path, name: str, body: str, header: str = HEADER) -> Path:
    """A .po file named `name` in `folder`, from a header and entries written as in a real one."""
    path = folder / f"{name}.po"
    path.write_text(header + "\n" + textwrap.dedent(body), encoding="utf-8")
    return path


GERMAN = """\
    msgid "Stop"
    msgstr "Anhalten"

    #, python-brace-format
    msgid "{brain} is answering… {seconds} s"
    msgstr "{brain} antwortet… {seconds} s"

    msgid "your settings"
    msgstr "deine Einstellungen"

    msgid "{n} note"
    msgid_plural "{n} notes"
    msgstr[0] "{n} Notiz"
    msgstr[1] "{n} Notizen"

    msgid "{n} reminder"
    msgid_plural "{n} reminders"
    msgstr[0] "{n} Erinnerung"
    msgstr[1] "{n} Erinnerungen"

    msgid "{list}, {item}"
    msgstr "{list}, {item}"

    msgid "{list} and {last}"
    msgstr "{list} und {last}"

    msgid "Brought back {what}."
    msgstr "Zurückgeholt: {what}."
"""


@pytest.fixture(autouse=True)
def english_after():
    """Each test leaves Chatmon in English, as every other test file expects it."""
    yield
    i18n.reset()


def extractor():
    spec = importlib.util.spec_from_file_location("chatmon_extract_strings", REPO / "packaging" / "extract_strings.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # its dataclasses look their module up by name
    spec.loader.exec_module(module)
    return module


# -- English, the language it's written in


def test_before_a_language_is_chosen_every_string_is_its_english():
    assert i18n.language() == "en"
    assert i18n._("Stop") == "Stop"
    assert [i18n.ngettext("{n} note", "{n} notes", n).format(n=n) for n in (0, 1, 2)] == ["0 notes", "1 note", "2 notes"]
    assert [i18n.join(items) for items in ([], ["tacos"], ["tacos", "sushi"], ["tacos", "sushi", "pizza"])] == [
        "", "tacos", "tacos and sushi", "tacos, sushi and pizza",
    ]
    assert [i18n.either(items) for items in ([], ["“Yes”"], ["“Yes”", "“No”", "“Later”"])] == ["", "“Yes”", "“Yes” or “No” or “Later”"]


# -- a translation reaches what's shown


def test_a_translated_sentence_and_its_plurals_reach_the_ask_box_and_whats_missing_stays_english(qapp, tmp_path):
    import time

    from chatmon import backup
    from chatmon.bubble import AskBox

    catalog(tmp_path, "de", GERMAN)
    assert i18n.setup("de", tmp_path) == "de"
    box = AskBox()
    try:
        box.set_busy("Claude", time.monotonic() - 12.2)
        assert box.stop_button.text() == "Anhalten"
        assert box.busy_label.text() == "Claude antwortet… 12 s"
        assert box.history_button.text() == "History", "a string the translation leaves out shows in English"
        assert box.reset_button.text() == "New chat"
    finally:
        box.set_busy(None)
        box.deleteLater()
    one = backup.Contents(settings={"size": 120}, notes=[{"text": "milk", "at": 0}], reminders=[{"due": 1, "text": "x"}] * 2)
    assert one.summary() == "deine Einstellungen, 1 Notiz und 2 Erinnerungen"
    assert backup.Contents(chats=[], notes=[{"text": "a", "at": 0}] * 3).summary() == "3 Notizen"
    assert backup.Contents(memory=[backup.Item("I use Arch", 0)]).summary() == "1 thing remembered", "no translation: English, with its plural"
    i18n.reset()
    assert one.summary() == "your settings, 1 note and 2 reminders"


def test_a_slip_in_a_translation_shows_english_and_never_a_hole(tmp_path):
    catalog(tmp_path, "de", """\
        #, fuzzy
        msgid "Stop"
        msgstr "Halt"

        msgid "Close"
        msgstr ""

        #, python-brace-format
        msgid "Remove {attachment}"
        msgstr "{datei} entfernen"

        msgid "{n} note"
        msgid_plural "{n} notes"
        msgstr[0] "{n} Notiz"

        msgid "{n} chat"
        msgid_plural "{n} chats"
        msgstr[0] "{n} Chat"
        msgstr[1] ""

        #~ msgid "Undo"
        #~ msgstr "Rückgängig"

        msgid "Redo"
        msgstr "Wieder\\nholen"
    """)
    i18n.setup("de", tmp_path)
    assert i18n._("Stop") == "Stop", "a fuzzy entry isn't a translation yet"
    assert i18n._("Close") == "Close", "an empty one isn't either"
    assert i18n._("Remove {attachment}").format(attachment="a.txt") == "Remove a.txt", "a placeholder the English hasn't would raise"
    assert i18n.ngettext("{n} note", "{n} notes", 2).format(n=2) == "2 notes", "a plural missing a form"
    assert i18n.ngettext("{n} chat", "{n} chats", 2).format(n=2) == "2 chats"
    assert i18n._("Undo") == "Undo", "an obsolete entry"
    assert i18n._("Redo") == "Wieder\nholen", "escapes are read as C writes them"


@pytest.mark.parametrize(
    "text",
    [
        'msgid "Stop"\nmsgstr "Anhalten\n',  # an unclosed string
        'msgid "Stop"\nmsgstr "An"halten"\n',  # a quote not escaped
        'msgid "Stop"\nmsgstr "Anhalten\\q"\n',  # an escape C hasn't
        'msgid "Stop"\nmsgstr "Anhalten"\nmsgstr "Halt"\n',  # two translations
        'msgstr "Anhalten"\n',  # no English
        'Stop = Anhalten\n',  # not .po
    ],
)
def test_a_file_that_isnt_a_catalog_leaves_english(tmp_path, text):
    (tmp_path / "de.po").write_text(HEADER + "\n" + text, encoding="utf-8")
    with pytest.raises(i18n.CatalogError):
        i18n.load_catalog(tmp_path / "de.po")
    assert i18n.setup("de", tmp_path) == "en" and i18n._("Stop") == "Stop"


def test_a_plural_rule_gettext_refuses_or_bytes_that_arent_utf8_leave_english(tmp_path):
    catalog(tmp_path, "de", 'msgid "Stop"\nmsgstr "Anhalten"\n', header=HEADER.replace("(n != 1)", "EXPRESSION"))
    assert i18n.setup("de", tmp_path) == "en"
    (tmp_path / "fr.po").write_bytes(HEADER.encode() + b'\nmsgid "Stop"\nmsgstr "Arr\xeat"\n')
    assert i18n.setup("fr", tmp_path) == "en" and i18n._("Stop") == "Stop"


# -- which language


def test_the_language_is_the_persons_choice_else_the_first_preferred_one_with_a_translation(tmp_path):
    catalog(tmp_path, "de", 'msgid "Stop"\nmsgstr "Anhalten"\n')
    catalog(tmp_path, "pt_BR", 'msgid "Stop"\nmsgstr "Parar"\n')
    catalog(tmp_path, "pt", 'msgid "Stop"\nmsgstr "Pare"\n')
    assert i18n.available(tmp_path) == ["en", "de", "pt", "pt_BR"]

    def chosen(wanted):
        return i18n.choose(wanted, tmp_path)[0]

    assert chosen(["fr_FR", "de_DE", "en_US"]) == "de", "French has none: the next one that has"
    assert chosen(["en_GB", "de_DE"]) == "en", "English first: English, the language it's written in"
    assert chosen(["pt-BR"]) == "pt_BR" and chosen(["pt_PT"]) == "pt" and chosen(["pt-Latn-BR"]) == "pt_BR"
    assert chosen(["de_DE.UTF-8@euro"]) == "de"
    assert chosen(["C", "POSIX", "", "klingon", "../de", "fr"]) == "en", "what isn't a language never names a file"
    assert i18n.setup("pt_BR", tmp_path) == "pt_BR" and i18n._("Stop") == "Parar"
    assert i18n.setup("", tmp_path) in i18n.available(tmp_path), "empty: the system's own"


def test_the_command_line_reads_the_same_preferred_languages_as_qt(tmp_path):
    """Without Qt (the command line), the system's preferred languages come from Windows itself, or LANGUAGE,
    LC_ALL, LC_MESSAGES and LANG elsewhere: the same first choice Qt makes."""
    if sys.platform == "darwin":
        pytest.skip("macOS: Qt reads the system's language list, a command line reads LANG")
    code = (
        "import sys; from chatmon import i18n; plain = i18n.preferred(); assert 'PyQt6.QtCore' not in sys.modules\n"
        "from PyQt6.QtCore import QLocale; qt = i18n.preferred(); print(plain[:1], qt[:1])\n"
        "assert i18n.candidates(plain[0])[0] == i18n.candidates(qt[0])[0], (plain, qt)\n"
    )
    env = None
    if sys.platform != "win32":
        import os

        env = {**os.environ, "LANGUAGE": "", "LC_ALL": "", "LC_MESSAGES": "", "LANG": "de_DE.UTF-8"}
    done = subprocess.run([sys.executable, "-c", code], cwd=REPO, env=env, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr


def test_localefmt_and_the_offline_phrases_follow_the_language_chosen(tmp_path):
    catalog(tmp_path, "pt_BR", 'msgid "Stop"\nmsgstr "Parar"\n')
    localefmt.set_locale()
    before = localefmt.language()
    i18n.setup("pt_BR", tmp_path)
    assert localefmt.language() == "pt_BR"
    assert offline.phrases() is offline.phrases("pt_BR"), "the phrases asked for are Brazilian Portuguese (English, as none ship)"
    assert offline.phrases().language == "en"
    i18n.reset()
    assert localefmt.language() == before


def test_qts_own_words_and_a_chosen_languages_dates_follow_it(qapp, tmp_path):
    from PyQt6.QtCore import QCoreApplication, QLibraryInfo, QLocale

    if not (Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)) / "qtbase_de.qm").is_file():
        pytest.skip("Qt's own translations aren't installed (a separate package on some distributions)")
    before = QLocale()
    catalog(tmp_path, "de", 'msgid "Stop"\nmsgstr "Anhalten"\n')
    assert QCoreApplication.translate("QPlatformTheme", "Cancel") == "Cancel"
    localefmt.set_locale()
    try:
        i18n.setup("de", tmp_path)
        assert QCoreApplication.translate("QPlatformTheme", "Cancel") == "Abbrechen"
        if QLocale.system().language() != QLocale.Language.German:
            assert QLocale().language() == QLocale.Language.German
            from datetime import time

            assert localefmt.time_of_day(time(15, 4)) == "15:04"
        i18n.reset()
        assert QCoreApplication.translate("QPlatformTheme", "Cancel") == "Cancel"
        assert QLocale() == before, "the default locale is put back"
    finally:
        i18n.reset()


def test_choosing_the_systems_own_language_keeps_its_regional_formats(qapp, tmp_path):
    from PyQt6.QtCore import QLocale

    before = QLocale()
    own = QLocale.system().name().split("_")[0]
    i18n.setup(own, tmp_path)
    assert QLocale() == before, "English chosen on a British system keeps its day-month dates"


# -- the template


def test_the_template_has_every_marked_string_and_reads_as_a_catalog():
    pot = REPO / "chatmon" / "locale" / "chatmon.pot"
    assert extractor().template(REPO) == pot.read_text(encoding="utf-8"), "run: python packaging/extract_strings.py"
    text = pot.read_text(encoding="utf-8")
    assert text.count("\nmsgid ") >= 2
    assert list(i18n.read_po(text)) == [""], "a template has nothing translated: only its header is read"


def test_the_extractor_finds_marked_strings_with_plurals_comments_and_formats():
    found, problems = extractor().scan(textwrap.dedent('''
        from .i18n import N_, _, ngettext

        TABLE = {"a": N_("Apple")}  # marked now, translated where shown


        def shown(n, key):
            # Translators: a count of files.
            text = ngettext("{n} file", "{n} files", n).format(n=n)
            return _("Done.") + text + _(TABLE[key]) + _("Say \\"hi\\"\\n")
    '''), "chatmon/x.py")
    assert problems == []
    assert [(f.msgid, f.plural, f.comment) for f in found] == [
        ("Apple", None, None), ("{n} file", "{n} files", "Translators: a count of files."), ("Done.", None, None), ('Say "hi"\n', None, None),
    ]


@pytest.mark.parametrize(
    "source, why",
    [
        ('def f(x):\n    return _(f"Hi {x}")\n', "plain string literals"),
        ('def f(x):\n    return _("Hi " + x)\n', "plain string literals"),
        ('def f(x):\n    return _("Hi {x}".format(x=x))\n', "plain string literals"),
        ('def f(n):\n    return ngettext("a", n, 2)\n', "plain string literals"),
        ('def f():\n    return N_(NAME)\n', "plain string literals"),
        ('def f():\n    return _("")\n', "header"),
        ('def f():\n    return _("a", "b")\n', "argument"),
        ('GREETING = _("Hi")\n', "imported"),
        ('class A:\n    LABEL = _("Hi")\n', "imported"),
        ('def f(label=_("Hi")):\n    return label\n', "imported"),
        ('@register(_("Hi"))\ndef f():\n    pass\n', "imported"),
        ('ROWS = [ngettext("a", "b", n) for n in range(3)]\n', "imported"),
        ('def f(pairs):\n    for _, b in pairs:\n        print(_("Hi"))\n', "throwaway"),
        ('def f(_):\n    return _("Hi")\n', "throwaway"),
    ],
)
def test_the_extractor_refuses_a_string_that_couldnt_be_translated(source, why):
    _found, problems = extractor().scan(source, "chatmon/x.py")
    assert len(problems) == 1 and why in problems[0] and problems[0].startswith("chatmon/x.py:"), problems


def test_the_extractor_lets_be_what_runs_later_and_throwaways_elsewhere():
    source = textwrap.dedent('''
        class A:
            def label(self):
                return _("Hi")

        def f(pairs):
            names = [a for _, a in pairs]  # a comprehension's names are its own
            return _("Hi"), lambda _=None: names

        def g():
            def inner(label=_("Hi")):
                return label
            return inner
    ''')
    found, problems = extractor().scan(source, "chatmon/x.py")
    assert problems == [] and len(found) == 3


def test_one_english_sentence_has_one_plural_everywhere(tmp_path):
    (tmp_path / "chatmon").mkdir()
    (tmp_path / "chatmon" / "a.py").write_text('def f(n):\n    return ngettext("{n} file", "{n} files", n)\n', encoding="utf-8")
    (tmp_path / "chatmon" / "b.py").write_text('def g():\n    return _("{n} file")\n', encoding="utf-8")
    module = extractor()
    with pytest.raises(module.ExtractError, match="two different plurals"):
        module.messages(tmp_path)
    (tmp_path / "chatmon" / "b.py").write_text('def g(n):\n    return ngettext("{n} file", "{n} files", n)\n', encoding="utf-8")
    [message] = module.messages(tmp_path)
    assert message.files == ["chatmon/a.py", "chatmon/b.py"]
    text = module.template(tmp_path)
    assert '#: chatmon/a.py chatmon/b.py\n#, python-brace-format\nmsgid "{n} file"\nmsgid_plural "{n} files"\nmsgstr[0] ""\nmsgstr[1] ""\n' in text


def test_the_template_check_fails_when_a_string_is_added_without_it(tmp_path, capsys):
    module = extractor()
    module.ROOT = tmp_path  # a little project of its own
    (tmp_path / "chatmon").mkdir()
    code = tmp_path / "chatmon" / "a.py"
    code.write_text('def f():\n    return _("One")\n', encoding="utf-8")
    assert module.main(["--check"]) == 1, "no template yet"
    assert module.main([]) == 0 and module.main(["--check"]) == 0
    code.write_text('def f():\n    return _("One"), _("Two")\n', encoding="utf-8")
    assert module.main(["--check"]) == 1 and "is out of date" in capsys.readouterr().err
    code.write_text('def f(x):\n    return _(f"One {x}")\n', encoding="utf-8")
    assert module.main(["--check"]) == 2, "a string that can't be translated stops it"
    done = subprocess.run([sys.executable, str(REPO / "packaging" / "extract_strings.py"), "--check"], cwd=REPO, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr  # and the real one is up to date
