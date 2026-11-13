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
    monkeypatch.setattr(paths, "SOCKET_PATH_MAX", 4096)  # pytest's own folders are long enough to need the next test's way
    sock = paths.socket_path()
    assert tmp_path in sock.parents and "/tmp/" not in str(sock).replace(str(tmp_path), "")
    assert (sock.parent.stat().st_mode & 0o777) == 0o700


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS's temporary folder of your own")
def test_a_long_user_name_puts_the_socket_in_your_own_temporary_folder(monkeypatch):
    """A socket's address is 104 bytes on macOS: past about 37 characters of user name, the usual path won't
    fit. Then it's in the temporary folder macOS keeps for you alone, the same for every process of yours."""
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.setattr(paths.Path, "home", lambda: Path("/Users") / ("a" * 40))
    sock = paths.socket_path()
    assert len(os.fsencode(sock)) <= paths.SOCKET_PATH_MAX and sock.name == "chatmon.sock"
    folder = sock.parent.stat()
    assert folder.st_uid == os.getuid() and folder.st_mode & 0o777 == 0o700
    assert paths.socket_path() == sock  # the CLI and hooks work it out the same way


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
    """The installers' Chatmon has no Python to run it with: hooks and autostart get its own programs."""
    exe = tmp_path / ("chatmon.exe" if sys.platform == "win32" else "Chatmon")
    monkeypatch.setattr(paths, "frozen", lambda: True)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(paths.shutil, "which", lambda name: "/somewhere/else/" + name)  # whatever else is on PATH
    if sys.platform == "win32":
        assert paths.command_line() == [str(tmp_path / "chatmon.exe")]
        assert paths.command_line(windowless=True) == [str(tmp_path / "chatmonw.exe")]
    else:
        assert paths.command_line() == paths.command_line(windowless=True) == [str(exe)]


def test_run_from_source_it_is_not_frozen():
    assert not paths.frozen()


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


def test_a_mac_app_started_from_finder_gets_your_login_shells_environment(tmp_path, monkeypatch):
    """launchd gives it /usr/bin:/bin and no keys; your shell would have /opt/homebrew/bin and OPENAI_API_KEY."""
    import sys

    if sys.platform == "win32":
        pytest.skip("a pretend shell script: not on Windows")
    from chatmon import paths

    shell = tmp_path / "zsh"
    shell.write_text(
        "#!/bin/sh\nprintf '%s\\0' --chatmon-environment--\n"
        "printf 'PATH=/opt/homebrew/bin:/usr/bin:/bin\\0OPENAI_API_KEY=from-zshrc\\0HOME=/elsewhere\\0PWD=/somewhere\\0'\n"
    )
    shell.chmod(0o755)
    monkeypatch.setattr(paths.sys, "platform", "darwin")
    monkeypatch.setenv("SHELL", str(shell))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    # What's taken from the shell, not how long a shell gets: a loaded machine can take longer than the app's
    # 4 s just to start this one (#17), and then only the usual folders are added.
    adopted = paths.login_environment(timeout=60)
    import os

    assert os.environ["PATH"].split(os.pathsep)[0] == "/opt/homebrew/bin" and "/usr/bin" in os.environ["PATH"]
    assert os.environ["OPENAI_API_KEY"] == "from-zshrc" and os.environ["HOME"] == str(tmp_path)  # nothing set is changed
    assert "PWD" not in adopted and "OPENAI_API_KEY" in adopted


def test_without_an_answer_from_the_shell_the_usual_folders(tmp_path, monkeypatch):
    from chatmon import paths

    monkeypatch.setattr(paths.sys, "platform", "darwin")
    monkeypatch.setenv("SHELL", str(tmp_path / "no-such-shell"))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    paths.login_environment()
    import os

    assert os.environ["PATH"].startswith("/opt/homebrew/bin" + os.pathsep + "/usr/local/bin")


def test_only_one_chatmon_holds_the_lock(tmp_path, monkeypatch):
    """Two started at once: the second finds the lock held, says "show" to the first, and doesn't take its socket."""
    import subprocess
    import sys

    if sys.platform == "win32":
        pytest.skip("Windows: the pipe's first instance does this")
    from chatmon import app as appmod

    lock = str(tmp_path / "chatmon.sock.lock")
    holder = subprocess.Popen(
        [sys.executable, "-c", "import fcntl, os, sys, time; fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT); fcntl.flock(fd, fcntl.LOCK_EX); print('held', flush=True); time.sleep(30)", lock],
        stdout=subprocess.PIPE, text=True,
    )
    try:
        assert holder.stdout.readline().strip() == "held"
        assert appmod._hold_instance_lock(lock) is False
    finally:
        holder.kill()
        holder.wait()
    monkeypatch.setattr(appmod, "_instance_lock", None)
    assert appmod._hold_instance_lock(lock) is True and appmod._instance_lock is not None
    os.close(appmod._instance_lock)


def test_the_login_shell_says_only_what_follows_its_marker_and_nothing_that_changes_chatmon(tmp_path, monkeypatch):
    import sys

    if sys.platform == "win32":
        pytest.skip("a pretend shell script: not on Windows")
    from chatmon import paths

    shell = tmp_path / "zsh"
    shell.write_text(
        "#!/bin/sh\n"
        "echo 'Welcome to my shell! NOTICE=from-motd'\n"  # what a startup file prints
        "printf '%s\\0' --chatmon-environment--\n"
        "printf 'PATH=/opt/homebrew/bin:/usr/bin\\0DYLD_INSERT_LIBRARIES=/tmp/evil.dylib\\0QT_QPA_PLATFORM=offscreen\\0"
        "XDG_RUNTIME_DIR=/tmp/shared\\0MY_API_KEY=k\\0'\n"
    )
    shell.chmod(0o755)
    monkeypatch.setattr(paths.sys, "platform", "darwin")
    monkeypatch.setenv("SHELL", str(shell))
    monkeypatch.setenv("PATH", "/usr/bin")
    for name in ("DYLD_INSERT_LIBRARIES", "QT_QPA_PLATFORM", "XDG_RUNTIME_DIR", "MY_API_KEY", "NOTICE"):
        monkeypatch.delenv(name, raising=False)
    adopted = paths.login_environment()
    assert "MY_API_KEY" in adopted and os.environ["MY_API_KEY"] == "k"
    for name in ("DYLD_INSERT_LIBRARIES", "QT_QPA_PLATFORM", "XDG_RUNTIME_DIR", "NOTICE"):
        assert name not in os.environ, name


def test_a_shell_that_never_answers_is_stopped_whole(tmp_path, monkeypatch):
    import sys
    import time

    if sys.platform == "win32":
        pytest.skip("a pretend shell script: not on Windows")
    from chatmon import paths

    shell = tmp_path / "zsh"
    shell.write_text("#!/bin/sh\nsleep 60 &\nsleep 60\n")
    shell.chmod(0o755)
    monkeypatch.setattr(paths.sys, "platform", "darwin")
    monkeypatch.setenv("SHELL", str(shell))
    started = time.monotonic()
    paths.login_environment(timeout=0.5)
    assert time.monotonic() - started < 5


def test_the_lock_is_never_followed_through_a_link_nor_taken_for_held_on_an_odd_error(tmp_path, monkeypatch):
    import sys

    if sys.platform == "win32":
        pytest.skip("Windows: the pipe's first instance does this")
    from chatmon import app as appmod

    target = tmp_path / "someone-elses"
    target.write_text("")
    link = tmp_path / "chatmon.sock.lock"
    link.symlink_to(target)
    monkeypatch.setattr(appmod, "_instance_lock", None)
    assert appmod._hold_instance_lock(str(link)) is True and appmod._instance_lock is None  # not through the link
