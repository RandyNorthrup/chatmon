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

from PyQt6.QtCore import QLocale, Qt, pyqtSignal

from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout, QKeySequenceEdit, QLabel, QLineEdit,
    QListWidget, QPlainTextEdit, QPushButton, QSlider, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from .i18n import N_, _

# The window's title and the choices' labels are in English here, marked for translating, and shown translated.
TITLE = N_("Chatmon Settings")
TABS = ("general", "ai", "chats", "breaks", "heads_up", "accessibility")  # show_tab's names, in the window's order
TEXT_SIZES = [(75, N_("Smaller (75%)")), (100, N_("Usual (100%)")), (125, N_("Larger (125%)")), (150, N_("Larger still (150%)")),
              (200, N_("Twice the size (200%)")), (300, N_("Three times (300%)"))]
BUBBLE_TIMES = [("normal", N_("Long enough to read")), ("longer", N_("Longer")), ("much longer", N_("Much longer")), ("until closed", N_("Until I close them"))]
MOTION = [("system", N_("As my system says")), ("on", N_("Always less movement")), ("off", N_("Never: move as usual"))]
ASK_BOX_WINDOW = [("auto", N_("When a screen reader is running")), ("on", N_("Always")), ("off", N_("Never"))]
# The sounds, as Settings names them (chatmon/sounds/<name>.wav): the alerts first.
CUES = [("needs-you", N_("An agent needs me")), ("reminder", N_("A reminder")), ("focus-done", N_("A focus session ends")),
        ("done", N_("An agent finished")), ("success", N_("Something went well")), ("error", N_("Something went wrong")), ("pop", N_("Every other bubble"))]
# What the window shows for a value it isn't given (an older caller, a test): Chatmon's own defaults.
DEFAULTS = {
    "reminder_snooze": 10, "text_scale": 100, "bubble_time": "normal", "reduced_motion": "system", "accessible_ask_box": "auto",
    "sound": True, "volume": 70, "cues": {name: name in ("needs-you", "reminder", "focus-done") for name, _label in CUES}, "hotkey": "",
    "follow_screen": False, "magnifier_follows": True, "speech_fallback": False, "language": "",
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


def _translated(choices: list[tuple]) -> list[tuple]:
    """One of this module's tables of choices, its labels in the person's language."""
    return [(key, _(label)) for key, label in choices]


class SettingsWindow(QDialog):
    saved = pyqtSignal(dict)
    open_file = pyqtSignal()  # "Open the settings file"
    test_requested = pyqtSignal(str, str)  # Test: the brain picked ("" for Automatic), and the key typed for it (or "")
    remove_key = pyqtSignal(str)  # Remove key: the brain whose saved key goes
    backup_requested = pyqtSignal(bool)  # Back up: with the chats, or not
    restore_requested = pyqtSignal()  # Bring back

    def __init__(self, values: dict, choices: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(_(TITLE))
        self.setMinimumSize(640, 660)
        values = {**DEFAULTS, **values}
        self._values = dict(values)
        # API brains that take a key: what's known of each one's key ({"said": words, "saved": in the keychain}), never the key.
        self._keys: dict[str, dict] = {name: dict(known) for name, known in (choices.get("keys") or {}).items()}
        self._key_store = str(choices.get("key_store") or _("your system's keychain"))
        self.tabs = QTabWidget()
        self.tabs.addTab(self._general(values, choices), _("General"))
        self.tabs.addTab(self._ai(values, choices), _("AI"))
        self.tabs.addTab(self._chats(values), _("Chats"))
        # Translators: a tab's name; "&&" shows as one "&" (a single & would mark a keyboard shortcut).
        self.tabs.addTab(self._breaks(values), _("Reminders, breaks && focus"))
        self.tabs.addTab(self._heads_up(values), _("Heads-up"))
        self.tabs.addTab(self._accessibility(values), _("Accessibility"))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        file_button = buttons.addButton(_("Open the settings file"), QDialogButtonBox.ButtonRole.ResetRole)
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
        self.name.setPlaceholderText(_("What your chatmon is called"))
        self.companion = _combo(c["companions"], v["companion"])
        languages = [("", _("System default"))] + [(code, QLocale(code).nativeLanguageName() or code) for code in c.get("languages") or ["en"]]
        self.language = _combo(languages, v["language"])
        # Translators: units after a number in a box, each with its space before it: pixels here, then minutes.
        self.size = _spin(60, 400, v["size"], _(" px"), 10)
        self.walk = QCheckBox(_("Walk around along the bottom of the screen"))
        self.walk.setChecked(v["walk"])
        self.follow_screen = QCheckBox(_("Follow me to another monitor"))
        self.follow_screen.setChecked(v["follow_screen"])
        self.sleep_after = _spin(0, 240, v["sleep_after_minutes"], _(" min"), special=_("Never"))
        self.autostart = QCheckBox(_("Start when I log in"))
        self.autostart.setChecked(v["autostart"])
        self.bubble_style = _combo(c["bubble_styles"], v["bubble_style"])
        self.bubble_effects = QCheckBox(_("Animate the bubbles' edges"))
        self.bubble_effects.setChecked(v["bubble_effects"])
        self.check_updates = QCheckBox(_("Look for a new Chatmon once a day"))
        self.check_updates.setChecked(v["check_updates"])
        form.addRow(_("Name"), self.name)
        form.addRow(_("Companion"), self.companion)
        form.addRow(_("Language"), self.language)
        form.addRow("", _note(_("Chatmon speaks it from the next time it starts.")))
        form.addRow(_("Size"), self.size)
        form.addRow("", self.walk)
        form.addRow("", self.follow_screen)
        form.addRow(_("Falls asleep after"), self.sleep_after)
        form.addRow(_("Bubble style"), self.bubble_style)
        form.addRow("", self.bubble_effects)
        form.addRow("", self.autostart)
        form.addRow("", self.check_updates)
        form.addRow("", _note(_("Updates are checked against the signed list of each release, and installed only when you say so.")))
        page.setLayout(form)
        return page

    def _ai(self, v: dict, c: dict) -> QWidget:
        page, form = QWidget(), QFormLayout()
        self.brain = _combo(c["brains"], v["brain"])
        self.brain.currentIndexChanged.connect(lambda _i: self._show_key())
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)  # never shown, never kept by the window
        self.key.setAccessibleName(_("API key"))
        self.key_status = _note("")
        self.remove_key_button = QPushButton(_("Remove key"))
        self.remove_key_button.clicked.connect(lambda: self.remove_key.emit(self._brain_name()))
        key_row = QHBoxLayout()
        key_row.addWidget(self.key, 1)
        key_row.addWidget(self.remove_key_button)
        self.key_label = QLabel(_("API key"))
        self.test_button = QPushButton(_("Test"))
        # Translators: "Say OK" is what the brain is asked, in English, as it is.
        self.test_button.setToolTip(_('Ask the brain "Say OK", and see how long it took or what went wrong'))
        self.test_button.clicked.connect(self._test)
        self.test_result = _note("")
        self.test_result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        test_row = QHBoxLayout()
        test_row.addWidget(self.test_button)
        test_row.addWidget(self.test_result, 1)
        # Translators: seconds, after a number in a box, with its space before it.
        self.timeout = _spin(10, 1800, v["timeout_seconds"], _(" s"), 10)
        self.show_replies = QCheckBox(_("Show the last words of an agent's reply when it finishes"))
        self.show_replies.setChecked(v["show_replies"])
        form.addRow(_("Brain"), self.brain)
        form.addRow("", _note(_(
            "Automatic picks an AI tool you're signed in to, or a model server on this computer. An API is "
            "billed per question, so it answers only once you pick it. Model, effort and thinking: the menu's Brain."
        )))
        form.addRow(self.key_label, key_row)
        form.addRow("", self.key_status)
        form.addRow("", test_row)
        form.addRow(_("Wait for an answer up to"), self.timeout)
        form.addRow("", self.show_replies)
        form.addRow("", _note(_("Off by default: an agent's reply can hold code or secrets you'd rather not have on screen.")))
        page.setLayout(form)
        self._show_key()
        return page

    def _chats(self, v: dict) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.keep_chats = QCheckBox(_("Keep my chats on this computer"))
        self.keep_chats.setChecked(v["keep_chats"])
        # Translators: after a number in a box, with its space before it: the pieces of text an AI counts.
        self.context_tokens = _spin(2_000, 1_000_000, v["context_tokens"], _(" tokens"), 1_000)
        form.addRow("", self.keep_chats)
        form.addRow("", _note(_("Readable by you alone, with the text you attach (sent again only to the brain you gave it to).")))
        form.addRow(_("Send a brain up to"), self.context_tokens)
        form.addRow("", _note(_(
            "Of a chat, with each question (about 3.5 characters a token). Past this, the earlier part goes as a "
            "summary, with the turns that bear on your question word for word. More costs more with an API; a "
            "model's own limit always comes first."
        )))
        layout.addLayout(form)
        layout.addWidget(QLabel(_("Instructions for every chat")))
        self.instructions = QPlainTextEdit(v["instructions"])
        self.instructions.setPlaceholderText(_("How to answer, what you do, what language… Sent with every question, to every brain."))
        self.instructions.setFixedHeight(80)
        layout.addWidget(self.instructions)
        layout.addWidget(QLabel(_("Memory: what I remember about you, for every chat")))
        self.memory = QListWidget()
        self.memory.addItems(v["memory"])
        self.memory.setFixedHeight(90)
        layout.addWidget(self.memory)
        row = QHBoxLayout()
        self.new_memory = QLineEdit()
        self.new_memory.setPlaceholderText(_("Something to remember (\"I use Arch\")"))
        self.new_memory.setMaxLength(500)
        self.new_memory.returnPressed.connect(self._add_memory)
        add, remove, clear = QPushButton(_("Add")), QPushButton(_("Forget")), QPushButton(_("Forget all"))
        add.clicked.connect(self._add_memory)
        remove.clicked.connect(lambda: [self.memory.takeItem(self.memory.row(i)) for i in self.memory.selectedItems()])
        clear.clicked.connect(self.memory.clear)
        for w in (self.new_memory, add, remove, clear):
            row.addWidget(w)
        layout.addLayout(row)
        # Translators: "remember that …", "what do you remember" and "forget that …" are what to type, in English.
        layout.addWidget(_note(_("Also in the chat: remember that …, what do you remember, forget that …")))
        backup = QGroupBox(_("Back up and move"))
        backup_layout = QHBoxLayout(backup)
        self.backup_chats = QCheckBox(_("With my chats"))
        self.backup_chats.setChecked(v["keep_chats"])
        back_up, bring_back = QPushButton(_("Back up…")), QPushButton(_("Bring back…"))
        back_up.setToolTip(_("Your settings, memory, notes and reminders (and chats, if you like) in one zip. Keys are never in it."))
        bring_back.setToolTip(_("A backup from this or another computer: checked, and what's in it said, before anything changes"))
        back_up.clicked.connect(lambda: self.backup_requested.emit(self.backup_chats.isChecked()))
        bring_back.clicked.connect(self.restore_requested.emit)
        for w in (back_up, self.backup_chats, bring_back):
            backup_layout.addWidget(w)
        backup_layout.addStretch(1)
        layout.addWidget(backup)
        return page

    def _breaks(self, v: dict) -> QWidget:
        page, form = QWidget(), QFormLayout()
        self.reminder_snooze = _spin(1, 120, v["reminder_snooze"], _(" min"))
        self.break_reminders = QCheckBox(_("Remind me to take breaks"))
        self.break_reminders.setChecked(v["break_reminders"])
        self.breaks_every = _spin(5, 480, v["breaks_every"] or 60, _(" min"), 5)
        self.snooze = _spin(1, 120, v["snooze"], _(" min"))
        for w in (self.breaks_every, self.snooze):  # kept as they are while reminders are off
            w.setEnabled(v["break_reminders"])
            self.break_reminders.toggled.connect(w.setEnabled)
        self.focus = _spin(1, 240, v["focus"], _(" min"), 5)
        self.focus_done = QCheckBox(_("Tell me when a focus session ends"))
        self.focus_done.setChecked(v["focus_done"])
        form.addRow(_("Snooze a reminder for"), self.reminder_snooze)
        form.addRow("", _note(_("A reminder waits until you press Done or snooze it; Later offers 5 minutes to tomorrow morning.")))
        form.addRow("", self.break_reminders)
        form.addRow(_("After this long at the screen"), self.breaks_every)
        form.addRow(_("Snooze a break for"), self.snooze)
        form.addRow(_("A focus session lasts"), self.focus)
        form.addRow("", self.focus_done)
        form.addRow("", _note(_("Time away from the keyboard counts as a break, and so does the computer sleeping or locked.")))
        page.setLayout(form)
        return page

    def _heads_up(self, v: dict) -> QWidget:
        page, form = QWidget(), QFormLayout()
        # Translators: a percentage after a number in a box, with its space before it (as the language writes it).
        self.battery_low = _spin(0, 90, v["battery_low"], _(" %"), special=_("Off"))
        self.battery_critical = _spin(1, 50, v["battery_critical"], _(" %"))
        self.battery_low.valueChanged.connect(self._keep_battery_order)
        self._keep_battery_order(self.battery_low.value())
        self.disk_full = _spin(0, 99, v["disk_full"], _(" %"), special=_("Off"))
        self.updates_heads_up = QCheckBox(_("Say when system updates are waiting"))
        self.updates_heads_up.setChecked(v["updates_heads_up"])
        # Translators: hours, after a number in a box, with its space before it.
        self.updates_every = _spin(1, 168, v["updates_every_hours"], _(" h"))
        form.addRow(_("Battery low at"), self.battery_low)
        form.addRow(_("Battery almost empty at"), self.battery_critical)
        form.addRow(_("Disk almost full at"), self.disk_full)
        form.addRow("", self.updates_heads_up)
        form.addRow(_("Look for them every"), self.updates_every)
        page.setLayout(form)
        return page

    def _accessibility(self, v: dict) -> QWidget:
        page, form = QWidget(), QFormLayout()
        self.text_scale = _combo(_translated(TEXT_SIZES), v["text_scale"] if any(v["text_scale"] == s for s, _label in TEXT_SIZES) else 100)
        if self.text_scale.findData(v["text_scale"]) < 0:  # a size of the settings file's own: kept, and shown
            self.text_scale.addItem(f"{v['text_scale']}%", v["text_scale"])
            self.text_scale.setCurrentIndex(self.text_scale.count() - 1)
        self.bubble_time = _combo(_translated(BUBBLE_TIMES), v["bubble_time"])
        self.read_aloud = QCheckBox(_("Read bubbles and answers aloud with my screen reader"))
        self.read_aloud.setChecked(v["read_aloud"])
        self.accessible_ask_box = _combo(_translated(ASK_BOX_WINDOW), v["accessible_ask_box"])
        self.reduced_motion = _combo(_translated(MOTION), v["reduced_motion"])
        self.magnifier_follows = QCheckBox(_("Magnifier goes to each bubble as it shows"))
        self.magnifier_follows.setChecked(v["magnifier_follows"])
        self.magnifier_follows.setVisible(sys.platform == "win32")  # Windows' Magnifier
        self.speech_fallback = QCheckBox(_("Speak announcements aloud while Chatmon is in the background (macOS's own voice)"))
        self.speech_fallback.setChecked(v["speech_fallback"])
        self.speech_fallback.setVisible(sys.platform == "darwin")  # VoiceOver holds them until Chatmon is in front
        self.hotkey = QKeySequenceEdit(QKeySequence(v["hotkey"], QKeySequence.SequenceFormat.PortableText))
        if hasattr(self.hotkey, "setMaximumSequenceLength"):  # Qt 6.5 and later; Ubuntu 24.04 has 6.4
            self.hotkey.setMaximumSequenceLength(1)
        self.hotkey.setClearButtonEnabled(True)
        self.hotkey.setAccessibleName(_("Hotkey to open the ask box"))
        self.sound = QCheckBox(_("Play sounds"))
        self.sound.setChecked(v["sound"])
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(int(v["volume"]))
        self.volume.setAccessibleName(_("Volume"))
        self.cues: dict[str, QCheckBox] = {}
        sounds = QGroupBox(_("Sounds for"))
        grid = QVBoxLayout(sounds)
        for name, label in CUES:
            box = QCheckBox(_(label))
            box.setChecked(bool(v["cues"].get(name, name in ("needs-you", "reminder", "focus-done"))))
            box.setEnabled(v["sound"])
            self.sound.toggled.connect(box.setEnabled)
            grid.addWidget(box)
            self.cues[name] = box
        self.volume.setEnabled(v["sound"])
        self.sound.toggled.connect(self.volume.setEnabled)
        form.addRow(_("Text size"), self.text_scale)
        form.addRow(_("Bubbles stay"), self.bubble_time)
        form.addRow("", _note(_("A bubble also waits while you point at it, and one that asks you something stays until you answer.")))
        form.addRow("", self.read_aloud)
        form.addRow("", _note(_("When one is running (Orca, VoiceOver, NVDA, JAWS, Narrator). Typing a bubble's button in the chat presses it, "
                                "and Ctrl+1 to Ctrl+9 press them while you type.")))
        form.addRow(_("Ask box as its own window"), self.accessible_ask_box)
        form.addRow("", _note(_("Where Chatmon draws on its own overlay (Wayland), a window of its own is what screen readers can find.")))
        form.addRow(_("Movement"), self.reduced_motion)
        form.addRow("", self.magnifier_follows)
        form.addRow("", self.speech_fallback)
        form.addRow(_("Hotkey to ask"), self.hotkey)
        form.addRow("", _note(_("Opens the ask box from anywhere; pressed again, closes it. Clear it for none.")))
        form.addRow("", self.sound)
        form.addRow(_("Volume"), self.volume)
        form.addRow("", sounds)
        form.addRow("", _note(_("No sound plays during Do Not Disturb, Focus, a full-screen app or a focus session.")))
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
            typed = _("A key typed here is saved in {store} when you press Save.").format(store=self._key_store)
            self.key_status.setText(f"{self._keys[name]['said']} {typed}")
            self.key.setPlaceholderText(_("Paste a new key to save it"))
            self.remove_key_button.setEnabled(bool(self._keys[name].get("saved")))
        self.test_result.setText("")

    def _test(self) -> None:
        self.test_result.setText(_("Asking…"))
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
            "language": self.language.currentData(),
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
