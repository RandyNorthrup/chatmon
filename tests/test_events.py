import json
import os
import sys
from pathlib import Path

import pytest

from chatmon import cli, events, paths


def test_aliases():
    assert events.normalize("Stop") == "done"
    assert events.normalize("needs_you") == "needs-you"
    assert events.normalize("nonsense") is None


def test_claude_code_hook_payloads():
    note = events.event_from(None, {"hook_event_name": "Notification", "message": "Claude needs your permission to use Bash"}, source="claude")
    assert note == {"type": "event", "event": "needs-you", "source": "claude", "message": "Claude needs your permission to use Bash"}
    assert events.event_from(None, {"hook_event_name": "UserPromptSubmit", "prompt": "hi"})["event"] == "working"
    assert events.event_from(None, {"hook_event_name": "Stop"})["event"] == "done"
    assert events.event_from(None, {"hook_event_name": "PreToolUse"}) is None


def test_codex_notify_payload():
    payload = {"type": "agent-turn-complete", "last-assistant-message": "All tests pass."}
    msg = events.event_from(None, payload, source="codex")
    assert (msg["event"], msg["message"]) == ("done", "All tests pass.")


def test_explicit_event_wins_and_unknown_is_dropped():
    assert events.event_from("working", {"hook_event_name": "Stop"})["event"] == "working"
    assert events.event_from("bogus") is None


def test_parse_lines_skips_garbage():
    data = b'{"type": "show"}\nnot json\n[1]\n{"type": "say", "text": "hi"}\n'
    assert [m["type"] for m in events.parse_lines(data)] == ["show", "say"]


def test_notify_sends_codex_style_trailing_json(monkeypatch):
    sent = []
    monkeypatch.setattr(events, "send", lambda m, timeout=0.5: sent.append(m) or True)
    monkeypatch.delenv(events.INTERNAL_ENV, raising=False)
    payload = json.dumps({"type": "agent-turn-complete", "last-assistant-message": "Done!"})
    assert cli.notify(["--source", "codex", payload]) == 0
    assert sent == [{"type": "event", "event": "done", "source": "codex", "message": "Done!"}]


def test_notify_ignores_the_companions_own_questions(monkeypatch):
    sent = []
    monkeypatch.setattr(events, "send", lambda m, timeout=0.5: sent.append(m) or True)
    monkeypatch.setenv(events.INTERNAL_ENV, "1")
    assert cli.notify(["done", "--source", "claude"]) == 0
    assert sent == []


def test_send_without_a_running_companion(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    assert events.send({"type": "show"}) is False


def test_clean_keeps_only_known_short_strings():
    big = "x" * 10_000
    cleaned = events.clean({"type": "say", "text": big, "evil": {"nested": 1}, "source": 5})
    assert cleaned == {"type": "say", "text": "x" * 2000}


def test_notify_never_waits_on_an_open_stdin(monkeypatch):
    import os
    import time

    sent = []
    monkeypatch.setattr(events, "send", lambda m, timeout=0.5: sent.append(m) or True)
    monkeypatch.delenv(events.INTERNAL_ENV, raising=False)
    read_end, write_end = os.pipe()  # a hook runner that never closes stdin
    monkeypatch.setattr("sys.stdin", os.fdopen(read_end, "r"))
    started = time.monotonic()
    assert cli.notify(["done", "--source", "x", "--stdin"]) == 0
    assert time.monotonic() - started < 2 and sent[0]["event"] == "done"
    os.close(write_end)


def test_payload_messages_from_other_agents():
    assert events.event_from("done", {"lastAssistantMessage": "grok says"})["message"] == "grok says"
    assert events.event_from("done", {"prompt_response": "gemini says"})["message"] == "gemini says"
    assert events.event_from("needs-you", {"notification": {"message": "cline says"}})["message"] == "cline says"
    assert events.event_from("working", {"prompt": "my secret prompt"})["message"] == ""


def test_helpers_inside_an_agent_are_ignored():
    assert events.event_from("done", {"subagentType": "explore"}) is None


def test_borrowed_claude_hooks_are_relabelled(monkeypatch):
    monkeypatch.setenv("GROK_HOOK_EVENT", "stop")
    assert cli._real_source("claude") == "grok" and cli._real_source("codex") == "codex"
    monkeypatch.delenv("GROK_HOOK_EVENT")
    assert cli._real_source("claude") == "claude"


@pytest.mark.skipif(sys.platform == "win32", reason="a named pipe there")
def test_without_a_runtime_folder_the_socket_is_in_a_private_one(tmp_path, monkeypatch):
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(paths.Path, "home", lambda: tmp_path)
    sock = paths.socket_path()
    assert tmp_path in sock.parents and "/tmp/" not in str(sock).replace(str(tmp_path), "")
    assert (sock.parent.stat().st_mode & 0o777) == 0o700


@pytest.mark.skipif(sys.platform == "win32", reason="a named pipe there")
def test_never_sends_to_a_socket_someone_else_owns(tmp_path, monkeypatch):
    import socket as sockets

    import tempfile

    short = Path(tempfile.mkdtemp(prefix="cm-", dir="/tmp"))  # a socket path must be short (104 bytes on macOS)
    path = short / "s.sock"
    server = sockets.socket(sockets.AF_UNIX, sockets.SOCK_STREAM)
    server.bind(str(path))
    server.listen(1)
    monkeypatch.setattr(paths, "server_name", lambda: str(path))
    try:
        monkeypatch.setattr(events.os, "getuid", lambda: os.stat(path).st_uid + 1)  # as if it were another user's
        assert events.send({"type": "say", "text": "secret"}, timeout=0.2) is False
        server.settimeout(0.2)
        with pytest.raises(OSError):
            server.accept()  # nothing ever connected
    finally:
        server.close()


def test_garbage_on_the_socket_is_dropped_not_fatal():
    deep = ("[" * 65000).encode()
    assert events.parse_lines(deep + b"\n" + b'{"type": "say", "text": "hi"}\n') == [{"type": "say", "text": "hi"}]


def test_installed_from_a_package_it_runs_its_own_programs(monkeypatch, tmp_path):
    """PyInstaller's Chatmon has no Python to run it with: hooks and autostart get its own programs."""
    exe = tmp_path / ("chatmon.exe" if sys.platform == "win32" else "Chatmon")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(paths.shutil, "which", lambda name: "/somewhere/else/" + name)  # whatever else is on PATH
    if sys.platform == "win32":
        assert paths.command_line() == [str(tmp_path / "chatmon.exe")]
        assert paths.command_line(windowless=True) == [str(tmp_path / "chatmonw.exe")]
    else:
        assert paths.command_line() == paths.command_line(windowless=True) == [str(exe)]


def test_dll_search_is_only_touched_when_frozen(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    paths.restore_dll_search()  # nothing to do, on any platform


def test_quit_says_when_nothing_is_running(monkeypatch, capsys):
    monkeypatch.setattr(events, "send", lambda m, timeout=0.5: False)
    monkeypatch.setattr(paths, "migrate", lambda: [])  # never the real settings folders
    assert cli.main(["quit"]) == 1 and "isn't running" in capsys.readouterr().err


@pytest.mark.skipif(sys.platform == "win32", reason="a named pipe there")
def test_a_full_queue_of_connections_is_waited_out_not_taken_for_absence(monkeypatch):
    """Several agents' hooks at once while the companion is busy drawing fill its queue of connections it
    hasn't taken yet: a sender then gets EAGAIN, which means wait a moment, not that nobody is there."""
    import socket as sockets
    import tempfile
    import threading
    import time

    folder = Path(tempfile.mkdtemp(prefix="cm-", dir="/tmp"))
    path = str(folder / "s.sock")
    server = sockets.socket(sockets.AF_UNIX, sockets.SOCK_STREAM)
    server.bind(path)
    server.listen(0)
    monkeypatch.setattr(paths, "server_name", lambda: path)
    fillers = []
    try:
        for _ in range(64):  # fill the queue, as a burst of hooks would
            filler = sockets.socket(sockets.AF_UNIX, sockets.SOCK_STREAM)
            filler.setblocking(False)
            try:
                filler.connect(path)
            except OSError:  # full: EAGAIN on Linux, refused on macOS
                filler.close()
                break
            fillers.append(filler)
        got = []

        def catch_up():  # the companion, done drawing, takes its connections and answers
            time.sleep(0.3)
            server.settimeout(2)
            for _ in range(len(fillers) + 1):
                conn, _ = server.accept()
                conn.settimeout(1)
                try:
                    data = conn.recv(1000)
                    if data:
                        got.append(data)
                        conn.sendall(events.ACK)
                except OSError:
                    pass
                conn.close()

        helper = threading.Thread(target=catch_up)
        helper.start()
        assert events.deliver({"type": "say", "text": "made it"}) == events.SENT
        helper.join()
        assert any(b"made it" in data for data in got)
    finally:
        for filler in fillers:
            filler.close()
        server.close()

    started = time.monotonic()
    monkeypatch.setattr(paths, "server_name", lambda: str(folder / "nobody.sock"))
    assert events.deliver({"type": "say", "text": "hi"}) == events.ABSENT and time.monotonic() - started < 0.5
