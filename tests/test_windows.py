"""Windows only: the named pipe hooks reach Chatmon through, and running without a console."""

import ctypes
import os
import subprocess
import sys
import threading
import time
import uuid

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")

if sys.platform == "win32":
    from PyQt6.QtCore import QCoreApplication, QEventLoop
    from PyQt6.QtNetwork import QLocalServer

    from chatmon import agents, app as appmod, events, paths, winpipe


@pytest.fixture
def pipe_name(monkeypatch):
    """A pipe name of this test's own, never the real Chatmon's."""
    name = f"chatmon-test-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(paths, "server_name", lambda: name)
    return name


def listening(name):
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    assert server.listen(name), server.errorString()
    return server


def deliver_while_serving(server, message, timeout=2.0):
    """`events.deliver` from another thread, as a hook would, while this one serves the pipe and answers each
    line the way Chatmon does. Returns what deliver said and every byte that arrived."""
    said, received, clients = [], bytearray(), []
    sender = threading.Thread(target=lambda: said.append(events.deliver(message, timeout)))
    sender.start()
    deadline = time.monotonic() + 10
    while (sender.is_alive() or server.hasPendingConnections()) and time.monotonic() < deadline:
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
        while server.hasPendingConnections():
            clients.append(server.nextPendingConnection())
        for client in clients:
            data = bytes(client.readAll())
            if data:
                received.extend(data)
                client.write(events.ACK)
                client.flush()
    sender.join(1)
    return said[0], bytes(received)


def someone_elses_pipe(name, access="D:(A;;GA;;;WD)"):
    """A pipe of this name as another user might make it first: by default, open to anyone."""
    descriptor = ctypes.c_void_p()
    assert winpipe._ConvertStringSecurityDescriptorToSecurityDescriptor(access, 1, ctypes.byref(descriptor), None)
    attributes = winpipe._SecurityAttributes(ctypes.sizeof(winpipe._SecurityAttributes), descriptor, False)
    handle = winpipe._CreateNamedPipe(winpipe.full_name(name), winpipe.PIPE_ACCESS_DUPLEX, 0, 255, 4096, 4096, 0, ctypes.byref(attributes))
    winpipe._LocalFree(descriptor)
    assert handle not in (None, winpipe.INVALID_HANDLE_VALUE), ctypes.get_last_error()
    return handle


def as_if_another_user(monkeypatch):
    """Whatever is at the other end runs as someone else: like their processes, it can't be looked into."""
    monkeypatch.setattr(winpipe, "_OpenProcess", lambda *args: None)


# -- a hook sending to the pipe


def test_a_hook_still_reaches_your_own_chatmon(qapp, pipe_name):
    server = listening(pipe_name)
    try:
        said, received = deliver_while_serving(server, {"type": "say", "text": "hello"})
    finally:
        server.close()
    assert said == events.SENT
    assert events.parse_lines(received) == [{"type": "say", "text": "hello"}]


def test_never_tells_a_pipe_someone_else_serves(qapp, pipe_name, monkeypatch):
    server = listening(pipe_name)
    as_if_another_user(monkeypatch)
    try:
        said, received = deliver_while_serving(server, {"type": "event", "event": "done", "message": "the secret plan"})
    finally:
        server.close()
    assert said == events.FOREIGN and received == b""
    assert events.send({"type": "say", "text": "x"}, timeout=0.2) is False


def test_nothing_there_is_not_running(pipe_name):
    assert events.deliver({"type": "show"}, timeout=0.2) == events.ABSENT


def test_the_owner_checks_fail_closed():
    assert not winpipe.server_is_me(0) and not winpipe.client_is_me(0)
    assert not winpipe.server_is_me(0xDEAD) and not winpipe.client_is_me(0xDEAD)  # not a pipe at all


def test_a_hooks_own_process_is_you(qapp, pipe_name):
    """Both ends, looked at from the other: this process, so this user."""
    from PyQt6.QtNetwork import QLocalSocket

    server = listening(pipe_name)
    client = QLocalSocket()
    try:
        client.connectToServer(pipe_name)
        assert client.waitForConnected(1000)
        assert winpipe.server_is_me(int(client.socketDescriptor()))
        assert server.waitForNewConnection(1000)
        assert winpipe.client_is_me(int(server.nextPendingConnection().socketDescriptor()))
    finally:
        client.abort()
        server.close()


# -- Chatmon opening its pipe


def test_chatmon_claims_its_pipe_and_listens(qapp, pipe_name):
    server, problem = appmod.open_server()
    try:
        assert problem is None and server.isListening()
        assert winpipe.claim(pipe_name) is None  # it's taken: Qt's instances hold it once the claim is let go
        said, _ = deliver_while_serving(server, {"type": "show"})
        assert said == events.SENT
    finally:
        server.close()


def test_chatmon_wont_join_a_pipe_someone_else_holds(qapp, pipe_name, monkeypatch):
    squatter = someone_elses_pipe(pipe_name)
    as_if_another_user(monkeypatch)
    try:
        reached = events.deliver({"type": "show"}, timeout=0.2)
        assert reached == events.FOREIGN
        server, problem = appmod.open_server(reached)
        assert not server.isListening() and "Another user" in problem
        # Even when the first look found nothing (all its instances busy, say), the claim finds it taken.
        server, problem = appmod.open_server(events.ABSENT)
        assert not server.isListening() and "Another user" in problem
    finally:
        winpipe.release(squatter)


def test_a_pipe_that_turns_you_away_is_someone_elses(qapp, pipe_name):
    """Your own Chatmon always lets you in; a pipe only its maker's account (here, SYSTEM) may use doesn't."""
    squatter = someone_elses_pipe(pipe_name, access="D:(A;;GA;;;SY)")
    try:
        assert events.deliver({"type": "show"}, timeout=0.2) == events.FOREIGN
        server, problem = appmod.open_server(events.ABSENT)
        assert not server.isListening() and "Another user" in problem
    finally:
        winpipe.release(squatter)


def test_a_second_chatmon_just_says_hi(qapp, pipe_name):
    """Two started at once: the second finds the name taken, but by the first, which answers."""
    first = listening(pipe_name)
    try:
        result = []
        opener = threading.Thread(target=lambda: result.append(appmod.open_server(events.ABSENT)))
        opener.start()
        deadline = time.monotonic() + 10
        clients = []
        while opener.is_alive() and time.monotonic() < deadline:
            QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
            while first.hasPendingConnections():
                clients.append(first.nextPendingConnection())
            for client in clients:
                if bytes(client.readAll()):
                    client.write(events.ACK)
                    client.flush()
        opener.join(1)
        assert result == [(None, None)]
    finally:
        first.close()


# -- hooks written into agents' settings


def gemini_hooks(home):
    import json

    data = json.loads((home / ".gemini" / "settings.json").read_text(encoding="utf-8"))
    return [h["command"] for groups in data.get("hooks", {}).values() for g in groups for h in g["hooks"]]


def test_hooks_run_chatmon_by_name_and_are_found_again(tmp_path, monkeypatch):
    """Windows finds chatmon.EXE; hooks name it plainly, which every shell an agent uses can run."""
    monkeypatch.setenv("GEMINI_CLI_HOME", str(tmp_path))
    monkeypatch.setattr(agents.shutil, "which", lambda name: rf"C:\Users\Some One\.local\bin\{name}.EXE")
    gemini = agents.Gemini()
    gemini.connect()
    assert gemini.connected() and all(c.startswith("chatmon notify ") for c in gemini_hooks(tmp_path))
    gemini.connect()
    assert len(gemini_hooks(tmp_path)) == 3  # once each, not twice
    gemini.disconnect()
    assert not gemini.connected() and gemini_hooks(tmp_path) == []


def test_hooks_written_with_a_full_path_are_still_ours(tmp_path, monkeypatch):
    """What 0.4.0 wrote on Windows: the full path, in PATHEXT's capitals. Connected, and taken out again."""
    import json

    monkeypatch.setenv("GEMINI_CLI_HOME", str(tmp_path))
    old = r"C:\Users\me\.local\bin\chatmon.EXE notify done --source gemini --stdin"
    (tmp_path / ".gemini").mkdir()
    (tmp_path / ".gemini" / "settings.json").write_text(json.dumps({"hooks": {"AfterAgent": [{"hooks": [{"type": "command", "command": old}]}]}}))
    gemini = agents.Gemini()
    assert gemini.connected()
    gemini.disconnect()
    assert gemini_hooks(tmp_path) == []


def test_cline_scripts_have_a_bom_for_windows_powershell(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr(agents.shutil, "which", lambda name: None)  # not on PATH: the full path, which may not be ASCII
    monkeypatch.setattr(paths, "command_line", lambda windowless=False: [r"C:\Users\José\chatmon\python.exe", r"C:\Users\José\chatmon\bin\chatmon"])
    cline = agents.Cline()
    cline.config_path().mkdir(parents=True)
    cline.connect()
    raw = cline._file("TaskComplete").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf") and "José".encode() in raw and cline.connected()
    cline.disconnect()
    assert not cline.connected()


# -- command-line brains, which npm installs as .cmd files


def spin_until(done, seconds=15):
    deadline = time.monotonic() + seconds
    while not done() and time.monotonic() < deadline:
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
    return done()


def still_running(pid):
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
    if not handle:
        return False
    try:
        return kernel32.WaitForSingleObject(handle, 0) == 0x102  # WAIT_TIMEOUT: not finished
    finally:
        kernel32.CloseHandle(handle)


def test_cancelling_a_question_stops_the_tool_behind_its_cmd_file(qapp, tmp_path, monkeypatch):
    from chatmon import brains

    child = tmp_path / "child.pid"
    (tmp_path / "slowbrain.cmd").write_text(
        f'@"{sys.executable}" -c "import os, time; open(r\'{child}\', \'w\').write(str(os.getpid())); time.sleep(60)"\r\n', encoding="utf-8"
    )
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    asker = brains.Asker()
    asker.ask(brains.Brain(name="slow", type="command", label="Slow", command=["slowbrain"]), "", [], "hi", 60)
    assert spin_until(lambda: child.exists() and child.read_text())
    pid = int(child.read_text())
    assert still_running(pid)
    asker.cancel()
    assert spin_until(lambda: not still_running(pid), 10), "the tool the .cmd file started is still running"


def test_a_question_is_never_put_on_a_cmd_files_command_line(qapp, tmp_path, monkeypatch):
    from chatmon import brains

    (tmp_path / "argbrain.cmd").write_text("@echo %*\r\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    asker, said = brains.Asker(), []
    asker.answered.connect(lambda text: said.append(("answered", text)))
    asker.failed.connect(lambda text: said.append(("failed", text)))
    asker.ask(brains.Brain(name="args", type="command", label="Args", command=["argbrain", "--ask", "{prompt}"]), "", [], 'a" & echo INJECTED & "b', 10)
    assert spin_until(lambda: said)
    assert said[0][0] == "failed" and "cmd.exe" in said[0][1]


def test_the_menu_never_waits_to_see_if_model_servers_are_running(monkeypatch):
    """On Windows a port nobody listens on takes 2 s to say so; the menu answers at once and looks later."""
    from chatmon import brains

    looked = []
    def look(url, timeout):
        looked.append(url)
        brains._reachable[url] = (time.monotonic(), True)
        return True

    monkeypatch.setattr(brains, "_look", look)
    monkeypatch.setattr(brains, "_reachable", {})
    monkeypatch.setattr(brains, "_unsure", set())
    url = "http://localhost:11434/v1"
    assert brains.reachable(url, wait=False) is False and looked == [] and brains.unsure()
    assert brains.look_again() is True and looked == [url] and not brains.unsure()
    assert brains.reachable(url, wait=False) is True and looked == [url]  # now known, and fresh
    assert brains.look_again() is False


# -- a locked screen counts as a break


def test_hears_the_screen_lock_and_unlock(qapp):
    from ctypes import wintypes

    from PyQt6 import sip

    from chatmon import winlock

    heard = []
    watcher = winlock.LockWatcher(heard.append)
    try:
        def tell(wparam, hwnd=watcher.hwnd):
            msg = wintypes.MSG(hwnd, winlock.WM_WTSSESSION_CHANGE, wparam, 0)
            return watcher.nativeEventFilter(b"windows_generic_MSG", sip.voidptr(ctypes.addressof(msg)))

        assert tell(winlock.WTS_SESSION_LOCK) == (False, 0)  # never kept from Qt
        tell(winlock.WTS_SESSION_LOCK)  # Qt shows filters a posted message twice
        tell(0x5)  # a logon: not a lock
        tell(winlock.WTS_SESSION_UNLOCK, hwnd=12345)  # another window's
        tell(winlock.WTS_SESSION_UNLOCK)
        assert heard == [True, False]
    finally:
        watcher.close()


def test_hears_remote_disconnects_and_sleep(qapp):
    """A Remote Desktop session that disconnects doesn't lock, and sleep isn't a lock: both are time away."""
    import ctypes
    from ctypes import wintypes

    from PyQt6 import sip

    from chatmon import winlock

    away, slept = [], []
    watcher = winlock.LockWatcher(away.append, slept.append)
    try:
        def tell(message, wparam):
            msg = wintypes.MSG(watcher.hwnd, message, wparam, 0)
            return watcher.nativeEventFilter(b"windows_generic_MSG", sip.voidptr(ctypes.addressof(msg)))

        tell(winlock.WM_WTSSESSION_CHANGE, winlock.WTS_REMOTE_DISCONNECT)
        tell(winlock.WM_WTSSESSION_CHANGE, winlock.WTS_REMOTE_CONNECT)
        tell(winlock.WM_POWERBROADCAST, winlock.PBT_APMSUSPEND)
        tell(winlock.WM_POWERBROADCAST, winlock.PBT_APMSUSPEND)  # the same news twice: once
        tell(winlock.WM_POWERBROADCAST, winlock.PBT_APMRESUMEAUTOMATIC)
        tell(winlock.WM_POWERBROADCAST, 0x8013)  # PBT_POWERSETTINGCHANGE: not ours
        assert away == [True, False] and slept == [True, False]
    finally:
        watcher.close()


# -- no console windows


def test_runs_an_npm_installed_tool(tmp_path, monkeypatch):
    """npm installs command-line tools as .cmd files, which Windows only finds by their full name."""
    (tmp_path / "faketool.cmd").write_text('@echo {"ok": true, "args": "%1"}\r\n', encoding="utf-8")
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    assert agents._run_json(["faketool", "list"], "Fake tool") == {"ok": True, "args": "list"}


def test_autostart_runs_it_without_a_console_window(monkeypatch):
    found = {"chatmon": r"C:\Users\me\.local\bin\chatmon.exe", "chatmonw": r"C:\Users\me\.local\bin\chatmonw.exe"}
    monkeypatch.setattr(paths.shutil, "which", found.get)
    assert paths.command_line(windowless=True) == [found["chatmonw"]]
    assert paths.command_line() == [found["chatmon"]]  # hooks: the console one, whose output they read
    del found["chatmonw"]  # installed before there was a chatmonw: pythonw, never chatmon.exe
    command = paths.command_line(windowless=True)
    assert command[0].lower().endswith("pythonw.exe") and found["chatmon"] not in command


@pytest.fixture
def run_key(monkeypatch):
    """A registry key of the test's own, standing in for the real Run key."""
    import winreg

    from chatmon import autostart

    path = rf"Software\chatmon-test-{uuid.uuid4().hex[:8]}"
    winreg.CreateKey(winreg.HKEY_CURRENT_USER, path).Close()
    monkeypatch.setattr(autostart, "_RUN_KEY", path)
    yield path
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)


def registered(run_key):
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key) as key:
        return winreg.QueryValueEx(key, "Chatmon")[0]


def register(run_key, command):
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "Chatmon", 0, winreg.REG_SZ, command)


def test_autostart_from_before_chatmonw_moves_to_it(run_key, monkeypatch):
    from chatmon import autostart

    found = {"chatmon": r"C:\Users\Some One\.local\bin\chatmon.exe", "chatmonw": r"C:\Users\Some One\.local\bin\chatmonw.exe"}
    monkeypatch.setattr(paths.shutil, "which", found.get)
    register(run_key, f'"{found["chatmon"]}"')  # as 0.4.0 set it up
    assert autostart.refresh() and registered(run_key) == f'"{found["chatmonw"]}"'
    assert not autostart.refresh()  # once
    autostart.set_enabled(False)
    assert not autostart.refresh() and not autostart.enabled()  # off stays off


def test_autostart_you_set_up_yourself_is_left_alone(run_key, monkeypatch):
    from chatmon import autostart

    monkeypatch.setattr(paths.shutil, "which", {"chatmonw": r"C:\bin\chatmonw.exe"}.get)
    register(run_key, r"C:\tools\my-launcher.exe --chatmon")
    assert not autostart.refresh() and registered(run_key) == r"C:\tools\my-launcher.exe --chatmon"
    monkeypatch.setattr(paths.shutil, "which", lambda name: None)  # no chatmonw installed: nothing better to run
    register(run_key, r"C:\bin\chatmon.exe")
    assert not autostart.refresh() and registered(run_key) == r"C:\bin\chatmon.exe"


def test_without_a_console_it_keeps_a_log(tmp_path):
    """pythonw has no stdout or stderr; what Chatmon says about problems goes to a log file instead."""
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]);"
        "from chatmon import app; app._log_without_a_console();"
        "print('a warning', file=sys.stderr); sys.stderr.flush()"
    )
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pythonw):
        pytest.skip("no pythonw.exe next to this Python")
    env = dict(os.environ, APPDATA=str(tmp_path))
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    subprocess.run([pythonw, "-c", code, root], env=env, timeout=60, check=True)
    log = tmp_path / "chatmon" / "state" / "chatmon.log"
    assert "a warning" in log.read_text(encoding="utf-8")


def test_the_pipe_is_named_for_you_and_this_session(qapp):
    """Pipe names are one namespace for every session: yours carries your SID and the session's number."""
    import re

    from chatmon import paths, winpipe

    identity = winpipe.my_identity()
    assert re.fullmatch(r"S-1-5-[\d-]+-\d+", identity)
    assert paths.server_name() == f"chatmon-{identity}"


# -- PowerShell, as Chatmon really runs it


def test_a_script_with_quotes_reaches_powershell_whole():
    """-Command would strip its double quotes and run something else; -EncodedCommand doesn't."""
    import subprocess

    from chatmon import paths

    script = '[Console]::Out.Write("a|$("b" + "c")|d")'  # double quotes, inside and out
    out = subprocess.run(paths.powershell(script), capture_output=True, text=True, timeout=120)
    assert out.returncode == 0 and out.stdout == "a|bc|d", out.stderr


def test_the_updaters_signature_check_reads_a_real_signed_file():
    """What the updater asks Windows of an installer, asked of Microsoft's own signed PowerShell here."""
    import os
    from pathlib import Path

    from chatmon import updates

    signed = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    status, signer, issuer, usages = updates.windows_signer(signed)
    assert status == "Valid" and "Microsoft" in signer and "Microsoft" in issuer and "1.3.6.1.5.5.7.3.3" in usages  # code signing
    assert "isn't Randy Northrup's" in updates.verify(signed, updates.sha256(signed), updates.WINDOWS)  # Microsoft's, not his


def test_the_windows_update_check_runs_and_says_something_readable():
    import subprocess

    from chatmon import heads_up

    (check,) = heads_up.update_checks()
    out = subprocess.run(check.argv, capture_output=True, text=True, timeout=300)
    # It answers "<count>|<restart>", or, where the runner's Windows Update service won't search, fails plainly.
    assert check.count(out.stdout, out.returncode) is not None or out.returncode != 0, (out.stdout, out.stderr)
