"""The running companion: the penguin, its bubbles and tray icon, and what it
keeps an eye on for you."""

from __future__ import annotations

import os
import shutil
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
from PyQt6.QtGui import QActionGroup, QDesktopServices, QGuiApplication, QIcon
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import agents, autostart, brains, companions, events, heads_up, paths, reminders, styles
from .behavior import Behavior
from .bubble import AskBox
from .penguin import Stage
from .settings import State, load_config
from .sprites import Sprites

PRETTY = {"claude": "Claude", "codex": "Codex", "gemini": "Gemini", "grok": "Grok", "copilot": "Copilot", "agent": "Your agent"}
WORK_EXPIRES = 30 * 60  # forget an agent that said it was working but never finished
AGENTS_FRESH = 30  # seconds a look at how the agents stand holds good for filling in the menu
MATCH = "match"  # the bubble style that follows the companion

HELP = """\
**Click me** to ask anything, **drag me** anywhere, **right-click** for the menu.

I also understand, without any AI:
- *remind me in 20m to stretch* · *remind me at 3pm to call Sam*
- *timer 10 min for the pasta* · *focus 50*
- *status* — battery, disk, reminders
- *hide* — I'll duck behind the taskbar and peek out now and then
"""


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


def pretty(source: str) -> str:
    return PRETTY.get(source.lower(), source[:1].upper() + source[1:])


class Companion(QObject):
    def __init__(self, app: QApplication, server: QLocalServer, server_problem: str | None = None):
        super().__init__()
        self.app = app
        self.server = server
        self.server_problem = server_problem  # why hooks can't reach it, if they can't
        self.state = State.load()
        self.config, self.config_error = load_config()
        self.brains = brains.load_brains(self.config["ai"])
        self.reminders = reminders.ReminderBook.from_list(self.state.get("reminders", []))
        self.breaks = reminders.BreakTracker(self.config["breaks"]["every_minutes"], time.time())
        self.watcher = self._make_watcher()
        self.history: list[tuple[str, str]] = []
        self.agents: dict[str, tuple[str, float]] = {}  # source: (state, since)
        self._last_event: tuple[str, str] | None = None
        self._last_event_at = 0.0
        self._alert_key: str | None = None
        self._waiting: list = []  # messages held back while an alert is up
        self._asking_name = False
        self._question = ""
        self._last_wall = time.time()
        self._last_ask = 0.0
        self._update_counts: dict[str, int] = {}

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

        self.stage.clicked.connect(self.on_click)
        self.stage.menu_requested.connect(self.show_menu)
        self.stage.head_moved.connect(self._follow)
        self.stage.message_closed.connect(self._message_closed)
        self.stage.menu_closed.connect(self._menu_closed)
        self.stage.scale_changed_to.connect(self._set_sprite_scale)
        self.ask_box.closed.connect(self._ask_closed)
        self.ask_box.submitted.connect(self.submit)
        self.ask_box.reset_requested.connect(self._new_chat)
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
        self._looking = False  # finding out, off the screen's thread, whether model servers here are running
        self._fill_menu()
        self.tray = QSystemTrayIcon(QIcon(self.sprites.frame("idle", 0, False).pixmap))
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._tray_clicked)
        self.tray.show()
        self.app.setWindowIcon(self.tray.icon())

        self._watch_screen_lock()
        self._every(5_000, self._check_reminders)
        self._every(30_000, self._check_time)
        self._every(60_000, self._check_system)
        self._every(int(self.config["heads_up"]["updates_every_hours"] * 3600_000), self._check_updates)
        QTimer.singleShot(120_000, self._check_updates)
        QTimer.singleShot(1500, self._greet)
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

    def say(self, title: str, text: str = "", buttons=None, timeout_s: float | None = 12) -> None:
        if self._alert_key is not None:  # don't talk over something that needs you
            self._later(partial(self.say, title, text, buttons, timeout_s))
            return
        self.stage.show_message(title, text, buttons, timeout_s)

    def alert(self, key: str, title: str, text: str, buttons=None) -> None:
        """Something needs you: the penguin waves its flippers until you answer."""
        if self._alert_key is not None:
            self._later(partial(self.alert, key, title, text, buttons))
            return
        self._alert_key = key
        self.behavior.set_hidden(False, self._now())
        self._menu_changed()
        self.behavior.set_alert(True, self._now())
        self.stage.show_message(title, text, buttons or [("OK", None)], None)

    def _later(self, show) -> None:
        self._waiting = (self._waiting + [show])[-5:]

    def _message_closed(self) -> None:
        if self._alert_key is not None:
            self._alert_key = None
            self.behavior.set_alert(False, self._now())
        if self._waiting:
            QTimer.singleShot(400, self._waiting.pop(0))

    def _greet(self) -> None:
        if self.config_error:
            self.say("I couldn't read my settings", f"`{self.config_error}`\n\nUsing the defaults for now.", timeout_s=30)
        elif self.server_problem:
            self.say("Your agents can't reach me", f"{self.server_problem}\n\nEverything else works.", timeout_s=30)
        elif not (self.config["name"] or self.state.get("name")):
            self._asking_name = True
            self.open_ask(focus=False)  # nobody clicked: don't take the keyboard from them
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
        self.stage.dismiss_message()
        if now - self._last_ask > 15 * 60:
            self.history.clear()
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
        else:
            brain = self._brain()
            via = f"answers from {brain.label}" if brain else "no AI set up yet; reminders and timers still work"
            self.ask_box.open(
                anchor, f"Ask {self.name}", f"Enter to ask · Esc to close · {via}", "Ask anything, or: remind me in 20m to stretch", prefill=prefill, activate=focus
            )
            self.ask_box.set_resettable(bool(self.history))

    def _ask_closed(self) -> None:
        now = self._now()
        self._asking_name = False
        self.asker.cancel()
        self.behavior.set_thinking(False, now)
        self.behavior.set_talking(False, now)
        self.behavior.set_attending(self._menu_open, now)

    def _new_chat(self) -> None:
        self.history.clear()
        self.ask_box.set_resettable(False)
        self.ask_box.set_answer("*New chat. Ask away.*")

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
        if self._local(text):
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
        self._question = text
        self.ask_box.set_answer(f"**You:** {text}\n\n*{brain.label} is thinking…*")
        self.behavior.set_thinking(True, now)
        self.asker.ask(brain, brains.system_prompt(self.name, self._companion().label.lower()), self.history[-6:], text, float(self.config["ai"]["timeout_seconds"]))

    def _answered(self, answer: str) -> None:
        now = self._now()
        self.behavior.set_thinking(False, now)
        self.history.append((self._question, answer))
        self.ask_box.set_answer(f"**You:** {self._question}\n\n{answer}")
        self.ask_box.set_resettable(True)
        self.behavior.set_talking(True, now)
        QTimer.singleShot(int(min(max(len(answer) / 18, 2), 10) * 1000), lambda: self.behavior.set_talking(False, self._now()))

    def _failed(self, error: str) -> None:
        self.behavior.set_thinking(False, self._now())
        self.ask_box.set_answer(f"**You:** {self._question}\n\n*Hmm, that didn't work.* {error}")

    def _local(self, text: str) -> bool:
        """Reminders, timers and the like, handled without any AI."""
        now = self._now()
        command = reminders.parse_command(text, datetime.now())
        if command is not None:
            if command.kind == "unclear":
                self.ask_box.set_answer("When should I remind you? Try *remind me in 20m to stretch* or *remind me at 3pm to call Sam*.")
            elif command.kind == "focus":
                self.ask_box.dismiss()
                self.start_focus(command.minutes or float(self.config["focus"]["minutes"]))
            else:
                r = self.reminders.add(command.due.timestamp(), command.text, command.kind)
                self.save()
                when = reminders.describe(r.due, time.time())
                what = f"Timer set: **{r.text}**, done {when}." if r.kind == "timer" else f"I'll remind you {when}: **{r.text}**"
                self.ask_box.set_answer(what)
                self.behavior.react("hop", now)
            return True
        word = text.lower().strip(" ?!.")
        if word in ("help", "what can you do", "commands"):
            self.ask_box.set_answer(HELP)
        elif word in ("status", "battery", "system status", "how's my computer"):
            self.ask_box.set_answer(self._status())
        elif word in ("hide", "go hide", "go away"):
            self.ask_box.dismiss()
            self.set_hidden(True)
        elif word in ("new chat", "/new", "reset"):
            self._new_chat()
        else:
            return False
        return True

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
        if len(rest) < len(due):
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
        if self._menu_clock != self._time_labels():
            self._menu_changed()
        mono = self._now()
        for source, (state, since) in list(self.agents.items()):
            if state == "working" and mono - since > WORK_EXPIRES:
                del self.agents[source]
        self._update_working()
        if self.breaks.due(now) and self.reminders.focus() is None and not self.stage.message_visible() and not self.ask_box.isVisible():
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
        if sys.platform == "win32":
            from . import winlock

            self._lock_watcher = winlock.LockWatcher(self._screen_locked)
            return
        if sys.platform == "darwin":
            # Suspend gaps stand in for it. PyQt ships QtDBus on macOS too, and on an Intel Mac with
            # Homebrew's dbus Qt finds its libdbus and asks for a session bus macOS doesn't have: a wait
            # on the screen's thread at every start, and a thread of its own, for nothing.
            return
        try:  # D-Bus: Linux and the BSDs
            from PyQt6.QtDBus import QDBusConnection
        except ImportError:
            return
        bus = QDBusConnection.sessionBus()
        if bus.isConnected():
            bus.connect("org.freedesktop.ScreenSaver", "/ScreenSaver", "org.freedesktop.ScreenSaver", "ActiveChanged", self._screen_locked)

    @pyqtSlot(bool)
    def _screen_locked(self, locked: bool) -> None:
        now = time.time()
        if locked:
            self.breaks.away(now)
        else:
            self.breaks.back(now)
            self.behavior.wake(self._now())

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
        # Both read what the system already knows (no network): the desktop's own updater refreshes it.
        checks = [
            ("apt", ["apt", "list", "--upgradable"], heads_up.count_apt),
            ("flatpak", ["flatpak", "remote-ls", "--updates", "--cached", "--columns=application"], heads_up.count_flatpak),
        ]
        checks = [c for c in checks if shutil.which(c[1][0])]
        self._update_counts = {}
        for name, command, count in checks:
            proc = QProcess(self)
            proc.finished.connect(partial(self._updates_counted, proc, name, count, len(checks)))
            proc.start(command[0], command[1:])

    def _updates_counted(self, proc: QProcess, name: str, count, expected: int, code: int, _status) -> None:
        output = bytes(proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        proc.deleteLater()
        self._update_counts[name] = count(output) if code == 0 else 0
        if len(self._update_counts) == expected:
            notice = self.watcher.updates(sum(self._update_counts.values()), date.today())
            if notice and not self.stage.message_visible():
                self.behavior.react("wave", self._now())
                self.say(notice.title, notice.text, [("OK", None)], timeout_s=60)

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
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
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
        return (left, tuple(reminders.describe(r.due, now) for r in self.reminders.upcoming() if r.kind != "focus"))

    def _fill_menu(self) -> None:
        self._menu_timer.stop()
        self._menu_clock = self._time_labels()
        m = self.menu
        for sub in m.findChildren(QMenu, options=Qt.FindChildOption.FindDirectChildrenOnly):
            sub.deleteLater()  # clear() keeps submenus
        m.clear()
        m.addAction(f"Ask {self.name}…", self.open_ask)
        m.addAction("Remind me…", partial(self.open_ask, "remind me in "))
        focus = self.reminders.focus()
        if focus:
            left = max(1, round((focus.due - time.time()) / 60))
            m.addAction(f"Stop focus ({left} min left)", self.stop_focus)
        else:
            sub = m.addMenu("Focus timer")
            for minutes in sorted({15, 25, 50, int(self.config["focus"]["minutes"])}):
                sub.addAction(f"{minutes} minutes", partial(self.start_focus, minutes))
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
        m.addAction("Edit settings…", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.config_file()))))
        m.addAction("Reload settings", self.reload)
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
        """A style chosen by name wins; otherwise the bubbles match the companion."""
        name = self._bubble_style_name()
        return styles.get(self._companion().bubble_style if name == MATCH else name)

    def _bubble_effects(self) -> bool:
        picked = self.state.get("bubble_effects")
        return bool(self.config["bubble_effects"] if picked is None else picked)

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
        self.behavior.set_walk(on, self._now())
        self._menu_changed()

    def _set_autostart(self, on: bool) -> None:
        autostart.set_enabled(on)
        self._menu_changed()

    def reload(self) -> None:
        self.config, self.config_error = load_config()
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
        self.say("Settings reloaded", timeout_s=3)

    def _set_sprite_scale(self, scale: float) -> None:
        """The stage's screen has this many device pixels to a pixel: draw the penguin with them."""
        if abs(scale - self._sprite_scale) > 0.01:
            self._sprite_scale = scale
            self._show_sprites()

    def quit(self) -> None:
        self.save()
        self.tray.hide()
        self.stage.close_stage()
        self.app.quit()


def _log_exception(kind, value, tb) -> None:
    traceback.print_exception(kind, value, tb, file=sys.stderr)


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
        QLocalServer.removeServer(name)  # a socket left behind in our own private folder
    try:
        if not server.listen(name):
            return server, f"I couldn't open `{name}` ({server.errorString()}), the address your agents' hooks reach me at."
    finally:
        if guard is not None:
            winpipe.release(guard)
    return server, None


def run() -> int:
    # On Wayland a window can't place itself or stay above other windows, so
    # the window runs through XWayland, where it can.
    if sys.platform.startswith("linux") and os.environ.get("XDG_SESSION_TYPE") == "wayland" and os.environ.get("DISPLAY") and "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "xcb"
    _log_without_a_console()
    # PyQt aborts the whole app on an exception that escapes a slot; log it and carry on instead.
    sys.excepthook = _log_exception
    reached = events.deliver({"type": "show"})
    if reached == events.SENT:
        print("Chatmon is already running; it says hi.")
        return 0
    app = QApplication(sys.argv[:1])
    app.setApplicationName(paths.APP)
    app.setApplicationDisplayName("Chatmon")
    autostart.migrate()
    autostart.refresh()
    app.setQuitOnLastWindowClosed(False)
    server, problem = open_server(reached)
    if server is None:
        print("Chatmon is already running; it says hi.")
        return 0
    if problem:
        print(f"{problem} Hooks won't reach Chatmon.", file=sys.stderr)
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
