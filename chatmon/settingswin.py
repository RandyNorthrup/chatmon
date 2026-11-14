"""Settings: everything in the settings file, in a window, and the menu's own choices too.

The window only shows and edits: it's given the values in use and hands back what you set when you press
Save (`saved`). The companion applies them with the same setters its menu uses, and keeps them in its state
file, laid over the settings file (which still works, for anything the window doesn't show: your own brains).
What it can't do itself, it asks for: testing a brain (`test_requested`), taking a saved key out of the keychain
(`remove_key`), and backing up or bringing a backup back (`backup_requested`, `restore_requested`). A key typed
here is handed back with Save as `api_key` (the brain's name and the key), for the companion to put in the
keychain; the window never keeps it anywhere.
"""

from __future__ import annotations

import sys

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout, QKeySequenceEdit, QLabel, QLineEdit,
    QListWidget, QPlainTextEdit, QPushButton, QSlider, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

TITLE = "Chatmon Settings"
TABS = ("general", "ai", "chats", "breaks", "heads_up", "accessibility")  # show_tab's names, in the window's order
TEXT_SIZES = [(75, "Smaller (75%)"), (100, "Usual (100%)"), (125, "Larger (125%)"), (150, "Larger still (150%)"), (200, "Twice the size (200%)"),
              (300, "Three times (300%)")]
BUBBLE_TIMES = [("normal", "Long enough to read"), ("longer", "Longer"), ("much longer", "Much longer"), ("until closed", "Until I close them")]
MOTION = [("system", "As my system says"), ("on", "Always less movement"), ("off", "Never: move as usual")]
ASK_BOX_WINDOW = [("auto", "When a screen reader is running"), ("on", "Always"), ("off", "Never")]
# The sounds, as Settings names them (chatmon/sounds/<name>.wav): the alerts first.
CUES = [("needs-you", "An agent needs me"), ("reminder", "A reminder"), ("focus-done", "A focus session ends"),
        ("done", "An agent finished"), ("success", "Something went well"), ("error", "Something went wrong"), ("pop", "Every other bubble")]
# What the window shows for a value it isn't given (an older caller, a test): Chatmon's own defaults.
DEFAULTS = {
    "reminder_snooze": 10, "text_scale": 100, "bubble_time": "normal", "reduced_motion": "system", "accessible_ask_box": "auto",
    "sound": True, "volume": 70, "cues": {name: name in ("needs-you", "reminder", "focus-done") for name, _ in CUES}, "hotkey": "",
    "follow_screen": False, "magnifier_follows": True, "speech_fallback": False,
    "api_key": None,
}


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


def _combo(choices: list[tuple], current) -> QComboBox:
    box = QComboBox()
    for key, label in choices:
        box.addItem(label, key)
    index = box.findData(current)
    box.setCurrentIndex(max(0, index))
    return box


class SettingsWindow(QDialog):
    saved = pyqtSignal(dict)
    open_file = pyqtSignal()  # "Open the settings file"
    test_requested = pyqtSignal(str, str)  # Test: the brain picked ("" for Automatic), and the key typed for it (or "")
    remove_key = pyqtSignal(str)  # Remove key: the brain whose saved key goes
    backup_requested = pyqtSignal(bool)  # Back up: with the chats, or not
    restore_requested = pyqtSignal()  # Bring back

    def __init__(self, values: dict, choices: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.setMinimumSize(640, 660)
        values = {**DEFAULTS, **values}
        self._values = dict(values)
        # API brains that take a key: what's known of each one's key ({"said": words, "saved": in the keychain}), never the key.
        self._keys: dict[str, dict] = {name: dict(known) for name, known in (choices.get("keys") or {}).items()}
        self._key_store = str(choices.get("key_store") or "your system's keychain")
        self.tabs = QTabWidget()
        self.tabs.addTab(self._general(values, choices), "General")
        self.tabs.addTab(self._ai(values, choices), "AI")
        self.tabs.addTab(self._chats(values), "Chats")
        self.tabs.addTab(self._breaks(values), "Reminders, breaks && focus")  # && : a plain &, not a shortcut
        self.tabs.addTab(self._heads_up(values), "Heads-up")
        self.tabs.addTab(self._accessibility(values), "Accessibility")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        file_button = buttons.addButton("Open the settings file", QDialogButtonBox.ButtonRole.ResetRole)
        file_button.clicked.connect(self.open_file.emit)
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(buttons)

    def show_tab(self, name: str) -> None:
        """Open at a tab by its name in TABS ("ai", "accessibility"...)."""
        if name in TABS:
            self.tabs.setCurrentIndex(TABS.index(name))

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
        self.follow_screen = QCheckBox("Follow me to another monitor")
        self.follow_screen.setChecked(v["follow_screen"])
        self.sleep_after = _spin(0, 240, v["sleep_after_minutes"], " min", special="Never")
        self.autostart = QCheckBox("Start when I log in")
        self.autostart.setChecked(v["autostart"])
        self.bubble_style = _combo(c["bubble_styles"], v["bubble_style"])
        self.bubble_effects = QCheckBox("Animate the bubbles' edges")
        self.bubble_effects.setChecked(v["bubble_effects"])
        self.check_updates = QCheckBox("Look for a new Chatmon once a day")
        self.check_updates.setChecked(v["check_updates"])
        form.addRow("Name", self.name)
        form.addRow("Companion", self.companion)
        form.addRow("Size", self.size)
        form.addRow("", self.walk)
        form.addRow("", self.follow_screen)
        form.addRow("Falls asleep after", self.sleep_after)
        form.addRow("Bubble style", self.bubble_style)
        form.addRow("", self.bubble_effects)
        form.addRow("", self.autostart)
        form.addRow("", self.check_updates)
        form.addRow("", _note("Updates are checked against the signed list of each release, and installed only when you say so."))
        page.setLayout(form)
        return page

    def _ai(self, v: dict, c: dict) -> QWidget:
        page, form = QWidget(), QFormLayout()
        self.brain = _combo(c["brains"], v["brain"])
        self.brain.currentIndexChanged.connect(lambda _i: self._show_key())
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)  # never shown, never kept by the window
        self.key.setAccessibleName("API key")
        self.key_status = _note("")
        self.remove_key_button = QPushButton("Remove key")
        self.remove_key_button.clicked.connect(lambda: self.remove_key.emit(self._brain_name()))
        key_row = QHBoxLayout()
        key_row.addWidget(self.key, 1)
        key_row.addWidget(self.remove_key_button)
        self.key_label = QLabel("API key")
        self.test_button = QPushButton("Test")
        self.test_button.setToolTip('Ask the brain "Say OK", and see how long it took or what went wrong')
        self.test_button.clicked.connect(self._test)
        self.test_result = _note("")
        self.test_result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        test_row = QHBoxLayout()
        test_row.addWidget(self.test_button)
        test_row.addWidget(self.test_result, 1)
        self.timeout = _spin(10, 1800, v["timeout_seconds"], " s", 10)
        self.show_replies = QCheckBox("Show the last words of an agent's reply when it finishes")
        self.show_replies.setChecked(v["show_replies"])
        form.addRow("Brain", self.brain)
        form.addRow("", _note(
            "Automatic picks an AI tool you're signed in to, or a model server on this computer. An API is "
            "billed per question, so it answers only once you pick it. Model, effort and thinking: the menu's Brain."
        ))
        form.addRow(self.key_label, key_row)
        form.addRow("", self.key_status)
        form.addRow("", test_row)
        form.addRow("Wait for an answer up to", self.timeout)
        form.addRow("", self.show_replies)
        form.addRow("", _note("Off by default: an agent's reply can hold code or secrets you'd rather not have on screen."))
        page.setLayout(form)
        self._show_key()
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
        self.instructions.setFixedHeight(80)
        layout.addWidget(self.instructions)
        layout.addWidget(QLabel("Memory: what I remember about you, for every chat"))
        self.memory = QListWidget()
        self.memory.addItems(v["memory"])
        self.memory.setFixedHeight(90)
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
        backup = QGroupBox("Back up and move")
        backup_layout = QHBoxLayout(backup)
        self.backup_chats = QCheckBox("With my chats")
        self.backup_chats.setChecked(v["keep_chats"])
        back_up, bring_back = QPushButton("Back up…"), QPushButton("Bring back…")
        back_up.setToolTip("Your settings, memory, notes and reminders (and chats, if you like) in one zip. Keys are never in it.")
        bring_back.setToolTip("A backup from this or another computer: checked, and what's in it said, before anything changes")
        back_up.clicked.connect(lambda: self.backup_requested.emit(self.backup_chats.isChecked()))
        bring_back.clicked.connect(self.restore_requested.emit)
        for w in (back_up, self.backup_chats, bring_back):
            backup_layout.addWidget(w)
        backup_layout.addStretch(1)
        layout.addWidget(backup)
        return page

    def _breaks(self, v: dict) -> QWidget:
        page, form = QWidget(), QFormLayout()
        self.reminder_snooze = _spin(1, 120, v["reminder_snooze"], " min")
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
        form.addRow("Snooze a reminder for", self.reminder_snooze)
        form.addRow("", _note("A reminder waits until you press Done or snooze it; Later offers 5 minutes to tomorrow morning."))
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
        self.battery_low.valueChanged.connect(self._keep_battery_order)
        self._keep_battery_order(self.battery_low.value())
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

    def _accessibility(self, v: dict) -> QWidget:
        page, form = QWidget(), QFormLayout()
        self.text_scale = _combo(TEXT_SIZES, v["text_scale"] if any(v["text_scale"] == s for s, _ in TEXT_SIZES) else 100)
        if self.text_scale.findData(v["text_scale"]) < 0:  # a size of the settings file's own: kept, and shown
            self.text_scale.addItem(f"{v['text_scale']}%", v["text_scale"])
            self.text_scale.setCurrentIndex(self.text_scale.count() - 1)
        self.bubble_time = _combo(BUBBLE_TIMES, v["bubble_time"])
        self.read_aloud = QCheckBox("Read bubbles and answers aloud with my screen reader")
        self.read_aloud.setChecked(v["read_aloud"])
        self.accessible_ask_box = _combo(ASK_BOX_WINDOW, v["accessible_ask_box"])
        self.reduced_motion = _combo(MOTION, v["reduced_motion"])
        self.magnifier_follows = QCheckBox("Magnifier goes to each bubble as it shows")
        self.magnifier_follows.setChecked(v["magnifier_follows"])
        self.magnifier_follows.setVisible(sys.platform == "win32")  # Windows' Magnifier
        self.speech_fallback = QCheckBox("Speak announcements aloud while Chatmon is in the background (macOS's own voice)")
        self.speech_fallback.setChecked(v["speech_fallback"])
        self.speech_fallback.setVisible(sys.platform == "darwin")  # VoiceOver holds them until Chatmon is in front
        self.hotkey = QKeySequenceEdit(QKeySequence(v["hotkey"], QKeySequence.SequenceFormat.PortableText))
        self.hotkey.setMaximumSequenceLength(1)
        self.hotkey.setClearButtonEnabled(True)
        self.hotkey.setAccessibleName("Hotkey to open the ask box")
        self.sound = QCheckBox("Play sounds")
        self.sound.setChecked(v["sound"])
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(int(v["volume"]))
        self.volume.setAccessibleName("Volume")
        self.cues: dict[str, QCheckBox] = {}
        sounds = QGroupBox("Sounds for")
        grid = QVBoxLayout(sounds)
        for name, label in CUES:
            box = QCheckBox(label)
            box.setChecked(bool(v["cues"].get(name, name in ("needs-you", "reminder", "focus-done"))))
            box.setEnabled(v["sound"])
            self.sound.toggled.connect(box.setEnabled)
            grid.addWidget(box)
            self.cues[name] = box
        self.volume.setEnabled(v["sound"])
        self.sound.toggled.connect(self.volume.setEnabled)
        form.addRow("Text size", self.text_scale)
        form.addRow("Bubbles stay", self.bubble_time)
        form.addRow("", _note("A bubble also waits while you point at it, and one that asks you something stays until you answer."))
        form.addRow("", self.read_aloud)
        form.addRow("", _note("When one is running (Orca, VoiceOver, NVDA, JAWS, Narrator). Typing a bubble's button in the chat presses it, "
                              "and Ctrl+1 to Ctrl+9 press them while you type."))
        form.addRow("Ask box as its own window", self.accessible_ask_box)
        form.addRow("", _note("Where Chatmon draws on its own overlay (Wayland), a window of its own is what screen readers can find."))
        form.addRow("Movement", self.reduced_motion)
        form.addRow("", self.magnifier_follows)
        form.addRow("", self.speech_fallback)
        form.addRow("Hotkey to ask", self.hotkey)
        form.addRow("", _note("Opens the ask box from anywhere; pressed again, closes it. Clear it for none."))
        form.addRow("", self.sound)
        form.addRow("Volume", self.volume)
        form.addRow("", sounds)
        form.addRow("", _note("No sound plays during Do Not Disturb, Focus, a full-screen app or a focus session."))
        page.setLayout(form)
        return page

    # -- the brain's key and Test

    def _brain_name(self) -> str:
        return str(self.brain.currentData() or "")

    def _show_key(self) -> None:
        """The key field only for an API brain that takes a key, with what's known of the one it has."""
        name = self._brain_name()
        needs = name in self._keys
        for w in (self.key_label, self.key, self.remove_key_button, self.key_status):
            w.setVisible(needs)
        if needs:
            self.key_status.setText(f"{self._keys[name]['said']} A key typed here is saved in {self._key_store} when you press Save.")
            self.key.setPlaceholderText("Paste a new key to save it")
            self.remove_key_button.setEnabled(bool(self._keys[name].get("saved")))
        self.test_result.setText("")

    def _test(self) -> None:
        self.test_result.setText("Asking…")
        self.test_button.setEnabled(False)
        name = self._brain_name()
        self.test_requested.emit(name, self.key.text().strip() if name in self._keys else "")

    def show_test(self, ok: bool, text: str, _seconds: float) -> None:
        """The test's result: how long the answer took, or what went wrong (never the key)."""
        self.test_button.setEnabled(True)
        self.test_result.setText(("✓ " if ok else "✕ ") + text)

    def show_key_status(self, name: str, said: str, known: dict | None) -> None:
        """What happened to a key (removed, or why not), and what's known of the key now."""
        if known is not None:
            self._keys[name] = dict(known)
        self._show_key()
        self.key_status.setText(f"{said} {self._keys.get(name, {}).get('said', '')}".strip())

    # -- keeping "almost empty" below "low"

    def _keep_battery_order(self, low: int) -> None:
        self.battery_critical.setMaximum(max(1, low - 1) if low else 50)

    # -- saving

    def _add_memory(self) -> None:
        text = " ".join(self.new_memory.text().split())
        existing = {self.memory.item(i).text().lower() for i in range(self.memory.count())}
        if text and text.lower() not in existing:
            self.memory.addItem(text)
        self.new_memory.clear()

    def values(self) -> dict:
        key = self.key.text().strip()
        return {
            "name": self.name.text().strip(),
            "companion": self.companion.currentData(),
            "size": self.size.value(),
            "walk": self.walk.isChecked(),
            "follow_screen": self.follow_screen.isChecked(),
            "sleep_after_minutes": self.sleep_after.value(),
            "autostart": self.autostart.isChecked(),
            "bubble_style": self.bubble_style.currentData(),
            "bubble_effects": self.bubble_effects.isChecked(),
            "check_updates": self.check_updates.isChecked(),
            "read_aloud": self.read_aloud.isChecked(),
            "brain": self.brain.currentData(),
            "api_key": (self._brain_name(), key) if key and self._brain_name() in self._keys else None,
            "timeout_seconds": self.timeout.value(),
            "show_replies": self.show_replies.isChecked(),
            "keep_chats": self.keep_chats.isChecked(),
            "context_tokens": self.context_tokens.value(),
            "instructions": self.instructions.toPlainText().strip(),
            "memory": [self.memory.item(i).text() for i in range(self.memory.count())],
            "reminder_snooze": self.reminder_snooze.value(),
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
            "text_scale": self.text_scale.currentData(),
            "bubble_time": self.bubble_time.currentData(),
            "accessible_ask_box": self.accessible_ask_box.currentData(),
            "magnifier_follows": self.magnifier_follows.isChecked(),
            "speech_fallback": self.speech_fallback.isChecked(),
            "reduced_motion": self.reduced_motion.currentData(),
            "hotkey": self.hotkey.keySequence().toString(QKeySequence.SequenceFormat.PortableText),
            "sound": self.sound.isChecked(),
            "volume": self.volume.value(),
            "cues": {name: box.isChecked() for name, box in self.cues.items()},
        }

    def _save(self) -> None:
        self._add_memory()  # typed but not added: meant all the same
        changed = {k: v for k, v in self.values().items() if self._values.get(k) != v}
        self.key.clear()  # handed back once, never kept
        self.saved.emit(changed)
        self.accept()
