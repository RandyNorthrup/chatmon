"""The running companion: the penguin, its bubbles and tray icon, and what it
keeps an eye on for you."""

from __future__ import annotations

import dataclasses
import logging
import os
import signal
import sys
import threading
import time
import weakref
from collections import deque
from collections.abc import Callable
from datetime import date, datetime
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from PyQt6 import sip
from PyQt6.QtCore import QEvent, QLocale, QObject, QPoint, QProcess, QRectF, Qt, QTimer, QUrl, pyqtSlot
from PyQt6.QtGui import QColor, QDesktopServices, QFontMetricsF, QGuiApplication, QIcon, QKeyEvent, QPainter, QPixmap
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QFileDialog, QMenu, QSystemTrayIcon

from . import __version__, a11y, agents, asking, i18n, attachments, autostart, backup, brains, changelog, chats, commands, companions, context, events, heads_up, keychain, memory, menus, messages, offline, paths, presence, reminders, report, richtext, styles, sysnotify, updates
from . import log as applog
from .behavior import Behavior
from .bubble import AskBox, TimeoutPolicy, clipboard_contents, overlay_contents
from .i18n import N_, _, either, join, ngettext
from .penguin import Stage
from .qtsignal import pyqtSignal
from .settings import State, coerce, merge, read_config
from .sprites import Sprites, silhouette

if TYPE_CHECKING:
    from .chatswin import ChatsWindow
    from .settingswin import SettingsWindow

logger = logging.getLogger(__name__)

PRETTY = {"claude": "Claude", "codex": "Codex", "gemini": "Gemini", "grok": "Grok", "copilot": "Copilot", "agent": N_("Your agent")}  # shown as _(…)
WORK_EXPIRES = 30 * 60  # forget an agent that said it was working but never finished
MATCH = "match"  # the bubble style that follows the companion
MAX_CONNECTIONS = 64  # hook connections open at once (each is a moment's); past that a new one is turned away
UPDATE_CHECK_TIMEOUT_S = 60  # a system update check still running after this long is stopped, and counts as none
APP_USER_MODEL_ID = "RandyNorthrup.Chatmon"  # Windows: the app's identity (packaging/windows/chatmon.iss gives its shortcuts it too)
NEW_CHAT_AFTER = 15 * 60  # seconds since the box was last opened after which it opens on a new chat
RECENT_MESSAGES = 10  # bubbles kept to show again (Recent messages); in memory only
MISSED_IDLE = 20.0  # seconds without input, the whole time a bubble was up, for one that timed out to count as missed
# How long bubbles stay (Settings › Accessibility): a factor on the reading time, or None for until they're closed.
BUBBLE_TIMES = {"normal": 1.0, "longer": 1.5, "much longer": 2.5, "until closed": None}
# Sounds (M4B's sound.py plays them): the alerts are on by default, the rest off until turned on (owner, 2026-11-14).
ALERT_CUES = ("needs-you", "reminder", "focus-done")
# Quick actions on the clipboard (the menu's Clipboard): what's typed in the box once the clipboard is attached.
# The menu names each one (menus.QUICK_LABELS), and its words are typed in the box as _(words): your question, in
# your language, which you send or change.
QUICK_ACTIONS = {
    "Explain": N_("Explain this:"),
    "Summarize": N_("Summarize this:"),
    "Translate": N_("Translate this into {language}:"),
    "Fix": N_("Fix the mistakes in this (spelling, grammar or code), and say what you changed:"),
}

# Shown as _(HELP), _(NO_AI) and _(ASK_HINT): the language is chosen after this module is imported.
HELP = N_("""\
**Click me** to ask anything, **drag me** anywhere, **right-click** for the menu.

I also do plenty without any AI, like *remind me in 20m to stretch*, *timer 10 min*, *note: buy milk*,
*5 km in miles* or *roll 2d6*. Ask me *help* to see it all.
""")

NO_AI = N_("Answered here, without any AI.")
ASK_HINT = N_("Enter to ask · Shift+Enter for a new line · Esc to close")
SILENT = "silent"  # a message's cue that's no sound at all (one shown again)


class Background(QObject):
    """Runs slow work (another tool's command line) off the screen thread and
    hands the result back on it; once stopped (Chatmon quitting), nothing more."""

    finished = pyqtSignal(object, object)

    def __init__(self):
        super().__init__()
        self.stopped = False
        self.finished.connect(self._hand_back)

    def run(self, work, then) -> None:
        if self.stopped:
            return

        def go() -> None:
            try:
                result = work()
            except Exception as exc:  # handed to `then`, which says what went wrong: never fatal
                logger.debug("background work failed", exc_info=True)
                result = exc
            try:
                self.finished.emit(then, result)
            except RuntimeError:  # freed meanwhile (the app ending): there's no one to hand it to
                pass

        threading.Thread(target=go, daemon=True).start()

    def stop(self) -> None:
        self.stopped = True

    def _hand_back(self, then, result) -> None:
        if not self.stopped:
            then(result)


def pretty(source: str) -> str:
    return _(PRETTY[source.lower()]) if source.lower() in PRETTY else source[:1].upper() + source[1:]


def _reminder_said(r: reminders.Reminder, repeat: bool = False) -> str:
    """A reminder as a bubble confirms it: "in 5 min: stretch", with how it repeats when `repeat`."""
    when = reminders.describe(r.due, time.time())
    if repeat and r.repeat:
        # Translators: a reminder just set: "tomorrow at 9:00 AM: stand up (every weekday at 9:00 AM)".
        return _("{when}: {reminder} ({repeat})").format(when=when, reminder=r.text, repeat=reminders.describe_repeat(r.repeat))
    # Translators: a reminder just set or changed: "in 5 min: stretch", "tomorrow at 9:00 AM: call Sam".
    return _("{when}: {reminder}").format(when=when, reminder=r.text)


def _took_first(room: int) -> str:
    """Said when more files come than fit: how many were taken, of how many at most."""
    most = attachments.MAX_COUNT
    return ngettext("I took the first {n}: {most} attachment at most.", "I took the first {n}: {most} attachments at most.", most).format(n=max(0, room), most=most)


class Companion(QObject):
    def __init__(self, app: QApplication, server: QLocalServer, server_problem: str | None = None):
        super().__init__()
        self.app = app
        self.server = server
        # Connections accepted and not yet done with, in the order they came, each with what's been read of it
        # so far: read in that order, and closed in quit().
        self._connections: dict[QLocalSocket, bytearray] = {}
        self.server_problem = server_problem  # why hooks can't reach it, if they can't
        if sys.platform == "darwin":
            from . import macnative

            # Bubbles that wait their turn and reminders due are timers: App Nap would hold them back by seconds
            # while none of Chatmon's windows can be seen.
            macnative.keep_time("Chatmon's reminders and bubbles keep their time")
        self.state = State.load()
        self.config, self.config_error = self._load_config()
        i18n.setup(self.config.get(i18n.SETTING) or None)  # before any window is built (a change applies at the next start)
        self._trust_saved_servers()
        self._settings_window: SettingsWindow | None = None
        self._chats_window: ChatsWindow | None = None
        # Whether you're there, and whether now's a time for quiet: the platform's own word for each.
        self.desk = presence.Desk(QGuiApplication.platformName())
        self._watch_desk(self.desk)  # before its first reading, whose answers come a moment later on Linux
        self._notifier = sysnotify.Notifier(self) if sys.platform.startswith("linux") else None  # Linux's notifications, one for the app
        self._toasts: dict[str, tuple[str, str, int]] = {}  # Windows: toasts not yet settled (tag: what the balloon would say)
        self._toasts_heard = False  # their failures and ends listened to
        self._quiet: str | None = None  # why bubbles from the background wait, if they do
        self.messages = messages.MessageQueue()  # what's to be said, in order (messages.py)
        self._message_timer = QTimer(self)  # looks at the queue again when something waiting may show
        self._message_timer.setSingleShot(True)
        self._message_timer.timeout.connect(self._show_next)
        self._quitting = False
        self._idle_away = False
        self._reduce_motion = self._reduced_motion()
        self._high_contrast = self.desk.high_contrast()
        self._walk_picked = "walk" in (self.state.get("settings") or {})  # turned on or off by you: reduce-motion no longer decides
        self.brains = brains.load_brains(self.config["ai"])
        self.finder = brains.Finder(self)  # which brain answers, found without ever waiting on the screen's thread
        self._fallback_told: str | None = None  # the pick from the menu whose stand-in has been announced
        self._server_offered: set[str] = set()  # model servers that aren't yours, offered once a run
        self.reminders = reminders.ReminderBook.from_list(self.state.get("reminders", []))
        self._sync_focus_hold()  # a focus session from before a restart still holds what comes on its own
        self.breaks = reminders.BreakTracker(self.config["breaks"]["every_minutes"], time.time())
        self.watcher = self._make_watcher()
        self.chat = chats.Chat()  # the one you're in: saved as it goes (if you keep them), resumable from History
        self.chat_book = chats.ChatBook()
        self.command_table = commands.Table()  # what Chatmon does by itself, by its phrases (commands.py)
        self.attached: list[attachments.Attachment] = []  # for the next question
        self.questions = asking.Questions()  # the question on its way to a brain, and the one waiting behind it
        self._renaming: str | None = None  # the chat whose new name the box is asking for
        self._stopwatch: float | None = None  # when the stopwatch started (monotonic), while it runs
        self.agents: dict[str, tuple[str, float]] = {}  # source: (state, since)
        self._recent: deque[tuple[float, messages.Message]] = deque(maxlen=RECENT_MESSAGES)  # (when, what) shown lately
        self._missed: list[messages.Message] = []  # what went by unseen (timed out while you were away, or dropped)
        self._on_screen: tuple[float, messages.Message] | None = None  # the bubble showing: since when (monotonic), what
        self._pressed_showing = False  # one of its buttons was pressed
        self._set_aside: chats.Chat | None = None  # the chat a new one replaced after a while: *carry on* goes back to it
        self._editing: str | None = None  # the reminder whose new words or time the box is asking for
        self._hotkey = ""  # the hotkey registered (M4B's hotkey.py), if any
        self._hotkey_said: str | None = None  # how the desktop has it, in its own words (hotkey.py's `bound`)
        self._brain_test: brains.BrainTest | None = None  # Settings' Test, while it runs
        self._last_event: tuple[str, str] | None = None
        self._last_event_at = 0.0
        self._alert_key: str | None = None  # what the alert showing is about
        self._asking_name = False
        self._last_wall = time.time()
        self._last_ask = 0.0
        self._update_counts: dict[str, int] = {}
        self._reading_system = False  # the battery and disks, being read off the screen's thread
        self._offline_shown = 0  # answers of Chatmon's own shown so far: a late one doesn't cover a newer one
        self._restart_needed = False
        self._update_procs: dict = {}  # the system's update checks while they run (QProcesses, PackageKit's count): their names
        self._update_round = 0  # which look at the system's updates this is: a late answer from an earlier one is ignored
        self._update_expected = 0
        self._update_deadline = QTimer(self)
        self._update_deadline.setSingleShot(True)
        self._update_deadline.timeout.connect(self._update_checks_timed_out)

        primary = QGuiApplication.primaryScreen()
        if primary is None:  # never: Qt has a screen (offscreen's own, at the least) before any widget
            raise RuntimeError("Qt has no screen to show Chatmon on")
        screen = primary.availableGeometry()
        x = float(self.state.get("x", screen.x() + screen.width() * 0.8))
        # Drawn for the scale of the screen it starts on; the stage says so when it moves to one of another.
        self._sprite_scale = (QGuiApplication.screenAt(QPoint(int(x), 0)) or primary).devicePixelRatio()
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
        self._overlay = self.stage.hosts_windows()  # the Wayland overlay draws the ask box, unless it's a window for a screen reader
        if self._overlay:
            self.stage.host(self.ask_box)
        else:
            self.stage.keep_clear_of(self.ask_box)
        self.asker = brains.Asker(self)
        self.compactor = brains.Asker(self)  # sums up a chat's earlier part, when a question needs that first
        self.compactor.answered.connect(self._compacted)
        self.compactor.failed.connect(self._compact_failed)
        self.memory = memory.Memory.load()
        self._reader: a11y.Reader | None = None  # the screen reader running, as last looked (a11y.py)
        self._reader_seen = float("-inf")
        self._answerable: tuple[float, list] | None = None  # (when, buttons) of a bubble the chat opened over
        self._instructing: str | None = None  # the chat whose instructions the box is asking for

        self.stage.bubble.on_more = self._show_more  # a bubble cut short: More shows the whole text in the box
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
        self.ask_box.stop_requested.connect(self._stop_answer)
        self.ask_box.copy_requested.connect(self._copy)
        self.ask_box.set_expanded(bool(self.state.get("ask_box_expanded")))
        self.ask_box.expand_changed.connect(self._remember_expanded)
        for widget in (self.ask_box, self.ask_box.entry, self.ask_box.answer):
            widget.installEventFilter(self)  # type: ignore[arg-type]  # Ctrl+1 to Ctrl+9: a bubble's buttons, while you type; PyQt6 6.12.1's stubs type the filter as Self, the widget's class
        scheme = getattr(self.app.styleHints(), "colorSchemeChanged", None)  # Qt 6.5 and later; Ubuntu 24.04 has 6.4
        if scheme is not None:
            scheme.connect(self._scheme_changed)  # light or dark: disconnected in quit()
        self._later(0, self._mac_edit_menu)  # once Qt has made the menu bar, as the app starts
        self.asker.answered.connect(self._answered)
        self.asker.failed.connect(self._failed)
        self.asker.partial.connect(self._partial)
        self.server.newConnection.connect(self._accept)

        # The menu is always filled in: a tray that shows it over D-Bus (Waybar,
        # and other StatusNotifierItem trays) reads it before asking for it to open.
        self.menus = menus.Menus(self)
        self.menu = self.menus.menu
        self._menu_open = False
        self._agent_status: dict[str, str] = {}
        self._refreshing = False  # finding out, off the screen's thread, how each agent stands
        self._refresh_next: bool | None = None  # asked again meanwhile: whether that look migrates too
        self._agents_seen = float("-inf")  # when the last look came back
        self._offer_due = False  # an offer to connect agents waits for the screen to be clear
        self._offered: set[str] = set()  # agents offered since Chatmon started; unanswered, they're asked again next time
        self._renamed = paths.first_run_since_rename()  # Penguin companion became Chatmon
        self.background = Background()
        self.updater = updates.Updater(self.background, self)
        self.updater.available.connect(self._update_available)
        self.updater.newer_only.connect(self._update_out)
        self.updater.up_to_date.connect(self._up_to_date)
        self.updater.failed.connect(self._update_failed)
        self.updater.installing.connect(self.quit)
        self.updater.handed_over.connect(lambda: self.say(_("Updating…"), _("The installer has it from here. I'll be back in a moment."), timeout_s=60))
        self._checking_by_hand = False  # a check you asked for says what it found, even "nothing new"
        self._install_kind: str | None = None
        self._problem_told = False
        self._looking = False  # finding out, off the screen's thread, whether model servers here are running
        self.menus.fill()
        self._tray_badge = False  # the dot on the tray icon: an agent needs you
        self.tray = QSystemTrayIcon(self._tray_icon())
        self.tray.setContextMenu(self.menu)
        self.tray.setToolTip("Chatmon")
        self.tray.activated.connect(self._tray_clicked)
        self.tray.show()
        self.app.setWindowIcon(QIcon(self.sprites.frame("idle", 0, False).pixmap))
        if sys.platform.startswith("linux"):
            self._later(60_000, self._no_tray_news)  # a minute in: a tray starting with the desktop is up by then

        self._watch_screen_lock()
        self._every(5_000, self._check_reminders)
        self._every(5_000, self._check_quiet)
        self._every(30_000, self._check_time)
        self._every(60_000, self._check_system)
        self._updates_timer = self._every(int(self.config["heads_up"]["updates_every_hours"] * 3600_000), self._check_updates)
        self._later(600_000 if sys.platform == "win32" else 120_000, self._check_updates)
        self._later(1500, self._greet)
        self._later(45_000, self._maybe_check_updates)
        self._every(3600_000, self._maybe_check_updates)
        global _running
        _running = self
        self._later(3000, self._refresh_agents, True)
        self._preload = QTimer(self)  # cuts the animations not shown yet, one at a time, between frames
        self._preload.setInterval(40)
        self._preload.timeout.connect(self._preload_next)
        self._later(2000, self._start_preload)  # once the screen's scale is known
        self._apply_accessibility()
        self._show_due_reminders()  # fired and not yet done or snoozed: back, as they were when Chatmon quit
        self._register_hotkey()

    # -- small helpers

    @property
    def name(self) -> str:
        return self.state.get("name") or self.config["name"] or self._companion().nickname

    def _every(self, ms: int, fn) -> QTimer:
        timer = QTimer(self)  # the Companion's own: quitting stops it (_stop_for_good)
        timer.timeout.connect(fn)
        timer.start(max(1000, ms))
        return timer

    def _later(self, ms: int, method: Callable[..., object], *args: object) -> None:
        """`method(*args)`, one of the Companion's own, in `ms` milliseconds, unless it has quit by then: how it
        waits to do something once, as its timers (_every) are how it does something again and again. Nothing of
        either runs once it's quit, in the app or in a test after its own (the tests make one Companion after
        another), and the wait holds the Companion only weakly, so a quit one is freed meanwhile."""
        func = getattr(method, "__func__", None)
        if func is None or getattr(method, "__self__", None) is not self:
            raise TypeError(f"_later waits for one of the Companion's own methods, not {method!r}")
        if self._quitting:
            return
        me = weakref.ref(self)

        def go() -> None:
            c = me()
            if c is not None and not c._quitting:
                func(c, *args)

        QTimer.singleShot(ms, go)

    def _heard(self, method: Callable[..., object]) -> Callable[..., None]:
        """`method`, one of the Companion's own, as a callback for something outside it that may call long after (the
        system's lock, sleep, power and settings watchers, the hotkey): it does nothing once the Companion has quit,
        and holds it only weakly. A D-Bus answer or an NSWorkspace notice can arrive after quit, and a quit
        Companion acts on nothing (as with _later)."""
        func = getattr(method, "__func__", None)
        if func is None or getattr(method, "__self__", None) is not self:
            raise TypeError(f"_heard passes on one of the Companion's own methods, not {method!r}")
        me = weakref.ref(self)

        def call(*args: object) -> None:
            c = me()
            if c is not None and not c._quitting:
                func(c, *args)

        return call

    def _make_watcher(self) -> heads_up.Watcher:
        h = self.config["heads_up"]
        return heads_up.Watcher(float(h["battery_low"]), float(h["battery_critical"]), float(h["disk_full_percent"]))

    def _brain(self, wait: bool = True) -> brains.Brain | None:
        """The brain to ask, with the model, effort and thinking picked for it from the menu. `wait` off:
        as far as can be told without holding up the screen (for the menu)."""
        return commands.brain_in_use(self.brains, self.config, self.state, wait)

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

    def _now(self) -> float:
        return time.monotonic()

    def _follow(self) -> None:
        if self.ask_box.isVisible():
            self.ask_box.place(self.stage.head_point())

    def save(self) -> None:
        self.state.set("x", round(self.behavior.x))
        self.state.set("reminders", self.reminders.to_list())
        self.state.save()
        self._sync_focus_hold()
        self._menu_changed()  # reminders and focus show in it

    # -- talking

    def _with_you(self) -> bool:
        """You're using Chatmon right now (its ask box or menu is open): it's no time to hold back. Not on
        macOS under a full-screen app (the one quiet there): its Space shows none of Chatmon's windows, the ask
        box included, so one left open there is no sign of you."""
        if sys.platform == "darwin" and self._quiet:
            return False
        return self.ask_box.isVisible() or self._menu_open

    def say(self, title: str, text: str = "", buttons=None, timeout_s: float | None = 12, *, key: str | None = None, background: bool = False,
            cue: str | None = None) -> None:
        """A bubble, once what matters more has been seen (messages.py). `key` names what it's about, so newer news
        of the same thing replaces it; `background`: it came on its own (an agent, a script, a heads-up), not from
        something you did, so a focus session holds it. `cue`: the sound it may make (see _cue)."""
        notice = self.desk.notice_seconds()  # how long you've asked notifications to stay up (Windows)
        if timeout_s is not None and notice:
            timeout_s = max(timeout_s, notice)
        self._post(messages.Message(title, text, buttons, timeout_s, key=key, background=background, cue=cue))

    def alert(self, key: str, title: str, text: str, buttons=None, *, reminder: bool = False) -> None:
        """Something needs you: the penguin waves its flippers until you answer. `reminder`: one of yours, which
        waits for an agent's alert but goes before anything else. Either comes on its own."""
        priority = messages.REMINDER if reminder else messages.ALERT
        message = messages.Message(title, text, buttons or [(_("OK"), None)], None, key=key, priority=priority, alert=True, background=True,
                                   cue="reminder" if reminder else "needs-you")
        if not self._post(message):
            # Under a full-screen app: it waits for you, and the system's own notification says so now
            # (which follows your Do Not Disturb). macOS's needs an app signed with an Apple Developer ID:
            # Chatmon's ad hoc signed one asks and is never answered (UNUserNotificationCenter), so there
            # it just waits.
            # Only that something's waiting: the system keeps notifications (Action Center, a phone linked
            # to the desktop), and an agent's message or a reminder's words are yours to see in Chatmon.
            # A reminder's notification offers what its bubble does (Done, a snooze), so it can be seen to from there.
            self._system_notice(title, _("Chatmon has something for you."), list(buttons[:2]) if reminder and buttons else [], "reminder" if reminder else None)

    def _system_notice(self, title: str, text: str, buttons=(), scenario: str | None = None, seconds: int = 10, aloud: bool = False) -> None:
        """A notification of the system's own, which keeps a history: Windows' toast (wintoast.py), else the tray's
        balloon; on Linux the desktop's notification server, tray or not (sysnotify.Notifier). macOS: none (see
        alert). `buttons`: (label, action) pairs, pressable from the notification. `aloud`: it's for a screen reader
        to read out (Linux: transient, each replacing the last). On Linux a held alert is urgent, which shows through
        GNOME's Do Not Disturb, so not when Do Not Disturb is why it's held."""
        if sys.platform.startswith("linux") and self._notifier is not None:
            labels = [label for label, _ in buttons]

            def pressed(i: int) -> None:
                if 0 <= i < len(buttons) and buttons[i][1]:
                    buttons[i][1]()

            if aloud:
                self._notifier.read_aloud(title, text, labels, pressed)
            else:
                urgency = sysnotify.URGENCY_NORMAL if self._quiet == "Do Not Disturb" else sysnotify.URGENCY_CRITICAL
                self._notifier.alert(title, text, labels, pressed, urgency=urgency)
        elif sys.platform == "win32":
            from . import wintoast

            tag = wintoast.show(title, text, list(buttons), scenario)
            if tag is None:  # no toast here (wintoast.toaster().why_not says why): the balloon
                self._balloon(title, text, seconds)
                return
            if not self._toasts_heard:  # Windows can still refuse it after it took it: the balloon then
                toaster = wintoast.toaster()
                toaster.failed.connect(self._toast_failed)
                toaster.dismissed.connect(self._toast_dismissed)
                self._toasts_heard = True
            self._toasts[tag] = (title, text, seconds)

    def _balloon(self, title: str, text: str, seconds: int) -> None:
        if QSystemTrayIcon.supportsMessages():
            self.tray.showMessage(title, text, QSystemTrayIcon.MessageIcon.Information, seconds * 1000)

    def _toast_failed(self, tag: str, _hresult: int) -> None:
        """Windows refused a toast after all (this app's notifications turned off, say): the balloon in its place."""
        notice = self._toasts.pop(tag, None)
        if notice is not None and not self._quitting:
            self._balloon(*notice)

    def _toast_dismissed(self, tag: str, reason: int) -> None:
        """A toast's end: timed out first (it's in Action Center, still there to click), then its final reason, after
        which nothing more comes for it."""
        from . import wintoast

        if reason != wintoast.TIMED_OUT:
            self._toasts.pop(tag, None)

    def _post(self, message: messages.Message) -> bool:
        """Queue it and show whatever's due; False if a hold (quiet, focus) keeps it back."""
        message.yours = self._with_you()
        self._missed += [m for m in self.messages.add(message) if m is not message]  # plain bubbles past the limit, never shown
        del self._missed[:-RECENT_MESSAGES]
        self._show_next()
        return self.messages.passes(message)

    def _show_next(self) -> None:
        """Show what the queue says is due now, and look again when it says to."""
        if self._quitting:
            return
        now = time.monotonic()
        message = self.messages.next(now, self.stage.message_visible())
        if message is not None:
            self._display(message)
        wake = self.messages.wake_at(now)
        if wake is None:
            self._message_timer.stop()
        else:
            self._message_timer.start(max(0, int((wake - now) * 1000)))

    def _display(self, message: messages.Message) -> None:
        now = self._now()
        if message.alert:
            self._alert_key = message.key
            self.behavior.set_hidden(False, now)
            self._menu_changed()
            self.behavior.set_alert(True, now)
            self.stage.raise_above(True)  # above a full-screen window: it needs you
        else:
            self._end_alert()  # newer news of the same thing: the agent got its answer elsewhere, say
        self._on_screen, self._pressed_showing = (time.monotonic(), message), False
        self._recent.append((time.time(), message))
        self.stage.show_message(message.title, message.text, [(label, self._presses(action)) for label, action in message.buttons], message.timeout_s)
        self._read_aloud(message.title, message.text, message.buttons, important=message.alert)
        if sys.platform == "win32" and self.config["accessibility"].get("magnifier_follows", True):
            self._later(50, self._magnify_bubble)  # once the stage has laid it out
        if message.cue != SILENT:
            self._cue(message.cue or "pop")

    def _presses(self, action):
        """A bubble's button as it's shown: noted as pressed (the bubble needn't stay answerable by typing), then
        doing what it does."""
        def press() -> None:
            self._pressed_showing = True
            if action:
                action()

        return press

    # -- sounds (M4B's sound.py plays them)

    def _cue(self, name: str) -> bool:
        """Play the sound `name` if sound is on, that sound is on (the alerts are, the rest only once you turn them on),
        and it isn't a time for quiet: Do Not Disturb, Focus, a full-screen app, or a focus session of yours. True if
        it was handed to the player."""
        sound = self.config["sound"]
        cues = sound.get("cues") if isinstance(sound.get("cues"), dict) else {}
        if not sound.get("enabled", True) or not cues.get(name, name in ALERT_CUES):
            return False
        if self._quiet or self.reminders.focus() is not None:
            return False
        return self._play(name)

    def _play(self, name: str) -> bool:
        """Hand `name` to the player (sound.py), as configured (_configure_sound): True if it started."""
        from . import sound

        return sound.play(name)

    def _configure_sound(self) -> None:
        """The player told the switch, the volume and each sound's setting, and asked before each sound whether it's a
        time for quiet, as _cue asks."""
        from . import sound

        s = self.config["sound"]
        sound.configure(bool(s.get("enabled", True)), int(s.get("volume", 70)), dict(s.get("cues") or {}),
                        quiet=lambda: self._quiet or self.reminders.focus() is not None)

    def _end_alert(self) -> None:
        if self._alert_key is not None:
            self._alert_key = None
            self.behavior.set_alert(False, self._now())
            if not self.ask_box.isVisible():
                self.stage.raise_above(False)

    # -- screen readers (a11y.py): what a bubble says, read out

    READER_EVERY = 15.0  # seconds between looks for a screen reader starting or stopping
    ANSWERABLE_FOR = 600.0  # seconds a bubble's buttons can still be typed after the chat opened over it

    def _press_typed_button(self, text: str) -> bool:
        """A bubble's button, typed in the chat: the one showing, or the one the chat opened over (opening it
        closes the bubble, and typing is how a keyboard or a screen reader answers one)."""
        if self.stage.press_button(text):
            self._answerable = None
            return True
        if self._answerable is None or time.monotonic() - self._answerable[0] > self.ANSWERABLE_FOR:
            return False
        buttons = self._answerable[1]
        index = a11y.typed_button([label for label, _ in buttons], text)
        if index is None:
            return False
        self._answerable = None
        action = buttons[index][1]
        if action:
            action()
        return True

    def _screen_reader(self) -> a11y.Reader | None:
        """The screen reader to read bubbles aloud with, unless reading aloud is off."""
        if not self.config["accessibility"].get("read_aloud", True):
            return None
        return self._reader_running()

    def _reader_running(self) -> a11y.Reader | None:
        """The screen reader running, as last looked (every READER_EVERY seconds)."""
        now = time.monotonic()
        if now - self._reader_seen > self.READER_EVERY:
            self._reader, self._reader_seen = a11y.reader(), now
        return self._reader

    def _ask_box_as_window(self) -> bool:
        """Whether the ask box is a window of its own where the overlay would draw it: as Settings says, and with
        "auto" while a screen reader runs (a window is what it can find and read; the overlay's drawing isn't)."""
        picked = str(self.config["accessibility"].get("accessible_ask_box", "auto"))
        return picked == "on" or (picked == "auto" and self._reader_running() is not None)

    def _check_hosting(self) -> None:
        """On the overlay: the ask box drawn there, or a window of its own (M3's set_hosting), as it should be now.
        Not while it's open: it moves the next time."""
        if self._overlay and not self.ask_box.isVisible():
            self.stage.set_hosting(not self._ask_box_as_window())

    def _read_aloud(self, title: str, text: str = "", buttons=None, important: bool = False) -> None:
        """Have a running screen reader say it: its own way where there's one (Orca, VoiceOver), else a
        system notification, which screen readers read (Narrator, NVDA, JAWS on Windows)."""
        reader = self._screen_reader()
        if reader is None:
            return
        words = a11y.spoken(title, text, [label for label, _ in buttons or []])
        a11y.announce(reader, words, important, notify=lambda: self._system_notice(a11y.plain(title), words, buttons or (), aloud=True, seconds=15))

    def _watch_desk(self, desk: presence.Desk) -> None:
        """What the desktop says as it changes (M4A's Desk): reduced motion and high contrast, applied at once rather
        than at the next look, and a screen reader starting or stopping (Windows)."""
        desk.settings_changed.connect(self._heard(self._check_accessibility))
        desk.screen_reader_changed.connect(self._heard(self._screen_reader_changed))

    def _screen_reader_changed(self) -> None:
        """A screen reader started or stopped (Windows says so): look again at once, and put the ask box where it
        can find it."""
        self._reader_seen = float("-inf")
        self._check_hosting()

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
        self._quiet = self.desk.quiet(self.stage.native_window())
        covered = self.desk.covered(self.stage.native_window())
        self.stage.set_covered(covered and self._alert_key is None)
        if self._quiet:
            # A full-screen app, a presentation, Do Not Disturb: what came while you were using Chatmon shows, and
            # an alert does unless a full-screen window covers the companion; the rest waits until it's over.
            self.messages.hold("quiet", lambda m: m.yours or (m.alert and not covered))
        elif self.messages.holding("quiet"):
            self.messages.release("quiet")
            self._show_soon(600)  # a moment after it ends

    def _sync_focus_hold(self) -> None:
        """A focus session holds what comes on its own (agents, scripts, heads-ups) below a reminder: it shows once
        the session is over, after what the session's end says."""
        if self.reminders.focus() is not None:
            self.messages.hold("focus", lambda m: not m.background or (m.priority is not None and m.priority <= messages.REMINDER))
        elif self.messages.holding("focus"):
            self.messages.release("focus")
            self._show_soon(400)

    def _check_accessibility(self) -> None:
        """Reduced motion and high contrast: followed as they change, unless you chose otherwise."""
        motion, contrast = self._reduced_motion(), self.desk.high_contrast()
        if (motion, contrast) == (self._reduce_motion, self._high_contrast):
            return
        self._reduce_motion, self._high_contrast = motion, contrast
        self._apply_bubble_style()
        self._apply_accessibility()
        self.behavior.set_walk(self._walks(), self._now())
        self._menu_changed()

    def _reduced_motion(self) -> bool:
        """Less movement: as Settings says (Accessibility), else as the system says."""
        picked = str(self.config["accessibility"].get("reduced_motion", "system"))
        return picked == "on" or (picked != "off" and bool(self.desk.reduce_motion()))

    def _palette_changed(self) -> None:
        """The desktop's colours changed (high contrast on or off, light or dark): the plain style's colours and the
        links in the box are read again at once."""
        self._high_contrast = self.desk.high_contrast()
        self._apply_bubble_style()
        self._menu_changed()

    def _scheme_changed(self, _scheme) -> None:
        if not self._quitting:
            self._palette_changed()

    def _apply_accessibility(self) -> None:
        """Text size, how long bubbles stay, and reduced motion (Settings › Accessibility), wherever they apply."""
        a = self.config["accessibility"]
        scale = int(a.get("text_scale", 100)) / 100
        self.stage.bubble.set_text_scale(scale)
        self.ask_box.set_text_scale(scale)
        factor = BUBBLE_TIMES.get(str(a.get("bubble_time", "normal")), 1.0)
        self.stage.bubble.timeout_policy = TimeoutPolicy(until_closed=True) if factor is None else TimeoutPolicy(factor=factor)
        self.ask_box.set_reduced_motion(self._reduce_motion)
        self.stage.set_reduced_motion(self._reduce_motion)
        a11y.set_speech_fallback(bool(a.get("speech_fallback", False)))  # macOS
        self.stage.follow_pointer_screen(bool(self.config["follow_screen"]))  # stays off where the pointer can't be followed
        self._check_hosting()
        self._configure_sound()

    def eventFilter(self, watched, event) -> bool:
        """Ctrl+1 to Ctrl+9 in the ask box press the bubble's buttons; the desktop's colours changing reach the box
        (a hidden top-level window hears it too) and so Chatmon."""
        kind = event.type()
        if kind == QEvent.Type.KeyPress:
            key, mods = event.key(), event.modifiers()
            plain_ctrl = mods & Qt.KeyboardModifier.ControlModifier and not mods & (Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ShiftModifier)
            if plain_ctrl and Qt.Key.Key_1.value <= key <= Qt.Key.Key_9.value:
                return self._press_bubble_button(key - Qt.Key.Key_1.value)
        elif kind == QEvent.Type.ApplicationPaletteChange and watched is self.ask_box:
            self._later(0, self._palette_changed)
        return False

    def _press_bubble_button(self, index: int) -> bool:
        """The showing bubble's button `index` (0 is the first), pressed as a click would: True if there was one."""
        buttons = self.stage.bubble.buttons if self.stage.message_visible() else []
        return 0 <= index < len(buttons) and self.stage.press_button(buttons[index].label)

    def _walks(self) -> bool:
        """Walking, as the settings say; the system's reduced motion stills it, unless you chose yourself."""
        return bool(self.config["walk"]) and (self._walk_picked or not self._reduce_motion)

    def _magnify_bubble(self) -> None:
        """Windows' Magnifier, when it runs, goes to the bubble that just showed (wincaret.py), unless you're typing
        in the ask box (it follows the field then)."""
        from . import wincaret

        rect = self.stage.bubble_rect()
        if rect.isEmpty() or self.ask_box.isActiveWindow() or not wincaret.magnifier_running():
            return
        scale = self.stage.device_scale()
        wincaret.place(self.stage.native_window(), round(rect.x() * scale), round(rect.y() * scale), round(rect.width() * scale), round(rect.height() * scale))

    def _message_closed(self) -> None:
        if sys.platform == "win32" and self.config["accessibility"].get("magnifier_follows", True):
            from . import wincaret

            wincaret.clear()
        self._end_alert()
        self._note_closed()
        self.messages.closed()
        self._show_soon(400)  # a moment between one bubble and the next

    def _note_closed(self) -> None:
        """The bubble showing went. With buttons and none pressed, it stays answerable by typing a button's label for
        ANSWERABLE_FOR; timed out with no input the whole time it was up (and for MISSED_IDLE at least), it was missed:
        a click on the chatmon brings it back."""
        if self._on_screen is None:
            return
        (since, message), self._on_screen = self._on_screen, None
        now = time.monotonic()
        if message.buttons and not self._pressed_showing:
            self._answerable = (now, list(message.buttons))
        if self.stage.bubble.timed_out:
            idle = self.desk.idle_seconds()
            if idle is not None and idle >= max(MISSED_IDLE, now - since):
                self._missed.append(message)
                del self._missed[:-RECENT_MESSAGES]

    def _bring_back_missed(self) -> None:
        """What went by unseen, again: as it was if it's one, else one bubble listing them."""
        missed, self._missed = self._missed, []
        if len(missed) == 1:
            self._show_again(missed[0])
        else:
            self.say(_("While you were away"), "\n".join(f"- {_gist(m)}" for m in missed), timeout_s=30)

    def _show_again(self, message: messages.Message) -> None:
        """A bubble from before (Recent messages, or missed), shown again as something you asked for: no alert, no sound."""
        self.say(message.title, message.text, message.buttons, timeout_s=max(message.timeout_s or 0, 20), cue=SILENT)

    def recent_messages(self) -> list[tuple[float, messages.Message]]:
        """The bubbles shown lately, newest first: (when, what)."""
        return list(reversed(self._recent))

    def _show_soon(self, ms: int) -> None:
        """Look at the queue again in a moment (a bubble just closed, a hold just ended)."""
        if not self._quitting:
            self._message_timer.start(ms)

    def _no_tray_news(self) -> None:
        """No tray here (stock GNOME, without the AppIndicator extension): where the menu is, said once ever."""
        if QSystemTrayIcon.isSystemTrayAvailable() or self.state.get("told_no_tray"):
            return
        if self.stage.message_visible() or self.ask_box.isVisible():
            self._later(60_000, self._no_tray_news)  # not over something else
            return
        self.state.set("told_no_tray", True)
        self.state.save()
        self.say(_("No tray icon here"), _("My menu is on me: right-click me. After **Hide**, click me when I peek, or open Chatmon from your apps, to bring me back."), timeout_s=20,
                 background=True)

    def _greet(self) -> None:
        for problem in (self.state.problem, self.memory.problem):  # a damaged file, kept aside, and what was used instead
            if problem:
                self.say(_("One of my files was damaged"), problem, timeout_s=30, background=True)
        if self.config_error:
            self._say_config_problem()
        elif self.server_problem:
            self.say(_("Your agents can't reach me"), _("{problem}\n\nEverything else works.").format(problem=self.server_problem), timeout_s=30)
        elif not (self.config["name"] or self.state.get("name")):
            self._asking_name = True
            self.open_ask(focus=False)  # nobody clicked: don't take the keyboard from them
        elif self._whats_new_after_update():
            pass
        elif not self.stage.message_visible() and not self._hello():  # an agent or a script got in first: theirs matters more
            self.say(_("Hi, I'm {name}!").format(name=self.name), _("Click me to ask anything."), timeout_s=5)

    def _hello(self) -> bool:
        """The first unlock (or start) of the day: one bubble naming today's reminders, the agents waiting for you and
        the updates waiting. Once a day, and only when there's something to name. True if said."""
        today = date.today()  # noqa: DTZ011 - your local day
        if self.state.get("hello_day") == today.isoformat():
            return False
        self.state.set("hello_day", today.isoformat())
        self.state.save()
        lines = []
        todays = [r for r in self.reminders.upcoming() if r.kind != "focus" and _day_of(r.due) == today]
        if todays:
            # Translators: one of today's reminders in the morning's hello: "stretch (3:00 PM)".
            each = [_("{reminder} ({time})").format(reminder=r.text, time=reminders.clock(datetime.fromtimestamp(r.due))) for r in todays[:5]]  # noqa: DTZ006 - your local time
            # Translators: the reminders are joined with semicolons: "Today: stretch (3:00 PM); call Sam (5:00 PM)".
            lines.append(_("Today: {reminders}").format(reminders="; ".join(each)))
        waiting = self._waiting_agents()
        if waiting:
            lines.append(ngettext("{agents} is waiting for you.", "{agents} are waiting for you.", len(waiting)).format(agents=join(waiting)))
        if self.updater.ready is not None and self.updater.release is not None:
            lines.append(_("Chatmon {version} is ready to install.").format(version=self.updater.release.version))
        system = sum(self._update_counts.values())
        if system:
            lines.append(ngettext("{n} system update is waiting.", "{n} system updates are waiting.", system).format(n=system))
        if not lines:
            return False
        self.say(_("Good morning") if datetime.now().hour < 12 else _("Welcome back"),  # noqa: DTZ005 - your local morning
                 "\n".join(f"- {line}" for line in lines), timeout_s=30)
        return True

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
        elif self._missed and not self.stage.message_visible():
            self._bring_back_missed()
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
        if self.stage.message_visible() and self.stage.bubble.buttons:  # still answerable, by typing a button
            self._answerable = (time.monotonic(), [(b.label, b.action) for b in self.stage.bubble.buttons])
        self.stage.dismiss_message()
        fresh = now - self._last_ask > NEW_CHAT_AFTER and bool(self.chat.messages) and self.questions.current is None and not self._asking_name
        if fresh:  # a while since: a fresh one, said so (the last is in History, and *carry on* goes back to it)
            set_aside = self.chat
            self._start_chat()
            self._set_aside = set_aside
        self._last_ask = now
        self._mac_edit_menu()  # still there (it's put back if the menu bar was made again)
        anchor = self.stage.head_point()
        if self._asking_name:
            self.ask_box.open(
                anchor,
                _("Hi! I'm your new desktop companion."),
                _("Enter to save · Esc to decide later"),
                _("A name for me"),
                text=_("What should I be called?"),
                activate=focus,
            )
            self.ask_box.chatting(False)
        else:
            brain = self._brain(wait=False)  # only for the hint: as far as can be told without holding up the screen
            if brain:
                hint = _("{keys} · answers from {brain}").format(keys=_(ASK_HINT), brain=brain.label)
            else:
                hint = _("{keys} · no AI set up yet; reminders and timers still work").format(keys=_(ASK_HINT))
            self.ask_box.open(
                anchor, _("Ask {name}").format(name=self.name), hint, _("Ask anything, or: remind me in 20m to stretch"),
                text=self._transcript(), prefill=prefill, activate=focus,
            )
            self.ask_box.chatting(True)
            self.ask_box.hint.setToolTip(hint)  # the box shortens it to its width
            self._show_chat()
            if fresh:
                self.ask_box.set_answer(_("*New chat* · **carry on** with the last one"))
            self.ask_box.set_attachments([a.label() for a in self.attached])
            self.ask_box.set_resettable(bool(self.chat.messages))

    def _box_shows_chat(self) -> bool:
        """The ask box is open on the chat (not naming, renaming, or showing notes to read)."""
        return self.ask_box.isVisible() and self.ask_box.entry.isVisible() and self.ask_box.history_button.isVisible()

    def _show_chat(self, pending: str = "") -> None:
        """The chat in the box, newest exchange first in view, with `pending` after it and what's streaming in so far."""
        self.ask_box.set_answer(self._transcript(pending), at_end=True)
        q = self.questions.answering(self.chat.id)
        if q is not None and q.partial:
            self.ask_box.set_partial(q.partial)

    def _carry_on(self) -> bool:
        """*carry on*, just after the box opened on a new chat for you: back to the chat before. False otherwise (the
        words are then the AI's: "carry on" in a chat asks it to go on)."""
        chat = self._set_aside
        if chat is None or self.chat.messages:
            return False
        self._set_aside = None
        self._back_to(chat)
        return True

    def _back_to(self, chat: chats.Chat) -> None:
        """`chat` (held in memory: kept or not), back in the box."""
        self.chat = chat
        self.attached.clear()
        self._last_ask = self._now()
        self.ask_box.set_attachments([])
        self.ask_box.set_resettable(True)
        self._show_chat()

    def _show_more(self, title: str, markdown: str) -> None:
        """A bubble cut short: its whole text, to read in the box."""
        self.ask_box.show_notes(self.stage.head_point(), title, markdown)

    def _remember_expanded(self, on: bool) -> None:
        self.state.set("ask_box_expanded", on)
        self.state.save()

    def _ask_closed(self) -> None:
        if self._alert_key is None:
            self.stage.raise_above(False)
        now = self._now()
        self._asking_name = False
        self._renaming = None
        self._instructing = None
        self._editing = None
        # A question on its way carries on: its answer is kept in the chat, and a bubble says it came (_answered).
        self.behavior.set_talking(False, now)
        self.behavior.set_attending(self._menu_open, now)

    # -- chats: kept, resumed, and what's attached to them

    def _keeps_chats(self) -> bool:
        picked = self.state.get("keep_chats")
        return bool(self.config["chats"]["keep"] if picked is None else picked)

    def _drop_question(self) -> None:
        """A question on its way belongs to the chat it was asked in: leaving that chat drops it."""
        if self.questions.current is not None:
            self.asker.cancel()
            self.compactor.cancel()
            self.questions.drop()
            self.behavior.set_thinking(False, self._now())
            self.ask_box.set_busy(None)

    def _start_chat(self) -> None:
        self._drop_question()
        self.chat = chats.Chat(keep=self._keeps_chats())
        self.attached.clear()

    def _new_chat(self) -> None:
        self._start_chat()
        self.ask_box.set_attachments([])
        self.ask_box.set_resettable(False)
        self.ask_box.set_answer(_("*New chat. Ask away.*"))

    def _transcript(self, pending: str = "") -> str:
        """The chat as the box shows it: each question and its answer, newest at the bottom, then what's still to
        be answered, then `pending` (an answer of Chatmon's own, a word about the question)."""
        parts = []
        for m in self.chat.messages[-40:]:
            if m.role == "user":
                parts.append(richtext.question_markdown(asking.typed(m.text), m.attached))
            else:
                parts.append(m.text)
        parts += asking.tail(self.questions, self._thinking())
        if pending:
            parts.append(pending)
        return "\n\n".join(parts)

    def _thinking(self) -> str:
        """What the brain is doing about the question on its way."""
        question = self.questions.current
        brain = question.brain if question is not None else None
        if question is not None and question.fold is not None:
            if brain is not None:
                return _("Catching {brain} up on this chat's earlier part…").format(brain=brain.label)
            return _("Catching the AI up on this chat's earlier part…")
        return _("{brain} is thinking…").format(brain=brain.label) if brain is not None else _("The AI is thinking…")

    def _save_chat(self) -> None:
        if self._keeps_chats() and self.chat.keep and self.chat.messages:
            try:
                self.chat_book.save(self.chat)
            except OSError as exc:
                logger.warning("couldn't save the chat: %s", exc)

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
        self.ask_box.open(self.stage.head_point(), _("Rename this chat"), _("Enter to save · Esc to leave it as it is"), _("A name for the chat"), prefill=chat.title)
        self.ask_box.chatting(False)
        self.ask_box.set_attachments([])
        self.ask_box.entry.selectAll()

    def _ask_chat_instructions(self, chat_id: str) -> None:
        chat = self._chat_by_id(chat_id)
        if chat is None:
            return
        self._instructing = chat_id
        self.ask_box.open(
            self.stage.head_point(), _("Instructions for this chat"), _("Sent with each question in this chat · Enter to save · empty to remove"),
            _("How to answer in this chat"), prefill=chat.instructions,
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
                name, _kind = QFileDialog.getSaveFileName(self.stage.dialog_owner(), _("Save the chat"), str(Path.home() / f"{safe}.md"),
                                                          _("Markdown (*.md);;Text (*.txt)"))
            finally:
                if shown:
                    self.ask_box.resume()
            self._write_chat(chat, name)

        if self._chooser() is not None:
            self._through_portal(lambda then, fallback: self._file_chooser.save_file(_("Save the chat"), Path.home(), f"{safe}.md", then, fallback),
                                 lambda names: self._write_chat(chat, names[0] if names else ""), with_qt)
        else:
            with_qt()

    def _write_chat(self, chat: chats.Chat, name: str) -> None:
        if not name:
            return
        try:
            Path(name).write_text(chat.markdown(), encoding="utf-8")
        except OSError as exc:
            self.say(_("Couldn't save the chat"), str(exc), timeout_s=10)
            return
        self.say(_("Chat saved"), f"`{Path(name).name}`", timeout_s=5)  # a file's name: nothing to translate

    def _ask_to_delete_chat(self, chat_id: str) -> None:
        chat = self._chat_by_id(chat_id)
        if chat is not None:
            title = _("Delete “{title}”?").format(title=chat.title or _("this chat"))
            self.say(title, _("It can't be brought back."), [(_("Delete it"), partial(self._delete_chat, chat_id)), (_("Keep it"), None)], timeout_s=30)

    def _popup(self, menu: QMenu, pos: QPoint) -> None:
        """A menu of the moment, where it can be seen: drawn by the stage on the Wayland overlay, and on macOS a
        native one, so a paste chosen there is yours to macOS (macnative.py)."""
        if self.stage.draws_menus():
            self.stage.open_menu(menu, pos, owned=True)
            return
        if QGuiApplication.platformName() == "cocoa":
            from . import macnative

            if macnative.popup(menu, pos, self.ask_box):
                return
        sip.transferto(menu, None)  # type: ignore[arg-type]  # sip's stub leaves out None, which sip takes: it outlives the caller's hold on it, until it closes
        menu.aboutToHide.connect(menu.deleteLater)
        menu.popup(pos)

    def _mac_edit_menu(self) -> None:
        """macOS: Cmd+V through an Edit menu of Chatmon's own, so macOS knows you pasted (macnative.py)."""
        if QGuiApplication.platformName() == "cocoa":
            from . import macnative

            macnative.edit_menu(self._paste_into_focus)

    @staticmethod
    def _paste_into_focus() -> None:
        """The Edit menu's Paste: to the widget with the keyboard, as Cmd+V itself would have gone."""
        widget = QApplication.focusWidget()
        if widget is not None:
            for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
                QApplication.sendEvent(widget, QKeyEvent(kind, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier, "v"))

    def _show_history(self, pos: QPoint | None = None) -> None:
        """Your chats, in a menu by the ask box's History button (or at `pos`)."""
        if pos is None:
            button = self.ask_box.history_button
            pos = button.mapToGlobal(QPoint(0, button.height()))
        menu = QMenu()
        menus.chats_menu(self, menu, in_box=True)
        self._popup(menu, pos)

    def _open_new_chat(self) -> None:
        self._start_chat()
        self.open_ask()

    def _resume_chat(self, chat_id: str) -> None:
        chat = self.chat
        if chat_id != self.chat.id:
            found = self.chat_book.load(chat_id)
            if found is None:
                self.say(_("That chat is gone"), _("It may have been cleared."), timeout_s=6)
                return
            chat = found
            self._drop_question()
        self.chat = chat
        self._set_aside = None
        self.attached.clear()
        self._last_ask = self._now()
        if not self.ask_box.isVisible():
            self.open_ask()
        self.ask_box.set_attachments([])
        self.ask_box.set_resettable(True)
        self._show_chat()

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
            _("Delete every saved chat?"), _("They can't be brought back."),
            [(_("Delete them"), self._clear_chats), (_("Keep them"), None)], timeout_s=30,
        )

    def _clear_chats(self) -> None:
        gone = self.chat_book.clear()
        self._start_chat()
        if self.ask_box.isVisible():
            self.ask_box.set_attachments([])
            self.ask_box.set_resettable(False)
            self.ask_box.set_answer(_("*Chat history cleared.*"))
        self._menu_changed()
        self.say(_("Chat history cleared"), ngettext("{n} chat deleted.", "{n} chats deleted.", gone).format(n=gone), timeout_s=5)

    def _set_keep_chats(self, on: bool) -> None:
        self.state.set("keep_chats", on)
        self.state.save()
        self._menu_changed()
        if on:  # from the next chat: what was said while it was off stays unsaved, as promised
            self.say(_("Keeping chats"), _("Chats from here on are kept, so you can come back to them."), timeout_s=8)
        else:
            self.chat.keep = False
            self.say(_("Not keeping chats"), _("From now on, chats stay only until I quit. Earlier ones stay until you clear them."), timeout_s=10)

    def _show_attach(self, pos: QPoint) -> None:
        menu = QMenu()
        menu.addAction(_("Attach files…"), self._attach_files)
        menu.addAction(_("Paste from the clipboard"), self._paste_into_box)
        if self.attached:
            menu.addAction(_("Take them all off"), self._clear_attachments)
        self._popup(menu, pos)

    def _paste_into_box(self) -> None:
        hosted = self.stage.hosted
        if hosted is not None and hosted.widget is self.ask_box:
            hosted.paste()  # the overlay's own clipboard
        else:
            self.ask_box.paste_clipboard()

    def _attach_files(self) -> None:
        if self._chooser() is not None:
            self._through_portal(lambda then, fallback: self._file_chooser.open_files(_("Attach to your question"), Path.home(), then, fallback),
                                 self._attach_files_named, self._attach_files_with_qt)
        else:
            self._attach_files_with_qt()

    def _attach_files_with_qt(self) -> None:
        # The system's file dialog needs the keyboard, which the ask box holds on the overlay: out of its way meanwhile.
        self.ask_box.pause()
        try:
            files, _kind = QFileDialog.getOpenFileNames(self.stage.dialog_owner(), _("Attach to your question"), str(Path.home()))
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
            self.say(_("That's a lot of files"), _took_first(room), timeout_s=8)
        for name in local[: max(0, room)]:
            self._attach(lambda name=name: attachments.from_path(Path(name)))

    def _attach_dropped(self, dropped: list) -> None:
        """Files that aren't on disk (winfiles.Dropped: out of Outlook or a zip), already read."""
        room = attachments.MAX_COUNT - len(self.attached)
        if len(dropped) > room:
            self.say(_("That's a lot of files"), _took_first(room), timeout_s=8)
        for item in dropped[: max(0, room)]:
            if item.problem:
                self._attached_one(attachments.AttachError(item.problem))  # a sentence that names the file
            else:
                self._attach(lambda item=item: attachments.from_bytes(item.data, item.name))

    def _attach_pasted(self, kind: str, payload) -> None:
        if kind == "files":
            self._attach_files_named(list(payload))
        elif kind == "named":
            self._attach_dropped(list(payload))
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
            self.say(_("Couldn't attach that"), str(exc)[:1].upper() + str(exc)[1:] + ".", timeout_s=8)
            return
        except Exception as exc:  # said, never fatal
            logger.debug("attaching failed", exc_info=True)
            self.say(_("Couldn't attach that"), str(exc), timeout_s=8)
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
        if not self.attached and self._press_typed_button(text):  # a bubble's button, by its label
            self.ask_box.entry.clear()
            return
        if self._asking_name:
            self._asking_name = False
            self.state.set("name", text.strip()[:40])
            self.state.save()
            self._menu_changed()
            self.ask_box.dismiss()
            self.behavior.react("hop", now)
            self._find_brain(self._welcome)
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
        if self._editing is not None:
            if self._apply_edit(self._editing, text):
                self._editing = None
                self.ask_box.dismiss()
            else:
                self.ask_box.entry.setText(text)
            return
        if not self.attached and self._local(text):  # with something attached, it's a question
            return
        chat_id = self.chat.id
        self._find_brain(lambda brain: self._ask(text, brain, chat_id))

    def _find_brain(self, then) -> None:
        """The brain to ask (the chat's own, then the menu's pick, the settings', the first found), handed to `then`:
        at once when that's known without waiting, else once a thread has looked at the model servers here
        (brains.Finder). Never waits on the screen's thread."""
        configured, picked, prefer = self.config["ai"]["brain"], self.state.get("brain"), self.chat.brain or None
        quick = brains.choose(self.brains, configured, picked, wait=False, prefer=prefer)
        if not brains.unsure():
            then(self._with_options(quick))
            return
        self.finder.find(self.brains, configured, picked, lambda found: then(self._with_options(found)), prefer=prefer)

    def _with_options(self, brain: brains.Brain | None) -> brains.Brain | None:
        """The brain with the model, effort and thinking picked for it from the menu."""
        return brain.with_options(dict((self.state.get("brain_options") or {}).get(brain.name) or {})) if brain else None

    def _welcome(self, brain: brains.Brain | None) -> None:
        """Named at the first run: hello, what it does, and which brain will answer (or how to set one up)."""
        if brain is None:
            line = _("No AI is set up yet: sign in to an AI command-line tool (Claude Code, Codex, Gemini CLI...), run a model "
                     "server here (Ollama, LM Studio...), or add an API key in **Settings › AI**. Reminders, timers and notes "
                     "work without one.")
        else:
            line = _("Your questions go to **{brain}**; **Brain** in my menu picks another.").format(brain=brain.label)
        self.say(_("{name}! I love it.").format(name=self.name), f"{_(HELP)}\n{line}", timeout_s=25)

    def _ask(self, text: str, brain: brains.Brain | None, chat_id: str | None = None) -> None:
        """Send `text` (with what's attached) to `brain`, or have it wait behind the question on its way."""
        if self._quitting or (chat_id is not None and chat_id != self.chat.id):
            return  # Chatmon quit, or you left that chat, while the brain was looked for
        if brain is None:
            self._no_brain()
            return
        self._announce_fallback(brain)
        attached = list(self.attached)
        refused = brains.cant_take(brain, attached)
        if refused:  # kept, for a brain that can
            self.ask_box.entry.setText(text)
            self._show_chat(f"*{refused}*")
            return
        if self.questions.full():  # kept, to send once those are answered
            self.ask_box.entry.setText(text)
            self._show_chat(_("*One question is waiting already. Send this once that one goes, or press Stop.*"))
            return
        self.attached.clear()
        self.ask_box.set_attachments([])
        question = asking.Question(self.chat.id, text, attached, brain)
        if self.questions.ask(question):  # else it waits for the one on its way: a brain answers one at a time
            self.behavior.set_thinking(True, self._now())
            self._send(question)
        self._show_chat()

    def _no_brain(self) -> None:
        """Nothing to ask: say how to set one up, and offer a model server here that isn't yours, once."""
        self.ask_box.set_answer(
            _("I haven't found an AI to ask yet. Any of these works: an AI command-line tool you're "
              "signed in to (Claude Code, Codex, Gemini CLI, Muse Code, Grok...), a model server on this "
              "computer (Ollama, LM Studio, llama.cpp, vLLM), or an API key, picked under **Brain** in my "
              "menu.") + "\n\n" + _(HELP)
        )
        self._offer_server()

    def _offer_server(self) -> bool:
        """A model server running here, but not as you (anyone on this computer can open its port, and would read your
        questions): Automatic leaves it alone, so ask once a run whether to use it. True if asked."""
        for brain in self.brains.values():
            if not (brain.local and brain.automatic()):
                continue
            url = brains.expand(brain.url)
            where = brains.server_key(url)
            if where in self._server_offered or not brains.reachable(url, wait=False) or brains.trusted(url, wait=False):
                continue
            self._server_offered.add(where)
            self.say(
                _("Use the model server at {server}?").format(server=where),
                _("{brain} is running here, but not as you: someone else on this computer may have started it, and would "
                  "see your questions. Use it anyway?").format(brain=brain.label),
                [(_("Use it"), partial(self._trust_server, url)), (_("Not now"), None)], timeout_s=None, key="trust-server",
            )
            return True
        return False

    def _trust_saved_servers(self) -> None:
        """The model servers you've said Automatic may use (brains.trusted), as kept in state, handed back."""
        for server in self.state.get("trusted_servers") or []:
            if isinstance(server, str):
                brains.confirm_server(f"http://{server}")

    def _trust_server(self, url: str) -> None:
        brains.confirm_server(url)
        self.state.set("trusted_servers", brains.confirmed_servers())
        self.state.save()
        self._menu_changed()

    def _announce_fallback(self, brain: brains.Brain) -> None:
        """The brain picked in the menu can't answer, so another does: said once for that pick, not every question."""
        picked = self.state.get("brain")
        chosen = self.brains.get(picked) if picked else None
        if chosen is None or brain.name == picked or chosen.available(wait=False):
            if chosen is not None and brain.name == picked:
                self._fallback_told = None  # it's back: say so again if it goes
            return
        if self._fallback_told == picked:
            return
        self._fallback_told = picked
        self.say(_("{brain} isn't available").format(brain=chosen.label),
                 _("It's {reason}, so {brain} answers for now.").format(reason=chosen.why_not(), brain=brain.label), timeout_s=12, key="brain-fallback")

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

    def _send(self, q: asking.Question, *, fold: bool = True) -> None:
        """Ask `q`'s brain, with as much of the chat as it can take: first summing up the chat's earlier part, when
        it has outgrown that (a step of its own, said in the box)."""
        brain, question, attached = q.brain, q.asked(), q.attached
        chat, timeout = self.chat, float(self.config["ai"]["timeout_seconds"])
        if not q.started:
            q.started = time.monotonic()
        self.ask_box.set_busy(brain.label, q.started)
        guard = brain.reads_files()  # one that reads files is never handed another brain's answers (one could tell it what to read)
        base = brains.system_prompt(self.name, self._companion().label_en.lower())  # sent to the brain: English, as the rest of the prompt
        everywhere, remembered = self._instructions(), self.memory.texts()
        asked_tokens = context.tokens(attachments.in_question(question, attached)) + attachments.media_tokens(attached)
        room = context.budget(brains.context_window(brain), self._context_cap(), context.system_text(base, everywhere, chat.instructions, remembered), asked_tokens)
        pairs = chat.history(brain.label, name=brain.name, own_only=guard, before=q.before)
        neutral = chat.history(brain.label if guard else "", name=brain.name if guard else "", own_only=guard, before=q.before)
        summary, summarized = chat.summary_for(brain.name, own_only=guard)
        plan = context.plan(pairs, neutral, summary, summarized, room, question, fold)
        if plan.fold:
            q.fold = asking.Fold(plan.fold_to, room)
            system, request = context.summary_request(plan.summary, plan.fold, room)
            if self._box_shows_chat():
                self._show_chat()
            self.compactor.ask(brain, system, [], request, timeout)
            return
        system = context.system_text(base, everywhere, chat.instructions, remembered, plan.summary, plan.recalled)
        q.tokens = context.tokens(system) + sum(context.pair_tokens(pair) for pair in plan.recent) + asked_tokens
        self.asker.ask(brain, system, plan.recent, question, timeout, attached)
        if brain.type == "openai" and not brains.window_known(brain):
            self.background.run(partial(brains.learn_window, brain), lambda _window: None)  # for the next question

    def _compacted(self, summary: str) -> None:
        q = self.questions.answering(self.chat.id)
        if q is None or q.fold is None:
            return  # the question went (another chat, or you closed the box)
        fold, q.fold = q.fold, None
        if not summary.strip():
            self._send(q, fold=False)
            return
        self.chat.set_summary(context.clip(summary.strip(), max(300, fold.room // 5)), fold.covers, by=q.brain.name if q.brain.reads_files() else "")
        self._save_chat()
        self._send(q)

    def _compact_failed(self, _error: str) -> None:
        """No summary: the question goes anyway, with the recent turns and the earlier ones that bear on it."""
        q = self.questions.answering(self.chat.id)
        if q is None or q.fold is None:
            return
        q.fold = None
        self._send(q, fold=False)

    def _partial(self, text: str) -> None:
        """A piece of the answer as it's written: kept with the question, and shown under the chat as it comes."""
        q = self.questions.answering(self.chat.id)
        if q is None or q.fold is not None:
            return
        first, q.partial = not q.partial, q.partial + text
        if self._box_shows_chat():
            if first:
                self._show_chat()  # "… is thinking" gives way to the answer itself
            else:
                self.ask_box.set_partial(q.partial)  # all of it so far: the box may have been drawn again since the last piece

    def _answered(self, answer: str) -> None:
        now = self._now()
        q = self.questions.answering(self.chat.id)
        if q is None:  # asked in a chat since left: not this one's
            self.behavior.set_thinking(False, now)
            self.questions.drop()
            self.ask_box.set_busy(None)
            return
        sent = attachments.in_question(q.asked(), q.attached)
        label, name = (q.brain.label, q.brain.name) if q.brain else ("", "")
        if q.brain is not None and q.brain.local:
            self.background.run(partial(brains.learn_window, q.brain), lambda _window: None)  # a model loaded now says its own
        self.chat.add(chats.Message("user", q.text, sent=sent if sent != q.text else "", attached=[a.name for a in q.attached], brain=label, by=name))
        self.chat.add(chats.Message("assistant", answer, brain=label, by=name))
        self._save_chat()
        self._next_question(now)
        self._show_chat()
        self.ask_box.set_resettable(True)
        came = _("{brain} answered").format(brain=label) if label else _("The AI answered")
        if self._box_shows_chat():
            self._read_aloud(came, answer)
        else:  # you closed the box meanwhile: the answer is kept, and this says it came
            self.say(came, buttons=[(_("Read"), self._read_answer)], timeout_s=30, key="answered", cue="done")
        self.behavior.set_talking(True, now)
        self._later(int(min(max(len(answer) / 18, 2), 10) * 1000), self._stop_talking)

    def _stop_talking(self) -> None:
        self.behavior.set_talking(False, self._now())

    def _read_answer(self) -> None:
        """The answered bubble's Read: the box, open at the chat the answer is in."""
        self._last_ask = self._now()  # however long it took, this is the chat to show
        self.open_ask()

    def _next_question(self, now: float) -> None:
        """The question on its way is done with: the one waiting goes now, if there is one."""
        waiting = self.questions.finish()
        if waiting is None:
            self.behavior.set_thinking(False, now)
            self.ask_box.set_busy(None)
        else:
            self._send(waiting)

    def _stop_answer(self) -> None:
        """Stop: the answer on its way ends here. What came of it stays in the chat, marked as stopped; if nothing came,
        the question goes back in the box. The question waiting goes next."""
        q = self.questions.answering(self.chat.id)
        if q is None:
            self.ask_box.set_busy(None)
            return
        self.asker.cancel()
        self.compactor.cancel()
        if q.partial.strip():
            label, name = (q.brain.label, q.brain.name) if q.brain else ("", "")
            sent = attachments.in_question(q.asked(), q.attached)
            self.chat.add(chats.Message("user", q.text, sent=sent if sent != q.text else "", attached=[a.name for a in q.attached], brain=label, by=name))
            self.chat.add(chats.Message("assistant", q.partial.rstrip() + "\n\n" + _("*(Stopped here.)*"), brain=label, by=name))
            self._save_chat()
            self.ask_box.set_resettable(True)
        else:
            self.attached = q.attached + self.attached
            self.ask_box.set_attachments([a.label() for a in self.attached])
            if q.text and not self.ask_box.entry.text():
                self.ask_box.entry.setText(q.text)
        self._next_question(self._now())
        self._show_chat()

    def _failed(self, error: str) -> None:
        now = self._now()
        q = self.questions.answering(self.chat.id)
        if q is not None and not q.retried and context.too_long(error):
            # Too long for it after all (a window smaller than it said, or than guessed): once more, with half.
            brains.shrink_window(q.brain, q.tokens)
            q.retried = True
            self._send(q)
            return
        if q is None:
            self.behavior.set_thinking(False, now)
            self.questions.drop()
            return
        # Back in the box, to try again (or with another brain); the one waiting goes meanwhile.
        self.attached = q.attached + self.attached
        self.ask_box.set_attachments([a.label() for a in self.attached])
        if q.text and not self.ask_box.entry.text():
            self.ask_box.entry.setText(q.text)
        self._next_question(now)
        self.questions.failure = (q.text, error)
        self._show_chat()
        self._offer_after_failure(q, error)

    def _offer_after_failure(self, q: asking.Question, error: str) -> None:
        """What to do about a failed question: ask the same brain again, the next one, or look at its settings."""
        buttons = [(_("Try again"), partial(self._try_again, q, None))]
        other = self._next_brain(q.brain)
        if other is not None:
            # Translators: a button that asks another brain the question that failed: "Ask Ollama".
            buttons.append((_("Ask {brain}").format(brain=other.label), partial(self._try_again, q, other)))
        buttons.append((_("Settings"), partial(self.open_settings, "ai")))
        title = _("{brain} couldn't answer").format(brain=q.brain.label) if q.brain else _("The AI couldn't answer")
        self.say(title, error, buttons, timeout_s=None, key="answer-failed", cue="error")

    def _try_again(self, q: asking.Question, brain: brains.Brain | None) -> None:
        """The failed question, asked again (of `brain`, or the one it went to), with what was attached to it."""
        if q.chat_id != self.chat.id:
            return  # you've moved to another chat since
        if self.ask_box.entry.text() == q.text:
            self.ask_box.entry.clear()
        self._ask(q.text, brain or q.brain)

    def _next_brain(self, failed: brains.Brain | None) -> brains.Brain | None:
        """Another brain to ask: the one Automatic would pick without `failed`, else one that's set up with a key."""
        others = {name: b for name, b in self.brains.items() if failed is None or name != failed.name}
        found = brains.choose(others, "auto", None, wait=False)
        if found is None:
            found = next((b for b in others.values() if b.type != "command" and not b.local and b.available(wait=False) and b.has_key()), None)
        return self._with_options(found)

    def _offline(self, question: str, reply: str, spoken: str | None = None) -> None:
        """An answer of Chatmon's own: shown under the chat, marked as such, and never part of it (no brain
        sees it, and it isn't kept). `spoken`: what a screen reader is told instead, when the answer itself
        mustn't leave the box (it may be read out through a system notification, which keeps a history)."""
        self._offline_shown += 1
        self._show_chat(f"{richtext.question_markdown(asking.typed(question))}\n\n{reply}\n\n*{_(NO_AI)}*")
        self._read_aloud(spoken or reply)

    def _local(self, text: str) -> bool:
        """What Chatmon does by itself, without any AI: True if it was that. Anything else is the AI's."""
        return commands.run(self, text, self.command_table)

    def _copy(self, text: str) -> None:
        """Onto the clipboard: the overlay's own, where Chatmon draws on one."""
        if hasattr(self.stage.surface, "copy"):
            self.stage.clipboard_copy(text)
        else:
            board = QGuiApplication.clipboard()
            if board is not None:  # never None while Qt's GUI runs
                board.setText(text)

    def _show_status(self, question: str) -> None:
        """The *status* command: which brain would answer comes from the brain finder (brains.Finder), which never
        waits, and asks the model servers here only as a question would; the battery and disks are read off the
        screen's thread; then it's shown, unless something else has been answered meanwhile."""
        self._offline(question, _("*Looking…*"))
        shown, upcoming = self._offline_shown, self.reminders.upcoming()

        def found(brain: brains.Brain | None) -> None:
            if self._offline_shown != shown or self._quitting:
                return
            brain = self._with_options(brain)

            def look() -> str:
                battery, disks = heads_up.read_battery(), heads_up.read_disks(heads_up.disk_folders())
                detail = brains.describe(brain) if brain else ""
                return "\n".join(commands.status_lines(battery, disks, upcoming, time.time(), brain.label if brain else None, detail))

            self.background.run(look, looked)

        def looked(status) -> None:
            if self._offline_shown == shown and not self._quitting:
                self._offline(question, status if isinstance(status, str) else _("I couldn't look: {problem}").format(problem=status))

        # The brain a question goes to, as the menu says it (commands.brain_in_use): the menu's pick, else the settings'.
        self.finder.find(self.brains, self.config["ai"]["brain"], self.state.get("brain"), found)

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
        # Translators: what a focus session is called in the list of reminders: "25-minute focus".
        self.reminders.add(time.time() + minutes * 60, _("{minutes}-minute focus").format(minutes=f"{minutes:g}"), "focus")
        self.save()
        self.behavior.react("hop", self._now())
        quiet = ngettext("{minutes} minute. I'll keep quiet until then.", "{minutes} minutes. I'll keep quiet until then.", round(minutes))
        self.say(_("Focus time"), quiet.format(minutes=f"{minutes:g}"), timeout_s=5)

    def stop_focus(self) -> None:
        focus = self.reminders.focus()
        if focus:
            held = self._take_focus_held()
            self.reminders.cancel(focus.id)
            self.save()
            if held:  # one bubble: stopped, and what waited meanwhile
                self.say(_("Focus stopped"), _("While you focused:") + "\n\n" + _summary(held), timeout_s=30)
            else:
                self.say(_("Focus stopped"), timeout_s=3)

    def _take_focus_held(self) -> list[messages.Message]:
        """The plain bubbles a focus session held, out of the queue (its end sums them up); ones with buttons stay, to
        show in turn."""
        held = self.messages.held("focus")
        return self.messages.take(lambda m: m in held and not m.buttons)

    def _summarize_focus(self, held: list[messages.Message]) -> None:
        if held:
            self.say(_("While you focused"), _summary(held), timeout_s=30)

    def _check_reminders(self) -> None:
        """What came due since the last look: one alert each, which waits until it's done or snoozed (the book keeps
        it, fired, meanwhile); a focus session that ended is over."""
        now = time.time()
        fired = self.reminders.fire(now)
        if not fired:
            return
        sessions = [r for r in fired if r.kind == "focus"]
        held = self._take_focus_held() if sessions else []
        for r in sessions:
            self.reminders.acknowledge(r.id, now)  # a session that ended is over: nothing to snooze
        self.save()
        if sessions and self.config["focus"].get("tell_when_done", True):
            self.behavior.react("beam", self._now())
            minutes = float(self.config["focus"]["minutes"])
            self.say(
                _("Focus session done!"),
                _("Nice work. Take five minutes away from the screen."),
                [(_("Another round"), partial(self.start_focus, minutes)), (_("Done"), None)],
                timeout_s=None, cue="focus-done",
            )
        self._summarize_focus(held)
        for r in fired:
            if r.kind != "focus":
                self._alert_reminder(r, now)

    def _show_due_reminders(self) -> None:
        """At start: the reminders that fired and weren't done or snoozed (Chatmon quit, or the computer was off), each
        shown again; a focus session that ended meanwhile is over."""
        now = time.time()
        due = self.reminders.due(now)
        for r in [r for r in due if r.kind == "focus"]:
            self.reminders.acknowledge(r.id, now)
        if due:
            self.save()
        for r in due:
            if r.kind != "focus":
                self._alert_reminder(r, now)

    def _alert_reminder(self, r: reminders.Reminder, now: float) -> None:
        """One reminder's alert, keyed by it (the queue never drops it, nor shows it twice): Done, a snooze of your own
        length, and Later (every snooze)."""
        text = r.text
        if now - r.due > 120:
            text = _("{reminder} (due at {time})").format(reminder=r.text, time=reminders.clock(datetime.fromtimestamp(r.due)))  # noqa: DTZ006 - your local time
        if r.repeat:
            repeat = reminders.describe_repeat(r.repeat)
            text += f"\n\n*{repeat[:1].upper()}{repeat[1:]}*"
        own = reminders.snooze_choices(now, self._snooze_minutes())[0][0]
        buttons = [
            (_("Done"), partial(self._reminder_done, r.id)),
            # Translators: a button that puts a reminder off for the person's own snooze: "Snooze 10 min".
            (_("Snooze {length}").format(length=own), partial(self._snooze_reminder, r.id, None)),
            (_("Later…"), partial(self._offer_snoozes, r.id)),
        ]
        self.alert(f"reminder:{r.id}", _("Time's up!") if r.kind == "timer" else _("Reminder"), text, buttons, reminder=True)

    def _snooze_minutes(self) -> float:
        return float(self.config["reminders"]["snooze_minutes"])

    def _reminder_done(self, rid: str) -> None:
        """Done: a one-off goes, a repeating one moves on to its next time."""
        if self.reminders.acknowledge(rid, time.time()):
            self.save()

    def _snooze_reminder(self, rid: str, until: float | None) -> None:
        """Put off until `until`, or for your own snooze from now."""
        if self.reminders.snooze(rid, time.time() + self._snooze_minutes() * 60 if until is None else until):
            self.save()

    def _offer_snoozes(self, rid: str) -> None:
        r = self.reminders.get(rid)
        if r is None:
            return
        choices = reminders.snooze_choices(time.time(), self._snooze_minutes())
        buttons = [(label, partial(self._snooze_reminder, rid, until)) for label, until in choices] + [(_("Done"), partial(self._reminder_done, rid))]
        self.say(_("Snooze until…"), _gist(messages.Message(r.text)), buttons, timeout_s=None, key=f"reminder:{rid}")

    def _edit_reminder(self, rid: str) -> None:
        """The box, asking for a reminder's new words, a new time, or both ("call Sam friday at 3pm")."""
        r = self.reminders.get(rid)
        if r is None:
            return
        self._editing = rid
        self.ask_box.open(
            self.stage.head_point(), _("Change this reminder"),
            _("Now {when} · Enter to save · Esc to leave it").format(when=reminders.describe(r.due, time.time())),
            _("New words, a new time, or both"), prefill=r.text,
        )
        self.ask_box.chatting(False)
        self.ask_box.set_attachments([])
        self.ask_box.entry.selectAll()

    def _apply_edit(self, rid: str, text: str) -> bool:
        """New words and time words for a reminder, as typed: applied, and said. False (and why, in the box) when the
        time can't be told, nothing is left of the words, or the book refuses: nothing changes then."""
        when = reminders.parse_when(text, datetime.now())  # noqa: DTZ005 - times are typed in local wall time
        words = (when.rest if when is not None else text).strip(" ,.:;")
        if when is not None and when.due is None:
            self.ask_box.set_answer(reminders.explain(reminders.Command("unclear", text=words, ambiguous=when.ambiguous)))
            return False
        changes: dict = {"text": words or None}
        if when is not None:
            if when.due is not None:  # it is: a time that can't be told was refused above
                changes["when"] = when.due.timestamp()
            if when.repeat:
                changes["repeat"] = when.repeat
        try:
            changed = self.reminders.update(rid, **changes)
        except ValueError as exc:
            self.ask_box.set_answer(_("That didn't change it: {problem}.").format(problem=exc))
            return False
        r = self.reminders.get(rid) if changed else None
        if r is not None:
            self.save()
            self.say(_("Reminder changed"), _reminder_said(r), timeout_s=6)
        return True

    def _set_repeat(self, rid: str, rule: str | None) -> None:
        """How a reminder repeats: a rule (reminders.next_time), or None for never."""
        if self.reminders.update(rid, repeat=rule):
            self.save()

    def _check_time(self) -> None:
        now = time.time()
        if now - self._last_wall > 300:  # the computer was asleep
            self.breaks.away(self._last_wall)
            self.breaks.back(now)
        self._last_wall = now
        self._check_away()
        self._check_hosting()  # a screen reader started or stopped (macOS and Linux say nothing of it)
        self.menus.tick()  # a countdown in the menu says what's left: the menu isn't built again for it
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
                _("Time for a break?"),
                ngettext("You've been at the screen for {n} minute. Stand up, stretch, and look at something far away.",
                         "You've been at the screen for {n} minutes. Stand up, stretch, and look at something far away.", minutes).format(n=minutes),
                [(_("Taking one"), partial(self.breaks.took_break, now)),
                 (ngettext("Snooze {minutes} min", "Snooze {minutes} min", round(snooze)).format(minutes=f"{snooze:g}"), None)],
                timeout_s=120,
            )

    def _watch_screen_lock(self) -> None:
        """Hear the screen lock and the computer sleep (time away counts as a break). macOS has no
        documented lock notification: there, time without input (presence.Desk) tells the same."""
        if sys.platform == "win32":
            from . import winlock

            self._lock_watcher = winlock.LockWatcher(self._heard(self._screen_locked), self._heard(self._sleeping), seen=self._heard(self._seen),
                                                     saving=self._heard(self._power_saving),
                                                     settings=self.desk.windows_setting_changed)
            return
        if sys.platform == "darwin":
            # Not QtDBus: PyQt ships it on macOS too, and on an Intel Mac with Homebrew's dbus Qt finds its libdbus and
            # asks for a session bus macOS doesn't have. NSWorkspace says it all instead (macnative.py).
            from . import macnative

            watcher = macnative.WorkspaceWatcher()
            watcher.slept.connect(self._heard(self._sleeping))
            seen = self._heard(self._seen)
            watcher.screens_slept.connect(lambda asleep: seen(not asleep))  # nothing drawn while the displays sleep
            watcher.accessibility_changed.connect(self._heard(self._check_accessibility))
            watcher.low_power_changed.connect(self._heard(self._power_saving))
            self._lock_watcher = watcher
            self._power_saving(bool(macnative.low_power_mode()))
            return
        try:  # D-Bus: Linux and the BSDs
            from . import linuxsession
        except ImportError:
            return
        self._lock_watcher = linuxsession.SessionWatcher(self._heard(self._screen_locked), self._heard(self._sleeping), seen=self._heard(self._seen),
                                                         parent=self)
        self._power_watcher = linuxsession.PowerProfile(self._heard(self._power_saving), parent=self)

    def _power_saving(self, on: bool) -> None:
        """The system's power saver: the stage draws less often, and the bubble and the box hold their still pictures."""
        self.stage.power_saving = on
        self.stage.bubble.set_power_saving(on)
        self.ask_box.set_power_saving(on)

    def _seen(self, on: bool) -> None:
        """Whether anything on screen can be seen (Windows: not while locked, or with the display off).
        Nothing is drawn while it can't, as Microsoft asks of apps; it all carries on when it can."""
        self.stage.set_drawing(on)
        self.ask_box.set_seen(on)

    @pyqtSlot(bool)
    def _screen_locked(self, locked: bool) -> None:
        now = time.time()
        if sys.platform != "win32":  # Windows says whether anything can be seen itself (_seen), display off included
            self.stage.set_drawing(not locked)  # nothing is drawn while nobody can see it
            self.ask_box.set_seen(not locked)
        if locked:
            self.breaks.away(now)
        else:
            self.breaks.back(now)
            self.behavior.wake(self._now())
            if not self._quitting and not self.stage.message_visible():
                self._hello()

    def _sleeping(self, going: bool) -> None:
        """The computer is going to sleep (True), or has woken (False): as good as stepping away."""
        self._screen_locked(going)
        if not going:
            self._last_wall = time.time()  # not a gap to be guessed at as well

    # -- heads-ups

    def _check_system(self) -> None:
        """The battery and the disks, read off the screen's thread (UPower over D-Bus, psutil and each disk can
        take a moment), one reading at a time."""
        if self._reading_system:
            return
        self._reading_system = True
        self.background.run(_read_system, self._system_read)

    def _system_read(self, reading) -> None:
        self._reading_system = False
        if isinstance(reading, Exception) or self._quitting:
            return
        battery, disks = reading
        notices = []
        low = self.watcher.battery(battery)
        if low:
            notices.append(low)
        notices += self.watcher.disks(disks, date.today())  # noqa: DTZ011 - once a local day
        for notice in notices:
            self.alert(notice.key, notice.title, notice.text)

    def _check_updates(self) -> None:
        if not self.config["heads_up"]["updates"]:
            return
        # Each reads what the system already knows (no network): the desktop's own updater keeps it fresh.
        checks = heads_up.update_checks()
        self._update_round += 1
        tag, self._update_expected = self._update_round, len(checks)
        self._update_counts = {}
        self._restart_needed = False
        for check in checks:
            if check.name == "packagekit":
                from . import packagekit

                counter = packagekit.UpdateCount(self)
                self._update_procs[counter] = check.name
                counter.counted.connect(partial(self._packagekit_counted, tag, counter))
                counter.start()
                continue
            proc = QProcess(self)
            self._update_procs[proc] = check.name
            proc.finished.connect(partial(self._updates_counted, tag, proc, check))
            proc.errorOccurred.connect(partial(self._update_check_failed, tag, proc, check))
            proc.start(check.argv[0], check.argv[1:])
        if checks:
            self._update_deadline.start(int(UPDATE_CHECK_TIMEOUT_S * 1000))

    def _update_check_failed(self, tag: int, proc: QProcess, check: heads_up.UpdateCheck, error) -> None:
        if sip.isdeleted(proc):
            return
        if error == QProcess.ProcessError.FailedToStart:
            self._forget_update_proc(proc)
            proc.deleteLater()
            self._tally_updates(tag, check.name, 0)

    def _packagekit_counted(self, tag: int, counter, count: int | None) -> None:
        self._forget_update_proc(counter)
        counter.deleteLater()
        self._tally_updates(tag, "packagekit", count or 0)

    def _forget_update_proc(self, proc) -> None:
        self._update_procs.pop(proc, None)

    def _update_checks_timed_out(self) -> None:
        """A check still running a minute on (a tool waiting on the network or a lock, say) is stopped, and counts as
        none, so the others are still heard."""
        late = list(self._update_procs.values())
        self._stop_update_checks()
        for name in late:
            self._tally_updates(self._update_round, name, 0)

    def _stop_update_checks(self) -> None:
        """The checks still running stop here, never to be heard from again (a QProcess destroyed while it runs says
        it finished, as it goes): at quitting, or when they took too long."""
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

    def _updates_counted(self, tag: int, proc: QProcess, check: heads_up.UpdateCheck, code: int, _status) -> None:
        if sip.isdeleted(proc):
            return
        self._forget_update_proc(proc)
        output = proc.readAllStandardOutput().data().decode("utf-8", errors="replace")
        proc.deleteLater()
        if check.name == "windows" and tag == self._update_round:
            self._restart_needed = heads_up.windows_restart_needed(output)
        self._tally_updates(tag, check.name, check.count(output, code) or 0)

    def _tally_updates(self, tag: int, name: str, count: int) -> None:
        if tag != self._update_round:
            return  # from an earlier look, answering late: this one's counts are its own
        self._update_counts[name] = count
        if len(self._update_counts) == self._update_expected:
            self._update_deadline.stop()
            notice = self.watcher.updates(sum(self._update_counts.values()), date.today(), self._restart_needed)  # noqa: DTZ011 - once a local day
            if notice:  # told once a day: it waits its turn behind a bubble on screen, rather than going unsaid
                self.behavior.react("wave", self._now())
                buttons: list[tuple[str, Callable[[], object] | None]] = [(_("OK"), None)]
                if sys.platform == "win32":
                    buttons.insert(0, (_("Open Windows Update"), partial(QDesktopServices.openUrl, QUrl("ms-settings:windowsupdate"))))
                self.say(notice.title, notice.text, buttons, timeout_s=60, key="system-updates", background=True)

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
        self.say(_("Looking for updates…"), timeout_s=10)
        self.state.set("update_checked", time.time())
        self.state.save()
        self.updater.check(self._install_kind, by_hand=True)

    def _update_available(self, release: updates.Release) -> None:
        by_hand, self._checking_by_hand = self._checking_by_hand, False
        self._install_kind = self.updater.kind
        self._menu_changed()
        self.behavior.react("wave", self._now())
        self.say(
            _("Chatmon {version} is ready").format(version=release.version),
            _("Downloaded and checked. Updating takes a moment, then I'll be right back."),
            [(_("Update now"), self._update_now), (_("What's new"), partial(self._show_release_notes, release)), (_("Later"), None)],
            timeout_s=90, key="chatmon-update", background=not by_hand,
        )

    def _update_out(self, release: updates.Release, how: str) -> None:
        by_hand, self._checking_by_hand = self._checking_by_hand, False
        self._install_kind = self.updater.kind
        first: tuple[str, Callable[[], object]] = (_("Release page"), partial(QDesktopServices.openUrl, QUrl(release.page)))
        if self.updater.metered:  # not downloaded only because the connection is metered: asking downloads it
            first = (_("Download it"), self.check_for_updates)
        self.say(_("Chatmon {version} is out").format(version=release.version), how,
                 [first, (_("What's new"), partial(self._show_release_notes, release)), (_("OK"), None)], timeout_s=60,
                 key="chatmon-update", background=not by_hand)

    def _up_to_date(self) -> None:
        self._install_kind = self.updater.kind
        if self._checking_by_hand:
            self._checking_by_hand = False
            self.say(_("You're up to date"), _("This is the newest Chatmon, {version}.").format(version=__version__), timeout_s=6)

    def _update_failed(self, why: str) -> None:
        logger.warning("%s", why)
        if self._checking_by_hand or self.updater.ready is not None or self.updater.failure == updates.INSTALL_FAILED:
            self._checking_by_hand = False
            self.say(_("No update this time"), why, [(_("OK"), None)], timeout_s=30)

    def _update_now(self) -> None:
        self.save()
        self.say(_("Updating…"), _("The installer may ask for your password. I'll be back in a moment."), timeout_s=None)
        self.updater.install()

    def _show_release_notes(self, release: updates.Release) -> None:
        self.ask_box.show_notes(self.stage.head_point(), _("What's new in Chatmon {version}").format(version=release.version),
                                release.notes or _("No notes for this release."))

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
        title = (_("Updated to Chatmon {version}") if updated else _("What's new in Chatmon {version}")).format(version=__version__)
        body = changelog.notes(releases) if releases else _("No notes for this version.")  # the notes themselves are English
        # Translators: under the release notes; keep the Markdown links' brackets and parentheses as they are.
        links = _("Found a problem? [Report it]({report}) · [All changes]({changes})")
        body += "\n\n" + links.format(report=self._report_url(), changes=f"https://github.com/{updates.REPO}/releases")
        self.ask_box.show_notes(self.stage.head_point(), title, body)

    def _report_url(self, template: str = report.BUG) -> str:
        brain = self._brain(wait=False)
        # A built-in brain by its name; one of your own only as that (its name could be a server of yours).
        label = (brain.label if brain.name in brains.PRESETS else "A brain of my own") if brain else ""
        return report.url(template, install=self._install_kind or "", brain=label)

    def report_problem(self, template: str = report.BUG) -> None:
        QDesktopServices.openUrl(QUrl(self._report_url(template)))

    def open_log(self) -> None:
        log = applog.log_file()
        if log.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(log)))
        else:
            self.say(_("No log yet"), _("I keep one in my state folder, and couldn't write it there."), timeout_s=8)

    def _problem(self) -> None:
        """Something in Chatmon failed (it's in the log): offer to report it, once a run."""
        if self._problem_told:
            return
        self._problem_told = True
        buttons: list[tuple[str, Callable[[], object] | None]] = [(_("Report it"), self.report_problem)]
        if applog.log_file().exists():
            buttons.append((_("Open the log"), self.open_log))
        self.say(_("Something went wrong in me"), _("I kept going, but you can tell my maker what happened."), [*buttons, (_("OK"), None)], timeout_s=45, background=True)

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
            if sock is None:  # never, while one is pending
                break
            if len(self._connections) >= MAX_CONNECTIONS:  # a flood (only you can connect, but a script can loop)
                sock.abort()
                sock.deleteLater()
                continue
            if sys.platform == "win32" and not _client_is_me(sock):  # the pipe's access list keeps others out; this checks again
                sock.abort()
                sock.deleteLater()
                continue
            sock.setReadBufferSize(events.MAX_MESSAGE + 1)  # Qt holds no more than a message for it, and a byte to tell
            self._connections[sock] = bytearray()
            sock.readyRead.connect(self._read_connections, type=queued)  # type: ignore[call-arg]  # PyQt6 6.11's stub leaves out connect's type, which it takes
            sock.disconnected.connect(self._read_connections, type=queued)  # type: ignore[call-arg]  # as above
        self._later(0, self._read_connections)  # anything already in

    def _read_connections(self) -> None:
        """Handle each complete line as it arrives and answer it, so the sender can hang up knowing it got here:
        every connection still open, in the order they came. Qt says data has arrived on each connection
        separately, in no particular order, so a sender that hung up before its answer (half a second, on a
        busy computer) could otherwise be heard after the one that came next: an agent's "done" before its
        "working", leaving it shown as working. So each pass first takes in what the system already holds for
        every earlier connection (waitForReadyRead(0) doesn't wait): whatever was sent before a later sender
        connected is heard before that sender is."""
        connected = QLocalSocket.LocalSocketState.ConnectedState
        for sock, buffer in list(self._connections.items()):
            if sip.isdeleted(sock):  # deleted by Qt along with its server
                self._connections.pop(sock, None)
                continue
            if sock.state() == connected:
                sock.waitForReadyRead(0)
            while True:
                if sock.bytesAvailable():  # (reading a socket Qt has closed only gets a warning)
                    # Never more than a message held for one connection: one longer is never going to be heard.
                    buffer.extend(bytes(sock.read(events.MAX_MESSAGE + 1 - len(buffer))))
                if len(buffer) > events.MAX_MESSAGE:
                    buffer.clear()
                    sock.abort()
                more = sock.bytesAvailable() > 0
                closed = sock.state() != connected and not more  # the sender hung up, and all it sent is in
                while b"\n" in buffer or (closed and buffer):
                    line, _, rest = bytes(buffer).partition(b"\n")
                    buffer[:] = rest
                    for message in events.parse_lines(line):
                        reply = self.handle(message)
                        if reply is not None and not closed and sock.state() == connected:
                            sock.write(events.reply_line(reply))  # before the ok: events.request reads it
                    if not closed and sock.state() == connected:
                        sock.write(events.ACK)
                        sock.flush()
                if not more:
                    break
            if closed:
                self._connections.pop(sock, None)
                sock.deleteLater()

    def _close_connections(self) -> None:
        """No more messages: the server closed, and each connection still open aborted and deleted now (its
        event loop may not run again). Left to outlive the Companion, a connection's socket notifier outlives
        its descriptor too: on macOS, Qt's (one CFSocket per descriptor number) then takes the next connection
        given that number, and its message is read and dropped there. Only another Companion in the same
        process could be given it: the tests make one after another."""
        self.server.close()
        for sock in self._connections:
            if not sip.isdeleted(sock):
                sock.abort()
                sip.delete(sock)
        self._connections.clear()

    def handle(self, message: dict) -> dict | None:
        """Do what a hook or a script says. Returns the answer to send back, for a message that asks for one (status)."""
        message = events.clean(message)
        kind = message.get("type")
        now = self._now()
        if kind == "event" and message.get("event") in events.EVENTS:
            self._agent_event(message["event"], str(message.get("source") or "agent"), str(message.get("message") or ""))
        elif kind == "say" and message.get("text"):
            self.behavior.wake(now)
            self.behavior.react("talk", now)
            self.say(self.name, str(message["text"]), timeout_s=15, background=True)
        elif kind == "remind":
            command = reminders.parse_command("remind me " + str(message.get("text", "")), datetime.now())  # noqa: DTZ005 - local wall time
            if command and command.kind == "reminder" and command.due is not None:
                r = self.reminders.add(command.due.timestamp(), command.text, repeat=command.repeat)
                self.save()
                self.say(_("Reminder set"), _reminder_said(r, repeat=True), timeout_s=6)
            elif command and command.kind == "unclear":  # chatmon remind says so itself; a script's own message is told here
                self.say(_("Reminder not set"), reminders.explain(command), timeout_s=15, background=True)
        elif kind == "status":  # chatmon status: how the agents stand, as only the running Chatmon knows
            return {"type": "status", "pid": os.getpid(), "version": __version__, "agents": self.agents_report(markdown=False) if self.agents else ""}
        elif kind == "ask":  # `chatmon ask [TEXT]`: a hotkey, a launcher, a script
            self.open_ask(str(message.get("text") or ""))
        elif kind == "show":
            self.set_hidden(False)
            self.behavior.poke(now)
        elif kind == "quit":  # `chatmon quit`: an installer updating it, say
            self._later(0, self.quit)  # once the sender has heard back
        return None

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
            self.messages.withdraw(key)  # a needs-you still waiting no longer stands
            if self._alert_key == key:
                self.stage.dismiss_message()
        elif event == "needs-you":
            self.agents[source] = ("needs-you", now)
            self.alert(key, _("{agent} needs you").format(agent=label), text or _("{agent} is waiting for you.").format(agent=label))
        else:
            self.agents.pop(source, None)
            self.messages.withdraw(key)
            if self._alert_key == key:
                self.stage.dismiss_message()
            # An agent's reply can hold code or secrets: on screen only if you said so.
            show = bool(self.config["agents"]["show_replies"])
            snippet = (text if len(text) <= 220 else text[:217].rstrip() + "…") if show else ""
            if event == "done":
                self.behavior.react("hop", now)
                if not self.ask_box.isVisible():
                    self.say(_("{agent} finished").format(agent=label), snippet, timeout_s=8, key=key, background=True, cue="done")
            elif event == "success":
                self.behavior.react("beam", now)
                self.say(_("{agent}: success!").format(agent=label), snippet, timeout_s=8, key=key, background=True, cue="success")
            elif event == "error":
                self.say(_("{agent} hit a problem").format(agent=label), snippet or _("Take a look when you can."), timeout_s=20, key=key, background=True,
                         cue="error")
        self._update_working()

    def _update_working(self) -> None:
        working = any(state == "working" for state, _ in self.agents.values())
        self.behavior.set_working(working, self._now())
        self._show_agent_states()

    def agents_report(self, markdown: bool = True) -> str:
        """How each AI agent stands (needs you, working) and for how long: the *agents* command, and status."""
        return offline.agents_report(self.agents, self._now(), pretty, markdown=markdown)

    def _waiting_agents(self) -> list[str]:
        return [pretty(source) for source, (state, _) in self.agents.items() if state == "needs-you"]

    def _show_agent_states(self) -> None:
        """The agents' states where they can be seen at a glance: the tray's tooltip, the stage window's name (what a
        screen reader says of it), and a dot on the tray icon while one needs you."""
        if self._quitting:
            return
        states = offline.agents_report(self.agents, self._now(), pretty, markdown=False) if self.agents else ""
        # Translators: the tray icon's tooltip while agents are working or waiting, one per line under it.
        self.tray.setToolTip(_("Chatmon\n{states}").format(states=states) if states else "Chatmon")
        name = getattr(self.stage.surface, "setAccessibleName", None)
        if name is not None:
            # Translators: what a screen reader calls the companion while agents are working: "Penguin: Claude is working (5 min so far)".
            name(_("{name}: {states}").format(name=self.name, states="; ".join(states.splitlines())) if states else self.name)
        waiting = len(self._waiting_agents())
        self.stage.set_badge(sum(1 for state, _ in self.agents.values() if state == "working"), waiting)
        if bool(waiting) != self._tray_badge:
            self._tray_badge = bool(waiting)
            self.tray.setIcon(self._tray_icon())

    # -- menus (menus.py)

    def show_menu(self, pos: QPoint) -> None:
        """The penguin's own menu (right-click): it stands still and looks at you while it's open."""
        self._menu_open = True
        self.behavior.set_attending(True, self._now())
        # On the overlay the penguin's menu is always the stage's own: with the ask box a window for a screen reader,
        # the overlay draws no menus for it, but a Qt menu opened from the overlay has no window of Qt's to belong to.
        if self.stage.draws_menus() or self._overlay:
            self.menus.opening()  # the stage draws it: no aboutToShow
            self.stage.open_menu(self.menu, pos)
        else:
            self.menu.popup(pos)

    def _menu_closed(self) -> None:
        if self._menu_open and not self.stage.menu.is_open():
            self._menu_open = False
            self.behavior.set_attending(self.ask_box.isVisible(), self._now())
        self.menus.closed()

    def _tray_clicked(self, reason) -> None:
        # On macOS opening the menu-bar menu is a Trigger too (Qt says so as the menu starts): there the menu's
        # own Hide / Come out does it.
        if reason == QSystemTrayIcon.ActivationReason.Trigger and sys.platform != "darwin":
            self.set_hidden(not self.behavior.hidden)

    def _menu_changed(self) -> None:
        """Something the menu shows changed: it's filled in again once things settle (menus.py), and so is the Chats
        window, if it's open."""
        self.menus.changed()
        window = self._chats_window
        if window is not None and not sip.isdeleted(window) and window.isVisible():
            window.refresh(self.chat.id, self._keeps_chats())

    def _offline_in_box(self, words: str) -> None:
        """Do something from the menu as if it were asked in the box, and show it there."""
        self.open_ask()
        self._local(words)

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
        meanwhile, it looks once more when this one is done. Never once quit, whoever asks: in a process that goes
        on (the tests'), a look then ran the agents' own command lines after the test's stand-ins were undone."""
        if self._quitting:
            return
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
                    logger.warning("%s", done)
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
                    _("I'm Chatmon now. If {agents} was connected before, tick it again under **AI agents** in my menu.").format(agents=either(unsure)),
                    timeout_s=30, background=True,
                )
        if isinstance(status, dict) and status != self._agent_status:
            self._agent_status = status
            self._menu_changed()
        if isinstance(status, dict):
            self._offer_agents()

    OFFER_AGAIN_MS = 30_000  # something's on screen: offer again this much later

    def _offer_agents(self) -> None:
        """What's new about the agents here, said with a button that does something about it: agents found that
        Chatmon hasn't asked about yet, offered together (connected, they tell your chatmon what they're doing),
        and an agent that was connected and has since been switched off, as Claude Code does to the plugin when a
        window open from before it was connected saves its settings. An answer is kept (state's "agent_status"
        holds what was last seen of each), so nothing answered is asked again; a bubble that went unanswered
        (you were away, or closed it) is asked again the next time Chatmon starts, never twice in one run.
        Waits while something is on screen, and never while the agents can't reach Chatmon anyway."""
        status = self._agent_status
        if not status or self.server_problem:
            return
        before = dict(self.state.get("agent_status") or {})
        new = [a for a in agents.AGENTS if status.get(a.name) == "found" and a.name not in before]
        off = [a for a in agents.AGENTS if status.get(a.name) == "installed but off" and before.get(a.name) == "connected"]
        unanswered = {a.name for a in new + off}  # kept out of what's seen until there's an answer
        seen = {**before, **{name: state for name, state in status.items() if state != "not found" and name not in unanswered}}
        if seen != before:
            self.state.set("agent_status", seen)
            self.state.save()
        new = [a for a in new if a.name not in self._offered]
        off = [a for a in off if a.name not in self._offered]
        busy = self._asking_name or self._alert_key is not None or self._menu_open or self.ask_box.isVisible() or self.stage.message_visible()
        # One bubble at a time, switched off first: whatever else is waiting is said on a later look.
        shown = [] if busy else (off or new)
        self._offered |= {a.name for a in shown}
        if {a.name for a in new + off} - self._offered and not self._offer_due:
            self._offer_due = True
            self._later(self.OFFER_AGAIN_MS, self._offer_agents_again)
        if not shown:
            return
        answered = {a.name: status[a.name] for a in shown}
        if off:
            title = _("{agent} switched me off").format(agent=off[0].label) if len(off) == 1 else _("An agent switched me off")
            self.say(
                title,
                _("My plugin in {agents} is off now. A window that was open when you connected it "
                  "may have saved its settings over mine. Switch it back on?").format(agents=join([a.label for a in off])),
                [(_("Switch on"), partial(self._offer_answered, answered, off)), (_("Leave it off"), partial(self._offer_answered, answered, []))],
                timeout_s=60, key="offer-agents", background=True,
            )
        else:
            self.say(
                _("Shall I watch your coding agents?"),
                ngettext("I found {agents} here. Connect it, and I'll show you when it is working, when it needs you, and when it is done. "
                         "You can change this any time under **AI agents** in my menu.",
                         "I found {agents} here. Connect them, and I'll show you when they are working, when they need you, and when they are done. "
                         "You can change this any time under **AI agents** in my menu.",
                         len(new)).format(agents=join([f"**{a.label}**" for a in new])),
                [(_("Connect"), partial(self._offer_answered, answered, new)), (_("Not now"), partial(self._offer_answered, answered, []))],
                timeout_s=60, key="offer-agents", background=True,
            )

    def _offer_answered(self, answered: dict[str, str], chosen: list[agents.Agent]) -> None:
        """An offer was answered: keep that it was (so it isn't asked again), and connect what was chosen."""
        self.state.set("agent_status", {**(self.state.get("agent_status") or {}), **answered})
        self.state.save()
        if chosen:
            self._connect_agents(chosen)

    def _offer_agents_again(self) -> None:
        self._offer_due = False
        self._offer_agents()

    def _connect_agents(self, chosen: list[agents.Agent]) -> None:
        self.say(_("Connecting {agents}…").format(agents=join([a.label for a in chosen])), timeout_s=30)

        def connect_each() -> list:
            results: list[tuple[agents.Agent, str | Exception]] = []
            for agent in chosen:
                try:
                    results.append((agent, agent.connect()))
                except (agents.AgentError, OSError) as exc:
                    results.append((agent, exc))
            return results

        self.background.run(connect_each, self._agents_connected)

    def _agents_connected(self, results) -> None:
        if isinstance(results, Exception):  # not one agent's trouble, which each reports itself: something of ours
            self.say(_("Couldn't connect your agents"), str(results), [(_("OK"), None)], timeout_s=None)
            self._refresh_agents()
            return
        done = [a.label for a, result in results if not isinstance(result, Exception)]
        failed = [(a.label, result) for a, result in results if isinstance(result, Exception)]
        if failed:
            text = "\n\n".join(f"**{label}:** {exc}" for label, exc in failed)
            if done:
                text = ngettext("{agents} is connected.", "{agents} are connected.", len(done)).format(agents=join(done)) + "\n\n" + text
            self.say(_("Couldn't connect {agents}").format(agents=join([label for label, _exc in failed])), text, [(_("OK"), None)], timeout_s=None)
        elif done:
            self.behavior.react("hop", self._now())
            self.say(
                _("Connected {agents}").format(agents=join(done)),
                _("I'll show you what each is doing from its next session on: one that's open now has to be started again first."),
                timeout_s=15,
            )
        self._refresh_agents()

    def _set_agent(self, agent: agents.Agent, on: bool) -> None:
        self.say((_("Connecting {agents}…") if on else _("Disconnecting {agent}…")).format(agents=agent.label, agent=agent.label), timeout_s=20)
        self.background.run(agent.connect if on else agent.disconnect, partial(self._agent_set, agent))

    def _agent_set(self, agent: agents.Agent, result) -> None:
        if isinstance(result, Exception):
            self.say(_("Couldn't change {agent}").format(agent=agent.label), str(result), [(_("OK"), None)], timeout_s=None)
        else:
            self.behavior.react("hop", self._now())
            self.say(agent.label, str(result), timeout_s=12)
        self._refresh_agents()

    def _quick_action(self, name: str) -> None:
        """Explain, Summarize, Translate or Fix: what's on the clipboard is attached now (you chose this; Chatmon never
        reads the clipboard otherwise), and the box opens with the prompt typed in, for you to send or change."""
        prompt = _(QUICK_ACTIONS[name]).format(language=QLocale.languageToString(QLocale().language()))
        self.open_ask(prompt)
        surface = self.stage.surface
        if self.stage.hosted is not None and hasattr(surface, "paste_rich"):  # the overlay: its own clipboard
            surface.paste_rich(lambda mime, data: self._attach_clipboard(overlay_contents(mime, data)))
        else:
            board = QGuiApplication.clipboard()
            self._attach_clipboard(clipboard_contents(board.mimeData()) if board is not None else None)

    def _attach_clipboard(self, found) -> None:
        if found is None:
            self.ask_box.set_answer(_("*The clipboard is empty: copy something first.*"))
            return
        kind, payload = found
        if kind == "text":
            self._attach(lambda: attachments.from_text(payload))  # attached, however short: it's what the prompt is about
        else:
            self._attach_pasted(kind, payload)

    def _register_hotkey(self) -> None:
        """The hotkey from Settings opens the ask box from anywhere (hotkey.py): registered at start and whenever it
        changes, taken back when it's emptied. A problem with it is said once for that hotkey."""
        sequence = str(self.config.get("hotkey") or "").strip()
        if sequence == self._hotkey:
            return
        from . import hotkey

        if not sequence:
            hotkey.unregister()
            self._hotkey = ""
            self._hotkey_bound(None)
            return
        error = hotkey.register(sequence, self._hotkey_pressed, failed=self._hotkey_failed, bound=self._hotkey_bound)  # quit unregisters it
        if error:
            self._hotkey_failed(error)
        else:
            self._hotkey = sequence

    def _hotkey_pressed(self) -> None:
        """The hotkey: the ask box, as a click on the chatmon opens it (and closes it, pressed again)."""
        if self.ask_box.isVisible():
            self.ask_box.dismiss()
        else:
            self.open_ask()

    def _hotkey_bound(self, description: str | None) -> None:
        """How the desktop has the hotkey, in its own words (on Wayland the desktop has the last word on the keys):
        shown in Settings › Accessibility, beside the keys you picked."""
        self._hotkey_said = description
        window = self._settings_window
        if window is not None and not sip.isdeleted(window):
            window.show_hotkey_bound(description)

    def _hotkey_failed(self, why: str) -> None:
        sequence = str(self.config.get("hotkey") or "")
        if self.state.get("hotkey_told") != sequence:  # said once for this hotkey, not at every start
            self.state.set("hotkey_told", sequence)
            self.state.save()
            self.say(_("The hotkey to ask didn't work"), _("{problem}\n\nSettings › Accessibility picks another.").format(problem=why), timeout_s=20, background=True)

    def _other_agents(self) -> None:
        self.open_ask()
        self.ask_box.set_answer(_("Any agent or script can tell me what it's doing:") + "\n\n```\n" + agents.generic() + "\n```")

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

    def _start_preload(self) -> None:
        self._preload.start()

    def _preload_next(self) -> None:
        if not self.sprites.load_next():
            self._preload.stop()

    def _tray_icon(self) -> QIcon:
        """The companion standing idle, with a dot while an agent needs you. In macOS's menu bar, its silhouette as a
        template image, which the menu bar draws in its own colour (light or dark, as the menu bar is), as Apple's
        guidance asks; the dot is cut out of it there, as the menu bar draws one colour."""
        frame = self.sprites.frame("idle", 0, False)
        if sys.platform != "darwin":
            return QIcon(_with_badge(frame.pixmap) if self._tray_badge else frame.pixmap)
        icon = QIcon(_with_badge(silhouette(frame)) if self._tray_badge else silhouette(frame))
        icon.setIsMask(True)
        return icon

    def _show_icon(self) -> None:
        self.tray.setIcon(self._tray_icon())
        self.app.setWindowIcon(QIcon(self.sprites.frame("idle", 0, False).pixmap))

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
            self.say(self.name, _("New look: {style}.").format(style=menus.style_word(self._bubble_style().name)), timeout_s=4)

    def _set_bubble_effects(self, on: bool) -> None:
        self.state.set("bubble_effects", on)
        self.state.save()
        self._apply_bubble_style()

    def _pick_brain(self, name: str | None) -> None:
        self.state.set("brain", name)
        self.state.save()
        self._fallback_told = None  # a new pick: its stand-in, if it needs one, is said again
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
        """The settings file, with what you set in Settings (or the menu) laid over it, every setting checked: and a
        sentence naming what was wrong, setting by setting (the rest apply), or why the file couldn't be read at all
        (then the defaults are used, with Settings' own laid over them; `_config_unreadable` says which)."""
        config, problems, unreadable = read_config()
        overrides = self.state.get("settings")
        if isinstance(overrides, dict):
            config, more = coerce(merge(config, overrides))
            problems += [p for p in more if p not in problems]
        brains.load_brains(config["ai"], problems)  # what's wrong in your own brains' settings, said too
        self._config_unreadable = unreadable is not None
        if unreadable:
            return config, unreadable
        return config, ("config.toml: " + "; ".join(problems) + ".") if problems else None

    def _say_config_problem(self) -> None:
        if self._config_unreadable:
            self.say(_("I couldn't read my settings"), _("`{problem}`\n\nUsing the defaults for now.").format(problem=self.config_error), timeout_s=30)
        else:
            self.say(_("Some of my settings were wrong"), _("`{problem}`\n\nEverything else applies.").format(problem=self.config_error), timeout_s=30)

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

    SETTINGS_PATHS: ClassVar[dict[str, tuple[str, ...]]] = {  # the window's name for a setting: where it lives in the settings
        "size": ("size",), "walk": ("walk",), "sleep_after_minutes": ("sleep_after_minutes",),
        "timeout_seconds": ("ai", "timeout_seconds"), "show_replies": ("agents", "show_replies"),
        "break_reminders": ("breaks", "remind"), "breaks_every": ("breaks", "every_minutes"), "snooze": ("breaks", "snooze_minutes"),
        "focus": ("focus", "minutes"), "focus_done": ("focus", "tell_when_done"),
        "battery_low": ("heads_up", "battery_low"), "battery_critical": ("heads_up", "battery_critical"),
        "disk_full": ("heads_up", "disk_full_percent"), "updates_heads_up": ("heads_up", "updates"),
        "updates_every_hours": ("heads_up", "updates_every_hours"), "read_aloud": ("accessibility", "read_aloud"),
        "reminder_snooze": ("reminders", "snooze_minutes"), "text_scale": ("accessibility", "text_scale"),
        "bubble_time": ("accessibility", "bubble_time"), "reduced_motion": ("accessibility", "reduced_motion"),
        "accessible_ask_box": ("accessibility", "accessible_ask_box"), "sound": ("sound", "enabled"), "volume": ("sound", "volume"),
        "cues": ("sound", "cues"), "hotkey": ("hotkey",), "follow_screen": ("follow_screen",),
        "magnifier_follows": ("accessibility", "magnifier_follows"), "speech_fallback": ("accessibility", "speech_fallback"),
        "language": (i18n.SETTING,),
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
            "read_aloud": bool(c["accessibility"]["read_aloud"]),
            "reminder_snooze": int(c["reminders"]["snooze_minutes"]),
            "text_scale": int(c["accessibility"]["text_scale"]), "bubble_time": str(c["accessibility"]["bubble_time"]),
            "reduced_motion": str(c["accessibility"]["reduced_motion"]), "accessible_ask_box": str(c["accessibility"]["accessible_ask_box"]),
            "sound": bool(c["sound"]["enabled"]), "volume": int(c["sound"]["volume"]), "cues": dict(c["sound"]["cues"]),
            "hotkey": str(c["hotkey"]), "follow_screen": bool(c["follow_screen"]), "api_key": None,
            "magnifier_follows": bool(c["accessibility"]["magnifier_follows"]),
            "speech_fallback": bool(c["accessibility"]["speech_fallback"]),
            "language": str(c.get(i18n.SETTING) or ""),
        }
        current = self._brain(wait=False)
        matching = menus.style_word(styles.get(self._companion().bubble_style).name)
        if current and not self.state.get("brain"):
            automatic = _("Automatic ({brain})").format(brain=current.label)
        else:
            automatic = _("Automatic (the first one found)")
        choices = {
            "companions": [(x.id, x.label) for x in companions.COMPANIONS.values() if companions.get(x.id) is x],
            "bubble_styles": [(MATCH, _("Match companion ({style})").format(style=matching))] + [(x.name, x.label) for x in styles.STYLES.values()],
            "brains": [("", automatic)]
            # Translators: a brain that can't answer now, and why: "Ollama (not running)".
            + [(b.name, b.label if b.available(wait=False) else _("{brain} ({reason})").format(brain=b.label, reason=b.why_not())) for b in self.brains.values()],
            # An API brain's key: whether one is saved in the keychain, else where it would come from (never the key).
            "keys": {b.name: _key_status(b) for b in self.brains.values() if b.type != "command" and not b.local and b.api_key_env},
            "key_store": keychain.where(),
            "languages": i18n.available(),
        }
        return values, choices

    def open_settings(self, tab: str | None = None) -> None:
        """The Settings window (`tab`: "ai", "accessibility"...: opened at it)."""
        from .settingswin import SettingsWindow

        window = self._settings_window
        if window is None or sip.isdeleted(window):
            values, choices = self._settings_values()
            window = SettingsWindow(values, choices)
            window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            window.setWindowIcon(self.tray.icon())
            window.saved.connect(self._apply_settings)
            window.open_file.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.config_file()))))
            window.test_requested.connect(self._test_brain)
            window.remove_key.connect(self._remove_key)
            window.backup_requested.connect(self._back_up)
            window.restore_requested.connect(self._bring_back)
            window.finished.connect(self._settings_closed)
            window.show_hotkey_bound(self._hotkey_said)
            self._settings_window = window
        if tab:
            window.show_tab(tab)
        window.show()
        window.raise_()
        window.activateWindow()

    def _settings_closed(self, _result: int) -> None:
        if self._brain_test is not None:
            self._brain_test.cancel()  # nothing more for a window that's gone
            self._brain_test = None

    def _test_brain(self, name: str, typed_key: str) -> None:
        """Settings' Test: the brain picked there (Automatic: whichever it would pick now) is asked "Say OK", with the
        key typed there if there is one (not saved by this), and the window shows how long it took, or the error."""
        window = self._settings_window
        if window is None or sip.isdeleted(window):  # never: its own button asks
            return
        brain = self._with_options(self.brains.get(name)) if name else self._brain(wait=False)
        if brain is None:
            window.show_test(False, _("There's no brain to test yet: pick one above."), 0.0)
            return
        if typed_key:
            brain = dataclasses.replace(brain, api_key=typed_key)
        if self._brain_test is not None:
            self._brain_test.cancel()
        self._brain_test = brain.test(self, timeout_s=float(self.config["ai"]["timeout_seconds"]))
        self._brain_test.finished.connect(lambda ok, text, seconds: self._tested(brain.label, ok, text, seconds))

    def _tested(self, label: str, ok: bool, text: str, seconds: float) -> None:
        self._brain_test = None
        window = self._settings_window
        if window is not None and not sip.isdeleted(window):
            window.show_test(ok, _("{brain} answered in {seconds} s.").format(brain=label, seconds=f"{seconds:.1f}") if ok else text, seconds)

    def _remove_key(self, name: str) -> None:
        """The key saved for brain `name` in the keychain, taken out (Settings' Remove key)."""
        problem = keychain.delete(name)
        window = self._settings_window
        if window is not None and not sip.isdeleted(window):
            # Translators: {store} is where keys are kept, as keychain names it: "Windows Credential Manager", "your desktop's keyring".
            said = problem or _("Removed from {store}.").format(store=keychain.where())
            window.show_key_status(name, said, _key_status(self.brains[name]) if name in self.brains else None)
        self._menu_changed()

    def _back_up(self, with_chats: bool) -> None:
        """Settings' Back up: where to, then the zip (backup.py)."""
        name, _kind = QFileDialog.getSaveFileName(self._settings_window, _("Back up Chatmon"), str(Path.home() / backup.default_name()), _("Chatmon backup (*.zip)"))
        if name:
            self._back_up_to(Path(name), with_chats)

    def _back_up_to(self, path: Path, with_chats: bool) -> None:
        self.save()
        try:
            contents = backup.export(path, self.state, self.memory, self.chat_book if with_chats else None)
        except OSError as exc:
            self.say(_("Couldn't back up"), str(exc), timeout_s=15)
            return
        self.say(_("Backed up"), _("`{file}` has {what}. Keys are never in a backup.").format(file=path.name, what=contents.summary()), timeout_s=12)

    def _bring_back(self) -> None:
        """Settings' Bring back: which backup, then what's in it, to confirm."""
        name, _kind = QFileDialog.getOpenFileName(self._settings_window, _("Bring back a Chatmon backup"), str(Path.home()), _("Chatmon backup (*.zip)"))
        if name:
            self._offer_restore(Path(name))

    def _offer_restore(self, path: Path) -> None:
        try:
            contents = backup.read(path)  # checked first: nothing changes if any of it isn't right
        except backup.BackupError as exc:
            self.say(_("That backup can't be used"), str(exc), timeout_s=20)
            return
        self.say(
            _("Bring this backup back?"),
            _("It has {what}. Your settings, memory, notes and reminders become its; its chats join yours.").format(what=contents.summary()),
            [(_("Bring it back"), partial(self._restore, contents)), (_("Not now"), None)], timeout_s=None,
        )

    def _restore(self, contents) -> None:
        """A checked backup, put in place, and everything read again from it."""
        said = backup.bring_back(contents, self.state, self.memory, self.chat_book)
        self.reminders = reminders.ReminderBook.from_list(self.state.get("reminders", []))
        self._sync_focus_hold()
        self.reload(quietly=True)
        window = self._settings_window
        if window is not None and not sip.isdeleted(window):
            window.close()  # it shows what was set before
        self.say(_("Backup brought back"), said, timeout_s=15)

    # -- Chats: a window of them all, with search (chatswin.py)

    def open_chats(self) -> None:
        from .chatswin import ChatsWindow

        window = self._chats_window
        if window is None or sip.isdeleted(window):
            window = ChatsWindow(self.chat_book)
            window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            window.setWindowIcon(self.tray.icon())
            window.carry_on.connect(self._resume_chat)
            window.rename.connect(self._ask_new_name)
            window.instructions.connect(self._ask_chat_instructions)
            window.pin.connect(self._pin_chat)
            window.export.connect(self._export_chat)
            window.delete.connect(self._ask_to_delete_chat)
            self._chats_window = window
        window.refresh(self.chat.id, self._keeps_chats())
        window.show()
        window.raise_()
        window.activateWindow()

    def _ask_other(self, name: str) -> None:
        """Ask another brain: the chat's last question again, of brain `name`, with the chat before it (as that brain
        may see it). What was attached goes only by name. Its answer is kept as its own, and the chat goes on with it."""
        other = self._with_options(self.brains.get(name))
        found = self.chat.last_question()
        if other is None or found is None:
            return
        index, asked = found
        if not self.ask_box.isVisible():
            self.open_ask()
        if self.questions.full():
            self._show_chat(_("*One question is waiting already. Ask again once that one goes, or press Stop.*"))
            return
        question = asking.Question(self.chat.id, asked.text, [], other, before=index)
        if self.questions.ask(question):
            self.behavior.set_thinking(True, self._now())
            self._send(question)
        self._show_chat()

    def _apply_settings(self, changed: dict) -> None:
        """What you set in Settings: each with the menu's own setter where there is one, the rest kept over
        the settings file and taken up at once."""
        if not changed:
            return
        self._keep_settings(changed)
        if "companion" in changed:
            self._pick_companion(changed["companion"])
        if "check_updates" in changed:
            self._set_check_updates(changed["check_updates"])
        if changed.get("api_key"):  # (brain, key): into the keychain, never into state or the settings file
            self._save_key(*changed["api_key"])
        if "autostart" in changed:
            autostart.set_enabled(changed["autostart"])
        for key, path in self.SETTINGS_PATHS.items():
            if key in changed:
                self._override(path, changed[key])
        if "walk" in changed:
            self._walk_picked = True
        self.state.save()
        self.reload(quietly=True)

    def _keep_settings(self, changed: dict) -> None:
        """The settings from Settings that are kept as the menu keeps them, in state (and your memory, in its own
        file), rather than over the settings file."""
        if "name" in changed:
            self.state.set("name", changed["name"][:40] or None)
        for key in ("bubble_style", "bubble_effects", "instructions"):
            if key in changed:
                self.state.set(key, changed[key])
        if "brain" in changed:
            self.state.set("brain", changed["brain"] or None)
            self._fallback_told = None
        if "keep_chats" in changed:
            self.state.set("keep_chats", changed["keep_chats"])
            if not changed["keep_chats"]:
                self.chat.keep = False
        if "context_tokens" in changed:
            self.state.set("context_tokens", int(changed["context_tokens"]))
        if "memory" in changed:
            self.memory.items = [memory.Item(t, time.time()) for t in changed["memory"]][: memory.MAX_ITEMS]
            self.memory.save()

    def _save_key(self, name: str, key: str) -> None:
        """Settings' new key for brain `name`: into the keychain, never into state or the settings file, and said."""
        problem = keychain.set(name, key)
        label = self.brains[name].label if name in self.brains else name
        self.say(_("{brain}'s key").format(brain=label), problem or _("Saved in {store}.").format(store=keychain.where()), timeout_s=10)

    def reload(self, quietly: bool = False) -> None:
        self.config, self.config_error = self._load_config()
        if self.config_error:
            self._say_config_problem()
            if self._config_unreadable:
                return
        self.brains = brains.load_brains(self.config["ai"])
        self._fallback_told = None
        self._updates_timer.setInterval(max(1000, int(self.config["heads_up"]["updates_every_hours"] * 3600_000)))  # no restart needed
        self._reduce_motion = self._reduced_motion()
        self._apply_accessibility()
        self._register_hotkey()
        self.watcher = self._make_watcher()
        self.breaks.every = float(self.config["breaks"]["every_minutes"]) * 60
        self._show_sprites()
        self._show_icon()
        self.behavior.set_walk(self._walks(), self._now())  # reduced motion still counts after a reload
        self.behavior.sleep_after = float(self.config["sleep_after_minutes"]) * 60
        self.behavior.speed = int(self.config["size"]) * 0.4
        self._apply_bubble_style()
        self._menu_changed()
        if not quietly and not self.config_error:
            self.say(_("Settings reloaded"), timeout_s=3)

    def _set_sprite_scale(self, scale: float) -> None:
        """The stage's screen has this many device pixels to a pixel: draw the penguin with them."""
        if abs(scale - self._sprite_scale) > 0.01:
            self._sprite_scale = scale
            self._show_sprites()

    def quit(self) -> None:
        self._quitting = True
        scheme = getattr(self.app.styleHints(), "colorSchemeChanged", None)  # Qt 6.5 and later
        try:
            if scheme is not None:
                scheme.disconnect(self._scheme_changed)
        except TypeError:  # never connected
            pass
        if self._hotkey:
            from . import hotkey

            hotkey.unregister()
        if sys.platform == "win32":
            from . import wintoast

            wintoast.toaster().clear()  # nothing would hear their buttons now
        self.menus.stop()
        self._stop_update_checks()
        watcher = getattr(self, "_lock_watcher", None)
        if watcher is not None and hasattr(watcher, "close"):
            # Windows: its native event filter out of the application before it goes (Qt would go on calling
            # a filter that's been freed), and the session and power notifications unregistered.
            watcher.close()
        self._save_chat()
        self.desk.close()
        global _running
        if _running is self:
            _running = None
        self.updater.cancel()
        from . import sound

        sound.close()  # a Linux player still sounding finishes and is reaped, never left behind
        self.save()
        self.tray.hide()
        self.stage.close_stage()
        self._close_connections()
        self._stop_for_good()
        self.app.quit()

    def _stop_for_good(self) -> None:
        """Nothing of this Companion runs or paints once it's quit, whether or not it's ever freed: every timer it
        owns stopped and silenced, should anything start one again (its checks, its menu's refill, the asker's),
        what it was waiting for let go of (the work handed to threads, a brain being found, the question on its
        way, Settings' test), and its windows hidden; its one-off waits (_later) see it has quit. Left open, the ask
        box went on redrawing its bubble 30 times a second, the checks went on every few seconds, and a look at the
        agents went off three seconds in, whenever that was. Only a process that goes on after quitting sees it:
        the tests make one Companion after another."""
        self.background.stop()
        self.finder.stop()
        self.asker.cancel()
        self.compactor.cancel()
        if self._brain_test is not None:
            self._brain_test.cancel()
            self._brain_test = None
        self.ask_box.hide()  # (its redraws stop as it hides)
        for widget in (self.ask_box, self.ask_box.entry, self.ask_box.answer):
            widget.removeEventFilter(self)  # type: ignore[arg-type]  # PyQt6 6.12.1's stub types the filter as the widget's own class (CONTRIBUTING.md); Qt called it for every event of theirs, a quit one's too
        for owner in (self, self.ask_box):
            for timer in owner.findChildren(QTimer):
                timer.stop()
                timer.blockSignals(True)
        for window in (self._settings_window, self._chats_window):
            if window is not None and not sip.isdeleted(window):
                window.close()


_running: Companion | None = None  # the Companion running, which offers to report what went wrong (_log_exception)


def _key_status(brain: brains.Brain) -> dict:
    """What's known of an API brain's key, for Settings, never reading it: in words, and whether the keychain has one."""
    saved = keychain.has(brain.name)
    if brain.api_key:
        said = _("Its key is in the settings file.")
    elif saved:
        said = _("A key is saved in {store}.").format(store=keychain.where())
    elif brain.api_key_env and os.environ.get(brain.api_key_env):
        said = _("Its key comes from {variable}.").format(variable=brain.api_key_env)
    else:
        said = _("No key yet: paste one here, or set {variable}.").format(variable=brain.api_key_env)
    return {"said": said, "saved": saved}


def _client_is_me(sock: QLocalSocket) -> bool:
    """Windows: the process at the other end of a connection runs as you (winpipe.client_is_me, on its pipe handle)."""
    from . import winpipe

    return winpipe.client_is_me(int(sock.socketDescriptor()))


def _day_of(t: float) -> date | None:
    try:
        return datetime.fromtimestamp(t).date()  # noqa: DTZ006 - your local day
    except (OSError, OverflowError, ValueError):
        return None


BADGE = QColor("#e5484d")  # the tray icon's dot: an agent needs you


def _with_badge(pixmap: QPixmap) -> QPixmap:
    """A copy of `pixmap` with a red dot, ringed in white, in its top-right corner."""
    out = QPixmap(pixmap)
    width, height = out.width() / out.devicePixelRatio(), out.height() / out.devicePixelRatio()  # the painter's units
    side = max(4.0, min(width, height) * 0.42)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor("white"))
    painter.setBrush(BADGE)
    painter.drawEllipse(QRectF(width - side, 0.5, side - 1, side - 1))
    painter.end()
    return out


def _summary(held: list[messages.Message]) -> str:
    return "\n".join(f"- {_gist(m)}" for m in held)


def _gist(message: messages.Message, most: int = 90) -> str:
    """A message in a line: its title in bold, and the start of its words."""
    words = " ".join(a11y.plain(message.text).split()) if message.text else ""
    words = words if len(words) <= most else words[: most - 1].rstrip() + "…"
    return f"**{message.title}**" + (f": {words}" if words else "")


def _read_system() -> tuple:
    """The battery and the disks, as they are now: slow, so never on the screen's thread."""
    return heads_up.read_battery(), heads_up.read_disks(heads_up.disk_folders())


def _log_exception(kind, value, tb) -> None:
    """An exception that escaped a slot (PyQt would abort the app over it): in the log, with its traceback, and
    offered to be reported."""
    logger.error("something went wrong", exc_info=(kind, value, tb))
    if _running is not None and not issubclass(kind, KeyboardInterrupt):
        _running._later(0, _running._problem)


def _find_fonts(app: QApplication) -> None:
    """Have Qt find its fonts now, before the chatmon is on screen. The first text it measures makes it
    read every font installed, and the first character that font lacks (the bubbles' ✕) makes it work
    out which fonts to fall back on. With a few thousand fonts installed, as Windows PCs can have, each
    takes seconds; left to the first bubble, the chatmon froze mid-wave while they happened."""
    QFontMetricsF(app.font()).horizontalAdvance("Chatmon ✕")


_instance_lock: int | None = None  # the lock this Chatmon holds while it runs (Linux, macOS)


def _hold_instance_lock(path: str) -> bool:
    """Take the lock that says this is the Chatmon here, for as long as it runs; False if another has it. Linux and
    macOS: Windows' pipe has its own guard (open_server)."""
    global _instance_lock
    if sys.platform == "win32":
        return True
    import fcntl

    import errno

    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    except OSError as exc:
        logger.debug("couldn't make the lock %s, so there's none: %s", path, exc)
        return True  # can't make one (a read-only folder, a link where it would be): go on as before
    if os.fstat(fd).st_uid != os.getuid():  # someone else's file: it says nothing about us
        os.close(fd)
        return True
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        os.close(fd)
        if exc.errno in (errno.EWOULDBLOCK, errno.EAGAIN):  # held by another Chatmon
            return False
        logger.debug("couldn't take the lock %s, so going on without it: %s", path, exc)
        return True
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
        # (cli.main has chosen the language already: the Companion chooses it again once Qt's application exists.)
        held = _("Another user on this computer is holding `{pipe}`, the address your agents' hooks reach me at, so I won't listen there and they'll "
                 "tell it nothing.").format(pipe=winpipe.full_name(name))
        if reached == events.FOREIGN:
            return server, held
        try:
            guard = winpipe.claim(name)
        except OSError as exc:  # can't tell; listen as Qt would on its own
            logger.warning("couldn't claim %s first: %s", name, exc)
        else:
            if guard is None:
                return (None, None) if events.send({"type": "show"}) else (server, held)
    else:
        # Two started at once could both find nothing listening, and the second would take the first's socket
        # away: whoever holds this lock (for as long as it runs) is the one Chatmon here.
        if not _hold_instance_lock(name + ".lock"):
            for _attempt in range(15):  # the other is starting, or running: it shows itself
                if events.send({"type": "show"}):
                    break
                time.sleep(0.2)
            return None, None
        QLocalServer.removeServer(name)  # a socket left behind in our own private folder
    try:
        if not server.listen(name):
            return server, _("I couldn't open `{pipe}` ({error}), the address your agents' hooks reach me at.").format(pipe=name, error=server.errorString())
    finally:
        if guard is not None:
            from . import winpipe

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
    applog.setup()  # chatmon.log in the state folder, and stderr when there is one (log.py)
    logger.info("Chatmon %s started", __version__)
    if sys.platform == "darwin":
        os.environ.setdefault("QT_MAC_SET_RAISE_PROCESS", "0")  # raising a window mustn't make Chatmon the active app
        if not os.environ.get("TERM_PROGRAM"):  # started from Finder, the Dock or at login, not a terminal
            paths.login_environment()
    paths.windows_environment()  # started by its installer, maybe, from before chatmon was on PATH
    # PyQt aborts the whole app on an exception that escapes a slot; log it and carry on instead.
    sys.excepthook = _log_exception
    reached = events.deliver({"type": "show"})
    if reached == events.SENT:
        print(_("Chatmon is already running; it says hi."))
        return 0
    if sys.platform == "win32":
        # Its identity on Windows (taskbar, notifications), the same one its shortcuts carry: set before any
        # window. https://learn.microsoft.com/en-us/windows/win32/shell/appids
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
        except (AttributeError, OSError) as exc:
            logger.debug("couldn't give Chatmon its identity on Windows: %s", exc)
        if not getattr(sys, "frozen", False):  # pip or source: no Start menu shortcut carries the ID, so name it for toasts
            from . import wintoast

            try:
                wintoast.register_app_id(APP_USER_MODEL_ID, "Chatmon")
            except OSError as exc:
                logger.warning("couldn't name Chatmon for Windows' notifications: %s", exc)
    app = QApplication(sys.argv[:1])
    app.setApplicationName(paths.APP)
    app.setApplicationDisplayName("Chatmon")
    app.setDesktopFileName(autostart.APP_ID)  # its identity to Linux desktops and portals
    autostart.migrate()
    autostart.refresh()
    app.setQuitOnLastWindowClosed(False)
    server, problem = open_server(reached)
    if server is None:
        print(_("Chatmon is already running; it says hi."))
        return 0
    if problem:
        logger.warning("%s Hooks won't reach Chatmon.", problem)
    _find_fonts(app)
    companion = Companion(app, server, server_problem=problem)
    # Windows ending the session (logging off, shutting down) says so with aboutToQuit and then ends the app
    # there and then: nothing after app.exec() gets to run.
    app.aboutToQuit.connect(companion.save)
    # Python runs a signal handler between any two steps of whatever it's doing,
    # say halfway through drawing a frame; quit from the event loop instead.
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: companion._later(0, companion.quit))
    try:
        return app.exec()
    finally:
        companion.save()
        server.close()
