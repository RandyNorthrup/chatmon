"""The rest of M7 in the whole app: missed and recent messages (M7-06), agents at a glance (M7-07), clipboard quick
actions (M7-08), copy and keys (M7-10), platform wiring (M7-11), a new chat after a while (M7-12), the first-unlock
hello (M7-13), settings applied at once (M7-03), what was wrong at start (M1B's notes 9 and 10), connections on Windows
(M0's note 8), and M2's notes (More, the box's size, the hint, a question's lines)."""

import sys
import threading
import time

import pytest
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QKeyEvent, QPalette
from PyQt6.QtWidgets import QApplication

from app_harness import PretendBrain, make_companion, spin, until
from chatmon import bubble, events, keychain


@pytest.fixture
def companion(tmp_path, monkeypatch):
    yield from make_companion(tmp_path, monkeypatch)


def labels(c) -> list[str]:
    return [b.label for b in c.stage.bubble.buttons]


def out_of_the_way(c) -> None:
    spin(1.8)
    c.stage.dismiss_message()


def quick_bubbles(c) -> None:
    """Bubbles that go by in a moment, so a test can see one time out."""
    c.stage.bubble.timeout_policy = bubble.TimeoutPolicy(least=0.3, per_word=0.0)


# -- M7-06: missed and recent messages


def test_recent_messages_are_in_the_menu_and_show_again(companion):
    c = companion
    out_of_the_way(c)
    c.say("Backup finished", "All three folders.", timeout_s=8)
    c.menus.fill()
    recent = next(a.menu() for a in c.menu.actions() if a.text() == "Recent messages")
    texts = [a.text() for a in recent.actions()]
    assert texts[0].startswith("Backup finished") and any(t.startswith("Hi, I'm Sparky!") for t in texts)  # newest first
    c.stage.dismiss_message()
    recent.actions()[0].trigger()
    assert until(lambda: c.stage.message_visible() and c.stage.bubble.title == "Backup finished")
    assert "All three folders." in c.stage.bubble.doc.toPlainText()


def test_a_bubble_that_went_by_while_you_were_away_comes_back_with_a_click(companion):
    c = companion
    out_of_the_way(c)
    quick_bubbles(c)
    c.desk.idle = 600.0  # nobody at the keyboard
    c.say("Claude finished", "All tests pass.", timeout_s=1)
    assert until(lambda: not c.stage.message_visible())
    assert [m.title for m in c._missed] == ["Claude finished"]
    c.on_click()  # back, rather than the ask box
    assert until(lambda: c.stage.bubble.title == "Claude finished") and not c.ask_box.isVisible() and c._missed == []
    c.stage.dismiss_message()
    c.desk.idle = 0.0  # you're there: one that times out was seen
    c.say("Seen", timeout_s=1)
    assert until(lambda: not c.stage.message_visible())
    assert c._missed == []
    c.on_click()
    assert c.ask_box.isVisible()


def test_plain_bubbles_the_queue_dropped_count_as_missed(companion):
    from chatmon import messages

    c = companion
    out_of_the_way(c)
    c.desk.why_quiet = "a presentation"
    c._check_quiet()
    for i in range(messages.PLAIN_LIMIT + 2):
        c.say(f"News {i}", timeout_s=8, background=True)
    assert [m.title for m in c._missed] == ["News 0", "News 1"]  # the oldest two, past the limit, never shown
    c.desk.why_quiet = None
    c._check_quiet()
    spin(1.0)
    c.stage.dismiss_message()
    for _ in range(messages.PLAIN_LIMIT):
        c.messages.closed()
    c.messages.waiting.clear()
    c.on_click()
    assert until(lambda: c.stage.bubble.title == "While you were away")
    assert "News 0" in c.stage.bubble.doc.toPlainText() and "News 1" in c.stage.bubble.doc.toPlainText()


# -- M7-07: agents at a glance


def test_the_tray_and_the_stage_name_what_each_agent_is_doing_with_a_badge_while_one_needs_you(companion):
    c = companion
    assert c.tray.toolTip() == "Chatmon" and not c._tray_badge
    c.handle({"type": "event", "event": "working", "source": "claude", "message": ""})
    assert "Claude is working" in c.tray.toolTip() and "Claude is working" in c.stage.surface.accessibleName()
    assert c.stage.badge_description() == "1 agent working" and not c._tray_badge
    plain_icon = c.tray.icon().pixmap(32, 32).toImage()
    c.handle({"type": "event", "event": "needs-you", "source": "codex", "message": "Approve?"})
    assert "Codex needs you" in c.tray.toolTip() and c._tray_badge
    assert c.stage.badge_description() == "1 agent needs you, 1 agent working"
    badged = c.tray.icon().pixmap(32, 32).toImage()
    corner = QColor(badged.pixel(badged.width() - 4, 4))
    assert badged != plain_icon and corner.red() > 180 and corner.green() < 120  # a red dot in its corner
    for source in ("claude", "codex"):
        c.handle({"type": "event", "event": "done", "source": source, "message": ""})
    assert c.tray.toolTip() == "Chatmon" and not c._tray_badge and c.stage.badge_description() == ""


def test_the_agents_command_says_how_each_stands(companion):
    c = companion
    c.open_ask()
    c.submit("agents")
    assert "No AI agent is working or waiting for you." in c.ask_box.answer.toPlainText()
    c.handle({"type": "event", "event": "needs-you", "source": "claude", "message": "Approve?"})
    c.open_ask()
    c.submit("what are my agents doing?")
    assert "Claude needs you (waiting under a minute)" in c.ask_box.answer.toPlainText()


def test_chatmon_status_hears_the_live_states_from_the_running_chatmon(companion):
    """events.request, through the real socket or pipe, from another thread (as `chatmon status` would, from another
    process): the companion answers its status before its ok."""
    c = companion
    c.handle({"type": "event", "event": "working", "source": "codex", "message": ""})
    got = []
    thread = threading.Thread(target=lambda: got.append(events.request({"type": "status"}, timeout=5)))
    thread.start()
    while thread.is_alive():
        spin(0.05)
    import os

    assert got[0]["type"] == "status" and got[0]["pid"] == os.getpid() and got[0]["agents"].startswith("Codex is working")
    sent = []
    thread = threading.Thread(target=lambda: sent.append(events.request({"type": "show"}, timeout=5)))  # no answer to that
    thread.start()
    while thread.is_alive():
        spin(0.05)
    assert sent == [None]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows pipes: the access list keeps other users out, and each connection is checked too")
def test_on_windows_each_connection_is_checked_to_be_yours(companion, monkeypatch):
    from chatmon import winpipe

    c = companion
    checked, real = [], winpipe.client_is_me
    monkeypatch.setattr(winpipe, "client_is_me", lambda handle: checked.append(real(handle)) or checked[-1])
    thread = threading.Thread(target=lambda: events.send({"type": "say", "text": "from a process of yours"}, timeout=5))
    thread.start()
    while thread.is_alive():
        spin(0.05)
    assert checked == [True] and until(lambda: "from a process of yours" in c.stage.bubble.doc.toPlainText())
    c.stage.dismiss_message()
    monkeypatch.setattr(winpipe, "client_is_me", lambda handle: False)  # as for another user's process
    thread = threading.Thread(target=lambda: events.send({"type": "say", "text": "from someone else"}, timeout=2))
    thread.start()
    while thread.is_alive():
        spin(0.05)
    spin(0.3)
    assert all("from someone else" not in m.text for _, m in c.recent_messages())  # turned away, unheard


# -- M7-08: quick actions on the clipboard


def test_quick_actions_attach_the_clipboard_only_when_chosen_and_type_the_prompt(companion, monkeypatch):
    c = companion
    read = []
    real = QGuiApplication.clipboard
    monkeypatch.setattr(QGuiApplication, "clipboard", staticmethod(lambda: read.append(1) or real()))
    real().setText("def f(): retrun 1")
    c.menus.fill()
    c.open_ask()
    c.ask_box.dismiss()
    assert read == [] and c.attached == []  # never read on its own
    clip = next(a.menu() for a in c.menu.actions() if a.text() == "Clipboard")
    assert [a.text() for a in clip.actions()] == ["Explain the clipboard…", "Summarize the clipboard…", "Translate the clipboard…", "Fix the clipboard…"]
    next(a for a in clip.actions() if a.text().startswith("Fix")).trigger()
    assert read == [1] and c.ask_box.isVisible() and c.ask_box.entry.text().startswith("Fix the mistakes in this")
    assert until(lambda: len(c.attached) == 1) and c.attached[0].text == "def f(): retrun 1"
    c._clear_attachments()
    c._quick_action("Translate")
    from PyQt6.QtCore import QLocale

    assert c.ask_box.entry.text() == f"Translate this into {QLocale.languageToString(QLocale().language())}:"
    assert until(lambda: len(c.attached) == 1)
    c._clear_attachments()
    real().clear()
    c._quick_action("Explain")
    assert "The clipboard is empty" in c.ask_box.answer.toPlainText() and c.attached == []


# -- M7-10: copy and keys


def test_copy_puts_an_answer_on_the_clipboard(companion):
    c = companion
    c.ask_box.copy_requested.emit("print('hello')")
    assert QGuiApplication.clipboard().text() == "print('hello')"


def test_ctrl_and_a_number_press_a_bubbles_buttons_while_the_box_is_open(companion):
    c = companion
    out_of_the_way(c)
    pressed = []
    c.open_ask()
    c.say("Delete “Cat names”?", "", [("Delete it", lambda: pressed.append("delete")), ("Keep it", lambda: pressed.append("keep"))], timeout_s=None)
    assert c.stage.message_visible()
    for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
        QApplication.sendEvent(c.ask_box.entry, QKeyEvent(kind, Qt.Key.Key_2, Qt.KeyboardModifier.ControlModifier, "2"))
    assert pressed == ["keep"] and c.ask_box.entry.text() == "" and not c.stage.message_visible()
    QApplication.sendEvent(c.ask_box.entry, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_1, Qt.KeyboardModifier.ControlModifier, "1"))
    assert pressed == ["keep"]  # no bubble: nothing pressed


def test_a_buttons_label_typed_after_its_bubble_went_is_answerable_for_a_while(companion, monkeypatch):
    c = companion
    PretendBrain(c, monkeypatch)
    out_of_the_way(c)
    quick_bubbles(c)
    pressed = []
    c.say("Time for a break?", "", [("Taking one", lambda: pressed.append("break")), ("Snooze 10 min", None)], timeout_s=1)
    assert until(lambda: not c.stage.message_visible())  # it timed out, unanswered
    c.open_ask()
    c.submit("taking one")
    assert pressed == ["break"] and c.questions.current is None
    c.say("Another?", "", [("Yes please", lambda: pressed.append("yes"))], timeout_s=1)
    assert until(lambda: not c.stage.message_visible())
    monkeypatch.setattr(c, "ANSWERABLE_FOR", 0.0)  # too long ago
    spin(0.05)
    c.submit("yes please")
    assert pressed == ["break"] and c.questions.current.text == "yes please"  # a question for the AI, then


# -- M7-11: platform wiring


def test_a_locked_session_stops_drawing_and_the_power_saver_reaches_the_bubble_and_box(companion, monkeypatch):
    c = companion
    monkeypatch.setattr(sys, "platform", "linux")  # logind and Hyprland say so here; Windows says what can be seen itself
    c._screen_locked(True)
    assert c.stage.drawing is False and c.ask_box.seen is False
    c._screen_locked(False)
    assert c.stage.drawing is True and c.ask_box.seen is True
    monkeypatch.undo()
    c._power_saving(True)
    assert c.stage.power_saving and c.stage.bubble.power_saving and c.ask_box.power_saving
    c._power_saving(False)
    assert not (c.stage.power_saving or c.stage.bubble.power_saving or c.ask_box.power_saving)


def test_the_desktops_colours_and_reduced_motion_apply_at_once(companion):
    c = companion
    c.state.set("bubble_style", None)
    c.desk.contrast = True  # high contrast turned on: the desktop's palette changes
    app = QApplication.instance()
    before = QPalette(app.palette())
    changed = QPalette(before)
    changed.setColor(QPalette.ColorRole.Window, QColor("black"))
    try:
        app.setPalette(changed)
        assert until(lambda: c.stage.bubble.style.name == "plain" and c.ask_box.style.name == "plain")  # without waiting for a look
    finally:
        app.setPalette(before)
    c.desk.motion = True
    c._check_accessibility()
    assert c.ask_box.reduced_motion and c.behavior.reduced_motion
    c.desk.motion = False
    c._override(("accessibility", "reduced_motion"), "on")  # Settings: always less movement, whatever the system says
    c.reload(quietly=True)
    assert c._reduce_motion and c.ask_box.reduced_motion


def test_sounds_play_for_alerts_only_unless_turned_on_and_never_in_quiet_or_focus(companion, monkeypatch):
    c = companion
    played = []
    monkeypatch.setattr(c, "_play", lambda name: played.append(name) or True)  # the player itself is sound.py's (test_sound.py)
    c._override(("sound", "enabled"), True)  # the harness turns sound off; Chatmon's own default is on
    c.reload(quietly=True)
    out_of_the_way(c)
    c.handle({"type": "event", "event": "needs-you", "source": "claude", "message": "Approve?"})
    c.handle({"type": "event", "event": "done", "source": "claude", "message": ""})
    c.say("A plain bubble", timeout_s=8)
    assert played == ["needs-you"]  # done and pop are off until turned on (owner, 2026-11-14)
    c._override(("sound", "cues", "done"), True)
    c.state.save()
    c.reload(quietly=True)
    c.stage.dismiss_message()
    c.handle({"type": "event", "event": "done", "source": "codex", "message": ""})
    assert played == ["needs-you", "done"]
    c.desk.why_quiet = "Do Not Disturb"
    c._check_quiet()
    c.handle({"type": "event", "event": "needs-you", "source": "codex", "message": "Approve?"})
    assert played == ["needs-you", "done"]  # quiet
    c.desk.why_quiet = None
    c._check_quiet()
    c.start_focus(25)
    assert c._cue("needs-you") is False  # a focus session: quiet too
    c.stop_focus()
    c._override(("sound", "enabled"), False)
    c.reload(quietly=True)
    assert c._cue("needs-you") is False  # one switch for all


def test_the_player_is_told_the_settings_and_asks_whether_its_a_time_for_quiet(companion, monkeypatch):
    from chatmon import sound

    c = companion
    told = []
    monkeypatch.setattr(sound, "configure", lambda enabled, volume, cues, quiet=None: told.append((enabled, volume, cues, quiet)))
    c._override(("sound",), {"enabled": True, "volume": 40, "cues": {"done": True}})
    c.reload(quietly=True)
    enabled, volume, cues, quiet = told[-1]
    assert (enabled, volume, cues["done"], cues["needs-you"]) == (True, 40, True, True)
    assert not quiet()
    c.desk.why_quiet = "Do Not Disturb"
    c._check_quiet()
    assert quiet()  # sound.py asks before each sound
    c.desk.why_quiet = None
    c._check_quiet()
    c.start_focus(25)
    assert quiet()


def test_the_hotkey_is_registered_from_settings_toggles_the_box_and_a_problem_is_said_once(companion, monkeypatch):
    from chatmon import hotkey

    c = companion
    calls = []
    monkeypatch.setattr(hotkey, "register", lambda sequence, callback, failed=None: calls.append(("register", sequence, callback, failed)) or None)
    monkeypatch.setattr(hotkey, "unregister", lambda: calls.append(("unregister",)))
    c._override(("hotkey",), "Ctrl+Alt+K")
    c.reload(quietly=True)
    assert calls == [("register", "Ctrl+Alt+K", c._hotkey_pressed, c._hotkey_failed)]
    c.reload(quietly=True)
    assert len(calls) == 1  # unchanged: not again
    calls[0][2]()
    assert c.ask_box.isVisible()  # pressed: the box
    calls[0][2]()
    assert not c.ask_box.isVisible()  # pressed again: closed
    out_of_the_way(c)
    monkeypatch.setattr(hotkey, "register", lambda sequence, callback, failed=None: "Ctrl+Alt+J is already used by another app. Pick another shortcut.")
    c._override(("hotkey",), "Ctrl+Alt+J")
    c.reload(quietly=True)
    assert until(lambda: c.stage.bubble.title == "The hotkey to ask didn't work") and "already used" in c.stage.bubble.doc.toPlainText()
    c.stage.dismiss_message()
    c._hotkey = ""
    c.reload(quietly=True)  # the same hotkey, failing again (the next start): not said again
    spin(0.3)
    assert not c.stage.message_visible()
    c._hotkey = "Ctrl+Alt+K"
    c._override(("hotkey",), "")
    c.reload(quietly=True)
    assert calls[-1] == ("unregister",) and c._hotkey == ""


def test_the_hotkeys_default_isnt_finders_search_on_macos():
    import importlib

    from chatmon import settings

    assert settings.DEFAULTS["hotkey"] == ("Ctrl+Shift+Space" if sys.platform == "darwin" else "Ctrl+Alt+Space")
    assert importlib.import_module("chatmon.hotkey").parse(settings.DEFAULTS["hotkey"])  # one hotkey.py can register


@pytest.mark.skipif(sys.platform != "win32", reason="Windows' toasts")
def test_on_windows_an_alert_under_a_full_screen_app_is_a_toast_with_the_reminders_buttons(companion, monkeypatch):
    import types

    from app_harness import NoToasts

    from chatmon import wintoast

    c = companion
    shown, balloons = [], []

    listeners: dict[str, list] = {}

    class Toasts(NoToasts):
        failed = types.SimpleNamespace(connect=lambda handler: listeners.setdefault("failed", []).append(handler))
        dismissed = types.SimpleNamespace(connect=lambda handler: listeners.setdefault("dismissed", []).append(handler))

        def show(self, title, text="", buttons=(), scenario=None):
            shown.append((title, text, [label for label, _ in buttons], scenario))
            return f"tag-{len(shown)}"

    monkeypatch.setattr(wintoast, "toaster", lambda: Toasts())
    monkeypatch.setattr(c.tray, "showMessage", lambda *a: balloons.append(a))
    from PyQt6.QtWidgets import QSystemTrayIcon

    monkeypatch.setattr(QSystemTrayIcon, "supportsMessages", staticmethod(lambda: True))  # offscreen has no tray
    c.desk.why_quiet, c.desk.is_covered = "a full-screen game", True
    c._check_quiet()
    r = c.reminders.add(time.time() - 1, "stretch")
    c._check_reminders()
    assert shown == [("Reminder", "Chatmon has something for you.", ["Done", "Snooze 10 min"], "reminder")] and balloons == []  # never its words
    listeners["failed"][0]("tag-1", -0x7FC1FEEC)  # Windows refused it after all (M4B): the balloon in its place
    assert balloons[-1][:2] == ("Reminder", "Chatmon has something for you.")
    balloons.clear()
    c.alert("agent:codex", "Codex needs you", "Approve?")
    listeners["dismissed"][0]("tag-2", wintoast.TIMED_OUT)  # in Action Center, still to be clicked
    listeners["dismissed"][0]("tag-2", wintoast.DISMISSED_BY_YOU)  # its final word
    listeners["failed"][0]("tag-2", -1)  # nothing after that is news
    assert balloons == [] and c._toasts == {}
    monkeypatch.setattr(wintoast, "toaster", lambda: NoToasts())  # no toast to be had: the balloon
    c.handle({"type": "event", "event": "needs-you", "source": "claude", "message": "Approve?"})
    assert balloons and balloons[-1][:2] == ("Claude needs you", "Chatmon has something for you.")
    assert c.reminders.get(r.id).fired


@pytest.mark.skipif(sys.platform != "win32", reason="Windows' Magnifier")
def test_on_windows_magnifier_goes_to_each_bubble_and_lets_go_when_it_closes(companion, monkeypatch):
    from chatmon import wincaret

    c = companion
    out_of_the_way(c)
    c.behavior.set_walk(False, c._now())  # the bubble follows a walking chatmon: held still, to compare where it is
    placed, cleared = [], []
    monkeypatch.setattr(wincaret, "magnifier_running", lambda: True)
    monkeypatch.setattr(wincaret, "place", lambda hwnd, x, y, w, h: placed.append((hwnd, x, y, w, h)) or True)
    monkeypatch.setattr(wincaret, "clear", lambda: cleared.append(1))
    c.say("Claude finished", "All tests pass.", timeout_s=8)
    assert until(lambda: placed)
    hwnd, x, y, w, h = placed[0]
    rect, scale = c.stage.bubble_rect(), c.stage.device_scale()
    assert hwnd == c.stage.native_window() and (x, y, w, h) == (round(rect.x() * scale), round(rect.y() * scale), round(rect.width() * scale), round(rect.height() * scale))
    assert w > 0 and h > 0
    c.stage.dismiss_message()
    assert cleared
    c._override(("accessibility", "magnifier_follows"), False)
    c.reload(quietly=True)
    placed.clear()
    c.say("Codex finished", timeout_s=8)
    spin(0.3)
    assert placed == []  # the option off


def test_the_ask_box_is_a_window_with_a_screen_reader_where_the_overlay_draws_it(companion):
    c = companion
    assert c._ask_box_as_window() is False  # no screen reader looked for in tests
    c._reader = object()  # one running, as last looked
    assert c._ask_box_as_window() is True
    c._override(("accessibility", "accessible_ask_box"), "off")
    c.reload(quietly=True)
    assert c._ask_box_as_window() is False
    c._override(("accessibility", "accessible_ask_box"), "on")
    c._reader = None
    c.reload(quietly=True)
    assert c._ask_box_as_window() is True
    c._overlay = True  # as on the Wayland overlay: told to leave the box a window
    c._check_hosting()
    assert c.stage._unhosted
    c._override(("accessibility", "accessible_ask_box"), "off")
    c.reload(quietly=True)
    assert not c.stage._unhosted


def test_follow_me_across_monitors_is_a_setting(companion, monkeypatch):
    c = companion
    asked = []
    monkeypatch.setattr(c.stage, "follow_pointer_screen", lambda on: asked.append(on) or on)
    c._override(("follow_screen",), True)
    c.reload(quietly=True)
    assert asked[-1] is True
    c._override(("follow_screen",), False)
    c.reload(quietly=True)
    assert asked[-1] is False


# -- M7-12: a new chat after a while, said, and carry on


def test_after_a_while_the_box_opens_on_a_new_chat_and_carry_on_goes_back(companion, monkeypatch):
    from chatmon import app as appmod

    c = companion
    brain = PretendBrain(c, monkeypatch)
    c.open_ask()
    c.submit("Name a cat")
    brain.answer("Mochi.")
    first = c.chat.id
    c.ask_box.dismiss()
    c._last_ask -= appmod.NEW_CHAT_AFTER + 1
    c.open_ask()
    assert c.chat.id != first and c.chat.messages == []
    assert c.ask_box.answer.toPlainText() == "New chat · carry on with the last one"
    c.submit("carry on")
    assert c.chat.id == first and "Mochi." in c.ask_box.answer.toPlainText() and brain.asked[-1][1] == "Name a cat"
    c.submit("carry on")  # in a chat with something said: asks the AI to go on
    assert brain.asked[-1][1] == "carry on"
    c.ask_box.dismiss()
    c._last_ask -= appmod.NEW_CHAT_AFTER + 1  # a question on its way: never dropped for a new chat
    c.open_ask()
    assert c.chat.id == first and c.questions.current is not None


# -- M7-13: the first-unlock hello


def test_the_first_unlock_of_the_day_names_reminders_agents_and_updates_once(companion):
    c = companion
    out_of_the_way(c)
    c.state.set("hello_day", None)
    now = time.time()
    from datetime import datetime

    if datetime.fromtimestamp(now + 120).date() != datetime.fromtimestamp(now).date():
        pytest.skip("too close to midnight for a reminder later today")
    c.reminders.add(now + 60, "stand-up")
    c.agents["claude"] = ("needs-you", c._now())
    c._update_counts = {"apt": 3}
    c._screen_locked(False)
    assert until(lambda: c.stage.bubble.title in ("Good morning", "Welcome back"))
    said = c.stage.bubble.doc.toPlainText()
    assert "stand-up" in said and "Claude is waiting for you" in said and "3 system updates are waiting" in said
    c.stage.dismiss_message()
    c._screen_locked(False)  # again that day: no
    spin(0.3)
    assert not c.stage.message_visible()
    c.state.set("hello_day", None)
    c.reminders.items.clear()
    c.agents.clear()
    c._update_counts = {}
    assert c._hello() is False  # nothing to name: no bubble


# -- M7-03: what's set in Settings applies at once


def test_text_size_and_how_long_bubbles_stay_apply_at_once(companion):
    c = companion
    c._apply_settings({"text_scale": 150, "bubble_time": "until closed"})
    assert c.stage.bubble.text_scale == 1.5 and c.ask_box.text_scale == 1.5
    assert c.stage.bubble.timeout_policy.until_closed
    c._apply_settings({"bubble_time": "longer"})
    assert c.stage.bubble.timeout_policy == bubble.TimeoutPolicy(factor=1.5)


def test_the_update_check_interval_applies_without_a_restart(companion):
    c = companion
    assert c._updates_timer.interval() == 6 * 3600_000
    c._apply_settings({"updates_every_hours": 2})
    assert c._updates_timer.interval() == 2 * 3600_000 and c._updates_timer.isActive()


def test_a_key_saved_in_settings_goes_to_the_keychain_only(companion):
    c = companion
    c._apply_settings({"api_key": ("anthropic-api", "sk-test-secret")})
    assert keychain.get("anthropic-api") == "sk-test-secret"
    assert "sk-test-secret" not in c.state.path.read_text(encoding="utf-8")
    from chatmon import paths

    assert "sk-test-secret" not in paths.config_file().read_text(encoding="utf-8")
    assert until(lambda: c.stage.bubble.title == "Anthropic API's key") and "memory only" in c.stage.bubble.doc.toPlainText()
    c.open_settings("ai")
    c._remove_key("anthropic-api")
    assert not keychain.has("anthropic-api") and "Removed" in c._settings_window.key_status.text()
    c._settings_window.close()


def test_settings_test_asks_the_brain_and_shows_the_time_or_the_error(companion, monkeypatch):
    from chatmon import brains

    c = companion
    ok = brains.Brain("echo", "command", label="Echo", command=[sys.executable, "-c", "print('OK')"], tools_off=True)
    broken = brains.Brain("broken", "command", label="Broken", command=[sys.executable, "-c", "import sys; sys.exit(3)"], tools_off=True)
    monkeypatch.setitem(c.brains, "echo", ok)
    monkeypatch.setitem(c.brains, "broken", broken)
    c.open_settings("ai")
    w = c._settings_window
    c._test_brain("echo", "")
    assert until(lambda: w.test_result.text().startswith("✓ Echo answered in"), 30)
    c._test_brain("broken", "")
    assert until(lambda: w.test_result.text().startswith("✕ "), 30) and "Broken" in w.test_result.text()
    w.close()


# -- M1B's notes 9 and 10: what was wrong, said at start


def test_wrong_settings_are_named_one_by_one_and_the_rest_apply(companion):
    from chatmon import paths

    c = companion
    paths.config_file().write_text('size = "big"\nwalk = false\n[ai.brains.mine]\ntype = "command"\ncommand = "my-tool"\n', encoding="utf-8")
    c.state.set("settings", {"sleep_after_minutes": "soon"})
    c.reload()
    assert until(lambda: c.stage.bubble.title == "Some of my settings were wrong")
    said = c.stage.bubble.doc.toPlainText()
    assert "size should be a number" in said and "sleep_after_minutes should be a number" in said
    assert "ai.brains.mine.command should be a list of text" in said and "Everything else applies" in said
    assert c.config["walk"] is False and c.config["size"] == 120  # the rest applied
    c.stage.dismiss_message()
    paths.config_file().write_text("size = [", encoding="utf-8")
    c.reload()
    assert until(lambda: c.stage.bubble.title == "I couldn't read my settings") and "Using the defaults" in c.stage.bubble.doc.toPlainText()


def test_a_damaged_file_recovered_at_start_is_said(companion):
    c = companion
    c.state.problem = "state.json was damaged, so I kept it as state.json.bad-1 and went back to the copy from 2026-11-14 09:00."
    c._greet()
    assert until(lambda: c.stage.bubble.title == "One of my files was damaged") and "state.json.bad-1" in c.stage.bubble.doc.toPlainText()


# -- M2's notes


def test_more_opens_the_whole_text_and_the_box_remembers_its_size_and_says_shift_enter(companion, monkeypatch):
    c = companion
    c.stage.bubble.on_more("A long message", "word " * 500)
    assert c.ask_box.isVisible() and c.ask_box.title.text() == "A long message" and "word word" in c.ask_box.answer.toPlainText()
    c.ask_box.dismiss()
    c.ask_box.set_expanded(True)
    assert c.state.get("ask_box_expanded") is True
    c.open_ask()
    assert c.ask_box.hint.text().startswith("Enter to ask · Shift+Enter")  # shortened to the box's width, keys first
    assert "Shift+Enter for a new line · Esc to close" in c.ask_box.entry.accessibleDescription() == c.ask_box.hint.toolTip()
    brain = PretendBrain(c, monkeypatch)
    c.submit("first line\nsecond line")
    brain.answer("ok")
    assert "first line\nsecond line" in c.ask_box.answer.toPlainText()  # each line as typed, not run together


def test_back_up_and_bring_back_from_settings(companion, tmp_path):
    """M7-09 and M1B's note 11: Settings' Back up writes the zip and says what's in it; Bring back checks a backup,
    says what's in it to confirm, puts it in place and reads everything again."""
    c = companion
    out_of_the_way(c)
    c.memory.add("I use Arch")
    c.memory.save()
    c.reminders.add(time.time() + 3600, "renew the domain")
    c.save()
    zipped = tmp_path / "chatmon-backup.zip"
    c._back_up_to(zipped, with_chats=False)
    assert zipped.exists() and until(lambda: c.stage.bubble.title == "Backed up")
    assert "1 thing remembered" in c.stage.bubble.doc.toPlainText() and "Keys are never in a backup" in c.stage.bubble.doc.toPlainText()
    c.stage.dismiss_message()
    c.memory.clear()
    c.reminders.items.clear()
    c.save()
    (tmp_path / "not-a-backup.zip").write_bytes(b"nonsense")
    c._offer_restore(tmp_path / "not-a-backup.zip")
    assert until(lambda: c.stage.bubble.title == "That backup can't be used") and c.memory.texts() == []  # nothing changed
    c.stage.dismiss_message()
    c._offer_restore(zipped)
    assert until(lambda: c.stage.bubble.title == "Bring this backup back?") and labels(c) == ["Bring it back", "Not now"]
    assert c.stage.press_button("Bring it back")
    assert c.memory.texts() == ["I use Arch"] and [r.text for r in c.reminders.upcoming()] == ["renew the domain"]  # read again
    assert until(lambda: c.stage.bubble.title == "Backup brought back")


# -- M4A: what the platform says, heard as it changes


def test_reduced_motion_contrast_and_screen_readers_are_heard_as_they_change(companion):
    """M4A's Desk says when reduced motion or high contrast may have changed, and when a screen reader starts or stops:
    applied at once, no longer at the next 30-second look."""
    from PyQt6.QtGui import QGuiApplication

    from chatmon import presence

    c = companion
    desk = presence.Desk(QGuiApplication.platformName())
    try:
        c._watch_desk(desk)
        c.desk.motion = True  # the readings stay the test's own (PretendDesk); the signal is the real Desk's
        desk.settings_changed.emit()
        assert c._reduce_motion and c.ask_box.reduced_motion
        c._reader_seen = time.monotonic()
        desk.screen_reader_changed.emit()
        assert c._reader_seen == float("-inf")  # looked for again at the next read-aloud
    finally:
        desk.close()


def test_on_macos_sleep_sleeping_displays_and_low_power_mode_are_heard(companion, monkeypatch):
    import types

    from chatmon import macnative

    c = companion
    handlers: dict[str, list] = {}

    def signal(name):
        return types.SimpleNamespace(connect=lambda handler: handlers.setdefault(name, []).append(handler))

    watcher = types.SimpleNamespace(**{n: signal(n) for n in ("slept", "screens_slept", "accessibility_changed", "low_power_changed")})
    monkeypatch.setattr(macnative, "WorkspaceWatcher", lambda: watcher)
    monkeypatch.setattr(macnative, "low_power_mode", lambda: True)
    old = getattr(c, "_lock_watcher", None)
    if old is not None and hasattr(old, "close"):
        old.close()  # this platform's own, let go of first
    monkeypatch.setattr(sys, "platform", "darwin")
    c._watch_screen_lock()
    assert c.stage.power_saving and c.ask_box.power_saving  # Low Power Mode, read once at start
    handlers["slept"][0](True)  # the Mac goes to sleep
    assert c.stage.drawing is False
    handlers["slept"][0](False)
    assert c.stage.drawing is True
    handlers["screens_slept"][0](True)  # the displays sleep: nothing drawn
    assert c.stage.drawing is False
    handlers["screens_slept"][0](False)
    handlers["low_power_changed"][0](False)
    assert not c.stage.power_saving
    c.desk.motion = True
    handlers["accessibility_changed"][0]()
    assert c._reduce_motion
    monkeypatch.undo()
    c._lock_watcher = None  # nothing of the stand-in's to close at quit


def test_on_linux_a_held_alert_is_urgent_unless_do_not_disturb_is_why_it_waits(companion, monkeypatch):
    from app_harness import PretendNotifier

    from chatmon import sysnotify

    c = companion
    c._notifier = PretendNotifier()
    monkeypatch.setattr(sys, "platform", "linux")
    c.desk.why_quiet, c.desk.is_covered = "a full-screen game", True
    c._check_quiet()
    r = c.reminders.add(time.time() - 1, "stretch")
    c._check_reminders()
    title, body, buttons, urgency, pressed = c._notifier.alerts[-1]
    assert (title, body, buttons, urgency) == ("Reminder", "Chatmon has something for you.", ["Done", "Snooze 10 min"], sysnotify.URGENCY_CRITICAL)
    pressed(0)  # Done, pressed on the notification
    assert c.reminders.get(r.id) is None
    c.desk.why_quiet = "Do Not Disturb"
    c._check_quiet()
    c.handle({"type": "event", "event": "needs-you", "source": "claude", "message": "Approve?"})
    assert c._notifier.alerts[-1][3] == sysnotify.URGENCY_NORMAL  # urgent would show through GNOME's Do Not Disturb


def test_chatmon_starts_in_the_language_set_before_any_window(companion, monkeypatch):
    """M8: the language setting is read as Chatmon starts, before a window is built; Settings keeps a change for the
    next start."""
    from PyQt6.QtNetwork import QLocalServer

    from chatmon import app as appmod, i18n

    c = companion
    c._apply_settings({"language": "de"})
    assert c.config["language"] == "de" and c.state.get("settings")["language"] == "de"
    chosen = []
    monkeypatch.setattr(i18n, "setup", lambda choice=None, folder=None: chosen.append(choice) or "de")
    built = []
    real_stage = appmod.Stage
    monkeypatch.setattr(appmod, "Stage", lambda *a, **k: built.append(list(chosen)) or real_stage(*a, **k))
    again = appmod.Companion(c.app, QLocalServer())  # the next start
    try:
        assert chosen == ["de"] and built == [["de"]]  # chosen before the stage (the first window) was made
    finally:
        again.quit()
