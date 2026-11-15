"""The Chats window and the light listing it reads (M7-09; M0's note 5). The companion's side (carrying on, renaming,
deleting) is in test_app_smoke.py and test_app_m7.py."""

import json

import pytest

from chatmon import chats
from chatmon.chatswin import ChatsWindow


def chat(title: str, *said: str, at: float = 1000.0, pinned: bool = False) -> chats.Chat:
    c = chats.Chat(title=title, pinned=pinned)
    for i, text in enumerate(said or (title,)):
        c.add(chats.Message("user" if i % 2 == 0 else "assistant", text, at=at + i))
    return c


@pytest.fixture
def book(tmp_path):
    b = chats.ChatBook(tmp_path / "chats")
    b.save(chat("Cat names", "Name a cat", "Mochi, or Biscuit", at=1000))
    b.save(chat("Rust lifetimes", "What's 'a?", "A lifetime parameter.", at=2000))
    b.save(chat("Groceries", "milk, eggs", at=3000, pinned=True))
    return b


def test_the_listing_has_titles_times_and_pins_never_messages(book):
    listed = book.listing()
    assert [(c.title, c.pinned) for c in listed] == [("Groceries", True), ("Rust lifetimes", False), ("Cat names", False)]
    assert all(not hasattr(c, "messages") for c in listed) and listed[1].updated == 2001
    assert len(book.listing(limit=2)) == 2


def test_the_listing_reads_each_file_once_while_it_doesnt_change(book, monkeypatch):
    read = []
    real = chats.from_json
    monkeypatch.setattr(chats, "from_json", lambda data: read.append(data.get("title")) or real(data))
    book.listing()
    assert sorted(read) == ["Cat names", "Groceries", "Rust lifetimes"]
    read.clear()
    book.listing()
    assert read == []  # nothing changed: nothing read again
    again = next(c for c in [book.load(x.id) for x in book.listing()] if c.title == "Cat names")
    read.clear()
    again.add(chats.Message("user", "and a dog?", at=4000))
    book.save(again)
    assert book.listing()[1].title == "Cat names" and read.count("Cat names") >= 1 and "Groceries" not in read


def test_a_file_that_isnt_a_chat_or_says_nothing_isnt_listed(book):
    (book.root() / ("0" * 32 + ".json")).write_text(json.dumps({"id": "0" * 32, "messages": []}), encoding="utf-8")
    (book.root() / ("1" * 32 + ".json")).write_text("not json", encoding="utf-8")
    assert [c.title for c in book.listing()] == ["Groceries", "Rust lifetimes", "Cat names"]


@pytest.fixture
def window(qapp, book):
    w = ChatsWindow(book)
    w.refresh(current="", kept=True)
    w.show()
    yield w
    w.close()
    w.deleteLater()


def titles(w) -> list[str]:
    return [w.list.item(i).text().split("   ·")[0] for i in range(w.list.count())]


def test_the_window_lists_every_chat_and_searches_titles_then_words_inside(window):
    from app_harness import until

    w = window
    assert titles(w) == ["★ Groceries", "Rust lifetimes", "Cat names"]
    w.search.setText("rust")
    assert titles(w) == ["Rust lifetimes"]  # by title, at once
    w.search.setText("biscuit")
    assert titles(w) == [] and "Looking inside" in w.empty.text()
    assert until(lambda: titles(w) == ["Cat names"], 3)  # and by the words in it, a moment later
    w.search.setText("biscuit mochi")
    assert until(lambda: titles(w) == ["Cat names"], 3)  # every word
    w.search.setText("nowhere")
    assert until(lambda: w.empty.text() == "No chat has those words.", 3)
    w.search.clear()
    assert len(titles(w)) == 3


def test_the_windows_buttons_say_what_was_chosen(window, book):
    w = window
    said = []
    for name in ("carry_on", "rename", "instructions", "export", "delete"):
        getattr(w, name).connect(lambda chat_id, name=name: said.append((name, chat_id)))
    w.pin.connect(lambda chat_id, on: said.append(("pin", chat_id, on)))
    w.list.setCurrentRow(1)  # Rust lifetimes
    rust = next(c.id for c in book.listing() if c.title == "Rust lifetimes")
    for name in ("carry_on", "rename", "instructions", "pin", "export", "delete"):
        w.buttons[name].click()
    assert said == [("carry_on", rust), ("rename", rust), ("instructions", rust), ("pin", rust, True), ("export", rust), ("delete", rust)]
    w.list.setCurrentRow(0)
    assert w.buttons["pin"].text() == "Unpin"


def test_the_chat_youre_in_is_marked_and_unkept_chats_are_said(window, book):
    w = window
    groceries = book.listing()[0].id
    w.refresh(current=groceries, kept=True)
    assert w.list.item(0).text().endswith("(this one)")
    w.refresh(current=groceries, kept=False)
    assert w.list.count() == 0 and "aren't being kept" in w.empty.text() and not w.buttons["carry_on"].isEnabled()


def test_chat_times_follow_the_locale(qapp):
    """M5's note: "today 3:04 PM" was always a 12-hour clock in English; it follows the locale now."""
    from datetime import datetime

    from PyQt6.QtCore import QLocale

    from chatmon import localefmt

    now = datetime(2026, 11, 14, 15, 4).timestamp()
    earlier = datetime(2026, 11, 14, 9, 30).timestamp()
    try:
        localefmt.set_locale(QLocale(QLocale.Language.German, QLocale.Country.Germany))
        assert chats.when(earlier, now) == "today 09:30"
        localefmt.set_locale(None)  # plain English
        assert chats.when(earlier, now) == "today 9:30 AM"
    finally:
        localefmt.set_locale()
