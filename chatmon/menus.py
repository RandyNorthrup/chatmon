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
from datetime import datetime
from functools import partial
from typing import cast

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtWidgets import QMenu

from . import __version__, agents, autostart, brains, chats, commands, companions, offline, reminders, report, styles
from .i18n import N_, _, ngettext

# A bubble style's name inside a sentence ("New look: electric.", "Match companion (fire)"), lower case where the
# language writes it so: a word of its own, not the menu's label cut down.
STYLE_WORDS = {"electric": N_("electric"), "fire": N_("fire"), "ghost": N_("ghost"), "fairy": N_("fairy"), "leaf": N_("leaf"), "plain": N_("plain")}


def _first_capital(text: str) -> str:
    """A phrase as a menu item: its first letter a capital and the rest as written ("Every day at 9:00 AM", and a
    translation's own capitals), not str.capitalize(), which lowers the rest."""
    return text[:1].upper() + text[1:]


def style_word(name: str) -> str:
    """A bubble style's name as said inside a sentence, in the person's language: "electric", "plain"."""
    return _(STYLE_WORDS[name]) if name in STYLE_WORDS else name


RECENT_CHATS = 8  # in the Chats menu itself; every chat is in the Chats window (All chats…)
AGENTS_FRESH = 30  # seconds a look at how the agents stand holds good when the menu opens
THINKING = {"auto": N_("Automatic (the model's own choice)"), "on": N_("On"), "off": N_("Off")}  # shown as _(THINKING[mode])
THINKING_SHORT = {"auto": N_("Automatic"), "on": N_("On"), "off": N_("Off")}  # in "Thinking: …"
# The clipboard's quick actions (app.QUICK_ACTIONS, whose prompts go to the brain in English) as the menu names them.
QUICK_LABELS = {"Explain": N_("Explain the clipboard…"), "Summarize": N_("Summarize the clipboard…"),
                "Translate": N_("Translate the clipboard…"), "Fix": N_("Fix the clipboard…")}


def _submenu(menu: QMenu, title: str) -> QMenu:
    """A new submenu at the end of `menu`. Qt always makes one."""
    return menu.addMenu(title)  # type: ignore[return-value]  # PyQt6 6.11's stub types it optional (6.12.1's as the menu's own class)


def _item(menu: QMenu, text: str) -> QAction:
    """A new item at the end of `menu`, to set up and connect. Qt always makes one; PyQt6 types addAction's result optional."""
    return cast(QAction, menu.addAction(text))


class Menus:
    def __init__(self, c) -> None:
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

    def _clock(self, action: QAction | None, words: Callable[[], str]) -> QAction | None:
        if action is not None:  # always: Qt makes it (PyQt6 types menuAction() and addAction() optional)
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
        m.addAction(_("Ask {name}…").format(name=c.name), c.open_ask)
        clipboard_menu(c, _submenu(m, _("Clipboard")))
        chats_menu(c, _submenu(m, _("Chats")))
        upcoming = [r for r in c.reminders.upcoming() if r.kind != "focus"]
        if upcoming:
            sub = _submenu(m, _("Reminders ({count})").format(count=len(upcoming)))
            # Translators: the box opens with "remind me in " typed, Chatmon's own (English) words for a reminder.
            sub.addAction(_("Remind me…"), partial(c.open_ask, "remind me in "))
            sub.addSeparator()
            for r in upcoming:
                item = _submenu(sub, _reminder(r))
                self._clock(item.menuAction(), partial(_reminder, r))
                reminder_menu(c, item, r)
        else:
            m.addAction(_("Remind me…"), partial(c.open_ask, "remind me in "))
        self._focus_and_notes(m)
        recent = c.recent_messages()
        if recent:
            recent_menu(c, _submenu(m, _("Recent messages")), recent)
        m.addSeparator()
        brain_menu(c, _submenu(m, _("Brain")))
        agents_menu(c, _submenu(m, _("AI agents")))
        appearance = _submenu(m, _("Appearance"))
        companion_menu(c, _submenu(appearance, _("Companion")))
        style_menu(c, _submenu(appearance, _("Bubble style")))
        walk = _item(appearance, _("Walk around"))
        walk.setCheckable(True)
        walk.setChecked(c.behavior.walk_enabled)
        walk.toggled.connect(c._set_walk)
        login = _item(appearance, _("Start when I log in"))
        login.setCheckable(True)
        login.setChecked(autostart.enabled())
        login.toggled.connect(c._set_autostart)
        m.addAction(_("Come out") if c.behavior.hidden else _("Hide (peek now and then)"), partial(c.set_hidden, not c.behavior.hidden))
        m.addSeparator()
        if c.updater.ready is not None and c.updater.release is not None:
            m.addAction(_("Update to Chatmon {version}").format(version=c.updater.release.version), c._update_now)
        m.addAction(_("Settings…"), c.open_settings)
        help_menu(c, _submenu(m, _("Help && updates")))
        m.addAction(_("Quit"), c.quit)
        c._look_again()


    def _focus_and_notes(self, m: QMenu) -> None:
        """A focus session (its countdown in the menu's name while it runs), the stopwatch, and your notes."""
        c = self.c
        focus = c.reminders.focus()
        sub = _submenu(m, _focus_title(focus))
        if focus:
            self._clock(sub.menuAction(), partial(_focus_title, focus))
            self._clock(sub.addAction(_focus_left(focus), c.stop_focus), partial(_focus_left, focus))
        else:
            sub.addSection(_("Focus timer"))
            for minutes in sorted({15, 25, 50, int(c.config["focus"]["minutes"])}):
                sub.addAction(ngettext("{n} minute", "{n} minutes", minutes).format(n=minutes), partial(c.start_focus, minutes))
        if c._stopwatch is not None:
            self._clock(sub.addAction(_stopwatch(c), partial(c._offline_in_box, "stop stopwatch")), partial(_stopwatch, c))
        kept = commands.notes(c.state)
        sub.addSection(_("Notes ({count})").format(count=len(kept)) if kept else _("Notes"))
        notes_menu(c, sub)


def _minutes_left(focus: reminders.Reminder) -> int:
    return max(1, round((focus.due - time.time()) / 60))


def _focus_title(focus: reminders.Reminder | None) -> str:
    if not focus:
        return _("Focus and notes")
    left = _minutes_left(focus)
    return ngettext("Focus and notes ({n} min left)", "Focus and notes ({n} min left)", left).format(n=left)


def _focus_left(focus: reminders.Reminder) -> str:
    left = _minutes_left(focus)
    return ngettext("Stop focus ({n} min left)", "Stop focus ({n} min left)", left).format(n=left)


def _stopwatch(c) -> str:
    if c._stopwatch is None:
        return _("Stop the stopwatch")
    return _("Stop the stopwatch ({time})").format(time=commands.offline_clock(c._now() - c._stopwatch, seconds=False))


def _reminder(r: reminders.Reminder) -> str:
    again = "  ↻" if r.repeat else ""
    # Translators: a reminder in the menu: "in 5 min: stretch", "tomorrow at 9:00 AM: call Sam".
    return _("{when}: {text}").format(when=reminders.describe(r.due, time.time()), text=r.text) + again


def reminder_menu(c, sub: QMenu, r: reminders.Reminder) -> None:
    """One reminder: Done and snoozes once it has come due; change its words or time, how it repeats, or cancel it."""
    if r.fired:
        sub.addAction(_("Done"), partial(c._reminder_done, r.id))
        later = _submenu(sub, _("Snooze"))
        for label, until in reminders.snooze_choices(time.time(), c._snooze_minutes()):
            later.addAction(label, partial(c._snooze_reminder, r.id, until))
        sub.addSeparator()
    sub.addAction(_("Edit…"), partial(c._edit_reminder, r.id))
    repeat = _submenu(sub, _("Repeat"))
    group = QActionGroup(repeat)
    for rule, label in [(None, _("Never")), *((rule, _first_capital(reminders.describe_repeat(rule))) for rule in repeat_rules(r.due))]:
        action = _item(repeat, label)
        action.setCheckable(True)
        action.setChecked(r.repeat == rule)
        action.triggered.connect(partial(c._set_repeat, r.id, rule))
        group.addAction(action)
    if r.repeat and r.repeat not in repeat_rules(r.due):  # one set another way ("every monday at 9" said in the box)
        current = _item(repeat, _first_capital(reminders.describe_repeat(r.repeat)))
        current.setCheckable(True)
        current.setChecked(True)
        group.addAction(current)
    sub.addAction(_("Cancel it"), partial(c._cancel, r.id))


def repeat_rules(due: float) -> list[str]:
    """The repeats a reminder due at `due` can take: every day, every weekday, or every week on its day, at its time."""
    when = datetime.fromtimestamp(due)  # noqa: DTZ006 - a repeat is at its time on your clock
    at = f"{when.hour:02d}:{when.minute:02d}"
    return [f"daily@{at}", f"weekdays@{at}", f"{('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')[when.weekday()]}@{at}"]


def recent_menu(c, sub: QMenu, recent: list) -> None:
    """The bubbles shown lately, newest first: picking one shows it again."""
    for shown_at, message in recent:
        title = " ".join(message.title.split())
        shown = title[:48] + "…" if len(title) > 48 else title
        # Translators: a bubble shown lately, and when: "Reminder: stretch   ·   5 min ago".
        sub.addAction(_("{title}   ·   {when}").format(title=shown, when=chats.when(shown_at)), partial(c._show_again, message))


def clipboard_menu(c, sub: QMenu) -> None:
    """What to ask about what's on the clipboard: it's attached only when one of these is chosen."""
    from .app import QUICK_ACTIONS

    for name in QUICK_ACTIONS:
        sub.addAction(_(QUICK_LABELS[name]) if name in QUICK_LABELS else f"{name}…", partial(c._quick_action, name))


def chats_menu(c, sub: QMenu, in_box: bool = False) -> None:
    """New chat, this chat's own (rename, another brain), the most recent chats (carry on) and All chats (the window,
    with search), and keeping or clearing them all. Only each chat's id, title, time and pin are read."""
    sub.addAction(_("New chat"), c._new_chat if in_box else c._open_new_chat)
    if c.chat.messages:
        sub.addAction(_("Rename this chat…"), partial(c._ask_new_name, c.chat.id))
    if c.chat.last_question() is not None:
        others = [b for b in c.brains.values() if b.name != c.chat.brain and b.available(wait=False)]
        if others:
            other = _submenu(sub, _("Ask another brain"))
            for brain in others:
                other.addAction(brain.label, partial(c._ask_other, brain.name))
    listed = c.chat_book.listing(RECENT_CHATS) if c._keeps_chats() else []
    if listed:
        sub.addSection(_("Your chats"))
        for chat in listed:
            mark = "★ " if chat.pinned else ""
            title, when = chat.title or _("A chat"), chats.when(chat.updated)
            if chat.id == c.chat.id:
                # Translators: the chat open now, in the list of chats: "Trip plans   ·   5 min ago  (this one)".
                label = _("{title}   ·   {when}  (this one)").format(title=title, when=when)
            else:
                label = _("{title}   ·   {when}").format(title=title, when=when)
            sub.addAction(mark + label, partial(c._resume_chat, chat.id))
    else:
        empty = _item(sub, _("No saved chats yet") if c._keeps_chats() else _("Chats aren't being kept"))
        empty.setEnabled(False)
    sub.addAction(_("All chats…"), c.open_chats)
    sub.addSeparator()
    keep = _item(sub, _("Keep chat history"))
    keep.setCheckable(True)
    keep.setChecked(c._keeps_chats())
    keep.toggled.connect(c._set_keep_chats)
    sub.addAction(_("Clear chat history…"), c._ask_to_clear_chats)


def notes_menu(c, sub: QMenu) -> None:
    for i, note in enumerate(commands.notes(c.state), 1):
        text = " ".join(note["text"].split())
        item = _submenu(sub, f"{i}. {text[:48] + '…' if len(text) > 48 else text}")
        item.addAction(_("Copy"), partial(c._copy, note["text"]))
        item.addAction(_("Delete"), partial(commands.kept, c, offline.Asked("delete note", str(i))))
    sub.addAction(_("Add a note…"), partial(c.open_ask, "note: "))


def help_menu(c, sub: QMenu) -> None:
    sub.addAction(_("What's new in {version}").format(version=__version__), c.show_whats_new)
    if c.updater.ready is not None and c.updater.release is not None:
        sub.addAction(_("Install Chatmon {version}").format(version=c.updater.release.version), c._update_now)
    else:
        sub.addAction(_("Check for updates now"), c.check_for_updates)
    auto = _item(sub, _("Check for updates every day"))
    auto.setCheckable(True)
    auto.setChecked(c._checks_updates())
    auto.toggled.connect(c._set_check_updates)
    sub.addSeparator()
    sub.addAction(_("Report a problem…"), c.report_problem)
    sub.addAction(_("Suggest an idea…"), partial(c.report_problem, report.IDEA))
    sub.addAction(_("Open the log"), c.open_log)
    sub.addAction(_("Reload settings file"), c.reload)
    version = _item(sub, f"Chatmon {__version__}")
    version.setEnabled(False)


def brain_menu(c, sub: QMenu) -> None:
    group = QActionGroup(sub)
    current = c._brain(wait=False)
    picked = c.state.get("brain")
    auto = _item(sub, _("Automatic ({brain})").format(brain=current.label) if current else _("Automatic (none found)"))
    auto.setCheckable(True)
    auto.setChecked(not picked)
    auto.triggered.connect(partial(c._pick_brain, None))
    group.addAction(auto)
    groups = (
        (_("AI tools you're signed in to"), lambda b: b.type == "command"),
        (_("On this computer"), lambda b: b.local),
        (_("APIs (billed per question; pick one to use it)"), lambda b: b.type != "command" and not b.local),
    )
    for title, belongs in groups:
        sub.addSection(title)
        for brain in (b for b in c.brains.values() if belongs(b)):
            ok = brain.available(wait=False)
            # Translators: a brain that can't answer now, and why: "Ollama (not running)".
            action = _item(sub, brain.label if ok else _("{brain} ({reason})").format(brain=brain.label, reason=brain.why_not()))
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
    sub.addSection(_("{brain}: how it answers").format(brain=brain.label))
    base = c.brains[brain.name]  # as set up, before any picks: its defaults
    if brain.models:
        own = _("The tool’s own choice") if brain.type == "command" else _("Its own default")
        # Translators: the same two, inside "Model: …".
        own_said = _("the tool’s own choice") if brain.type == "command" else _("its own default")
        menu = _submenu(sub, _("Model: {model}").format(model=brain.model or own_said))
        group = QActionGroup(menu)
        if not base.model:
            _option(c, menu, group, own, not brain.model, None, brain.name, "model", "")
        for model in dict.fromkeys([*brain.models, *([brain.model] if brain.model else [])]):
            label = _("{option}  (default)").format(option=model) if model == base.model else model
            # Any model can be picked: an effort or thinking it doesn't take is dropped with the switch.
            _option(c, menu, group, label, brain.model == model, brain.refuses(model=model, effort="", thinking="auto"), brain.name, "model", model)
    levels = brain.effort_levels()
    if levels:
        menu = _submenu(sub, _("Effort: {effort}").format(effort=brain.effort or _("the model’s default")))
        group = QActionGroup(menu)
        _option(c, menu, group, _("The model’s default"), not brain.effort, None, brain.name, "effort", "")
        for level in levels:
            label = _("{option}  (default)").format(option=level) if level == base.effort else level
            _option(c, menu, group, label, brain.effort == level, brain.refuses(effort=level), brain.name, "effort", level)
    if len(modes) > 1:
        menu = _submenu(sub, _("Thinking: {mode}").format(mode=_(THINKING_SHORT[brain.thinking])))
        group = QActionGroup(menu)
        for mode in modes:
            _option(c, menu, group, _(THINKING[mode]), brain.thinking == mode, brain.refuses(thinking=mode), brain.name, "thinking", mode)


def _option(c, menu: QMenu, group: QActionGroup, label: str, checked: bool, refused: str | None, brain: str, key: str, value: str) -> None:
    # Translators: a choice the brain doesn't take, and why: "high  (it has no effort setting)".
    action = _item(menu, label if refused is None else _("{option}  ({reason})").format(option=label, reason=refused))
    action.setCheckable(True)
    action.setChecked(checked)
    action.setEnabled(refused is None)
    action.triggered.connect(partial(c._set_brain_option, brain, key, value))
    group.addAction(action)


def agents_menu(c, sub: QMenu) -> None:
    sub.addSection(_("Let them tell me what they're doing"))
    missing = []
    for agent in agents.AGENTS:
        state = c._agent_status.get(agent.name, "found" if agent.detected() else "not found")
        if state == "not found":
            missing.append(agent.label)
            continue
        if state == "installed but off":
            # Translators: an agent and how it stands: "Claude Code (installed but off)".
            action = _item(sub, _("{agent} ({status})").format(agent=agent.label, status=agents.status_words(state)))
        else:
            action = _item(sub, agent.label)
        action.setCheckable(True)
        action.setChecked(state == "connected")
        action.toggled.connect(partial(c._set_agent, agent))
    if missing:
        note = _item(sub, _("Not found here: {agents}").format(agents=", ".join(missing)))
        note.setEnabled(False)
    sub.addSeparator()
    sub.addAction(_("Another agent or script…"), c._other_agents)


def companion_menu(c, sub: QMenu) -> None:
    group = QActionGroup(sub)
    current = c._companion().id
    for companion in companions.COMPANIONS.values():
        action = _item(sub, companion.label)
        action.setCheckable(True)
        action.setChecked(companion.id == current)
        action.setEnabled(companions.get(companion.id) is companion)  # its strips are installed
        action.triggered.connect(partial(c._pick_companion, companion.id))
        group.addAction(action)


def style_menu(c, sub: QMenu) -> None:
    from .app import MATCH

    group = QActionGroup(sub)
    current = c._bubble_style_name()
    matching = style_word(styles.get(c._companion().bubble_style).name)
    for name, label in [(MATCH, _("Match companion ({style})").format(style=matching))] + [(s.name, s.label) for s in styles.STYLES.values()]:
        action = _item(sub, label)
        action.setCheckable(True)
        action.setChecked(name == current)
        action.triggered.connect(partial(c._pick_style, name))
        group.addAction(action)
        if name == MATCH:
            sub.addSeparator()
    sub.addSeparator()
    moving = _item(sub, _("Animate bubbles"))
    moving.setCheckable(True)
    moving.setChecked(c._bubble_effects())
    moving.toggled.connect(c._set_bubble_effects)
