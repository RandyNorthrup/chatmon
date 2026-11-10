"""The whole companion, headless: build it, poke it, check it reacts."""

import os
import subprocess
import sys
import tempfile
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEventLoop, QTimer  # noqa: E402
from PyQt6.QtNetwork import QLocalServer  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMenu  # noqa: E402


def spin(seconds: float) -> None:
    loop = QEventLoop()
    QTimer.singleShot(int(seconds * 1000), loop.quit)
    loop.exec()


@pytest.fixture
def companion(tmp_path, monkeypatch):
    for var in ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "APPDATA"):
        monkeypatch.setenv(var, str(tmp_path / var))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    # socket paths are limited to ~100 characters, so keep this one short
    run = tempfile.mkdtemp(prefix="pc-", dir=None if sys.platform == "win32" else "/tmp")
    monkeypatch.setenv("XDG_RUNTIME_DIR", run)
    from chatmon import agents, app as appmod, paths
    from chatmon.settings import State

    monkeypatch.setattr(agents, "_run_json", lambda argv, what: [])  # never run a real agent's command line

    State(paths.state_file(), {"name": "Sparky", "x": 600}).save()
    qapp = QApplication.instance() or QApplication([])
    qapp.setQuitOnLastWindowClosed(False)
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    QLocalServer.removeServer(paths.server_name())
    assert server.listen(paths.server_name()), server.errorString()
    c = appmod.Companion(qapp, server)
    yield c
    c.quit()
    server.close()


def test_greets_and_reacts_to_agents(companion):
    c = companion
    spin(1.8)
    assert c.stage.message_visible() and "Sparky" in c.stage.bubble.title
    c.handle({"type": "event", "event": "working", "source": "claude", "message": ""})
    assert c.behavior.working_since is not None
    c.handle({"type": "event", "event": "needs-you", "source": "claude", "message": "Approve the deploy?"})
    assert c.behavior.alert and c.stage.bubble.title == "Claude needs you"
    # something else to say waits until the alert is answered
    c.handle({"type": "event", "event": "done", "source": "codex", "message": "All tests pass."})
    assert c.stage.bubble.title == "Claude needs you" and len(c._waiting) == 1
    c.handle({"type": "event", "event": "done", "source": "claude", "message": "Deployed."})
    assert not c.behavior.alert and c.behavior.working_since is None
    spin(0.6)
    assert c.stage.message_visible()


def test_a_hook_reaches_it(companion):
    """A separate process, as a hook would be, says something and hears back."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]);"
        "from chatmon import events;"
        "sys.exit(0 if events.send({'type': 'say', 'text': 'hello from a hook'}, timeout=5) else 1)"
    )
    proc = subprocess.Popen([sys.executable, "-c", code, root])
    deadline = time.monotonic() + 20
    while proc.poll() is None and time.monotonic() < deadline:
        spin(0.05)
    assert proc.returncode == 0
    spin(0.2)
    assert companion.stage.bubble.title == "Sparky" and "hello from a hook" in companion.stage.bubble.doc.toPlainText()


def test_local_commands_and_reminders(companion):
    c = companion
    c.open_ask()
    assert c.ask_box.isVisible()
    c.submit("remind me in 1 second to stretch")
    assert "stretch" in c.ask_box.answer.toPlainText()
    c.submit("status")
    assert "Brain:" in c.ask_box.answer.toPlainText()
    c.ask_box.dismiss()
    spin(5.5)
    assert c.behavior.alert and c.stage.bubble.title == "Reminder"
    c.stage.dismiss_message()
    assert not c.behavior.alert


def test_hide_menu_and_reload(companion):
    c = companion
    c.set_hidden(True)
    spin(1.0)
    assert c.behavior.hidden
    c.set_hidden(False)
    c._fill_menu()
    labels = [a.text() for a in c.menu.actions() if a.text()]
    assert labels[0] == "Ask Sparky…" and "Quit" in labels
    c.reload()
    assert c.stage.message_visible()


def test_the_tray_menu_is_filled_before_anyone_opens_it(companion):
    """D-Bus trays (Waybar and other StatusNotifierItem hosts) read the menu
    before they ask for it to open, so it can't wait for aboutToShow."""
    c = companion
    labels = [a.text() for a in c.menu.actions() if a.text()]
    assert "Hide (peek now and then)" in labels and "Quit" in labels
    c.set_hidden(True)
    spin(0.1)
    assert "Come out" in [a.text() for a in c.menu.actions()]
    c.handle({"type": "remind", "text": "in 30m to stretch"})
    spin(0.1)
    assert any(a.text().startswith("Reminders (1)") for a in c.menu.actions())


def test_a_window_manager_cant_close_the_stage_or_strand_the_ask_box(companion):
    from PyQt6.QtWidgets import QWidget

    c = companion
    window = c.stage.surface
    if isinstance(window, QWidget):
        QWidget.close(window)  # what Super+C does
        assert window.isVisible()
    closed = []
    c.ask_box.closed.connect(lambda: closed.append(True))
    c.open_ask()
    QWidget.close(c.ask_box)
    assert not c.ask_box.isVisible() and closed


def test_picking_a_companion_swaps_its_sprites_at_once(companion):
    from chatmon import companions

    c = companion
    assert c._companion().id == "penguin" and c.sprites is c.stage.sprites
    penguin_frame = c.sprites.frame("idle", 0, False).image
    c._fill_menu()
    menu = next(a.menu() for a in c.menu.actions() if a.text() == "Companion")
    labels = [a.text() for a in menu.actions()]
    assert labels == [x.label for x in companions.COMPANIONS.values()]
    assert [a.text() for a in menu.actions() if a.isChecked()] == ["Electric penguin"]

    next(a for a in menu.actions() if a.text() == "Ghost rabbit").trigger()
    assert c._companion().id == "ghost-rabbit" and c.state.get("companion") == "ghost-rabbit"
    assert c.stage.sprites is c.sprites and c.sprites.frame("idle", 0, False).image != penguin_frame
    assert c.behavior.anims == c.sprites.anims()
    c.state.set("name", "")
    assert c.name == "Rabbit"  # until it is named, it answers to what it is
    c.state.set("name", "Sparky")
    for anim in ("hop", "beam", "wave"):  # it carries on with the new strips: reactions, hiding and peeking
        c.behavior.react(anim, c._now())
        spin(0.25)
        assert c.stage._frame.anim in c.sprites.anims()
    c.set_hidden(True)
    spin(0.4)
    c.set_hidden(False)
    spin(0.4)
    assert c.stage._frame.anim in c.sprites.anims()

    from chatmon.settings import State

    assert State.load().get("companion") == "ghost-rabbit"  # remembered for next time
    c.state.set("companion", "no-such-creature")
    c.reload()
    assert c._companion().id == "penguin" and c.sprites.frame("idle", 0, False).image == penguin_frame


def test_bubbles_match_the_companion_unless_a_style_was_chosen(companion):
    c = companion
    assert c._bubble_style_name() == "match" and c._bubble_style().name == "electric"
    c._pick_companion("fire-red-panda")
    assert c._bubble_style().name == "fire" and c.stage.bubble.style.name == "fire" and c.ask_box.style.name == "fire"
    c._fill_menu()
    menu = next(a.menu() for a in c.menu.actions() if a.text() == "Bubble style")
    assert [a.text() for a in menu.actions() if a.isChecked() and a.text() != "Animate bubbles"] == ["Match companion (fire)"]

    next(a for a in menu.actions() if a.text() == "Leaf").trigger()  # a style chosen by name wins
    assert c._bubble_style().name == "leaf" and c.stage.bubble.style.name == "leaf"
    c._pick_companion("fairy-axolotl")
    assert c._bubble_style().name == "leaf"

    c._pick_style("match")
    assert c._bubble_style().name == "fairy" and c.ask_box.style.name == "fairy"
    c.state.set("bubble_style", None)  # settings that already name a style keep it
    c.config["bubble_style"] = "ghost"
    assert c._bubble_style().name == "ghost"
    c.config["bubble_style"] = "no-such-style"
    assert c._bubble_style().name == "fairy"


def test_first_run_after_the_rename_asks_about_plugin_agents(companion):
    """Claude Code may have dropped the old plugin before Chatmon could move it: say so, once."""
    c = companion
    c._renamed = True
    c._agents_known({"claude": "found", "muse": "not found", "codex": "found"})
    text = c.stage.bubble.doc.toPlainText()
    assert "Claude Code" in text and "Muse" not in text and "Codex" not in text and "AI agents" in text
    c.stage.dismiss_message()
    c._agents_known({"claude": "found"})
    assert not c.stage.message_visible()  # once


def test_the_greeting_never_covers_a_message_that_came_first(companion):
    """A hook's message can arrive before the greeting is due (1.5 s after start): it stays."""
    c = companion
    c.handle({"type": "say", "text": "Deploy finished."})
    spin(1.8)  # past when the greeting would show
    assert "Deploy finished." in c.stage.bubble.doc.toPlainText() and "Hi, I'm" not in c.stage.bubble.title


def test_brain_menu_sets_model_effort_and_thinking(companion, monkeypatch):
    c = companion
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    c._pick_brain("anthropic-api")
    menu = QMenu()
    c._brain_menu(menu)
    subs = {a.text().split(":")[0]: a.menu() for a in menu.actions() if a.menu()}
    assert {"Model", "Effort", "Thinking"} <= set(subs)

    def click(sub, starts):
        (action,) = [a for a in subs[sub].actions() if a.text().startswith(starts)]
        assert action.isEnabled(), action.text()
        action.trigger()

    click("Model", "claude-sonnet-5-5")
    click("Effort", "medium")
    off = [a for a in subs["Thinking"].actions() if a.text().startswith("Off")][0]
    assert off.isEnabled() is False and "always thinks" in off.text()  # still Opus 5.5 when the menu was made
    brain = c._brain()
    assert (brain.name, brain.model, brain.effort) == ("anthropic-api", "claude-sonnet-5-5", "medium")
    menu = QMenu()
    c._brain_menu(menu)
    subs = {a.text().split(":")[0]: a.menu() for a in menu.actions() if a.menu()}
    click("Thinking", "Off")  # Sonnet 5.5 can, at medium
    assert c._brain().thinking == "off" and c.state.get("brain_options")["anthropic-api"]["thinking"] == "off"
    c.submit("status")
    assert "claude-sonnet-5-5, effort medium, thinking off" in c.ask_box.answer.toPlainText()


def test_quits_when_asked(companion, monkeypatch):
    """`chatmon quit` (an installer about to update it): it answers first, then quits, saving as it goes."""
    quits = []
    monkeypatch.setattr(companion.app, "quit", lambda: quits.append(True))
    companion.handle({"type": "quit"})
    assert quits == []  # not under the sender: it hears back first
    spin(0.1)
    assert quits == [True]
