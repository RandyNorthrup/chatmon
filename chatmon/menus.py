"""The companion's menu, in the tray and on the companion itself.

It's built when it opens, and again when something it shows changes (a reminder set, a chat renamed, a brain
picked); never on a clock tick, which only sets the text of the items that show a time. Submenus are built with
it, not as each one opens: the stage's own menu (stagemenu.py) and some trays (D-Bus StatusNotifierItem hosts)
read them without asking for them to open, and a tray reads the whole menu before it's shown. The coding agents
are looked at again (their command lines run) only when the menu opens.

Each item acts through the companion `c` that made it.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from functools import partial

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtWidgets import QMenu

from . import __version__, agents, autostart, brains, chats, commands, companions, offline, reminders, report, styles

RECENT_CHATS = 12  # in the Chats menu itself; the rest under "Older chats"
AGENTS_FRESH = 30  # seconds a look at how the agents stand holds good when the menu opens
THINKING = {"auto": "Automatic (the model's own choice)", "on": "On", "off": "Off"}


class Menus:
    def __init__(self, c):
        self.c = c
        self.menu = QMenu()
        self.menu.aboutToShow.connect(self.opening)  # the tray's menu (and a D-Bus tray's, when it opens it)
        self.menu.aboutToHide.connect(c._menu_closed)  # the QMenu popup; the stage's menu says so itself
        self._stale = False  # something it shows changed while it was open
        self._refill = QTimer(c)  # the companion's: stopped with its other timers when it quits
        self._refill.setSingleShot(True)
        self._refill.timeout.connect(self.fill)
        self._clocks: list[tuple[QAction, Callable[[], str]]] = []  # the items that show a time, and their words now
        self._done = False

    def opening(self) -> None:
        """About to open: built as things are now, and the agents looked at again if the last look is stale (they
        may have been set up or switched off outside Chatmon; a look under way fills the menu in again)."""
        self.fill()
        c = self.c
        if not c._refreshing and c._now() - c._agents_seen > AGENTS_FRESH:
            c._refresh_agents()

    def changed(self) -> None:
        """Something the menu shows changed: fill it in again once things settle, and never under an open menu
        (its items would vanish under the pointer)."""
        if self._done:
            return
        if self.menu.isVisible() or self.c.stage.menu.is_open():
            self._stale = True
        else:
            self._refill.start(0)

    def closed(self) -> None:
        if self._stale and not self._done:
            self._stale = False
            self._refill.start(0)

    def stop(self) -> None:
        """The companion quit: no refill ever again (a look at the brains or the agents may come back late)."""
        self._done = True
        self._refill.stop()

    def tick(self) -> None:
        """A minute or so went by: the items that show a time say it as it is now."""
        for action, words in self._clocks:
            action.setText(words())

    def _clock(self, action: QAction, words: Callable[[], str]) -> QAction:
        self._clocks.append((action, words))
        return action

    def fill(self) -> None:
        self._refill.stop()
        self._clocks = []
        c, m = self.c, self.menu
        for sub in m.findChildren(QMenu, options=Qt.FindChildOption.FindDirectChildrenOnly):
            sub.deleteLater()  # clear() keeps submenus
        m.clear()
        # What you do with it first; then the brain and the agents; how it looks; and Chatmon itself.
        m.addAction(f"Ask {c.name}…", c.open_ask)
        chats_menu(c, m.addMenu("Chats"))
        upcoming = [r for r in c.reminders.upcoming() if r.kind != "focus"]
        if upcoming:
            sub = m.addMenu(f"Reminders ({len(upcoming)})")
            sub.addAction("Remind me…", partial(c.open_ask, "remind me in "))
            sub.addSeparator()
            for r in upcoming:
                self._clock(sub.addAction(_reminder(r), partial(c._cancel, r.id)), partial(_reminder, r))
        else:
            m.addAction("Remind me…", partial(c.open_ask, "remind me in "))
        self._focus_and_notes(m)
        m.addSeparator()
        brain_menu(c, m.addMenu("Brain"))
        agents_menu(c, m.addMenu("AI agents"))
        appearance = m.addMenu("Appearance")
        companion_menu(c, appearance.addMenu("Companion"))
        style_menu(c, appearance.addMenu("Bubble style"))
        walk = appearance.addAction("Walk around")
        walk.setCheckable(True)
        walk.setChecked(c.behavior.walk_enabled)
        walk.toggled.connect(c._set_walk)
        login = appearance.addAction("Start when I log in")
        login.setCheckable(True)
        login.setChecked(autostart.enabled())
        login.toggled.connect(c._set_autostart)
        m.addAction("Come out" if c.behavior.hidden else "Hide (peek now and then)", partial(c.set_hidden, not c.behavior.hidden))
        m.addSeparator()
        if c.updater.ready is not None and c.updater.release is not None:
            m.addAction(f"Update to Chatmon {c.updater.release.version}", c._update_now)
        m.addAction("Settings…", c.open_settings)
        help_menu(c, m.addMenu("Help & updates"))
        m.addAction("Quit", c.quit)
        c._look_again()


    def _focus_and_notes(self, m: QMenu) -> None:
        """A focus session (its countdown in the menu's name while it runs), the stopwatch, and your notes."""
        c = self.c
        focus = c.reminders.focus()
        sub = m.addMenu(_focus_title(focus))
        if focus:
            self._clock(sub.menuAction(), partial(_focus_title, focus))
            self._clock(sub.addAction(_focus_left(focus), c.stop_focus), partial(_focus_left, focus))
        else:
            sub.addSection("Focus timer")
            for minutes in sorted({15, 25, 50, int(c.config["focus"]["minutes"])}):
                sub.addAction(f"{minutes} minutes", partial(c.start_focus, minutes))
        if c._stopwatch is not None:
            self._clock(sub.addAction(_stopwatch(c), partial(c._offline_in_box, "stop stopwatch")), partial(_stopwatch, c))
        kept = commands.notes(c.state)
        sub.addSection(f"Notes ({len(kept)})" if kept else "Notes")
        notes_menu(c, sub)


def _focus_title(focus: reminders.Reminder | None) -> str:
    return f"Focus and notes ({max(1, round((focus.due - time.time()) / 60))} min left)" if focus else "Focus and notes"


def _focus_left(focus: reminders.Reminder) -> str:
    return f"Stop focus ({max(1, round((focus.due - time.time()) / 60))} min left)"


def _stopwatch(c) -> str:
    return f"Stop the stopwatch ({commands.offline_clock(c._now() - c._stopwatch, seconds=False)})" if c._stopwatch is not None else "Stop the stopwatch"


def _reminder(r: reminders.Reminder) -> str:
    return f"✕  {reminders.describe(r.due, time.time())}: {r.text}"


def chats_menu(c, sub: QMenu, in_box: bool = False) -> None:
    """Your chats, each with what can be done with it, and keeping or clearing them all. Only each chat's id,
    title, when it was last talked in and whether it's pinned are read."""
    sub.addAction("New chat", c._new_chat if in_box else c._open_new_chat)
    if c.chat.messages:
        sub.addAction("Rename this chat…", partial(c._ask_new_name, c.chat.id))
    recent = c.chat_book.recent() if c._keeps_chats() else []
    if recent:
        sub.addSection("Your chats")
        for chat in recent[:RECENT_CHATS]:
            _chat_item(c, sub, chat)
        if len(recent) > RECENT_CHATS:
            older = sub.addMenu(f"Older chats ({len(recent) - RECENT_CHATS})")
            for chat in recent[RECENT_CHATS:]:
                _chat_item(c, older, chat)
    else:
        empty = sub.addAction("No saved chats yet" if c._keeps_chats() else "Chats aren't being kept")
        empty.setEnabled(False)
    sub.addSeparator()
    keep = sub.addAction("Keep chat history")
    keep.setCheckable(True)
    keep.setChecked(c._keeps_chats())
    keep.toggled.connect(c._set_keep_chats)
    sub.addAction("Clear chat history…", c._ask_to_clear_chats)


def _chat_item(c, menu: QMenu, chat: chats.Chat) -> None:
    """One chat: carry on with it, rename, pin, save or delete it."""
    mark = "★ " if chat.pinned else ""
    here = "  (this one)" if chat.id == c.chat.id else ""
    item = menu.addMenu(f"{mark}{chat.title or 'A chat'}   ·   {chats.when(chat.updated)}{here}")
    item.addAction("Carry on", partial(c._resume_chat, chat.id))
    item.addAction("Rename…", partial(c._ask_new_name, chat.id))
    item.addAction("Instructions for this chat…", partial(c._ask_chat_instructions, chat.id))
    item.addAction("Unpin" if chat.pinned else "Pin to the top", partial(c._pin_chat, chat.id, not chat.pinned))
    item.addAction("Save as Markdown…", partial(c._export_chat, chat.id))
    item.addSeparator()
    item.addAction("Delete…", partial(c._ask_to_delete_chat, chat.id))


def notes_menu(c, sub: QMenu) -> None:
    for i, note in enumerate(commands.notes(c.state), 1):
        text = " ".join(note["text"].split())
        item = sub.addMenu(f"{i}. {text[:48] + '…' if len(text) > 48 else text}")
        item.addAction("Copy", partial(c._copy, note["text"]))
        item.addAction("Delete", partial(commands.kept, c, offline.Asked("delete note", str(i))))
    sub.addAction("Add a note…", partial(c.open_ask, "note: "))


def help_menu(c, sub: QMenu) -> None:
    sub.addAction(f"What's new in {__version__}", c.show_whats_new)
    if c.updater.ready is not None and c.updater.release is not None:
        sub.addAction(f"Install Chatmon {c.updater.release.version}", c._update_now)
    else:
        sub.addAction("Check for updates now", c.check_for_updates)
    auto = sub.addAction("Check for updates every day")
    auto.setCheckable(True)
    auto.setChecked(c._checks_updates())
    auto.toggled.connect(c._set_check_updates)
    sub.addSeparator()
    sub.addAction("Report a problem…", c.report_problem)
    sub.addAction("Suggest an idea…", partial(c.report_problem, report.IDEA))
    sub.addAction("Open the log", c.open_log)
    sub.addAction("Reload settings file", c.reload)
    version = sub.addAction(f"Chatmon {__version__}")
    version.setEnabled(False)


def brain_menu(c, sub: QMenu) -> None:
    group = QActionGroup(sub)
    current = c._brain(wait=False)
    picked = c.state.get("brain")
    auto = sub.addAction(f"Automatic ({current.label if current else 'none found'})")
    auto.setCheckable(True)
    auto.setChecked(not picked)
    auto.triggered.connect(partial(c._pick_brain, None))
    group.addAction(auto)
    groups = (
        ("AI tools you're signed in to", lambda b: b.type == "command"),
        ("On this computer", lambda b: b.local),
        ("APIs (billed per question; pick one to use it)", lambda b: b.type != "command" and not b.local),
    )
    for title, belongs in groups:
        sub.addSection(title)
        for brain in (b for b in c.brains.values() if belongs(b)):
            ok = brain.available(wait=False)
            action = sub.addAction(brain.label if ok else f"{brain.label} ({brain.why_not()})")
            action.setCheckable(True)
            action.setEnabled(ok)
            action.setChecked(picked == brain.name)
            action.triggered.connect(partial(c._pick_brain, brain.name))
            group.addAction(action)
    if current is not None:
        _brain_options_menu(c, sub, current)


def _brain_options_menu(c, sub: QMenu, brain: brains.Brain) -> None:
    """How the brain in use answers: its model, how hard it thinks, whether it thinks at all."""
    modes = brain.thinking_modes()
    if not (brain.models or brain.effort_levels() or len(modes) > 1):
        return
    sub.addSection(f"{brain.label}: how it answers")
    base = c.brains[brain.name]  # as set up, before any picks: its defaults
    if brain.models:
        own = "The tool’s own choice" if brain.type == "command" else "Its own default"
        menu = sub.addMenu(f"Model: {brain.model or own.lower()}")
        group = QActionGroup(menu)
        if not base.model:
            _option(c, menu, group, own, not brain.model, None, brain.name, "model", "")
        for model in dict.fromkeys([*brain.models, *([brain.model] if brain.model else [])]):
            label = model + ("  (default)" if model == base.model else "")
            # Any model can be picked: an effort or thinking it doesn't take is dropped with the switch.
            _option(c, menu, group, label, brain.model == model, brain.refuses(model=model, effort="", thinking="auto"), brain.name, "model", model)
    levels = brain.effort_levels()
    if levels:
        menu = sub.addMenu(f"Effort: {brain.effort or 'the model’s default'}")
        group = QActionGroup(menu)
        _option(c, menu, group, "The model’s default", not brain.effort, None, brain.name, "effort", "")
        for level in levels:
            label = level + ("  (default)" if level == base.effort else "")
            _option(c, menu, group, label, brain.effort == level, brain.refuses(effort=level), brain.name, "effort", level)
    if len(modes) > 1:
        menu = sub.addMenu(f"Thinking: {THINKING[brain.thinking].split(' (')[0]}")
        group = QActionGroup(menu)
        for mode in modes:
            _option(c, menu, group, THINKING[mode], brain.thinking == mode, brain.refuses(thinking=mode), brain.name, "thinking", mode)


def _option(c, menu: QMenu, group: QActionGroup, label: str, checked: bool, refused: str | None, brain: str, key: str, value: str) -> None:
    action = menu.addAction(label if refused is None else f"{label}  ({refused})")
    action.setCheckable(True)
    action.setChecked(checked)
    action.setEnabled(refused is None)
    action.triggered.connect(partial(c._set_brain_option, brain, key, value))
    group.addAction(action)


def agents_menu(c, sub: QMenu) -> None:
    sub.addSection("Let them tell me what they're doing")
    missing = []
    for agent in agents.AGENTS:
        state = c._agent_status.get(agent.name, "found" if agent.detected() else "not found")
        if state == "not found":
            missing.append(agent.label)
            continue
        action = sub.addAction(agent.label + (" (installed but off)" if state == "installed but off" else ""))
        action.setCheckable(True)
        action.setChecked(state == "connected")
        action.toggled.connect(partial(c._set_agent, agent))
    if missing:
        note = sub.addAction("Not found here: " + ", ".join(missing))
        note.setEnabled(False)
    sub.addSeparator()
    sub.addAction("Another agent or script…", c._other_agents)


def companion_menu(c, sub: QMenu) -> None:
    group = QActionGroup(sub)
    current = c._companion().id
    for companion in companions.COMPANIONS.values():
        action = sub.addAction(companion.label)
        action.setCheckable(True)
        action.setChecked(companion.id == current)
        action.setEnabled(companions.get(companion.id) is companion)  # its strips are installed
        action.triggered.connect(partial(c._pick_companion, companion.id))
        group.addAction(action)


def style_menu(c, sub: QMenu) -> None:
    from .app import MATCH

    group = QActionGroup(sub)
    current = c._bubble_style_name()
    matching = styles.get(c._companion().bubble_style).label.split(" (")[0].lower()
    for name, label in [(MATCH, f"Match companion ({matching})")] + [(s.name, s.label) for s in styles.STYLES.values()]:
        action = sub.addAction(label)
        action.setCheckable(True)
        action.setChecked(name == current)
        action.triggered.connect(partial(c._pick_style, name))
        group.addAction(action)
        if name == MATCH:
            sub.addSeparator()
    sub.addSeparator()
    moving = sub.addAction("Animate bubbles")
    moving.setCheckable(True)
    moving.setChecked(c._bubble_effects())
    moving.toggled.connect(c._set_bubble_effects)
