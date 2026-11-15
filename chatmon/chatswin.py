"""Chats: every kept chat in a window, with search.

Like Settings, the window only shows and asks: it lists the chats (`ChatBook.listing`: titles, times and pins, never
the messages) and says what you chose (carry on, rename, instructions, pin, save, delete) through its signals; the
companion does it. Typing in the search field narrows the list by title at once, and a moment after you stop, by the
words in the chats themselves too (each chat read once while it doesn't change: `ChatBook.load`).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from . import chats

TITLE = "Chats"
SEARCH_AFTER_MS = 300  # after the last key, the words inside chats are searched too
MOST = 2000  # chats listed at most


def matches(chat: chats.Chat, words: list[str]) -> bool:
    """Every word is in the chat: its title, a question or an answer (any case)."""
    text = " ".join([chat.title, *(m.text for m in chat.messages)]).casefold()
    return all(word in text for word in words)


class ChatsWindow(QDialog):
    carry_on = pyqtSignal(str)
    rename = pyqtSignal(str)
    instructions = pyqtSignal(str)
    pin = pyqtSignal(str, bool)
    export = pyqtSignal(str)
    delete = pyqtSignal(str)

    def __init__(self, book: chats.ChatBook, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.setMinimumSize(520, 460)
        self.book = book
        self.current = ""  # the chat you're in: marked in the list
        self._listed: list[chats.Listed] = []
        self._inside: set[str] | None = None  # chats whose words match the search (None: not looked yet)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search your chats")
        self.search.setAccessibleName("Search your chats")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._typed)
        self.list = QListWidget()
        self.list.setAccessibleName("Your chats")
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
        buttons = QHBoxLayout()
        self.buttons: dict[str, QPushButton] = {}
        for name, label, act in (
            ("carry_on", "Carry on", lambda: self._chosen(self.carry_on)),
            ("rename", "Rename…", lambda: self._chosen(self.rename)),
            ("instructions", "Instructions…", lambda: self._chosen(self.instructions)),
            ("pin", "Pin", self._pin),
            ("export", "Save as Markdown…", lambda: self._chosen(self.export)),
            ("delete", "Delete…", lambda: self._chosen(self.delete)),
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
        self.current = current
        self._listed = self.book.listing(MOST) if kept else []
        self._inside = None
        self.empty.setText("" if self._listed else ("No saved chats yet." if kept else "Chats aren't being kept (Keep chat history is off)."))
        self._show()
        if self.search.text().strip():
            self._later.start()

    def shown_ids(self) -> list[str]:
        items = (self.list.item(i) for i in range(self.list.count()))
        return [item.data(Qt.ItemDataRole.UserRole) for item in items if item is not None]

    def _words(self) -> list[str]:
        return self.search.text().casefold().split()

    def _typed(self) -> None:
        self._inside = None
        self._show()
        if self._words():
            self._later.start()

    def _search_inside(self) -> None:
        """The words inside the chats not already found by title."""
        words = self._words()
        if not words:
            return
        inside = set()
        for listed in self._listed:
            chat = self.book.load(listed.id)
            if chat is not None and matches(chat, words):
                inside.add(listed.id)
        self._inside = inside
        self._show()

    def _show(self) -> None:
        current = self.list.currentItem()
        chosen = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        words = self._words()
        self.list.clear()
        for listed in self._listed:
            if words and not (all(w in listed.title.casefold() for w in words) or (self._inside is not None and listed.id in self._inside)):
                continue
            mark = "★ " if listed.pinned else ""
            here = "  (this one)" if listed.id == self.current else ""
            item = QListWidgetItem(f"{mark}{listed.title or 'A chat'}   ·   {chats.when(listed.updated)}{here}")
            item.setData(Qt.ItemDataRole.UserRole, listed.id)
            item.setData(Qt.ItemDataRole.UserRole + 1, listed.pinned)
            self.list.addItem(item)
            if listed.id == chosen:
                self.list.setCurrentItem(item)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        if words and not self.list.count() and self._listed:
            self.empty.setText("No chat has those words." if self._inside is not None else "Looking inside your chats…")
        elif self._listed:
            self.empty.setText("")
        self._enable()

    def _enable(self) -> None:
        item = self.list.currentItem()
        for button in self.buttons.values():
            button.setEnabled(item is not None)
        if item is not None:
            self.buttons["pin"].setText("Unpin" if item.data(Qt.ItemDataRole.UserRole + 1) else "Pin")

    def _chosen(self, signal) -> None:
        item = self.list.currentItem()
        if item is not None:
            signal.emit(item.data(Qt.ItemDataRole.UserRole))

    def _pin(self) -> None:
        item = self.list.currentItem()
        if item is not None:
            self.pin.emit(item.data(Qt.ItemDataRole.UserRole), not item.data(Qt.ItemDataRole.UserRole + 1))
