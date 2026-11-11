"""The running companion: the penguin, its bubbles and tray icon, and what it
keeps an eye on for you."""

from __future__ import annotations

import os
import re
import signal
import sys
import threading
import time
import traceback
from datetime import date, datetime
from functools import partial
from pathlib import Path

from PyQt6 import sip
from PyQt6.QtCore import QObject, QPoint, QProcess, Qt, QTimer, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QActionGroup, QDesktopServices, QFontMetricsF, QGuiApplication, QIcon
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QFileDialog, QMenu, QSystemTrayIcon

from . import __version__, agents, attachments, autostart, brains, changelog, chats, companions, context, events, heads_up, memory, offline, paths, presence, reminders, report, styles, sysnotify, updates
from .behavior import Behavior
from .bubble import AskBox
from .penguin import Stage
from .settings import State, load_config, merge
from .sprites import Sprites

PRETTY = {"claude": "Claude", "codex": "Codex", "gemini": "Gemini", "grok": "Grok", "copilot": "Copilot", "agent": "Your agent"}
WORK_EXPIRES = 30 * 60  # forget an agent that said it was working but never finished
AGENTS_FRESH = 30  # seconds a look at how the agents stand holds good for filling in the menu
MATCH = "match"  # the bubble style that follows the companion
APP_USER_MODEL_ID = "RandyNorthrup.Chatmon"  # Windows: the app's identity (packaging/windows/chatmon.iss gives its shortcuts it too)

HELP = """\
**Click me** to ask anything, **drag me** anywhere, **right-click** for the menu.

I also do plenty without any AI, like *remind me in 20m to stretch*, *timer 10 min*, *note: buy milk*,
*5 km in miles* or *roll 2d6*. Ask me *help* to see it all.
"""

HELP_ALL = """\
**Without any AI** (nothing leaves your computer, and none of it goes in a chat):

- **Reminders and timers:** *remind me in 20m to stretch* · *remind me at 3pm to call Sam* · *timer 10 min for the pasta* · *reminders* · *cancel reminder 2* · *clear reminders*
- **Focus and breaks:** *focus 50* · *stop focus* · *breaks off* · *breaks on* · *focus alerts off* · *focus alerts on*
- **Notes:** *note: buy milk* · *notes* · *delete note 2* · *clear notes*
- **Stopwatch:** *stopwatch* · *stop stopwatch*
- **Sums:** *2 + 2 * 3* · *15% of 80* · *sqrt(2)* · *calc 2^10*
- **Units:** *5 km in miles* · *70 f to c* · *3 cups to ml* · *2 GB in MiB*
- **Time and days:** *time* · *date* · *what week is it* · *days until Christmas* · *days until 2027-01-01*
- **Chance:** *flip a coin* · *roll 2d6* · *random number between 1 and 10* · *pick one: tacos, sushi or pizza*
- **Passwords:** *password* · *password 32*
- **Your computer:** *status* (battery, disks, reminders, the brain in use)
- **Me:** *settings* · *hide* · *new chat* · *rename chat* · *history* · *what's new* · *check for updates* · *report a problem* · *version*
- **Memory:** *remember that I use Arch* · *what do you remember* · *forget that I use Arch* · *forget everything*. What you ask me to remember goes with every question, to whichever AI you ask: that's what it's for.

Anything else goes to the AI you picked, under **Brain** in my menu.
"""
NO_AI = "Answered here, without any AI."


class Background(QObject):
    """Runs slow work (another tool's command line) off the screen thread and
    hands the result back on it."""

    finished = pyqtSignal(object, object)

    def __init__(self):
        super().__init__()
        self.finished.connect(lambda then, result: then(result))

    def run(self, work, then) -> None:
        def go() -> None:
            try:
                result = work()
            except Exception as exc:  # reported in a bubble, never fatal
                result = exc
            self.finished.emit(then, result)

        threading.Thread(target=go, daemon=True).start()


def offline_clock(elapsed: float, seconds: bool = True) -> str:
    """How long the stopwatch has run: "4:05", "1:02:09"; without `seconds`, "4 min", "1:02 h" (for the menu)."""
    s = int(max(0, elapsed))
    h, m, sec = s // 3600, s // 60 % 60, s % 60
    if not seconds:
        return f"{h}:{m:02d} h" if h else f"{m} min"
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def pretty(source: str) -> str:
    return PRETTY.get(source.lower(), source[:1].upper() + source[1:])


class Companion(QObject):
    def __init__(self, app: QApplication, server: QLocalServer, server_problem: str | None = None):
        super().__init__()
        self.app = app
        self.server = server
        self.server_problem = server_problem  # why hooks can't reach it, if they can't
        self.state = State.load()
        self.config, self.config_error = self._load_config()
        self._settings_window = None
        # Whether you're there, and whether now's a time for quiet: the platform's own word for each.
        self.desk = presence.Desk(QGuiApplication.platformName())
        self._quiet: str | None = None  # why bubbles from the background wait, if they do
        self._held: list = []  # what waited, shown once it's not quiet
        self._idle_away = False
        self._reduce_motion = self.desk.reduce_motion()
        self._high_contrast = self.desk.high_contrast()
        self._walk_picked = "walk" in (self.state.get("settings") or {})  # turned on or off by you: reduce-motion no longer decides
        self.brains = brains.load_brains(self.config["ai"])
        self.reminders = reminders.ReminderBook.from_list(self.state.get("reminders", []))
        self.breaks = reminders.BreakTracker(self.config["breaks"]["every_minutes"], time.time())
        self.watcher = self._make_watcher()
        self.chat = chats.Chat()  # the one you're in: saved as it goes (if you keep them), resumable from History
        self.chat_book = chats.ChatBook()
        self.attached: list[attachments.Attachment] = []  # for the next question
        self._asking: tuple[str, str, list[attachments.Attachment]] | None = None  # (chat id, question, attached), on its way
        self._renaming: str | None = None  # the chat whose new name the box is asking for
        self._stopwatch: float | None = None  # when the stopwatch started (monotonic), while it runs
        self.agents: dict[str, tuple[str, float]] = {}  # source: (state, since)
        self._last_event: tuple[str, str] | None = None
        self._last_event_at = 0.0
        self._alert_key: str | None = None
        self._waiting: list = []  # messages held back while an alert is up
        self._asking_name = False
        self._last_wall = time.time()
        self._last_ask = 0.0
        self._update_counts: dict[str, int] = {}
        self._restart_needed = False
        self._update_procs: list = []  # the system's update checks, while they run: QProcesses, and PackageKit's count

        screen = QGuiApplication.primaryScreen().availableGeometry()
        x = float(self.state.get("x", screen.x() + screen.width() * 0.8))
        # Drawn for the scale of the screen it starts on; the stage says so when it moves to one of another.
        self._sprite_scale = (QGuiApplication.screenAt(QPoint(int(x), 0)) or QGuiApplication.primaryScreen()).devicePixelRatio()
        self.sprites = self._load_sprites()
        self.behavior = Behavior(
            self.sprites.anims(),
            now=time.monotonic(),
            x=x,
            walk=bool(self.config["walk"]),
            sleep_after=float(self.config["sleep_after_minutes"]) * 60,
            speed=int(self.config["size"]) * 0.4,
        )
        self.stage = Stage(self.sprites, self.behavior)
        self.ask_box = AskBox()
        self._apply_bubble_style()
        if self.stage.hosts_windows():  # the Wayland overlay: drawn there, not a window of its own
            self.stage.host(self.ask_box)
        else:
            self.stage.keep_clear_of(self.ask_box)
        self.asker = brains.Asker(self)
        self.compactor = brains.Asker(self)  # sums up a chat's earlier part, when a question needs that first
        self.compactor.answered.connect(self._compacted)
        self.compactor.failed.connect(self._compact_failed)
        self._folding: tuple | None = None  # (chat id, pairs the summary will stand for, the question waiting)
        self._asked: dict | None = None  # what the question on its way went with: to ask once more, with less
        self.memory = memory.Memory.load()
        self._instructing: str | None = None  # the chat whose instructions the box is asking for

        self.stage.clicked.connect(self.on_click)
        self.stage.menu_requested.connect(self.show_menu)
        self.stage.head_moved.connect(self._follow)
        self.stage.message_closed.connect(self._message_closed)
        self.stage.away_changed.connect(self._overlay_away)
        self.stage.lock_changed.connect(self._screen_locked)  # Hyprland's word, beside logind's
        if self._reduce_motion:  # the system asks for less movement: standing still, unless you say walk
            self.behavior.set_walk(False, time.monotonic())
        self.stage.menu_closed.connect(self._menu_closed)
        self.stage.scale_changed_to.connect(self._set_sprite_scale)
        self.ask_box.closed.connect(self._ask_closed)
        self.ask_box.submitted.connect(self.submit)
        self.ask_box.reset_requested.connect(self._new_chat)
        self.ask_box.history_requested.connect(self._show_history)
        self.ask_box.attach_requested.connect(self._show_attach)
        self.ask_box.pasted.connect(self._attach_pasted)
        self.ask_box.attachment_removed.connect(self._remove_attachment)
        self.asker.answered.connect(self._answered)
        self.asker.failed.connect(self._failed)
        self.server.newConnection.connect(self._accept)

        # The menu is always filled in: a tray that shows it over D-Bus (Waybar,
        # and other StatusNotifierItem trays) reads it before asking for it to open.
        self.menu = QMenu()
        self.menu.aboutToShow.connect(self._fill_menu)
        self.menu.aboutToHide.connect(self._menu_closed)  # the QMenu popup; the stage's menu says so itself
        self._menu_open = False
        self._menu_stale = False
        self._menu_timer = QTimer(self)
        self._menu_timer.setSingleShot(True)
        self._menu_timer.timeout.connect(self._fill_menu)
        self._menu_clock: tuple = ()
        self._agent_status: dict[str, str] = {}
        self._refreshing = False  # finding out, off the screen's thread, how each agent stands
        self._refresh_next: bool | None = None  # asked again meanwhile: whether that look migrates too
        self._agents_seen = float("-inf")  # when the last look came back
        self._renamed = paths.first_run_since_rename()  # Penguin companion became Chatmon
        self.background = Background()
        self.updater = updates.Updater(self.background, self)
        self.updater.available.connect(self._update_available)
        self.updater.newer_only.connect(self._update_out)
        self.updater.up_to_date.connect(self._up_to_date)
        self.updater.failed.connect(self._update_failed)
        self.updater.installing.connect(self.quit)
        self.updater.handed_over.connect(lambda: self.say("Updating…", "The installer has it from here. I'll be back in a moment.", timeout_s=60))
        self._checking_by_hand = False  # a check you asked for says what it found, even "nothing new"
        self._install_kind: str | None = None
        self._problem_told = False
        self._looking = False  # finding out, off the screen's thread, whether model servers here are running
        self._fill_menu()
        self.tray = QSystemTrayIcon(QIcon(self.sprites.frame("idle", 0, False).pixmap))
        self.tray.setContextMenu(self.menu)
        self.tray.setToolTip("Chatmon")
        self.tray.activated.connect(self._tray_clicked)
        self.tray.show()
        self.app.setWindowIcon(self.tray.icon())
        if sys.platform.startswith("linux"):
            QTimer.singleShot(60_000, self._no_tray_news)  # a minute in: a tray starting with the desktop is up by then

        self._watch_screen_lock()
        self._every(5_000, self._check_reminders)
        self._every(5_000, self._check_quiet)
        self._every(30_000, self._check_time)
        self._every(60_000, self._check_system)
        self._every(int(self.config["heads_up"]["updates_every_hours"] * 3600_000), self._check_updates)
        QTimer.singleShot(600_000 if sys.platform == "win32" else 120_000, self._check_updates)
        QTimer.singleShot(1500, self._greet)
        QTimer.singleShot(45_000, self._maybe_check_updates)
        self._every(3600_000, self._maybe_check_updates)
        global _problem
        _problem = self._problem
        QTimer.singleShot(3000, partial(self._refresh_agents, True))
        self._preload = QTimer(self)  # cuts the animations not shown yet, one at a time, between frames
        self._preload.setInterval(40)
        self._preload.timeout.connect(self._preload_next)
        QTimer.singleShot(2000, self._preload.start)  # once the screen's scale is known

    # -- small helpers

    @property
    def name(self) -> str:
        return self.config["name"] or self.state.get("name") or self._companion().nickname

    def _every(self, ms: int, fn) -> None:
        timer = QTimer(self)
        timer.timeout.connect(fn)
        timer.start(max(1000, ms))

    def _make_watcher(self) -> heads_up.Watcher:
        h = self.config["heads_up"]
        return heads_up.Watcher(float(h["battery_low"]), float(h["battery_critical"]), float(h["disk_full_percent"]))

    def _brain(self, wait: bool = True) -> brains.Brain | None:
        """The brain to ask, with the model, effort and thinking picked for it from the menu. `wait` off:
        as far as can be told without holding up the screen (for the menu)."""
        brain = brains.choose(self.brains, self.config["ai"]["brain"], self.state.get("brain"), wait)
        return brain.with_options(self._brain_options(brain.name)) if brain else None

    def _look_again(self) -> None:
        """Find out, off the screen's thread, what the menu couldn't wait to (whether model servers on this
        computer are running), and fill the menu in again if anything changed."""
        if self._looking or not brains.unsure():
            return
        self._looking = True

        def looked(changed) -> None:
            self._looking = False
            if changed is True:
                self._menu_changed()

        self.background.run(brains.look_again, looked)

    def _brain_options(self, name: str) -> dict:
        return dict((self.state.get("brain_options") or {}).get(name) or {})

    def _now(self) -> float:
        return time.monotonic()

    def _follow(self) -> None:
        if self.ask_box.isVisible():
            self.ask_box.place(self.stage.head_point())

    def save(self) -> None:
        self.state.set("x", round(self.behavior.x))
        self.state.set("reminders", self.reminders.to_list())
        self.state.save()
        self._menu_changed()  # reminders and focus show in it

    # -- talking

    def _with_you(self) -> bool:
        """You're using Chatmon right now (its ask box or menu is open): it's no time to hold back."""
        return self.ask_box.isVisible() or self._menu_open

    def say(self, title: str, text: str = "", buttons=None, timeout_s: float | None = 12) -> None:
        if self._alert_key is not None:  # don't talk over something that needs you
            self._later(partial(self.say, title, text, buttons, timeout_s))
            return
        if self._quiet and not self._with_you():  # a full-screen app, a presentation, Do Not Disturb: later
            self._held = (self._held + [partial(self.say, title, text, buttons, timeout_s)])[-5:]
            return
        notice = self.desk.notice_seconds()  # how long you've asked notifications to stay up (Windows)
        if timeout_s is not None and notice:
            timeout_s = max(timeout_s, notice)
        self.stage.show_message(title, text, buttons, timeout_s)

    def alert(self, key: str, title: str, text: str, buttons=None) -> None:
        """Something needs you: the penguin waves its flippers until you answer."""
        if self._alert_key is not None:
            self._later(partial(self.alert, key, title, text, buttons))
            return
        if self._quiet and self.desk.covered(self.stage.native_window()):
            # Under a full-screen app: it waits for you, and the system's own notification says so now
            # (which follows your Do Not Disturb). macOS's needs a signed app: there it just waits.
            self._held = (self._held + [partial(self.alert, key, title, text, buttons)])[-5:]
            # Only that something's waiting: the system keeps notifications (Action Center, a phone linked
            # to the desktop), and an agent's message or a reminder's words are yours to see in Chatmon.
            if sys.platform.startswith("linux"):
                sysnotify.send(title, "Chatmon has something for you.")  # tray or not
            elif sys.platform != "darwin" and QSystemTrayIcon.supportsMessages():
                self.tray.showMessage(title, "Chatmon has something for you.", QSystemTrayIcon.MessageIcon.Information, 10_000)
            return
        self._alert_key = key
        self.behavior.set_hidden(False, self._now())
        self._menu_changed()
        self.behavior.set_alert(True, self._now())
        self.stage.raise_above(True)  # above a full-screen window: it needs you
        self.stage.show_message(title, text, buttons or [("OK", None)], None)

    # -- you being away, and times for quiet

    def _overlay_away(self, away: bool) -> None:
        self.desk.overlay_idle_since = time.monotonic() if away else None
        self._check_away()

    def _check_away(self) -> None:
        """Away from the keyboard and mouse a while counts toward a break, locked or not."""
        idle = self.desk.idle_seconds()
        if idle is None:
            return
        now = time.time()
        if idle >= presence.AWAY_AFTER:
            self.breaks.away(now - idle)
            self._idle_away = True
        elif self._idle_away:
            self._idle_away = False
            self.breaks.back(now)

    def _check_quiet(self) -> None:
        was = self._quiet
        self._quiet = self.desk.quiet()
        self.stage.set_covered(self.desk.covered(self.stage.native_window()) and self._alert_key is None)
        if was and not self._quiet and self._held:
            held, self._held = self._held, []
            for i, show in enumerate(held):
                QTimer.singleShot(600 * (i + 1), show)

    def _check_accessibility(self) -> None:
        """Reduced motion and high contrast: followed as they change, unless you chose otherwise."""
        motion, contrast = self.desk.reduce_motion(), self.desk.high_contrast()
        if (motion, contrast) == (self._reduce_motion, self._high_contrast):
            return
        self._reduce_motion, self._high_contrast = motion, contrast
        self._apply_bubble_style()
        if not self._walk_picked:
            self.behavior.set_walk(bool(self.config["walk"]) and not motion, self._now())
        self._menu_changed()

    def _later(self, show) -> None:
        self._waiting = (self._waiting + [show])[-5:]

    def _message_closed(self) -> None:
        if self._alert_key is not None:
            self._alert_key = None
            self.behavior.set_alert(False, self._now())
            if not self.ask_box.isVisible():
                self.stage.raise_above(False)
        if self._waiting:
            QTimer.singleShot(400, self._waiting.pop(0))

    def _no_tray_news(self) -> None:
        """No tray here (stock GNOME, without the AppIndicator extension): where the menu is, said once ever."""
        if QSystemTrayIcon.isSystemTrayAvailable() or self.state.get("told_no_tray"):
            return
        if self.stage.message_visible() or self.ask_box.isVisible():
            QTimer.singleShot(60_000, self._no_tray_news)  # not over something else
            return
        self.state.set("told_no_tray", True)
        self.state.save()
        self.say("No tray icon here", "My menu is on me: right-click me. After **Hide**, click me when I peek, or open Chatmon from your apps, to bring me back.", timeout_s=20)

    def _greet(self) -> None:
        if self.config_error:
            self.say("I couldn't read my settings", f"`{self.config_error}`\n\nUsing the defaults for now.", timeout_s=30)
        elif self.server_problem:
            self.say("Your agents can't reach me", f"{self.server_problem}\n\nEverything else works.", timeout_s=30)
        elif not (self.config["name"] or self.state.get("name")):
            self._asking_name = True
            self.open_ask(focus=False)  # nobody clicked: don't take the keyboard from them
        elif self._whats_new_after_update():
            pass
        elif not self.stage.message_visible():  # an agent or a script got in first: theirs matters more
            self.say(f"Hi, I'm {self.name}!", "Click me to ask anything.", timeout_s=5)

    # -- clicks and the ask box

    def on_click(self) -> None:
        now = self._now()
        if self.behavior.alert:
            self.stage.dismiss_message()
        elif self.behavior.asleep:
            self.behavior.wake(now)
        elif self.behavior.hidden:
            self.set_hidden(False)
        elif self.ask_box.isVisible():
            self.ask_box.dismiss()
        else:
            self.open_ask()

    def open_ask(self, prefill: str = "", *, focus: bool = True) -> None:
        """Open the ask box. It takes the keyboard (`focus`) when you asked for
        it, with a click or the menu; otherwise you click it to type."""
        now = self._now()
        if self.behavior.hidden:
            self.set_hidden(False)
        self.behavior.wake(now)
        self.behavior.set_attending(True, now)
        self.stage.raise_above(True)  # you asked for it: above anything full screen
        self.stage.dismiss_message()
        if now - self._last_ask > 15 * 60 and self.chat.messages:
            self._start_chat()  # a while since: a fresh one (the last is in History)
        self._last_ask = now
        anchor = self.stage.head_point()
        if self._asking_name:
            self.ask_box.open(
                anchor,
                "Hi! I'm your new desktop companion.",
                "Enter to save · Esc to decide later",
                "A name for me",
                text="What should I be called?",
                activate=focus,
            )
            self.ask_box.chatting(False)
        else:
            brain = self._brain()
            via = f"answers from {brain.label}" if brain else "no AI set up yet; reminders and timers still work"
            self.ask_box.open(
                anchor, f"Ask {self.name}", f"Enter to ask · Esc to close · {via}", "Ask anything, or: remind me in 20m to stretch",
                text=self._transcript(), prefill=prefill, activate=focus,
            )
            self.ask_box.chatting(True)
            self.ask_box.set_answer(self._transcript(), at_end=True)
            self.ask_box.set_attachments([a.label() for a in self.attached])
            self.ask_box.set_resettable(bool(self.chat.messages))

    def _ask_closed(self) -> None:
        if self._alert_key is None:
            self.stage.raise_above(False)
        now = self._now()
        self._asking_name = False
        self._renaming = None
        self._instructing = None
        self.asker.cancel()
        self.compactor.cancel()
        self._folding = None
        self.behavior.set_thinking(False, now)
        self.behavior.set_talking(False, now)
        self.behavior.set_attending(self._menu_open, now)

    # -- chats: kept, resumed, and what's attached to them

    def _keeps_chats(self) -> bool:
        picked = self.state.get("keep_chats")
        return bool(self.config["chats"]["keep"] if picked is None else picked)

    def _drop_question(self) -> None:
        """A question on its way belongs to the chat it was asked in: leaving that chat drops it."""
        if self._asking is not None:
            self.asker.cancel()
            self.compactor.cancel()
            self._folding = None
            self._asking = None
            self.behavior.set_thinking(False, self._now())

    def _start_chat(self) -> None:
        self._drop_question()
        self.chat = chats.Chat(keep=self._keeps_chats())
        self.attached.clear()

    def _new_chat(self) -> None:
        self._start_chat()
        self.ask_box.set_attachments([])
        self.ask_box.set_resettable(False)
        self.ask_box.set_answer("*New chat. Ask away.*")

    def _transcript(self, pending: str = "") -> str:
        """The chat as the box shows it: each question and its answer, newest at the bottom."""
        parts = []
        for m in self.chat.messages[-40:]:
            if m.role == "user":
                line = f"**You:** {m.text}" if m.text else "**You:**"
                if m.attached:
                    line += f"\n\n*Attached: {', '.join(m.attached)}*"
                parts.append(line)
            else:
                parts.append(m.text)
        if pending:
            parts.append(pending)
        return "\n\n".join(parts)

    def _save_chat(self) -> None:
        if self._keeps_chats() and self.chat.keep and self.chat.messages:
            try:
                self.chat_book.save(self.chat)
            except OSError as exc:
                print(f"{paths.APP}: couldn't save the chat: {exc}", file=sys.stderr)

    RECENT_CHATS = 12  # in the menu itself; the rest under "Older chats"

    def _chats_menu(self, sub: QMenu, in_box: bool = False) -> None:
        """Your chats, each with what can be done with it, and keeping or clearing them all."""
        sub.addAction("New chat", self._new_chat if in_box else self._open_new_chat)
        if self.chat.messages:
            sub.addAction("Rename this chat…", partial(self._ask_new_name, self.chat.id))
        recent = self.chat_book.recent() if self._keeps_chats() else []
        if recent:
            sub.addSection("Your chats")
            for chat in recent[: self.RECENT_CHATS]:
                self._chat_item(sub, chat)
            if len(recent) > self.RECENT_CHATS:
                older = sub.addMenu(f"Older chats ({len(recent) - self.RECENT_CHATS})")
                for chat in recent[self.RECENT_CHATS :]:
                    self._chat_item(older, chat)
        else:
            empty = sub.addAction("No saved chats yet" if self._keeps_chats() else "Chats aren't being kept")
            empty.setEnabled(False)
        sub.addSeparator()
        keep = sub.addAction("Keep chat history")
        keep.setCheckable(True)
        keep.setChecked(self._keeps_chats())
        keep.toggled.connect(self._set_keep_chats)
        sub.addAction("Clear chat history…", self._ask_to_clear_chats)

    def _chat_item(self, menu: QMenu, chat: chats.Chat) -> None:
        """One chat: carry on with it, rename, pin, save or delete it."""
        mark = "★ " if chat.pinned else ""
        here = "  (this one)" if chat.id == self.chat.id else ""
        item = menu.addMenu(f"{mark}{chat.title or 'A chat'}   ·   {chats.when(chat.updated)}{here}")
        item.addAction("Carry on", partial(self._resume_chat, chat.id))
        item.addAction("Rename…", partial(self._ask_new_name, chat.id))
        item.addAction("Instructions for this chat…", partial(self._ask_chat_instructions, chat.id))
        item.addAction("Unpin" if chat.pinned else "Pin to the top", partial(self._pin_chat, chat.id, not chat.pinned))
        item.addAction("Save as Markdown…", partial(self._export_chat, chat.id))
        item.addSeparator()
        item.addAction("Delete…", partial(self._ask_to_delete_chat, chat.id))

    def _chat_by_id(self, chat_id: str) -> chats.Chat | None:
        return self.chat if chat_id == self.chat.id else self.chat_book.load(chat_id)

    def _changed_chat(self, chat: chats.Chat) -> None:
        """A chat's name or pin changed: kept, and the menus show it."""
        if chat.id == self.chat.id:
            self.chat = chat
        if self._keeps_chats() and chat.keep:
            self.chat_book.save(chat)
        self._menu_changed()

    def _ask_new_name(self, chat_id: str) -> None:
        chat = self._chat_by_id(chat_id)
        if chat is None:
            return
        self._renaming = chat_id
        self.ask_box.open(self.stage.head_point(), "Rename this chat", "Enter to save · Esc to leave it as it is", "A name for the chat", prefill=chat.title)
        self.ask_box.chatting(False)
        self.ask_box.set_attachments([])
        self.ask_box.entry.selectAll()

    def _ask_chat_instructions(self, chat_id: str) -> None:
        chat = self._chat_by_id(chat_id)
        if chat is None:
            return
        self._instructing = chat_id
        self.ask_box.open(
            self.stage.head_point(), "Instructions for this chat", "Sent with each question in this chat · Enter to save · empty to remove",
            "How to answer in this chat", prefill=chat.instructions,
        )
        self.ask_box.chatting(False)
        self.ask_box.set_attachments([])
        self.ask_box.entry.selectAll()

    def _set_chat_instructions(self, chat_id: str, text: str) -> None:
        chat = self._chat_by_id(chat_id)
        if chat is not None:
            chat.instructions = " ".join(text.split())[: chats.MAX_INSTRUCTIONS]
            self._changed_chat(chat)

    def _rename(self, chat_id: str, title: str) -> None:
        chat = self._chat_by_id(chat_id)
        title = " ".join(title.split())
        if chat is None or not title:
            return
        chat.rename(title)
        self._changed_chat(chat)

    def _pin_chat(self, chat_id: str, on: bool) -> None:
        chat = self._chat_by_id(chat_id)
        if chat is not None:
            chat.pinned = on
            self._changed_chat(chat)

    def _export_chat(self, chat_id: str) -> None:
        chat = self._chat_by_id(chat_id)
        if chat is None:
            return
        safe = "".join(c if c.isalnum() or c in " -_" else " " for c in chat.title or "chat").strip()[:60] or "chat"

        def with_qt() -> None:
            shown = self.ask_box.isVisible()
            if shown:
                self.ask_box.pause()  # the save dialog needs the keyboard
            try:
                name, _ = QFileDialog.getSaveFileName(None, "Save the chat", str(Path.home() / f"{safe}.md"), "Markdown (*.md);;Text (*.txt)")
            finally:
                if shown:
                    self.ask_box.resume()
            self._write_chat(chat, name)

        if self._chooser() is not None:
            self._through_portal(lambda then, fallback: self._file_chooser.save_file("Save the chat", Path.home(), f"{safe}.md", then, fallback),
                                 lambda names: self._write_chat(chat, names[0] if names else ""), with_qt)
        else:
            with_qt()

    def _write_chat(self, chat: chats.Chat, name: str) -> None:
        if not name:
            return
        try:
            Path(name).write_text(chat.markdown(), encoding="utf-8")
        except OSError as exc:
            self.say("Couldn't save the chat", str(exc), timeout_s=10)
            return
        self.say("Chat saved", f"`{Path(name).name}`", timeout_s=5)

    def _ask_to_delete_chat(self, chat_id: str) -> None:
        chat = self._chat_by_id(chat_id)
        if chat is not None:
            self.say(f"Delete “{chat.title or 'this chat'}”?", "It can't be brought back.", [("Delete it", partial(self._delete_chat, chat_id)), ("Keep it", None)], timeout_s=30)

    def _popup(self, menu: QMenu, pos: QPoint) -> None:
        """A menu of the moment, where it can be seen: drawn by the stage on the Wayland overlay."""
        if self.stage.draws_menus():
            self.stage.open_menu(menu, pos, owned=True)
        else:
            menu.aboutToHide.connect(menu.deleteLater)
            menu.popup(pos)

    def _show_history(self, pos: QPoint) -> None:
        menu = QMenu()
        self._chats_menu(menu, in_box=True)
        self._popup(menu, pos)

    def _open_new_chat(self) -> None:
        self._start_chat()
        self.open_ask()

    def _resume_chat(self, chat_id: str) -> None:
        if chat_id == self.chat.id:
            chat = self.chat
        else:
            chat = self.chat_book.load(chat_id)
            if chat is None:
                self.say("That chat is gone", "It may have been cleared.", timeout_s=6)
                return
            self._drop_question()
        self.chat = chat
        self.attached.clear()
        self._last_ask = self._now()
        if not self.ask_box.isVisible():
            self.open_ask()
        self.ask_box.set_attachments([])
        self.ask_box.set_resettable(True)
        self.ask_box.set_answer(self._transcript(), at_end=True)

    def _delete_chat(self, chat_id: str | None = None) -> None:
        chat_id = chat_id or self.chat.id
        self.chat_book.delete(chat_id)
        if chat_id == self.chat.id:
            self._start_chat()
            if self.ask_box.isVisible():
                self._new_chat()
        self._menu_changed()

    def _ask_to_clear_chats(self) -> None:
        self.say(
            "Delete every saved chat?", "They can't be brought back.",
            [("Delete them", self._clear_chats), ("Keep them", None)], timeout_s=30,
        )

    def _clear_chats(self) -> None:
        gone = self.chat_book.clear()
        self._start_chat()
        if self.ask_box.isVisible():
            self.ask_box.set_attachments([])
            self.ask_box.set_resettable(False)
            self.ask_box.set_answer("*Chat history cleared.*")
        self._menu_changed()
        self.say("Chat history cleared", f"{gone} chat{'s' if gone != 1 else ''} deleted.", timeout_s=5)

    def _set_keep_chats(self, on: bool) -> None:
        self.state.set("keep_chats", on)
        self.state.save()
        self._menu_changed()
        if on:  # from the next chat: what was said while it was off stays unsaved, as promised
            self.say("Keeping chats", "Chats from here on are kept, so you can come back to them.", timeout_s=8)
        else:
            self.chat.keep = False
            self.say("Not keeping chats", "From now on, chats stay only until I quit. Earlier ones stay until you clear them.", timeout_s=10)

    def _show_attach(self, pos: QPoint) -> None:
        menu = QMenu()
        menu.addAction("Attach files…", self._attach_files)
        menu.addAction("Paste from the clipboard", self._paste_into_box)
        if self.attached:
            menu.addAction("Take them all off", self._clear_attachments)
        self._popup(menu, pos)

    def _paste_into_box(self) -> None:
        hosted = self.stage.hosted
        if hosted is not None and hosted.widget is self.ask_box:
            hosted.paste()  # the overlay's own clipboard
        else:
            self.ask_box.paste_clipboard()

    def _attach_files(self) -> None:
        if self._chooser() is not None:
            self._through_portal(lambda then, fallback: self._file_chooser.open_files("Attach to your question", Path.home(), then, fallback),
                                 self._attach_files_named, self._attach_files_with_qt)
        else:
            self._attach_files_with_qt()

    def _attach_files_with_qt(self) -> None:
        # The system's file dialog needs the keyboard, which the ask box holds on the overlay: out of its way meanwhile.
        self.ask_box.pause()
        try:
            files, _ = QFileDialog.getOpenFileNames(None, "Attach to your question", str(Path.home()))
        finally:
            self.ask_box.resume()
        self._attach_files_named(files)

    def _chooser(self):
        """The desktop's own file chooser (portal.py), on Linux where the portal has one; else None (Qt's)."""
        if not hasattr(self, "_file_chooser"):
            self._file_chooser = None
            if sys.platform.startswith("linux"):
                try:
                    from . import portal

                    if portal.available():
                        self._file_chooser = portal.FileChooser(self)
                except ImportError:  # no QtDBus
                    pass
        return self._file_chooser

    def _through_portal(self, ask, then, fallback) -> None:
        """`ask(then, fallback)` the portal, the ask box out of the keyboard's way until it answers."""
        shown = self.ask_box.isVisible()
        if shown:
            self.ask_box.pause()

        def done(run, *args) -> None:
            if shown:
                self.ask_box.resume()
            run(*args)

        ask(lambda names: done(then, names), lambda: done(fallback))

    def _attach_files_named(self, names: list[str]) -> None:
        room = attachments.MAX_COUNT - len(self.attached)
        # Never a network path (\\server\share): even looking at one would sign in to that server as you.
        local = [n for n in names if n and not n.startswith(("//", "\\\\"))]
        if len(local) > room:
            self.say("That's a lot of files", f"I took the first {max(0, room)}: {attachments.MAX_COUNT} attachments at most.", timeout_s=8)
        for name in local[: max(0, room)]:
            self._attach(lambda name=name: attachments.from_path(Path(name)))

    def _attach_pasted(self, kind: str, payload) -> None:
        if kind == "files":
            self._attach_files_named(list(payload))
        elif kind == "image":
            self._attach(lambda: attachments.from_image(payload))
        elif kind == "text":
            self._attach(lambda: attachments.from_text(payload))

    def _attach(self, make) -> None:
        """Read it off the screen's thread (a big file or picture takes a moment), then add it."""
        self.background.run(make, self._attached_one)

    def _attached_one(self, result) -> None:
        try:
            if isinstance(result, Exception):
                raise result
            attachments.check_total(self.attached, result)
        except attachments.AttachError as exc:
            self.say("Couldn't attach that", str(exc)[:1].upper() + str(exc)[1:] + ".", timeout_s=8)
            return
        except Exception as exc:  # reported, never fatal
            self.say("Couldn't attach that", str(exc), timeout_s=8)
            return
        self.attached.append(result)
        self.ask_box.set_attachments([a.label() for a in self.attached])

    def _remove_attachment(self, index: int) -> None:
        if 0 <= index < len(self.attached):
            del self.attached[index]
            self.ask_box.set_attachments([a.label() for a in self.attached])

    def _clear_attachments(self) -> None:
        self.attached.clear()
        self.ask_box.set_attachments([])

    def submit(self, text: str) -> None:
        now = self._now()
        self._last_ask = now
        if self._asking_name:
            self._asking_name = False
            self.state.set("name", text.strip()[:40])
            self.state.save()
            self._menu_changed()
            self.ask_box.dismiss()
            self.behavior.react("hop", now)
            self.say(f"{self.name}! I love it.", HELP, timeout_s=25)
            return
        if self._renaming is not None:
            chat_id, self._renaming = self._renaming, None
            self._rename(chat_id, text)
            self.open_ask()  # back to the chat, renamed
            return
        if self._instructing is not None:
            chat_id, self._instructing = self._instructing, None
            self._set_chat_instructions(chat_id, text)
            self.open_ask()
            return
        if not self.attached and self._local(text):  # with something attached, it's a question
            return
        brain = self._brain()
        if brain is None:
            self.ask_box.set_answer(
                "I haven't found an AI to ask yet. Any of these works: an AI command-line tool you're "
                "signed in to (Claude Code, Codex, Gemini CLI, Muse Code, Grok...), a model server on this "
                "computer (Ollama, LM Studio, llama.cpp, vLLM), or an API key, picked under **Brain** in my "
                "menu.\n\n" + HELP
            )
            return
        attached = list(self.attached)
        refused = brains.cant_take(brain, attached)
        if refused:  # kept, for a brain that can
            self.ask_box.entry.setText(text)
            self.ask_box.set_answer(self._transcript(f"*{refused}*"), at_end=True)
            return
        self.attached.clear()
        self.ask_box.set_attachments([])
        self._asking = (self.chat.id, text, attached)
        you = f"**You:** {text}" + (f"\n\n*Attached: {attachments.mentioned(attached)}*" if attached else "")
        self.ask_box.set_answer(self._transcript(f"{you}\n\n*{brain.label} is thinking…*"), at_end=True)
        self.behavior.set_thinking(True, now)
        self._send(brain, text or "Have a look at what I attached.", attached)

    # -- what a question goes with: the chat, fitted to the brain (context.py), your instructions and memory

    def _instructions(self) -> str:
        """Yours, for every chat: Settings, else the settings file."""
        picked = self.state.get("instructions")
        return str(self.config["chats"].get("instructions", "") if picked is None else picked)

    def _context_cap(self) -> int:
        picked = self.state.get("context_tokens")
        try:
            cap = int(self.config["chats"].get("context_tokens", context.DEFAULT_CAP) if picked is None else picked)
        except (TypeError, ValueError):
            cap = context.DEFAULT_CAP
        return max(2_000, min(cap, 2_000_000))

    def _send(self, brain: brains.Brain, question: str, attached, *, fold: bool = True, retried: bool = False) -> None:
        """Ask `brain`, with as much of the chat as it can take: first summing up the chat's earlier part, when
        it has outgrown that (a step of its own, said in the box)."""
        chat, timeout = self.chat, float(self.config["ai"]["timeout_seconds"])
        base = brains.system_prompt(self.name, self._companion().label.lower())
        everywhere, remembered = self._instructions(), self.memory.texts()
        asked_tokens = context.tokens(attachments.in_question(question, attached)) + attachments.media_tokens(attached)
        room = context.budget(brains.context_window(brain), self._context_cap(), context.system_text(base, everywhere, chat.instructions, remembered), asked_tokens)
        plan = context.plan(chat.history(brain.label), chat.history(), chat.summary, chat.summarized, room, question, fold)
        if plan.fold:
            self._folding = (chat.id, plan.fold_to, room, brain, question, attached, retried)
            system, request = context.summary_request(plan.summary, plan.fold, room)
            self.ask_box.set_answer(self._transcript(f"*Catching {brain.label} up on this chat's earlier part…*"), at_end=True)
            self.compactor.ask(brain, system, [], request, timeout)
            return
        system = context.system_text(base, everywhere, chat.instructions, remembered, plan.summary, plan.recalled)
        sent = context.tokens(system) + sum(context.pair_tokens(pair) for pair in plan.recent) + asked_tokens
        self._asked = {"brain": brain, "question": question, "attached": attached, "retried": retried, "tokens": sent}
        self.asker.ask(brain, system, plan.recent, question, timeout, attached)
        if brain.type == "openai" and not brains.window_known(brain):
            self.background.run(partial(brains.learn_window, brain), lambda _window: None)  # for the next question

    def _compacted(self, summary: str) -> None:
        folding, self._folding = self._folding, None
        if folding is None or self._asking is None or folding[0] != self.chat.id or self._asking[0] != self.chat.id:
            return  # the question went (another chat, or you closed the box)
        _, covers, room, brain, question, attached, retried = folding
        if not summary.strip():
            self._send(brain, question, attached, fold=False, retried=retried)
            return
        self.chat.summary, self.chat.summarized = context.clip(summary.strip(), max(300, room // 5)), covers
        self._save_chat()
        self._send(brain, question, attached, retried=retried)

    def _compact_failed(self, _error: str) -> None:
        """No summary: the question goes anyway, with the recent turns and the earlier ones that bear on it."""
        folding, self._folding = self._folding, None
        if folding is None or self._asking is None or folding[0] != self.chat.id or self._asking[0] != self.chat.id:
            return
        _, _covers, _room, brain, question, attached, retried = folding
        self._send(brain, question, attached, fold=False, retried=retried)

    def _answered(self, answer: str) -> None:
        now = self._now()
        self.behavior.set_thinking(False, now)
        if self._asking is None or self._asking[0] != self.chat.id:  # asked in a chat since left: not this one's
            self._asking = None
            return
        _, text, attached = self._asking
        self._asking = None
        sent = attachments.in_question(text or "Have a look at what I attached.", attached)
        asked = self._asked
        brain = asked["brain"] if asked else self._brain(wait=False)
        label = brain.label if brain else ""
        if brain is not None and brain.local:
            self.background.run(partial(brains.learn_window, brain), lambda _window: None)  # a model loaded now says its own
        self.chat.add(chats.Message("user", text, sent=sent if sent != text else "", attached=[a.name for a in attached], brain=label))
        self.chat.add(chats.Message("assistant", answer, brain=label))
        self._save_chat()
        self.ask_box.set_answer(self._transcript(), at_end=True)
        self.ask_box.set_resettable(True)
        self.behavior.set_talking(True, now)
        QTimer.singleShot(int(min(max(len(answer) / 18, 2), 10) * 1000), lambda: self.behavior.set_talking(False, self._now()))

    def _failed(self, error: str) -> None:
        asked = self._asked
        if asked and not asked["retried"] and context.too_long(error) and self._asking is not None and self._asking[0] == self.chat.id:
            # Too long for it after all (a window smaller than it said, or than guessed): once more, with half.
            brains.shrink_window(asked["brain"], asked["tokens"])
            self._send(asked["brain"], asked["question"], asked["attached"], retried=True)
            return
        self.behavior.set_thinking(False, self._now())
        if self._asking is None or self._asking[0] != self.chat.id:
            self._asking = None
            return
        _, text, attached = self._asking
        self._asking = None
        # Back in the box, to try again (or with another brain).
        self.attached = attached + self.attached
        self.ask_box.set_attachments([a.label() for a in self.attached])
        if text and not self.ask_box.entry.text():
            self.ask_box.entry.setText(text)
        self.ask_box.set_answer(self._transcript(f"**You:** {text}\n\n*Hmm, that didn't work.* {error}"), at_end=True)

    def _memory_reply(self, kind: str, what: str) -> str:
        """Remembering for every chat, as you asked, and forgetting it again: Chatmon's own (memory.py)."""
        if kind == "remember":
            refused = self.memory.add(what)
            return refused or f"I'll remember that: *{what.strip(' .')}*. Every brain you ask gets it with each question."
        if kind == "forget":
            gone = self.memory.forget(what)
            if not gone:
                return "I don't remember anything like that. *What do you remember* lists it all."
            return "Forgotten: " + "; ".join(f"*{g}*" for g in gone) + "."
        if kind == "forget-all":
            n = len(self.memory.items)
            self.memory.clear()
            return f"Forgotten, all {n} of them." if n else "There was nothing to forget."
        if not self.memory.items:
            return "Nothing yet. Tell me *remember that …* and I'll keep it for every chat."
        listed = "\n".join(f"- {i.text}" for i in self.memory.items)
        return f"What I remember, for every chat:\n\n{listed}\n\n*Forget that …* takes one out."

    def _offline(self, question: str, reply: str) -> None:
        """An answer of Chatmon's own: shown under the chat, marked as such, and never part of it (no brain
        sees it, and it isn't kept)."""
        self.ask_box.set_answer(self._transcript(f"**You:** {question}\n\n{reply}\n\n*{NO_AI}*"), at_end=True)

    def _local(self, text: str) -> bool:
        """What Chatmon does by itself, without any AI: True if it was that. Anything else is the AI's."""
        now = self._now()
        asked = memory.command(text)
        if asked is not None:
            self._offline(text, self._memory_reply(*asked))
            self._menu_changed()
            return True
        command = reminders.parse_command(text, datetime.now())
        if command is not None and command.kind == "unclear":
            asked = re.match(r"^(?:please\s+)?remind me\b[\s,:]*(.*)$", text.strip(), re.I | re.S)
            if asked and offline.reminder_or_question(asked.group(1)):
                return False  # "remind me how decorators work": a question, not a reminder
        if command is not None:
            if command.kind == "unclear":
                self._offline(text, "When should I remind you? Try *remind me in 20m to stretch* or *remind me at 3pm to call Sam*.")
            elif command.kind == "focus":
                self.ask_box.dismiss()
                self.start_focus(command.minutes or float(self.config["focus"]["minutes"]))
            else:
                r = self.reminders.add(command.due.timestamp(), command.text, command.kind)
                self.save()
                when = reminders.describe(r.due, time.time())
                what = f"Timer set: **{r.text}**, done {when}." if r.kind == "timer" else f"I'll remind you {when}: **{r.text}**"
                self._offline(text, what)
                self.behavior.react("hop", now)
            return True
        kept = offline.parse_kept(text)
        if kept is not None:
            self._offline(text, self._kept(kept))
            return True
        reply = offline.answer(text, datetime.now())
        if reply is not None:
            self._offline(text, reply)
            return True
        word = text.lower().strip(" ?!.")
        if word in ("help", "what can you do", "commands"):
            self._offline(text, HELP_ALL)
        elif word in ("status", "battery", "system status", "how's my computer"):
            self._offline(text, self._status())
        elif word in ("stop focus", "end focus", "cancel focus"):
            self.stop_focus()
            self._offline(text, "Focus stopped.")
        elif word in ("hide", "go hide", "go away"):
            self.ask_box.dismiss()
            self.set_hidden(True)
        elif word in ("new chat", "/new", "reset"):
            self._new_chat()
        elif word in ("rename chat", "rename this chat", "name this chat") and self.chat.messages:
            self._ask_new_name(self.chat.id)
        elif word in ("breaks off", "no breaks", "stop break reminders", "break reminders off", "breaks on", "break reminders on"):
            on = word in ("breaks on", "break reminders on")
            self._override(("breaks", "remind"), on)
            self.state.save()
            self.config["breaks"]["remind"] = on
            self._offline(text, "Break reminders are on." if on else "No more break reminders. *Breaks on* brings them back.")
        elif word in ("focus alerts off", "focus notifications off", "focus alerts on", "focus notifications on"):
            on = word.endswith(" on")
            self._override(("focus", "tell_when_done"), on)
            self.state.save()
            self.config["focus"]["tell_when_done"] = on
            self._offline(text, "I'll say when a focus session ends." if on else "Focus sessions will end quietly. *Focus alerts on* brings it back.")
        elif word in ("settings", "preferences", "options", "open settings"):
            self.ask_box.dismiss()
            self.open_settings()
        elif word in ("history", "chats", "my chats", "chat history"):
            self._show_history(self.ask_box.history_button.mapToGlobal(QPoint(0, self.ask_box.history_button.height())))
        elif word in ("what's new", "whats new", "what is new", "changes", "changelog", "release notes"):
            self.show_whats_new()
        elif word in ("check for updates", "update", "updates", "update yourself", "install update"):
            self.ask_box.dismiss()
            self._update_now() if self.updater.ready else self.check_for_updates()
        elif word in ("report a problem", "report a bug", "report bug", "bug", "report"):
            self.ask_box.set_answer("Opening a problem report in your browser…")
            self.report_problem()
        elif word in ("suggest an idea", "feature request", "suggest a feature", "idea"):
            self.ask_box.set_answer("Opening an idea form in your browser…")
            self.report_problem(report.IDEA)
        elif word in ("version", "what version", "which version"):
            self._offline(text, f"I'm Chatmon {__version__}.")
        else:
            return False
        return True

    # -- notes, the stopwatch, and reminders by number

    MAX_NOTES = 200
    MAX_NOTE = 2000  # characters

    def _notes(self) -> list[dict]:
        notes = self.state.get("notes")
        return [n for n in notes if isinstance(n, dict) and isinstance(n.get("text"), str)] if isinstance(notes, list) else []

    def _kept(self, asked: offline.Asked) -> str:
        """Notes, the stopwatch and reminders, which Chatmon keeps: do what's asked, say what was done."""
        notes = self._notes()
        upcoming = [r for r in self.reminders.upcoming() if r.kind != "focus"]
        if asked.kind == "note":
            if len(notes) >= self.MAX_NOTES:
                return f"I keep {self.MAX_NOTES} notes at most: *delete note 1* makes room."
            notes.append({"text": asked.arg[: self.MAX_NOTE], "at": time.time()})
            self._set_notes(notes)
            self.behavior.react("hop", self._now())
            return f"Noted (note {len(notes)}). *delete note {len(notes)}* takes it back."
        if asked.kind == "notes":
            return "\n".join(f"{i}. {n['text']}" for i, n in enumerate(notes, 1)) if notes else "No notes yet: *note: buy milk* makes one."
        if asked.kind == "delete note":
            i = int(asked.arg)
            if not 1 <= i <= len(notes):
                return f"There's no note {i}." + (f" You have {len(notes)}." if notes else "")
            gone = notes.pop(i - 1)
            self._set_notes(notes)
            return f"Deleted note {i}: {gone['text'][:80]}"
        if asked.kind == "clear notes":
            self._set_notes([])
            return f"Deleted {len(notes)} note{'s' if len(notes) != 1 else ''}."
        if asked.kind == "stopwatch":
            if self._stopwatch is None:
                self._stopwatch = self._now()
                self._menu_changed()
                return "Stopwatch started. *stop stopwatch* stops it."
            return f"Stopwatch: **{offline_clock(self._now() - self._stopwatch)}** and counting."
        if asked.kind == "stop stopwatch":
            if self._stopwatch is None:
                return "The stopwatch isn't running: *stopwatch* starts it."
            took, self._stopwatch = self._now() - self._stopwatch, None
            self._menu_changed()
            return f"Stopwatch stopped at **{offline_clock(took)}**."
        if asked.kind == "reminders":
            if not upcoming:
                return "No reminders or timers set."
            return "\n".join(f"{i}. {r.kind.capitalize()} {reminders.describe(r.due, time.time())}: {r.text}" for i, r in enumerate(upcoming, 1))
        if asked.kind == "cancel reminder":
            i = int(asked.arg)
            if not 1 <= i <= len(upcoming):
                return f"There's no reminder {i}: *reminders* lists them."
            self._cancel(upcoming[i - 1].id)
            return f"Cancelled: {upcoming[i - 1].text}"
        if asked.kind == "clear reminders":
            for r in upcoming:
                self.reminders.cancel(r.id)
            self.save()
            return f"Cancelled {len(upcoming)} reminder{'s' if len(upcoming) != 1 else ''}."
        return "Hmm."

    def _set_notes(self, notes: list[dict]) -> None:
        self.state.set("notes", notes)
        self.state.save()
        self._menu_changed()

    def _copy(self, text: str) -> None:
        """Onto the clipboard: the overlay's own, where Chatmon draws on one."""
        if hasattr(self.stage.surface, "copy"):
            self.stage.clipboard_copy(text)
        else:
            QGuiApplication.clipboard().setText(text)

    def _notes_menu(self, sub: QMenu) -> None:
        for i, note in enumerate(self._notes(), 1):
            text = " ".join(note["text"].split())
            item = sub.addMenu(f"{i}. {text[:48] + '…' if len(text) > 48 else text}")
            item.addAction("Copy", partial(self._copy, note["text"]))
            item.addAction("Delete", partial(self._kept, offline.Asked("delete note", str(i))))
        sub.addSeparator()
        sub.addAction("Add a note…", partial(self.open_ask, "note: "))

    def _status(self) -> str:
        lines = []
        battery = heads_up.read_battery()
        if battery:
            lines.append(f"- Battery: {battery[0]:.0f}%{' (plugged in)' if battery[1] else ''}")
        for folder, percent in heads_up.read_disks(heads_up.disk_folders()):
            lines.append(f"- Disk for {folder}: {percent:.0f}% full")
        upcoming = self.reminders.upcoming()
        for r in upcoming[:5]:
            lines.append(f"- {r.kind.capitalize()} {reminders.describe(r.due, time.time())}: {r.text}")
        if not upcoming:
            lines.append("- No reminders set")
        brain = self._brain()
        lines.append(f"- Brain: {brain.label if brain else 'none'}" + (f" ({brains.describe(brain)})" if brain and brains.describe(brain) else ""))
        return "\n".join(lines)

    # -- hiding

    def set_hidden(self, on: bool) -> None:
        self.behavior.set_hidden(on, self._now())
        if on:
            self.stage.dismiss_message()
            self.ask_box.dismiss()
        self._menu_changed()

    # -- reminders, timers, focus, breaks

    def start_focus(self, minutes: float) -> None:
        old = self.reminders.focus()
        if old:
            self.reminders.cancel(old.id)
        self.reminders.add(time.time() + minutes * 60, f"{minutes:g}-minute focus", "focus")
        self.save()
        self.behavior.react("hop", self._now())
        self.say("Focus time", f"{minutes:g} minutes. I'll keep quiet until then.", timeout_s=5)

    def stop_focus(self) -> None:
        focus = self.reminders.focus()
        if focus:
            self.reminders.cancel(focus.id)
            self.save()
            self.say("Focus stopped", timeout_s=3)

    def _check_reminders(self) -> None:
        now = time.time()
        due = self.reminders.pop_due(now)
        if not due:
            return
        self.save()
        rest = [r for r in due if r.kind != "focus"]
        if len(rest) < len(due) and self.config["focus"].get("tell_when_done", True):
            self.behavior.react("beam", self._now())
            minutes = float(self.config["focus"]["minutes"])
            self.say(
                "Focus session done!",
                "Nice work. Take five minutes away from the screen.",
                [("Another round", partial(self.start_focus, minutes)), ("Done", None)],
                timeout_s=None,
            )
        if not rest:
            return

        def line(r: reminders.Reminder) -> str:
            late = f" (due at {reminders.clock(datetime.fromtimestamp(r.due))})" if now - r.due > 120 else ""
            return r.text + late

        snooze = float(self.config["breaks"]["snooze_minutes"])
        buttons = [(f"Snooze {snooze:g} min", partial(self._snooze, rest, snooze)), ("Done", None)]
        if len(rest) == 1:
            title = "Time's up!" if rest[0].kind == "timer" else "Reminder"
            self.alert(f"reminder:{rest[0].id}", title, line(rest[0]), buttons)
        else:
            self.alert("reminders", "Reminders", "\n".join(f"- {line(r)}" for r in rest), buttons)

    def _snooze(self, due: list[reminders.Reminder], minutes: float) -> None:
        for r in due:
            self.reminders.add(time.time() + minutes * 60, r.text, r.kind)
        self.save()

    def _check_time(self) -> None:
        now = time.time()
        if now - self._last_wall > 300:  # the computer was asleep
            self.breaks.away(self._last_wall)
            self.breaks.back(now)
        self._last_wall = now
        self._check_away()
        self._check_accessibility()
        if self._menu_clock != self._time_labels():
            self._menu_changed()
        mono = self._now()
        for source, (state, since) in list(self.agents.items()):
            if state == "working" and mono - since > WORK_EXPIRES:
                del self.agents[source]
        self._update_working()
        if (
            self.config["breaks"].get("remind", True) and self.breaks.due(now) and self.reminders.focus() is None
            and not self.stage.message_visible() and not self.ask_box.isVisible()
        ):
            minutes = self.breaks.minutes_on(now)
            snooze = float(self.config["breaks"]["snooze_minutes"])
            self.breaks.snooze(now, snooze)
            self.behavior.react("wave", mono)
            self.say(
                "Time for a break?",
                f"You've been at the screen for {minutes} minutes. Stand up, stretch, and look at something far away.",
                [("Taking one", partial(self.breaks.took_break, now)), (f"Snooze {snooze:g} min", None)],
                timeout_s=120,
            )

    def _watch_screen_lock(self) -> None:
        """Hear the screen lock and the computer sleep (time away counts as a break). macOS has no
        documented lock notification: there, time without input (presence.Desk) tells the same."""
        if sys.platform == "win32":
            from . import winlock

            self._lock_watcher = winlock.LockWatcher(self._screen_locked, self._sleeping)
            return
        if sys.platform == "darwin":
            # PyQt ships QtDBus on macOS too, and on an Intel Mac with Homebrew's dbus Qt finds its libdbus and
            # asks for a session bus macOS doesn't have: a wait on the screen's thread at every start, for nothing.
            return
        try:  # D-Bus: Linux and the BSDs
            from . import linuxsession
        except ImportError:
            return
        self._lock_watcher = linuxsession.SessionWatcher(self._screen_locked, self._sleeping)
        self._power_watcher = linuxsession.PowerProfile(self._power_saving)

    def _power_saving(self, on: bool) -> None:
        self.stage.power_saving = on

    @pyqtSlot(bool)
    def _screen_locked(self, locked: bool) -> None:
        now = time.time()
        if locked:
            self.breaks.away(now)
        else:
            self.breaks.back(now)
            self.behavior.wake(self._now())

    def _sleeping(self, going: bool) -> None:
        """The computer is going to sleep (True), or has woken (False): as good as stepping away."""
        self._screen_locked(going)
        if not going:
            self._last_wall = time.time()  # not a gap to be guessed at as well

    # -- heads-ups

    def _check_system(self) -> None:
        notices = []
        battery = self.watcher.battery(heads_up.read_battery())
        if battery:
            notices.append(battery)
        notices += self.watcher.disks(heads_up.read_disks(heads_up.disk_folders()), date.today())
        for notice in notices:
            self.alert(notice.key, notice.title, notice.text)

    def _check_updates(self) -> None:
        if not self.config["heads_up"]["updates"]:
            return
        # Each reads what the system already knows (no network): the desktop's own updater keeps it fresh.
        checks = heads_up.update_checks()
        self._update_counts = {}
        self._restart_needed = False
        for check in checks:
            if check.name == "packagekit":
                from . import packagekit

                counter = packagekit.UpdateCount(self)
                self._update_procs.append(counter)
                counter.counted.connect(partial(self._packagekit_counted, counter, len(checks)))
                counter.start()
                continue
            proc = QProcess(self)
            self._update_procs.append(proc)
            proc.finished.connect(partial(self._updates_counted, proc, check, len(checks)))
            proc.errorOccurred.connect(partial(self._update_check_failed, proc, check, len(checks)))
            proc.start(check.argv[0], check.argv[1:])

    def _update_check_failed(self, proc: QProcess, check: heads_up.UpdateCheck, expected: int, error) -> None:
        if sip.isdeleted(proc):
            return
        if error == QProcess.ProcessError.FailedToStart:
            self._forget_update_proc(proc)
            proc.deleteLater()
            self._tally_updates(check.name, 0, expected)

    def _packagekit_counted(self, counter, expected: int, count: int | None) -> None:
        self._forget_update_proc(counter)
        counter.deleteLater()
        self._tally_updates("packagekit", count or 0, expected)

    def _forget_update_proc(self, proc: QProcess) -> None:
        if proc in self._update_procs:
            self._update_procs.remove(proc)

    def _stop_update_checks(self) -> None:
        """Quitting: the checks still running stop here, never to be heard from again (a QProcess destroyed
        while it runs says it finished, as it goes)."""
        for proc in self._update_procs:
            if not isinstance(proc, QProcess):  # PackageKit's count: a D-Bus transaction, not a process
                if not sip.isdeleted(proc):
                    proc.stop()
                continue
            if not sip.isdeleted(proc):
                proc.finished.disconnect()
                proc.errorOccurred.disconnect()
                proc.kill()
                proc.waitForFinished(1000)
        self._update_procs.clear()

    def _updates_counted(self, proc: QProcess, check: heads_up.UpdateCheck, expected: int, code: int, _status) -> None:
        if sip.isdeleted(proc):
            return
        self._forget_update_proc(proc)
        output = bytes(proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        proc.deleteLater()
        if check.name == "windows":
            self._restart_needed = heads_up.windows_restart_needed(output)
        self._tally_updates(check.name, check.count(output, code) or 0, expected)

    def _tally_updates(self, name: str, count: int, expected: int) -> None:
        self._update_counts[name] = count
        if len(self._update_counts) == expected:
            notice = self.watcher.updates(sum(self._update_counts.values()), date.today(), self._restart_needed)
            if notice and not self.stage.message_visible():
                self.behavior.react("wave", self._now())
                buttons = [("OK", None)]
                if sys.platform == "win32":
                    buttons.insert(0, ("Open Windows Update", partial(QDesktopServices.openUrl, QUrl("ms-settings:windowsupdate"))))
                self.say(notice.title, notice.text, buttons, timeout_s=60)

    # -- updating Chatmon, what's new, and reporting problems

    def _checks_updates(self) -> bool:
        picked = self.state.get("check_updates")
        return bool(self.config["updates"]["check"] if picked is None else picked)

    def _maybe_check_updates(self) -> None:
        """Once a day or so, while Chatmon runs: never more often, whatever restarts it."""
        if self._checks_updates() and time.time() - float(self.state.get("update_checked") or 0) > updates.CHECK_EVERY:
            self.state.set("update_checked", time.time())
            self.state.save()
            self.updater.check(self._install_kind)

    def check_for_updates(self) -> None:
        """You asked: look now, and say what was found, even if it's nothing."""
        self._checking_by_hand = True
        self.say("Looking for updates…", timeout_s=10)
        self.state.set("update_checked", time.time())
        self.state.save()
        self.updater.check(self._install_kind, by_hand=True)

    def _update_available(self, release: updates.Release) -> None:
        self._checking_by_hand = False
        self._install_kind = self.updater.kind
        self._menu_changed()
        self.behavior.react("wave", self._now())
        self.say(
            f"Chatmon {release.version} is ready",
            "Downloaded and checked. Updating takes a moment, then I'll be right back.",
            [("Update now", self._update_now), ("What's new", partial(self._show_release_notes, release)), ("Later", None)],
            timeout_s=90,
        )

    def _update_out(self, release: updates.Release, how: str) -> None:
        self._checking_by_hand = False
        self._install_kind = self.updater.kind
        first = ("Release page", partial(QDesktopServices.openUrl, QUrl(release.page)))
        if "metered" in how:
            first = ("Download it", self.check_for_updates)
        self.say(f"Chatmon {release.version} is out", how, [first, ("What's new", partial(self._show_release_notes, release)), ("OK", None)], timeout_s=60)

    def _up_to_date(self) -> None:
        self._install_kind = self.updater.kind
        if self._checking_by_hand:
            self._checking_by_hand = False
            self.say("You're up to date", f"This is the newest Chatmon, {__version__}.", timeout_s=6)

    def _update_failed(self, why: str) -> None:
        print(f"{paths.APP}: {why}", file=sys.stderr)
        if self._checking_by_hand or self.updater.ready is not None or why.startswith("The update"):
            self._checking_by_hand = False
            self.say("No update this time", why, [("OK", None)], timeout_s=30)

    def _update_now(self) -> None:
        self.save()
        self.say("Updating…", "The installer may ask for your password. I'll be back in a moment.", timeout_s=None)
        self.updater.install()

    def _show_release_notes(self, release: updates.Release) -> None:
        self.ask_box.show_notes(self.stage.head_point(), f"What's new in Chatmon {release.version}", release.notes or "No notes for this release.")

    def _whats_new_after_update(self) -> bool:
        """The first start after an update: what changed since the version you last ran. True if shown."""
        seen = self.state.get("seen_version")
        self.state.set("seen_version", __version__)
        self.state.save()
        if seen is None:
            # Never noted: a new install (nothing to tell), or an update from before 0.6.0, which didn't note it.
            if not (set(self.state.data) - {"seen_version", "x"}) or "name" not in self.state.data:
                return False
            seen = "0"
            releases = [r for r in changelog.since(seen, __version__) if changelog.version_key(r.version) == changelog.version_key(__version__)]
        else:
            releases = changelog.since(seen, __version__)
        if not releases or not updates.newer(__version__, seen):
            return False
        self.behavior.react("beam", self._now())
        self.show_whats_new(releases, updated=True)
        return True

    def show_whats_new(self, releases: list[changelog.Release] | None = None, updated: bool = False) -> None:
        releases = releases or [r for r in [changelog.find(__version__)] if r]
        title = f"Updated to Chatmon {__version__}" if updated else f"What's new in Chatmon {__version__}"
        body = changelog.notes(releases) if releases else "No notes for this version."
        body += f"\n\nFound a problem? [Report it]({self._report_url()}) · [All changes](https://github.com/{updates.REPO}/releases)"
        self.ask_box.show_notes(self.stage.head_point(), title, body)

    def _report_url(self, template: str = report.BUG) -> str:
        brain = self._brain(wait=False)
        # A built-in brain by its name; one of your own only as that (its name could be a server of yours).
        label = (brain.label if brain.name in brains.PRESETS else "A brain of my own") if brain else ""
        return report.url(template, install=self._install_kind or "", brain=label)

    def report_problem(self, template: str = report.BUG) -> None:
        QDesktopServices.openUrl(QUrl(self._report_url(template)))

    def open_log(self) -> None:
        log = log_file()
        if log.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(log)))
        else:
            self.say("No log yet", "I write one when I run without a terminal, and nothing has gone wrong in it so far.", timeout_s=8)

    def _problem(self) -> None:
        """Something in Chatmon failed (it's in the log): offer to report it, once a run."""
        if self._problem_told:
            return
        self._problem_told = True
        buttons = [("Report it", self.report_problem)]
        if log_file().exists():
            buttons.append(("Open the log", self.open_log))
        self.say("Something went wrong in me", "I kept going, but you can tell my maker what happened.", buttons + [("OK", None)], timeout_s=45)

    def _help_menu(self, sub: QMenu) -> None:
        sub.addAction(f"What's new in {__version__}", self.show_whats_new)
        if self.updater.ready is not None and self.updater.release is not None:
            sub.addAction(f"Install Chatmon {self.updater.release.version}", self._update_now)
        else:
            sub.addAction("Check for updates now", self.check_for_updates)
        auto = sub.addAction("Check for updates every day")
        auto.setCheckable(True)
        auto.setChecked(self._checks_updates())
        auto.toggled.connect(self._set_check_updates)
        sub.addSeparator()
        sub.addAction("Report a problem…", self.report_problem)
        sub.addAction("Suggest an idea…", partial(self.report_problem, report.IDEA))
        sub.addAction("Open the log", self.open_log)
        version = sub.addAction(f"Chatmon {__version__}")
        version.setEnabled(False)

    def _set_check_updates(self, on: bool) -> None:
        self.state.set("check_updates", on)
        self.state.save()
        self._menu_changed()
        if on:
            self._maybe_check_updates()

    # -- messages from hooks and scripts

    def _accept(self) -> None:
        # Each connection is read and answered from the event loop, never from inside Qt's notice that its
        # socket is ready. A sender waits only half a second for its answer, and a slow or busy computer can
        # take longer: answering one that has hung up makes Qt tear its socket down right there, and then a
        # connection accepted in the same pass could go unheard for good (`chatmon quit`, on an Intel Mac).
        queued = Qt.ConnectionType.QueuedConnection
        while self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            buffer = bytearray()
            sock.readyRead.connect(partial(self._received, sock, buffer, False), type=queued)
            sock.disconnected.connect(partial(self._received, sock, buffer, True), type=queued)
            QTimer.singleShot(0, partial(self._received, sock, buffer, False))  # anything already in

    def _received(self, sock: QLocalSocket, buffer: bytearray, closed: bool) -> None:
        """Handle each complete line as it arrives and answer it, so the
        sender can hang up knowing it got here."""
        if sip.isdeleted(sock):  # done with before this call came round
            return
        if sock.bytesAvailable():  # (reading a socket Qt has closed only gets a warning)
            buffer.extend(bytes(sock.readAll()))
        if len(buffer) > events.MAX_MESSAGE:
            buffer.clear()
            sock.abort()
            return
        while b"\n" in buffer or (closed and buffer):
            line, _, rest = bytes(buffer).partition(b"\n")
            buffer[:] = rest
            for message in events.parse_lines(line):
                self.handle(message)
            if not closed and sock.state() == QLocalSocket.LocalSocketState.ConnectedState:
                sock.write(events.ACK)
                sock.flush()
        if closed:
            sock.deleteLater()

    def handle(self, message: dict) -> None:
        message = events.clean(message)
        kind = message.get("type")
        now = self._now()
        if kind == "event" and message.get("event") in events.EVENTS:
            self._agent_event(message["event"], str(message.get("source") or "agent"), str(message.get("message") or ""))
        elif kind == "say" and message.get("text"):
            self.behavior.wake(now)
            self.behavior.react("talk", now)
            self.say(self.name, str(message["text"]), timeout_s=15)
        elif kind == "remind":
            command = reminders.parse_command("remind me " + str(message.get("text", "")), datetime.now())
            if command and command.kind == "reminder":
                r = self.reminders.add(command.due.timestamp(), command.text)
                self.save()
                self.say("Reminder set", f"{reminders.describe(r.due, time.time())}: {r.text}", timeout_s=6)
        elif kind == "show":
            self.set_hidden(False)
            self.behavior.poke(now)
        elif kind == "quit":  # `chatmon quit`: an installer updating it, say
            QTimer.singleShot(0, self.quit)  # once the sender has heard back

    def _agent_event(self, event: str, source: str, text: str) -> None:
        now = self._now()
        # The same news twice in a moment (an agent running its own hook and a borrowed one): once is enough.
        if self._last_event == (source, event) and now - self._last_event_at < 1.5:
            return
        self._last_event, self._last_event_at = (source, event), now
        label = pretty(source)
        key = f"agent:{source}"
        self.behavior.wake(now)
        if event == "working":
            self.agents[source] = ("working", now)
            if self._alert_key == key:
                self.stage.dismiss_message()
        elif event == "needs-you":
            self.agents[source] = ("needs-you", now)
            self.alert(key, f"{label} needs you", text or f"{label} is waiting for you.")
        else:
            self.agents.pop(source, None)
            if self._alert_key == key:
                self.stage.dismiss_message()
            # An agent's reply can hold code or secrets: on screen only if you said so.
            show = bool(self.config["agents"]["show_replies"])
            snippet = (text if len(text) <= 220 else text[:217].rstrip() + "…") if show else ""
            if event == "done":
                self.behavior.react("hop", now)
                if not self.ask_box.isVisible():
                    self.say(f"{label} finished", snippet, timeout_s=8)
            elif event == "success":
                self.behavior.react("beam", now)
                self.say(f"{label}: success!", snippet, timeout_s=8)
            elif event == "error":
                self.say(f"{label} hit a problem", snippet or "Take a look when you can.", timeout_s=20)
        self._update_working()

    def _update_working(self) -> None:
        working = any(state == "working" for state, _ in self.agents.values())
        self.behavior.set_working(working, self._now())

    # -- menus

    def show_menu(self, pos: QPoint) -> None:
        """The penguin's own menu (right-click): it stands still and looks at you while it's open."""
        self._menu_open = True
        self.behavior.set_attending(True, self._now())
        if self.stage.draws_menus():
            self._fill_menu()
            self.stage.open_menu(self.menu, pos)
        else:
            self.menu.popup(pos)

    def _menu_closed(self) -> None:
        if self._menu_open and not self.stage.menu.is_open():
            self._menu_open = False
            self.behavior.set_attending(self.ask_box.isVisible(), self._now())
        if self._menu_stale:
            self._menu_stale = False
            self._menu_timer.start(0)

    def _tray_clicked(self, reason) -> None:
        # On macOS opening the menu-bar menu is a Trigger too (Qt says so as the menu starts): there the menu's
        # own Hide / Come out does it.
        if reason == QSystemTrayIcon.ActivationReason.Trigger and sys.platform != "darwin":
            self.set_hidden(not self.behavior.hidden)

    def _menu_changed(self) -> None:
        """Something the menu shows changed: fill it in again, once things settle,
        and never under an open menu (its items would vanish under the pointer)."""
        if self.menu.isVisible() or self.stage.menu.is_open():
            self._menu_stale = True
        else:
            self._menu_timer.start(0)

    def _time_labels(self) -> tuple:
        """The parts of the menu that change with the clock."""
        now = time.time()
        focus = self.reminders.focus()
        left = max(1, round((focus.due - now) / 60)) if focus else None
        watch = offline_clock(self._now() - self._stopwatch, seconds=False) if self._stopwatch is not None else None
        return (left, watch, tuple(reminders.describe(r.due, now) for r in self.reminders.upcoming() if r.kind != "focus"))

    def _offline_in_box(self, words: str) -> None:
        """Do something from the menu as if it were asked in the box, and show it there."""
        self.open_ask()
        self._local(words)

    def _fill_menu(self) -> None:
        self._menu_timer.stop()
        self._menu_clock = self._time_labels()
        m = self.menu
        for sub in m.findChildren(QMenu, options=Qt.FindChildOption.FindDirectChildrenOnly):
            sub.deleteLater()  # clear() keeps submenus
        m.clear()
        m.addAction(f"Ask {self.name}…", self.open_ask)
        self._chats_menu(m.addMenu("Chats"))
        m.addAction("Remind me…", partial(self.open_ask, "remind me in "))
        focus = self.reminders.focus()
        if focus:
            left = max(1, round((focus.due - time.time()) / 60))
            m.addAction(f"Stop focus ({left} min left)", self.stop_focus)
        else:
            sub = m.addMenu("Focus timer")
            for minutes in sorted({15, 25, 50, int(self.config["focus"]["minutes"])}):
                sub.addAction(f"{minutes} minutes", partial(self.start_focus, minutes))
        if self._stopwatch is not None:
            m.addAction(f"Stop the stopwatch ({offline_clock(self._now() - self._stopwatch, seconds=False)})", partial(self._offline_in_box, "stop stopwatch"))
        notes = self._notes()
        self._notes_menu(m.addMenu(f"Notes ({len(notes)})" if notes else "Notes"))
        upcoming = [r for r in self.reminders.upcoming() if r.kind != "focus"]
        if upcoming:
            sub = m.addMenu(f"Reminders ({len(upcoming)})")
            for r in upcoming:
                sub.addAction(f"✕  {reminders.describe(r.due, time.time())}: {r.text}", partial(self._cancel, r.id))
        m.addSeparator()
        self._brain_menu(m.addMenu("Brain"))
        self._companion_menu(m.addMenu("Companion"))
        self._style_menu(m.addMenu("Bubble style"))
        self._agents_menu(m.addMenu("AI agents"))
        if not self._refreshing and self._now() - self._agents_seen > AGENTS_FRESH:
            self._refresh_agents()  # changed outside Chatmon, maybe; a look under way fills the menu in again
        walk = m.addAction("Walk around")
        walk.setCheckable(True)
        walk.setChecked(self.behavior.walk_enabled)
        walk.toggled.connect(self._set_walk)
        m.addAction("Come out" if self.behavior.hidden else "Hide (peek now and then)", partial(self.set_hidden, not self.behavior.hidden))
        login = m.addAction("Start when I log in")
        login.setCheckable(True)
        login.setChecked(autostart.enabled())
        login.toggled.connect(self._set_autostart)
        m.addSeparator()
        if self.updater.ready is not None and self.updater.release is not None:
            m.addAction(f"Update to Chatmon {self.updater.release.version}", self._update_now)
        self._help_menu(m.addMenu("Help & updates"))
        m.addAction("Settings…", self.open_settings)
        m.addAction("Reload settings file", self.reload)
        m.addAction("Quit", self.quit)
        self._look_again()

    def _brain_menu(self, sub: QMenu) -> None:
        group = QActionGroup(sub)
        current = self._brain(wait=False)
        picked = self.state.get("brain")
        auto = sub.addAction(f"Automatic ({current.label if current else 'none found'})")
        auto.setCheckable(True)
        auto.setChecked(not picked)
        auto.triggered.connect(partial(self._pick_brain, None))
        group.addAction(auto)
        groups = (
            ("AI tools you're signed in to", lambda b: b.type == "command"),
            ("On this computer", lambda b: b.local),
            ("APIs (billed per question; pick one to use it)", lambda b: b.type != "command" and not b.local),
        )
        for title, belongs in groups:
            sub.addSection(title)
            for brain in (b for b in self.brains.values() if belongs(b)):
                ok = brain.available(wait=False)
                action = sub.addAction(brain.label if ok else f"{brain.label} ({brain.why_not()})")
                action.setCheckable(True)
                action.setEnabled(ok)
                action.setChecked(picked == brain.name)
                action.triggered.connect(partial(self._pick_brain, brain.name))
                group.addAction(action)
        if current is not None:
            self._brain_options_menu(sub, current)

    THINKING = {"auto": "Automatic (the model's own choice)", "on": "On", "off": "Off"}

    def _brain_options_menu(self, sub: QMenu, brain: brains.Brain) -> None:
        """How the brain in use answers: its model, how hard it thinks, whether it thinks at all."""
        modes = brain.thinking_modes()
        if not (brain.models or brain.effort_levels() or len(modes) > 1):
            return
        sub.addSection(f"{brain.label}: how it answers")
        base = self.brains[brain.name]  # as set up, before any picks: its defaults
        if brain.models:
            own = "The tool’s own choice" if brain.type == "command" else "Its own default"
            menu = sub.addMenu(f"Model: {brain.model or own.lower()}")
            group = QActionGroup(menu)
            if not base.model:
                self._option(menu, group, own, not brain.model, None, brain.name, "model", "")
            for model in dict.fromkeys([*brain.models, *([brain.model] if brain.model else [])]):
                label = model + ("  (default)" if model == base.model else "")
                # Any model can be picked: an effort or thinking it doesn't take is dropped with the switch.
                self._option(menu, group, label, brain.model == model, brain.refuses(model=model, effort="", thinking="auto"), brain.name, "model", model)
        levels = brain.effort_levels()
        if levels:
            menu = sub.addMenu(f"Effort: {brain.effort or 'the model’s default'}")
            group = QActionGroup(menu)
            self._option(menu, group, "The model’s default", not brain.effort, None, brain.name, "effort", "")
            for level in levels:
                label = level + ("  (default)" if level == base.effort else "")
                self._option(menu, group, label, brain.effort == level, brain.refuses(effort=level), brain.name, "effort", level)
        if len(modes) > 1:
            menu = sub.addMenu(f"Thinking: {self.THINKING[brain.thinking].split(' (')[0]}")
            group = QActionGroup(menu)
            for mode in modes:
                self._option(menu, group, self.THINKING[mode], brain.thinking == mode, brain.refuses(thinking=mode), brain.name, "thinking", mode)

    def _option(self, menu: QMenu, group: QActionGroup, label: str, checked: bool, refused: str | None, brain: str, key: str, value: str) -> None:
        action = menu.addAction(label if refused is None else f"{label}  ({refused})")
        action.setCheckable(True)
        action.setChecked(checked)
        action.setEnabled(refused is None)
        action.triggered.connect(partial(self._set_brain_option, brain, key, value))
        group.addAction(action)

    def _set_brain_option(self, brain: str, key: str, value: str) -> None:
        options = dict(self.state.get("brain_options") or {})
        options[brain] = {**options.get(brain, {}), key: value}
        self.state.set("brain_options", options)
        self.state.save()
        self._menu_changed()

    # -- connecting AI agents

    def _refresh_agents(self, migrate: bool = False) -> None:
        """How each agent stands, off the main thread. The first time, hooks connected under the old name
        (penguin-companion) are swapped for chatmon's first. One look at a time: each starts the agents'
        own command lines (a second or so each), and every refill of the menu asks for one. Asked again
        meanwhile, it looks once more when this one is done."""
        if self._refreshing:
            self._refresh_next = migrate or bool(self._refresh_next)
            return
        self._refreshing = True
        self.background.run(partial(self._agent_statuses, migrate), self._agents_refreshed)

    def _agents_refreshed(self, status) -> None:
        self._refreshing = False
        self._agents_seen = self._now()
        again, self._refresh_next = self._refresh_next, None
        self._agents_known(status)
        if again is not None:
            self._refresh_agents(again)

    @staticmethod
    def _agent_statuses(migrate: bool) -> dict[str, str]:
        status = {}
        for agent in agents.AGENTS:
            if migrate:
                try:
                    done = agent.migrate()
                except (agents.AgentError, OSError) as exc:
                    done = f"{agent.label}: couldn't move its hooks to the new name: {exc}"
                if done:
                    print(f"{paths.APP}: {done}", file=sys.stderr)
            status[agent.name] = agent.status()
        return status

    def _agents_known(self, status) -> None:
        if self._renamed and isinstance(status, dict):
            self._renamed = False
            # An agent that installs a plugin from a folder of ours may have dropped it when the old
            # folder went, before it could be moved over; nothing records that it was connected.
            unsure = [a.label for a in agents.AGENTS if a.name in ("claude", "muse") and status.get(a.name) == "found"]
            if unsure:
                self.say(
                    self.name,
                    f"I'm Chatmon now. If {' or '.join(unsure)} was connected before, tick it again under **AI agents** in my menu.",
                    timeout_s=30,
                )
        if isinstance(status, dict) and status != self._agent_status:
            self._agent_status = status
            self._menu_changed()

    def _agents_menu(self, sub: QMenu) -> None:
        sub.addSection("Let them tell me what they're doing")
        missing = []
        for agent in agents.AGENTS:
            state = self._agent_status.get(agent.name, "found" if agent.detected() else "not found")
            if state == "not found":
                missing.append(agent.label)
                continue
            action = sub.addAction(agent.label + (" (installed but off)" if state == "installed but off" else ""))
            action.setCheckable(True)
            action.setChecked(state == "connected")
            action.toggled.connect(partial(self._set_agent, agent))
        if missing:
            note = sub.addAction("Not found here: " + ", ".join(missing))
            note.setEnabled(False)
        sub.addSeparator()
        sub.addAction("Another agent or script…", self._other_agents)

    def _set_agent(self, agent: agents.Agent, on: bool) -> None:
        self.say(f"{'Connecting' if on else 'Disconnecting'} {agent.label}…", timeout_s=20)
        self.background.run(agent.connect if on else agent.disconnect, partial(self._agent_set, agent))

    def _agent_set(self, agent: agents.Agent, result) -> None:
        if isinstance(result, Exception):
            self.say(f"Couldn't change {agent.label}", str(result), [("OK", None)], timeout_s=None)
        else:
            self.behavior.react("hop", self._now())
            self.say(agent.label, str(result), timeout_s=12)
        self._refresh_agents()

    def _other_agents(self) -> None:
        self.open_ask()
        self.ask_box.set_answer("Any agent or script can tell me what it's doing:\n\n```\n" + agents.generic() + "\n```")

    # -- which companion, and how its bubbles look

    def _companion(self) -> companions.Companion:
        """The one picked from the menu, else the one in the settings, else the penguin."""
        return companions.get(self.state.get("companion") or self.config["companion"])

    def _load_sprites(self) -> Sprites:
        """The chosen companion's strips, and only those."""
        return Sprites(self._companion().anim_dir(), int(self.config["size"]), self._sprite_scale)

    def _show_sprites(self) -> None:
        """Draw with the companion, size and screen scale as they are now."""
        self.sprites = self._load_sprites()
        self.behavior.anims = self.sprites.anims()
        self.stage.set_sprites(self.sprites)
        if hasattr(self, "_preload"):
            self._preload.start()

    def _preload_next(self) -> None:
        if not self.sprites.load_next():
            self._preload.stop()

    def _show_icon(self) -> None:
        icon = QIcon(self.sprites.frame("idle", 0, False).pixmap)
        self.tray.setIcon(icon)
        self.app.setWindowIcon(icon)

    def _companion_menu(self, sub: QMenu) -> None:
        group = QActionGroup(sub)
        current = self._companion().id
        for companion in companions.COMPANIONS.values():
            action = sub.addAction(companion.label)
            action.setCheckable(True)
            action.setChecked(companion.id == current)
            action.setEnabled(companions.get(companion.id) is companion)  # its strips are installed
            action.triggered.connect(partial(self._pick_companion, companion.id))
            group.addAction(action)

    def _pick_companion(self, name: str) -> None:
        if name == self._companion().id:
            return
        self.state.set("companion", name)
        self.state.save()
        self._show_sprites()
        self._show_icon()
        self._apply_bubble_style()  # "Match companion" follows it
        self._menu_changed()
        self.behavior.react("wave", self._now())

    def _style_menu(self, sub: QMenu) -> None:
        group = QActionGroup(sub)
        current = self._bubble_style_name()
        matching = styles.get(self._companion().bubble_style).label.split(" (")[0].lower()
        for name, label in [(MATCH, f"Match companion ({matching})")] + [(s.name, s.label) for s in styles.STYLES.values()]:
            action = sub.addAction(label)
            action.setCheckable(True)
            action.setChecked(name == current)
            action.triggered.connect(partial(self._pick_style, name))
            group.addAction(action)
            if name == MATCH:
                sub.addSeparator()
        sub.addSeparator()
        moving = sub.addAction("Animate bubbles")
        moving.setCheckable(True)
        moving.setChecked(self._bubble_effects())
        moving.toggled.connect(self._set_bubble_effects)

    def _bubble_style_name(self) -> str:
        """The style picked from the menu, else the one in the settings: a style's name, or MATCH."""
        name = str(self.state.get("bubble_style") or self.config["bubble_style"] or MATCH).strip().lower()
        return name if name in styles.STYLES else MATCH

    def _bubble_style(self) -> styles.Style:
        """A style chosen by name wins; otherwise high contrast (the system's setting) gets the plain one,
        in the desktop's own colours, and else the bubbles match the companion."""
        name = self._bubble_style_name()
        if name == MATCH and self._high_contrast and not self.state.get("bubble_style"):
            return styles.get("plain")
        return styles.get(self._companion().bubble_style if name == MATCH else name)

    def _bubble_effects(self) -> bool:
        """Moving edges, unless you turned them off, or the system asks for reduced motion (and you didn't
        turn them on)."""
        picked = self.state.get("bubble_effects")
        if picked is not None:
            return bool(picked)
        return bool(self.config["bubble_effects"]) and not self._reduce_motion

    def _apply_bubble_style(self) -> None:
        style, animate = self._bubble_style(), self._bubble_effects()
        self.stage.bubble.set_style(style, animate)
        self.ask_box.set_style(style, animate)

    def _pick_style(self, name: str) -> None:
        self.state.set("bubble_style", name)
        self.state.save()
        self._apply_bubble_style()
        self._menu_changed()
        if not self.ask_box.isVisible():
            self.say(self.name, f"New look: {self._bubble_style().label.split(' (')[0].lower()}.", timeout_s=4)

    def _set_bubble_effects(self, on: bool) -> None:
        self.state.set("bubble_effects", on)
        self.state.save()
        self._apply_bubble_style()

    def _pick_brain(self, name: str | None) -> None:
        self.state.set("brain", name)
        self.state.save()
        self._menu_changed()

    def _cancel(self, rid: str) -> None:
        self.reminders.cancel(rid)
        self.save()

    def _set_walk(self, on: bool) -> None:
        self._walk_picked = True
        self._override(("walk",), on)  # remembered, as Settings remembers it
        self.state.save()
        self.config["walk"] = on
        self.behavior.set_walk(on, self._now())
        self._menu_changed()

    def _set_autostart(self, on: bool) -> None:
        autostart.set_enabled(on)
        self._menu_changed()

    def _load_config(self) -> tuple[dict, str | None]:
        """The settings file, with what you set in Settings (or the menu) laid over it."""
        config, error = load_config()
        overrides = self.state.get("settings")
        if isinstance(overrides, dict):
            config = merge(config, overrides)
        return config, error

    def _override(self, path: tuple[str, ...], value) -> None:
        """Keep a setting you made (Settings, the menu) over the settings file's."""
        settings = self.state.get("settings")
        settings = settings if isinstance(settings, dict) else {}
        node = settings
        for key in path[:-1]:
            if not isinstance(node.get(key), dict):
                node[key] = {}
            node = node[key]
        node[path[-1]] = value
        self.state.set("settings", settings)

    # -- Settings: a window for it all (settingswin.py)

    SETTINGS_PATHS = {  # the window's name for a setting: where it lives in the settings
        "size": ("size",), "walk": ("walk",), "sleep_after_minutes": ("sleep_after_minutes",),
        "timeout_seconds": ("ai", "timeout_seconds"), "show_replies": ("agents", "show_replies"),
        "break_reminders": ("breaks", "remind"), "breaks_every": ("breaks", "every_minutes"), "snooze": ("breaks", "snooze_minutes"),
        "focus": ("focus", "minutes"), "focus_done": ("focus", "tell_when_done"),
        "battery_low": ("heads_up", "battery_low"), "battery_critical": ("heads_up", "battery_critical"),
        "disk_full": ("heads_up", "disk_full_percent"), "updates_heads_up": ("heads_up", "updates"),
        "updates_every_hours": ("heads_up", "updates_every_hours"),
    }

    def _settings_values(self) -> tuple[dict, dict]:
        c = self.config
        values = {
            "name": str(self.state.get("name") or c["name"] or ""), "companion": self._companion().id,
            "size": int(c["size"]), "walk": bool(self.behavior.walk_enabled), "sleep_after_minutes": int(c["sleep_after_minutes"]),
            "autostart": autostart.enabled(), "bubble_style": self._bubble_style_name(), "bubble_effects": self._bubble_effects(),
            "check_updates": self._checks_updates(), "brain": str(self.state.get("brain") or ""),
            "timeout_seconds": int(c["ai"]["timeout_seconds"]), "show_replies": bool(c["agents"]["show_replies"]),
            "keep_chats": self._keeps_chats(), "context_tokens": self._context_cap(), "instructions": self._instructions(),
            "memory": self.memory.texts(),
            "break_reminders": bool(c["breaks"]["remind"]) and int(c["breaks"]["every_minutes"]) > 0,  # 0: the file's old "off"
            "breaks_every": int(c["breaks"]["every_minutes"]),
            "snooze": int(c["breaks"]["snooze_minutes"]), "focus": int(c["focus"]["minutes"]), "focus_done": bool(c["focus"]["tell_when_done"]),
            "battery_low": int(c["heads_up"]["battery_low"]), "battery_critical": int(c["heads_up"]["battery_critical"]),
            "disk_full": int(c["heads_up"]["disk_full_percent"]), "updates_heads_up": bool(c["heads_up"]["updates"]),
            "updates_every_hours": int(c["heads_up"]["updates_every_hours"]),
        }
        current = self._brain(wait=False)
        matching = styles.get(self._companion().bubble_style).label.split(" (")[0].lower()
        choices = {
            "companions": [(x.id, x.label) for x in companions.COMPANIONS.values() if companions.get(x.id) is x],
            "bubble_styles": [(MATCH, f"Match companion ({matching})")] + [(x.name, x.label) for x in styles.STYLES.values()],
            "brains": [("", f"Automatic ({current.label if current and not self.state.get('brain') else 'the first one found'})")]
            + [(b.name, b.label if b.available(wait=False) else f"{b.label} ({b.why_not()})") for b in self.brains.values()],
        }
        return values, choices

    def open_settings(self) -> None:
        from .settingswin import SettingsWindow

        if self._settings_window is not None and not sip.isdeleted(self._settings_window):
            self._settings_window.raise_()
            self._settings_window.activateWindow()
            return
        values, choices = self._settings_values()
        window = SettingsWindow(values, choices)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        window.setWindowIcon(self.tray.icon())
        window.saved.connect(self._apply_settings)
        window.open_file.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.config_file()))))
        self._settings_window = window
        window.show()
        window.raise_()
        window.activateWindow()

    def _apply_settings(self, changed: dict) -> None:
        """What you set in Settings: each with the menu's own setter where there is one, the rest kept over
        the settings file and taken up at once."""
        if not changed:
            return
        if "name" in changed:
            self.state.set("name", changed["name"][:40] or None)
        if "companion" in changed:
            self._pick_companion(changed["companion"])
        if "bubble_style" in changed:
            self.state.set("bubble_style", changed["bubble_style"])
        if "bubble_effects" in changed:
            self.state.set("bubble_effects", changed["bubble_effects"])
        if "check_updates" in changed:
            self._set_check_updates(changed["check_updates"])
        if "brain" in changed:
            self.state.set("brain", changed["brain"] or None)
        if "keep_chats" in changed:
            self.state.set("keep_chats", changed["keep_chats"])
            if not changed["keep_chats"]:
                self.chat.keep = False
        if "autostart" in changed:
            autostart.set_enabled(changed["autostart"])
        if "instructions" in changed:
            self.state.set("instructions", changed["instructions"])
        if "context_tokens" in changed:
            self.state.set("context_tokens", int(changed["context_tokens"]))
        if "memory" in changed:
            self.memory.items = [memory.Item(t, time.time()) for t in changed["memory"]][: memory.MAX_ITEMS]
            self.memory.save()
        for key, path in self.SETTINGS_PATHS.items():
            if key in changed:
                self._override(path, changed[key])
        if "walk" in changed:
            self._walk_picked = True
        self.state.save()
        self.reload(quietly=True)

    def reload(self, quietly: bool = False) -> None:
        self.config, self.config_error = self._load_config()
        if self.config_error:
            self.say("I couldn't read my settings", f"`{self.config_error}`", timeout_s=30)
            return
        self.brains = brains.load_brains(self.config["ai"])
        self.watcher = self._make_watcher()
        self.breaks.every = float(self.config["breaks"]["every_minutes"]) * 60
        self._show_sprites()
        self._show_icon()
        self.behavior.set_walk(bool(self.config["walk"]), self._now())
        self.behavior.sleep_after = float(self.config["sleep_after_minutes"]) * 60
        self.behavior.speed = int(self.config["size"]) * 0.4
        self._apply_bubble_style()
        self._menu_changed()
        if not quietly:
            self.say("Settings reloaded", timeout_s=3)

    def _set_sprite_scale(self, scale: float) -> None:
        """The stage's screen has this many device pixels to a pixel: draw the penguin with them."""
        if abs(scale - self._sprite_scale) > 0.01:
            self._sprite_scale = scale
            self._show_sprites()

    def quit(self) -> None:
        self._stop_update_checks()
        self._save_chat()
        self.desk.close()
        global _problem
        if _problem == self._problem:
            _problem = None
        self.updater.cancel()
        self.save()
        self.tray.hide()
        self.stage.close_stage()
        self.app.quit()


_problem = None  # the running Companion's offer to report what went wrong


def _log_exception(kind, value, tb) -> None:
    traceback.print_exception(kind, value, tb, file=sys.stderr)
    if _problem is not None and not issubclass(kind, KeyboardInterrupt):
        QTimer.singleShot(0, _problem)


def _find_fonts(app: QApplication) -> None:
    """Have Qt find its fonts now, before the chatmon is on screen. The first text it measures makes it
    read every font installed, and the first character that font lacks (the bubbles' ✕) makes it work
    out which fonts to fall back on. With a few thousand fonts installed, as Windows PCs can have, each
    takes seconds; left to the first bubble, the chatmon froze mid-wave while they happened."""
    QFontMetricsF(app.font()).horizontalAdvance("Chatmon ✕")


LOG_LIMIT = 1_000_000  # bytes; past this the log starts over, the last one kept as chatmon.log.old


def log_file() -> Path:
    return paths.state_dir() / f"{paths.APP}.log"


def _log_without_a_console() -> None:
    """Started with no console (autostart, chatmonw, pythonw on Windows), Python has no stdout or
    stderr, and what Chatmon has to say about a problem would go nowhere: keep it in a log instead."""
    if sys.stderr is not None:
        return
    log = log_file()
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        if log.exists() and log.stat().st_size > LOG_LIMIT:
            os.replace(log, log.with_name(log.name + ".old"))
        stream = open(log, "a", encoding="utf-8", errors="replace", buffering=1)
    except OSError:
        return
    sys.stdout = sys.stderr = stream
    print(f"--- Chatmon started {datetime.now():%Y-%m-%d %H:%M:%S}")


_instance_lock: int | None = None  # the lock this Chatmon holds while it runs (Linux, macOS)


def _hold_instance_lock(path: str) -> bool:
    """Take the lock that says this is the Chatmon here, for as long as it runs; False if another has it."""
    global _instance_lock
    import fcntl

    import errno

    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    except OSError:
        return True  # can't make one (a read-only folder, a link where it would be): go on as before
    if os.fstat(fd).st_uid != os.getuid():  # someone else's file: it says nothing about us
        os.close(fd)
        return True
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        os.close(fd)
        return exc.errno not in (errno.EWOULDBLOCK, errno.EAGAIN)  # held by another Chatmon; any other error: go on
    _instance_lock = fd
    return True


def open_server(reached: str = events.ABSENT) -> tuple[QLocalServer | None, str | None]:
    """The server that hooks and a second launch reach Chatmon through, and what's wrong with it, if
    anything. `reached` is what `events.deliver` found at its address. No server: another copy of
    Chatmon got there first, a moment ago."""
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)  # only you can talk to it
    name = paths.server_name()
    guard = None
    if sys.platform == "win32":
        from . import winpipe

        # Any user can make a pipe of any name, and Qt would quietly add its own to theirs: claim the
        # name before Qt listens on it, and don't listen at all if someone else has it.
        held = f"Another user on this computer is holding `{winpipe.full_name(name)}`, the address your agents' hooks reach me at, so I won't listen there and they'll tell it nothing."
        if reached == events.FOREIGN:
            return server, held
        try:
            guard = winpipe.claim(name)
        except OSError as exc:  # can't tell; listen as Qt would on its own
            print(f"Couldn't claim {name} first: {exc}", file=sys.stderr)
        else:
            if guard is None:
                return (None, None) if events.send({"type": "show"}) else (server, held)
    else:
        # Two started at once could both find nothing listening, and the second would take the first's socket
        # away: whoever holds this lock (for as long as it runs) is the one Chatmon here.
        if not _hold_instance_lock(name + ".lock"):
            for _ in range(15):  # the other is starting, or running: it shows itself
                if events.send({"type": "show"}):
                    break
                time.sleep(0.2)
            return None, None
        QLocalServer.removeServer(name)  # a socket left behind in our own private folder
    try:
        if not server.listen(name):
            return server, f"I couldn't open `{name}` ({server.errorString()}), the address your agents' hooks reach me at."
    finally:
        if guard is not None:
            winpipe.release(guard)
    return server, None


def run() -> int:
    if sys.platform.startswith("linux") and os.environ.get("XDG_SESSION_TYPE") == "wayland" and "QT_QPA_PLATFORM" not in os.environ:
        from . import layer

        if layer.offered():
            # The stage is a layer-shell overlay of its own (layer.py): Qt runs on Wayland itself, its windows
            # sharp at any scale; through XWayland if Qt's Wayland plugin isn't installed.
            os.environ["QT_QPA_PLATFORM"] = "wayland;xcb"
        elif os.environ.get("DISPLAY"):
            # No overlay (GNOME): a Wayland window can't place itself or stay above others, so the stage is an X
            # window, through XWayland, where it can.
            os.environ["QT_QPA_PLATFORM"] = "xcb"
    _log_without_a_console()
    if sys.platform == "darwin":
        os.environ.setdefault("QT_MAC_SET_RAISE_PROCESS", "0")  # raising a window mustn't make Chatmon the active app
        if not os.environ.get("TERM_PROGRAM"):  # started from Finder, the Dock or at login, not a terminal
            paths.login_environment()
    # PyQt aborts the whole app on an exception that escapes a slot; log it and carry on instead.
    sys.excepthook = _log_exception
    reached = events.deliver({"type": "show"})
    if reached == events.SENT:
        print("Chatmon is already running; it says hi.")
        return 0
    if sys.platform == "win32":
        # Its identity on Windows (taskbar, notifications), the same one its shortcuts carry: set before any
        # window. https://learn.microsoft.com/en-us/windows/win32/shell/appids
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
        except (AttributeError, OSError):
            pass
    app = QApplication(sys.argv[:1])
    app.setApplicationName(paths.APP)
    app.setApplicationDisplayName("Chatmon")
    app.setDesktopFileName(autostart.APP_ID)  # its identity to Linux desktops and portals
    autostart.migrate()
    autostart.refresh()
    app.setQuitOnLastWindowClosed(False)
    server, problem = open_server(reached)
    if server is None:
        print("Chatmon is already running; it says hi.")
        return 0
    if problem:
        print(f"{problem} Hooks won't reach Chatmon.", file=sys.stderr)
    _find_fonts(app)
    companion = Companion(app, server, server_problem=problem)
    # Windows ending the session (logging off, shutting down) says so with aboutToQuit and then ends the app
    # there and then: nothing after app.exec() gets to run.
    app.aboutToQuit.connect(companion.save)
    # Python runs a signal handler between any two steps of whatever it's doing,
    # say halfway through drawing a frame; quit from the event loop instead.
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: QTimer.singleShot(0, companion.quit))
    try:
        return app.exec()
    finally:
        companion.save()
        server.close()
