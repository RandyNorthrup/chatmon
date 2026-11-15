"""Translation in the whole app (M8-01, phase B): a Companion whose settings choose a language speaks it in its menu,
its bubbles, the commands' replies and the status lines, English where the translation leaves something out, and
still sends its brains English.

Only English ships, so the catalog is a throwaway one written in the test's own folder."""

import textwrap

import pytest

from chatmon import i18n

HEADER = """\
msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\\n"
"""


@pytest.fixture(autouse=True)
def english_after():
    """Each test leaves Chatmon in English, as every other test file expects it."""
    yield
    i18n.reset()


def catalog(folder, name, body):
    """A .po file named `name` in `folder`, from the header and entries written as in a real one."""
    path = folder / f"{name}.po"
    path.write_text(HEADER + "\n" + textwrap.dedent(body), encoding="utf-8")
    return path


APP_GERMAN = """\
    #, python-brace-format
    msgid "Ask {name}…"
    msgstr "{name} fragen…"

    msgid "Settings…"
    msgstr "Einstellungen…"

    #, python-brace-format
    msgid "New look: {style}."
    msgstr "Neuer Look: {style}."

    msgid "fire"
    msgstr "Feuer"

    #, python-brace-format
    msgid "Cancelled {n} reminder."
    msgid_plural "Cancelled {n} reminders."
    msgstr[0] "{n} Erinnerung gelöscht."
    msgstr[1] "{n} Erinnerungen gelöscht."

    msgid "No reminders set"
    msgstr "Keine Erinnerungen"

    #, python-brace-format
    msgid "Reminder {when}: {text}"
    msgstr "Erinnerung {when}: {text}"

    #, python-brace-format
    msgid "in {n} min"
    msgid_plural "in {n} min"
    msgstr[0] "in {n} Min."
    msgstr[1] "in {n} Min."

    msgid "Electric penguin"
    msgstr "Elektrischer Pinguin"
"""


def test_the_app_itself_speaks_the_translation_and_english_where_it_has_none(tmp_path, monkeypatch):
    """A whole Companion, its settings choosing German, with a German catalog: its menu, a bubble it says, the
    commands' replies (with their plural) and the status lines are German, and what the catalog leaves out is English."""
    import time

    from app_harness import make_companion, until
    from chatmon import commands

    folder = tmp_path / "po"
    folder.mkdir()
    catalog(folder, "de", APP_GERMAN)
    real_setup = i18n.setup
    chosen = []
    # The Companion chooses the language itself as it starts (i18n.setup with its setting); here from this catalog.
    monkeypatch.setattr(i18n, "setup", lambda choice=None, folder_=None: chosen.append(choice) or real_setup("de", folder))
    companion = make_companion(tmp_path, monkeypatch)
    c = next(companion)
    try:
        assert chosen and i18n.language() == "de"
        c.menus.fill()
        shown = [a.text() for a in c.menus.menu.actions()]
        assert f"{c.name} fragen…" in shown and "Einstellungen…" in shown
        assert "Quit" in shown, "what the catalog leaves out is English"
        c._pick_style("fire")
        assert until(lambda: "Neuer Look: Feuer." in c.stage.bubble.doc.toPlainText())
        now = time.time()
        assert commands.status_lines(None, [], [], now, None) == ["- Keine Erinnerungen", "- Brain: none"]
        c.reminders.add(now + 600, "stretch")
        c.reminders.add(now + 900, "pasta")
        assert commands.status_lines(None, [], c.reminders.upcoming(), now, None)[0] == "- Erinnerung in 10 Min.: stretch"
        assert commands._clear_reminders(c, "") == "2 Erinnerungen gelöscht."
        c.reminders.add(now + 600, "tea")
        assert commands._clear_reminders(c, "") == "1 Erinnerung gelöscht."
        # What's sent to a brain stays English, the companion's kind included, though the menu shows it in German.
        from app_harness import PretendBrain

        PretendBrain(c, monkeypatch)
        systems = []
        monkeypatch.setattr(c.asker, "ask", lambda brain, system, history, question, timeout, attached=(): systems.append(system))
        assert c._companion().label == "Elektrischer Pinguin"
        c.open_ask()
        c.submit("Name a cat")
        assert until(lambda: systems) and "a small electric penguin desktop companion" in systems[0], systems
    finally:
        next(companion, None)
