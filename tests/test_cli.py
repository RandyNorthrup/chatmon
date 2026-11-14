"""The command line: what each command does and says, and what it sends to the running chatmon.

What's sent goes through events.send (tested in test_events.py); here it's recorded instead, so these tests never
reach another Chatmon (on Windows every Chatmon in a session shares the hooks' pipe name). test_app_smoke.py checks
the companion's side: what it does with each message.
"""

import json
import sys
import time

import pytest

from chatmon import __version__, agents, cli, events, paths


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    """Settings, state and every agent's files live in a temporary home, and no agent's command line is found, so
    none is ever run (agents._run_json runs only what it finds)."""
    for var in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(var, str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / ".state"))
    for var in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "GEMINI_CLI_HOME", "GROK_HOME", "COPILOT_HOME", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(agents.shutil, "which", lambda name: None)  # no agent's command line is installed
    monkeypatch.setattr(paths, "windows_environment", lambda: False)  # PATH as the test has it
    return tmp_path


@pytest.fixture
def sent(monkeypatch):
    """What the CLI hands the running chatmon; `sent.running = False` makes it as if none were running."""

    class Sent(list):
        running = True

    out = Sent()

    def send(message, timeout=0.5):
        if out.running:
            out.append(message)
        return out.running

    monkeypatch.setattr(events, "send", send)
    return out


def test_help_version_and_what_it_doesnt_know(capsys):
    assert cli.main(["--help"]) == 0
    usage = capsys.readouterr().out
    for line in ("ask [TEXT]", "status", "remind WHEN [to] TEXT", "hooks connect AGENT|all", "notify [EVENT] [JSON]"):
        assert line in usage
    assert cli.main(["--version"]) == 0 and capsys.readouterr().out.strip() == __version__
    for wrong in (["frobnicate"], ["autostart"], ["autostart", "maybe"]):
        assert cli.main(wrong) == 2
        assert "usage: chatmon" in capsys.readouterr().err


def test_say_remind_and_quit_reach_the_running_chatmon(sent, capsys):
    assert cli.main(["say", "Deploy", "finished."]) == 0
    assert cli.main(["remind", "in", "20m", "to", "stretch"]) == 0
    assert cli.main(["quit"]) == 0
    assert sent == [{"type": "say", "text": "Deploy finished."}, {"type": "remind", "text": "in 20m to stretch"}, {"type": "quit"}]
    sent.running = False
    assert cli.main(["say", "hello"]) == 1
    assert "Chatmon isn't running" in capsys.readouterr().err


def test_a_reminder_it_cant_read_says_so_and_exits_2(sent, capsys):
    for words in (["sometime", "to", "stretch"], ["to", "call", "Sam"], []):
        assert cli.main(["remind", *words]) == 2
        err = capsys.readouterr().err
        assert "Couldn't tell when to remind you" in err and "chatmon remind in 20m to stretch" in err
    assert cli.main(["remind", "at", "3pm", "to", "call", "Sam"]) == 0
    assert sent == [{"type": "remind", "text": "at 3pm to call Sam"}]  # only the one it could read


def test_ask_opens_the_box_with_the_text_typed_in(sent, capsys):
    assert cli.main(["ask", "how", "do", "I", "rebase?"]) == 0
    assert cli.main(["ask"]) == 0
    assert sent == [{"type": "ask", "text": "how do I rebase?"}, {"type": "ask", "text": ""}]
    sent.running = False
    assert cli.main(["ask", "hi"]) == 1 and "Chatmon isn't running" in capsys.readouterr().err


@pytest.mark.skipif(sys.platform != "win32", reason="only Windows keeps a program you're not using from coming to the front")
def test_on_windows_ask_lets_chatmon_come_forward_before_sending(sent, monkeypatch):
    import ctypes

    order = []
    monkeypatch.setattr(ctypes.windll.user32, "AllowSetForegroundWindow", lambda pid: order.append(("allow", pid.value)) or 1)
    monkeypatch.setattr(events, "send", lambda message, timeout=0.5: order.append(("send", message["type"])) or True)
    assert cli.main(["ask", "hello"]) == 0
    assert order == [("allow", cli.ASFW_ANY), ("send", "ask")]


def test_letting_chatmon_come_forward_is_windows_only_and_never_fails():
    allowed = cli._let_chatmon_come_forward()  # the real call, on Windows: whether it took depends on the desktop
    assert isinstance(allowed, bool) and (allowed is False or sys.platform == "win32")


def test_status_says_whether_its_running_the_brain_reminders_and_agents(monkeypatch, capsys, home):
    from chatmon.settings import State

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    now = time.time()
    State(paths.state_file(), {
        "brain": "anthropic-api", "brain_options": {"anthropic-api": {"model": "claude-sonnet-5-5"}},
        "reminders": [{"due": now + 30 * 60 + 20, "text": "stretch", "kind": "reminder", "id": "a1"},
                      {"due": now + 600, "text": "pasta", "kind": "timer", "id": "b2"}],
    }).save()
    (home / ".gemini").mkdir()  # Gemini CLI's settings folder: found, not connected
    pinged = []
    monkeypatch.setattr(events, "deliver", lambda message, timeout=0.5: pinged.append(message) or events.ABSENT)
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert pinged == [{"type": "ping"}] and out.startswith("Chatmon isn't running.")
    assert "- Timer in 10 min: pasta" in out and "- Reminder in 30 min: stretch" in out
    assert out.index("pasta") < out.index("stretch")  # soonest first
    assert "- Brain: Anthropic API (claude-sonnet-5-5, effort low)" in out
    gemini = next(line for line in out.splitlines() if "Gemini CLI" in line)
    assert gemini.split() == ["Gemini", "CLI", "found"]
    assert next(line for line in out.splitlines() if "Codex" in line).endswith("not found")
    monkeypatch.setattr(events, "deliver", lambda message, timeout=0.5: events.SENT)
    assert cli.main(["status"]) == 0
    assert capsys.readouterr().out.startswith("Chatmon is running.")


def test_status_with_nothing_set_up(monkeypatch, capsys):
    monkeypatch.setattr(events, "deliver", lambda message, timeout=0.5: events.ABSENT)
    monkeypatch.setattr("chatmon.brains.reachable", lambda url, wait=True: False)  # no model server on this computer
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "- No reminders set" in out and "- Brain: none" in out and "- Agents:" in out


def test_hooks_lists_shows_connects_and_disconnects(capsys, home):
    assert cli.main(["hooks"]) == 0
    listed = capsys.readouterr().out
    assert all(agent.label in listed for agent in agents.AGENTS) and "Connect one with: chatmon hooks connect NAME" in listed
    assert cli.main(["hooks", "show", "gemini"]) == 0 and ".gemini" in capsys.readouterr().out
    assert cli.main(["hooks", "show", "any"]) == 0 and "Any other agent or script" in capsys.readouterr().out
    assert cli.main(["hooks", "connect", "all"]) == 0 and capsys.readouterr().out.strip() == "No coding agents found here."
    assert cli.main(["hooks", "disconnect", "all"]) == 0 and capsys.readouterr().out.strip() == "No coding agents are connected."

    (home / ".gemini").mkdir()
    assert cli.main(["hooks", "connect", "all"]) == 0  # every agent found here: Gemini CLI alone
    assert capsys.readouterr().out.startswith("Connected Gemini CLI")
    hooks = json.loads((home / ".gemini" / "settings.json").read_text())["hooks"]
    assert set(hooks) == {"BeforeAgent", "Notification", "AfterAgent"}
    assert cli.main(["hooks"]) == 0
    assert next(line for line in capsys.readouterr().out.splitlines() if "gemini" in line).split()[-1] == "connected"
    assert cli.main(["hooks", "disconnect", "all"]) == 0 and capsys.readouterr().out.startswith("Disconnected Gemini CLI")
    assert "hooks" not in json.loads((home / ".gemini" / "settings.json").read_text())


def test_hooks_says_what_it_cant_do(capsys, home):
    for wrong in (["hooks", "connect"], ["hooks", "frob", "gemini"], ["hooks", "disconnect"]):
        assert cli.main(wrong) == 2 and "usage: chatmon" in capsys.readouterr().err
    assert cli.main(["hooks", "connect", "nosuch"]) == 2
    err = capsys.readouterr().err
    assert "Unknown agent 'nosuch'" in err and "gemini" in err
    (home / ".gemini").mkdir()
    (home / ".gemini" / "settings.json").write_text("{not json")
    assert cli.main(["hooks", "connect", "gemini"]) == 1  # left alone, and said why
    assert "isn't valid JSON" in capsys.readouterr().err and (home / ".gemini" / "settings.json").read_text() == "{not json"
