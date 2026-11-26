"""Chats: every kept chat in a window, with search.

Like Settings, the window only shows and asks: it lists the chats (`ChatBook.listing`: titles, times and pins, never
the messages) and says what you chose (carry on, rename, instructions, pin, save, delete) through its signals; the
companion does it. Typing in the search field narrows the list by title at once, and a moment after you stop, by the
words in the chats themselves too. Reads happen in small batches so Qt can handle input between them; ChatBook
keeps only a bounded set of recently read conversations.
"""

from __future__ import annotations

from collections import deque

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QHideEvent
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from . import chats
from .i18n import N_, _
from .qtsignal import pyqtSignal

TITLE = N_("Chats")  # the window's title, shown as _(TITLE)
SEARCH_AFTER_MS = 300  # after the last key, the words inside chats are searched too
SEARCH_BATCH = 8  # conversations read before handing control back to Qt
MOST = 2000  # chats listed at most


def matches(chat: chats.Chat, words: list[str]) -> bool:
    """Every word is in the chat: its title, a question or an answer (any case)."""
    title = chat.title.casefold()
    missing = {word for word in words if word not in title}
    for message in chat.messages:
        if not missing:
            break
        text = message.text.casefold()
        missing = {word for word in missing if word not in text}
    return not missing


class ChatsWindow(QDialog):
    carry_on = pyqtSignal(str)
    rename = pyqtSignal(str)
    instructions = pyqtSignal(str)
    pin = pyqtSignal(str, bool)
    export = pyqtSignal(str)
    delete = pyqtSignal(str)

    def __init__(self, book: chats.ChatBook, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(_(TITLE))
        self.setMinimumSize(520, 460)
        self.book = book
        self.current = ""  # the chat you're in: marked in the list
        self._listed: list[chats.Listed] = []
        self._inside: set[str] | None = None  # chats whose words match the search (None: not looked yet)
        self._pending: deque[chats.Listed] = deque()
        self._found: set[str] = set()
        self.search = QLineEdit()
        self.search.setPlaceholderText(_("Search your chats"))
        self.search.setAccessibleName(_("Search your chats"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._typed)
        self.list = QListWidget()
        self.list.setAccessibleName(_("Your chats"))
        self.list.itemActivated.connect(lambda _item: self._chosen(self.carry_on))
        self.list.currentItemChanged.connect(lambda *_: self._enable())
        self.empty = QLabel()
        self.empty.setWordWrap(True)
        self.empty.setTextFormat(Qt.TextFormat.PlainText)
        self.empty.setStyleSheet("color: palette(placeholder-text);")
        self._later = QTimer(self)
        self._later.setSingleShot(True)
        self._later.setInterval(SEARCH_AFTER_MS)
        self._later.timeout.connect(self._search_inside)
        self._scan = QTimer(self)
        self._scan.timeout.connect(self._search_batch)
        buttons = QHBoxLayout()
        self.buttons: dict[str, QPushButton] = {}
        for name, label, act in (
            ("carry_on", _("Carry on"), lambda: self._chosen(self.carry_on)),
            ("rename", _("Rename…"), lambda: self._chosen(self.rename)),
            ("instructions", _("Instructions…"), lambda: self._chosen(self.instructions)),
            ("pin", _("Pin"), self._pin),
            ("export", _("Save as Markdown…"), lambda: self._chosen(self.export)),
            ("delete", _("Delete…"), lambda: self._chosen(self.delete)),
        ):
            button = QPushButton(label)
            button.clicked.connect(act)
            buttons.addWidget(button)
            self.buttons[name] = button
        layout = QVBoxLayout(self)
        layout.addWidget(self.search)
        layout.addWidget(self.list, 1)
        layout.addWidget(self.empty)
        layout.addLayout(buttons)
        self.search.setFocus()

    def refresh(self, current: str, kept: bool) -> None:
        """List the chats as they are now (`current`: the chat you're in; `kept`: whether chats are being kept)."""
        self._stop_search()
        self.current = current
        self._listed = self.book.listing(MOST) if kept else []
        self._inside = None
        if self._listed:
            self.empty.setText("")
        else:
            self.empty.setText(_("No saved chats yet.") if kept else _("Chats aren't being kept (Keep chat history is off)."))
        self._show()
        if self.search.text().strip():
            self._later.start()

    def shown_ids(self) -> list[str]:
        items = (self.list.item(i) for i in range(self.list.count()))
        return [item.data(Qt.ItemDataRole.UserRole) for item in items if item is not None]

    def _words(self) -> list[str]:
        return self.search.text().casefold().split()

    def _typed(self) -> None:
        self._stop_search()
        self._inside = None
        self._show()
        if self._words():
            self._later.start()

    def _search_inside(self) -> None:
        """The words inside the chats not already found by title."""
        if not self._words():
            return
        self._pending = deque(self._listed)
        self._found.clear()
        self._scan.start(0)
        self._search_batch()

    def _search_batch(self) -> None:
        words = self._words()
        for _item in range(min(SEARCH_BATCH, len(self._pending))):
            listed = self._pending.popleft()
            chat = self.book.load(listed.id)
            if chat is not None and matches(chat, words):
                self._found.add(listed.id)
        if not self._pending:
            self._scan.stop()
            self._inside, self._found = self._found, set()
            self._show()

    def _stop_search(self) -> None:
        self._later.stop()
        self._scan.stop()
        self._pending.clear()
        self._found.clear()

    def hideEvent(self, event: QHideEvent | None) -> None:
        self._stop_search()
        super().hideEvent(event)

    def _show(self) -> None:
        current = self.list.currentItem()
        chosen = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        words = self._words()
        self.list.clear()
        for listed in self._listed:
            if words and not (all(w in listed.title.casefold() for w in words) or (self._inside is not None and listed.id in self._inside)):
                continue
            mark = "★ " if listed.pinned else ""
            title, when = listed.title or _("A chat"), chats.when(listed.updated)
            # The same sentences as the menu's list of chats (menus.chats_menu).
            if listed.id == self.current:
                label = _("{title}   ·   {when}  (this one)").format(title=title, when=when)
            else:
                label = _("{title}   ·   {when}").format(title=title, when=when)
            item = QListWidgetItem(mark + label)
            item.setData(Qt.ItemDataRole.UserRole, listed.id)
            item.setData(Qt.ItemDataRole.UserRole + 1, listed.pinned)
            self.list.addItem(item)
            if listed.id == chosen:
                self.list.setCurrentItem(item)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        if words and not self.list.count() and self._listed:
            self.empty.setText(_("No chat has those words.") if self._inside is not None else _("Looking inside your chats…"))
        elif self._listed:
            self.empty.setText("")
        self._enable()

    def _enable(self) -> None:
        item = self.list.currentItem()
        for button in self.buttons.values():
            button.setEnabled(item is not None)
        if item is not None:
            self.buttons["pin"].setText(_("Unpin") if item.data(Qt.ItemDataRole.UserRole + 1) else _("Pin"))

    def _chosen(self, signal) -> None:
        item = self.list.currentItem()
        if item is not None:
            signal.emit(item.data(Qt.ItemDataRole.UserRole))

    def _pin(self) -> None:
        item = self.list.currentItem()
        if item is not None:
            self.pin.emit(item.data(Qt.ItemDataRole.UserRole), not item.data(Qt.ItemDataRole.UserRole + 1))
