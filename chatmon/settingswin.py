"""Settings: everything in the settings file, in a window, and the menu's own choices too.

The window only shows and edits: it's given the values in use and hands back what you set when you press
Save (`saved`). The companion applies them with the same setters its menu uses, and keeps them in its state
file, laid over the settings file (which still works, for anything the window doesn't show: your own brains).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QPlainTextEdit, QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

TITLE = "Chatmon Settings"


def _note(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setMinimumHeight(label.fontMetrics().height() * (1 + len(text) // 70))  # wrapped lines a form leaves room for
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setStyleSheet("color: palette(placeholder-text);")
    return label


def _spin(low: int, high: int, value: int, suffix: str = "", step: int = 1, special: str = "") -> QSpinBox:
    box = QSpinBox()
    box.setRange(low, high)
    box.setSingleStep(step)
    box.setValue(max(low, min(high, int(value))))
    if suffix:
        box.setSuffix(suffix)
    if special:
        box.setSpecialValueText(special)  # shown at the lowest value: "Never", "Off"
    return box


def _combo(choices: list[tuple[str, str]], current: str) -> QComboBox:
    box = QComboBox()
    for key, label in choices:
        box.addItem(label, key)
    index = box.findData(current)
    box.setCurrentIndex(max(0, index))
    return box


class SettingsWindow(QDialog):
    saved = pyqtSignal(dict)
    open_file = pyqtSignal()  # "Open the settings file"

    def __init__(self, values: dict, choices: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.setMinimumSize(620, 640)
        self._values = dict(values)
        tabs = QTabWidget()
        tabs.addTab(self._general(values, choices), "General")
        tabs.addTab(self._ai(values, choices), "AI")
        tabs.addTab(self._chats(values), "Chats")
        tabs.addTab(self._breaks(values), "Breaks && focus")  # && : a plain &, not a shortcut
        tabs.addTab(self._heads_up(values), "Heads-up")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        file_button = buttons.addButton("Open the settings file", QDialogButtonBox.ButtonRole.ResetRole)
        file_button.clicked.connect(self.open_file.emit)
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

    # -- tabs

    def _general(self, v: dict, c: dict) -> QWidget:
        page, form = QWidget(), QFormLayout()
        self.name = QLineEdit(v["name"])
        self.name.setMaxLength(40)
        self.name.setPlaceholderText("What your chatmon is called")
        self.companion = _combo(c["companions"], v["companion"])
        self.size = _spin(60, 400, v["size"], " px", 10)
        self.walk = QCheckBox("Walk around along the bottom of the screen")
        self.walk.setChecked(v["walk"])
        self.sleep_after = _spin(0, 240, v["sleep_after_minutes"], " min", special="Never")
        self.autostart = QCheckBox("Start when I log in")
        self.autostart.setChecked(v["autostart"])
        self.bubble_style = _combo(c["bubble_styles"], v["bubble_style"])
        self.bubble_effects = QCheckBox("Animate the bubbles' edges")
        self.bubble_effects.setChecked(v["bubble_effects"])
        self.read_aloud = QCheckBox("Read bubbles and answers aloud with my screen reader")
        self.read_aloud.setChecked(v["read_aloud"])
        self.check_updates = QCheckBox("Look for a new Chatmon once a day")
        self.check_updates.setChecked(v["check_updates"])
        form.addRow("Name", self.name)
        form.addRow("Companion", self.companion)
        form.addRow("Size", self.size)
        form.addRow("", self.walk)
        form.addRow("Falls asleep after", self.sleep_after)
        form.addRow("Bubble style", self.bubble_style)
        form.addRow("", self.bubble_effects)
        form.addRow("", self.read_aloud)
        form.addRow("", _note("When one is running (Orca, VoiceOver, NVDA, JAWS, Narrator). Typing a bubble's button in the chat presses it."))
        form.addRow("", self.autostart)
        form.addRow("", self.check_updates)
        form.addRow("", _note("Updates are checked against the signed list of each release, and installed only when you say so."))
        page.setLayout(form)
        return page

    def _ai(self, v: dict, c: dict) -> QWidget:
        page, form = QWidget(), QFormLayout()
        self.brain = _combo(c["brains"], v["brain"])
        self.timeout = _spin(10, 1800, v["timeout_seconds"], " s", 10)
        self.show_replies = QCheckBox("Show the last words of an agent's reply when it finishes")
        self.show_replies.setChecked(v["show_replies"])
        form.addRow("Brain", self.brain)
        form.addRow("", _note(
            "Automatic picks an AI tool you're signed in to, or a model server on this computer. An API is "
            "billed per question, so it answers only once you pick it. Its key comes from its environment "
            "variable (ANTHROPIC_API_KEY, OPENAI_API_KEY...). Model, effort and thinking: the menu's Brain."
        ))
        form.addRow("Wait for an answer up to", self.timeout)
        form.addRow("", self.show_replies)
        form.addRow("", _note("Off by default: an agent's reply can hold code or secrets you'd rather not have on screen."))
        page.setLayout(form)
        return page

    def _chats(self, v: dict) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.keep_chats = QCheckBox("Keep my chats on this computer")
        self.keep_chats.setChecked(v["keep_chats"])
        self.context_tokens = _spin(2_000, 1_000_000, v["context_tokens"], " tokens", 1_000)
        form.addRow("", self.keep_chats)
        form.addRow("", _note("Readable by you alone, with the text you attach (sent again only to the brain you gave it to)."))
        form.addRow("Send a brain up to", self.context_tokens)
        form.addRow("", _note(
            "Of a chat, with each question (about 3.5 characters a token). Past this, the earlier part goes as a "
            "summary, with the turns that bear on your question word for word. More costs more with an API; a "
            "model's own limit always comes first."
        ))
        layout.addLayout(form)
        layout.addWidget(QLabel("Instructions for every chat"))
        self.instructions = QPlainTextEdit(v["instructions"])
        self.instructions.setPlaceholderText("How to answer, what you do, what language… Sent with every question, to every brain.")
        self.instructions.setFixedHeight(90)
        layout.addWidget(self.instructions)
        layout.addWidget(QLabel("Memory: what I remember about you, for every chat"))
        self.memory = QListWidget()
        self.memory.addItems(v["memory"])
        self.memory.setFixedHeight(110)
        layout.addWidget(self.memory)
        row = QHBoxLayout()
        self.new_memory = QLineEdit()
        self.new_memory.setPlaceholderText("Something to remember (\"I use Arch\")")
        self.new_memory.setMaxLength(500)
        self.new_memory.returnPressed.connect(self._add_memory)
        add, remove, clear = QPushButton("Add"), QPushButton("Forget"), QPushButton("Forget all")
        add.clicked.connect(self._add_memory)
        remove.clicked.connect(lambda: [self.memory.takeItem(self.memory.row(i)) for i in self.memory.selectedItems()])
        clear.clicked.connect(self.memory.clear)
        for w in (self.new_memory, add, remove, clear):
            row.addWidget(w)
        layout.addLayout(row)
        layout.addWidget(_note("Also in the chat: remember that …, what do you remember, forget that …"))
        return page

    def _breaks(self, v: dict) -> QWidget:
        page, form = QWidget(), QFormLayout()
        self.break_reminders = QCheckBox("Remind me to take breaks")
        self.break_reminders.setChecked(v["break_reminders"])
        self.breaks_every = _spin(5, 480, v["breaks_every"] or 60, " min", 5)
        self.snooze = _spin(1, 120, v["snooze"], " min")
        for w in (self.breaks_every, self.snooze):  # kept as they are while reminders are off
            w.setEnabled(v["break_reminders"])
            self.break_reminders.toggled.connect(w.setEnabled)
        self.focus = _spin(1, 240, v["focus"], " min", 5)
        self.focus_done = QCheckBox("Tell me when a focus session ends")
        self.focus_done.setChecked(v["focus_done"])
        form.addRow("", self.break_reminders)
        form.addRow("After this long at the screen", self.breaks_every)
        form.addRow("Snooze a break for", self.snooze)
        form.addRow("A focus session lasts", self.focus)
        form.addRow("", self.focus_done)
        form.addRow("", _note("Time away from the keyboard counts as a break, and so does the computer sleeping or locked."))
        page.setLayout(form)
        return page

    def _heads_up(self, v: dict) -> QWidget:
        page, form = QWidget(), QFormLayout()
        self.battery_low = _spin(0, 90, v["battery_low"], " %", special="Off")
        self.battery_critical = _spin(1, 50, v["battery_critical"], " %")
        self.disk_full = _spin(0, 99, v["disk_full"], " %", special="Off")
        self.updates_heads_up = QCheckBox("Say when system updates are waiting")
        self.updates_heads_up.setChecked(v["updates_heads_up"])
        self.updates_every = _spin(1, 168, v["updates_every_hours"], " h")
        form.addRow("Battery low at", self.battery_low)
        form.addRow("Battery almost empty at", self.battery_critical)
        form.addRow("Disk almost full at", self.disk_full)
        form.addRow("", self.updates_heads_up)
        form.addRow("Look for them every", self.updates_every)
        page.setLayout(form)
        return page

    # -- saving

    def _add_memory(self) -> None:
        text = " ".join(self.new_memory.text().split())
        existing = {self.memory.item(i).text().lower() for i in range(self.memory.count())}
        if text and text.lower() not in existing:
            self.memory.addItem(text)
        self.new_memory.clear()

    def values(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "companion": self.companion.currentData(),
            "size": self.size.value(),
            "walk": self.walk.isChecked(),
            "sleep_after_minutes": self.sleep_after.value(),
            "autostart": self.autostart.isChecked(),
            "bubble_style": self.bubble_style.currentData(),
            "bubble_effects": self.bubble_effects.isChecked(),
            "check_updates": self.check_updates.isChecked(),
            "read_aloud": self.read_aloud.isChecked(),
            "brain": self.brain.currentData(),
            "timeout_seconds": self.timeout.value(),
            "show_replies": self.show_replies.isChecked(),
            "keep_chats": self.keep_chats.isChecked(),
            "context_tokens": self.context_tokens.value(),
            "instructions": self.instructions.toPlainText().strip(),
            "memory": [self.memory.item(i).text() for i in range(self.memory.count())],
            "break_reminders": self.break_reminders.isChecked(),
            "breaks_every": self.breaks_every.value(),
            "focus_done": self.focus_done.isChecked(),
            "snooze": self.snooze.value(),
            "focus": self.focus.value(),
            "battery_low": self.battery_low.value(),
            "battery_critical": self.battery_critical.value(),
            "disk_full": self.disk_full.value(),
            "updates_heads_up": self.updates_heads_up.isChecked(),
            "updates_every_hours": self.updates_every.value(),
        }

    def _save(self) -> None:
        self._add_memory()  # typed but not added: meant all the same
        changed = {k: v for k, v in self.values().items() if self._values.get(k) != v}
        self.saved.emit(changed)
        self.accept()
