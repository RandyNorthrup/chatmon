"""Windows: a hook reaching Chatmon's named pipe (winpipe.deliver). Pipe names are one namespace for the whole PC,
so whoever serves the name may not be your Chatmon: the hook opens the pipe for identification only, so even a
server that tries can't act as you, and tells a server that isn't you nothing.

Each test serves a pipe of its own, raw, from a thread of this process: a server that reads what it's sent,
then tries to take on the sender's identity, as a squatter would, and reports how far that got."""

import ctypes
import os
import sys
import threading
import uuid
from ctypes import wintypes

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="named pipes: Windows")

if sys.platform == "win32":
    from chatmon import events, paths, winpipe

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    for fn, res, args in (
        (kernel32.ConnectNamedPipe, wintypes.BOOL, [wintypes.HANDLE, ctypes.c_void_p]),
        (kernel32.ReadFile, wintypes.BOOL, [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]),
        (kernel32.WriteFile, wintypes.BOOL, [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]),
        (kernel32.GetCurrentThread, wintypes.HANDLE, []),
        (kernel32.CloseHandle, wintypes.BOOL, [wintypes.HANDLE]),
        (advapi32.ImpersonateNamedPipeClient, wintypes.BOOL, [wintypes.HANDLE]),
        (advapi32.RevertToSelf, wintypes.BOOL, []),
        (advapi32.OpenThreadToken, wintypes.BOOL, [wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, ctypes.POINTER(wintypes.HANDLE)]),
        (advapi32.GetTokenInformation, wintypes.BOOL, [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]),
    ):
        fn.restype, fn.argtypes = res, args

SECURITY_IDENTIFICATION_LEVEL = 1  # SECURITY_IMPERSONATION_LEVEL: Anonymous 0, Identification 1, Impersonation 2, Delegation 3
TOKEN_QUERY = 0x8
TOKEN_IMPERSONATION_LEVEL = 9  # TOKEN_INFORMATION_CLASS


@pytest.fixture
def pipe_name(monkeypatch):
    name = f"chatmon-test-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(paths, "server_name", lambda: name)
    return name


class Squatter(threading.Thread):
    """A pipe served from here, one instance at a time (the next made once the last client has gone): for each
    of `clients`, it reads what it's sent, tries to impersonate the sender, notes the level Windows allowed,
    and answers as Chatmon does."""

    def __init__(self, name: str, clients: int = 1, access: str | None = None):
        super().__init__(daemon=True)
        self.name, self.clients, self.received, self.levels = name, clients, [], []
        self.handles = [self._make(access)]
        self.ready = threading.Event()

    def _make(self, access):
        attributes = None
        if access:
            descriptor = ctypes.c_void_p()
            assert winpipe._ConvertStringSecurityDescriptorToSecurityDescriptor(access, 1, ctypes.byref(descriptor), None)
            attributes = ctypes.byref(winpipe._SecurityAttributes(ctypes.sizeof(winpipe._SecurityAttributes), descriptor, False))
        handle = winpipe._CreateNamedPipe(winpipe.full_name(self.name), winpipe.PIPE_ACCESS_DUPLEX, 0, 255, 4096, 4096, 0, attributes)
        assert handle not in (None, winpipe.INVALID_HANDLE_VALUE), ctypes.get_last_error()
        return handle

    def run(self):
        self.ready.set()
        for served in range(self.clients):
            if served:
                self.handles.append(self._make(None))
            handle = self.handles[-1]
            kernel32.ConnectNamedPipe(handle, None)  # returns once a client is there (or already was)
            buffer, got = ctypes.create_string_buffer(65536), wintypes.DWORD()
            if not kernel32.ReadFile(handle, buffer, len(buffer), ctypes.byref(got), None):
                self.received.append(b"")  # the client hung up without a word
                continue
            self.received.append(buffer.raw[: got.value])
            self.levels.append(self._impersonated_level(handle))
            kernel32.WriteFile(handle, events.ACK, len(events.ACK), ctypes.byref(got), None)

    @staticmethod
    def _impersonated_level(handle):
        if not advapi32.ImpersonateNamedPipeClient(handle):
            return f"refused ({ctypes.get_last_error()})"
        try:
            token = wintypes.HANDLE()
            if not advapi32.OpenThreadToken(kernel32.GetCurrentThread(), TOKEN_QUERY, True, ctypes.byref(token)):
                return f"no token ({ctypes.get_last_error()})"
            level, size = wintypes.DWORD(), wintypes.DWORD()
            ok = advapi32.GetTokenInformation(token, TOKEN_IMPERSONATION_LEVEL, ctypes.byref(level), ctypes.sizeof(level), ctypes.byref(size))
            kernel32.CloseHandle(token)
            return level.value if ok else f"unreadable ({ctypes.get_last_error()})"
        finally:
            advapi32.RevertToSelf()

    def close(self):
        for handle in self.handles:
            winpipe.release(handle)
        self.join(5)


def test_a_server_learns_who_you_are_but_can_never_act_as_you(pipe_name):
    server = Squatter(pipe_name)
    server.start()
    server.ready.wait()
    try:
        said = events.deliver({"type": "say", "text": "hello"}, timeout=5)
    finally:
        server.close()
    assert said == events.SENT
    assert events.parse_lines(server.received[0]) == [{"type": "say", "text": "hello"}]
    assert server.levels == [SECURITY_IDENTIFICATION_LEVEL]  # never Impersonation (2), what CreateFile grants by default


def test_a_pipe_someone_else_serves_is_told_nothing(pipe_name, monkeypatch):
    """Its server runs as someone else (here: a process that can't be looked into, as another user's can't)."""
    monkeypatch.setattr(winpipe, "_OpenProcess", lambda *args: None)
    server = Squatter(pipe_name)
    server.start()
    server.ready.wait()
    try:
        said = events.deliver({"type": "event", "event": "done", "message": "the secret plan"}, timeout=2)
    finally:
        server.close()
    assert said == events.FOREIGN and server.received == [b""] and server.levels == []


def test_a_busy_pipe_is_waited_for_not_taken_for_absent(pipe_name):
    """Its one instance taken by another hook: the next waits for it to be free, within its time."""
    server = Squatter(pipe_name, clients=2)
    first = winpipe._CreateFile(winpipe.full_name(pipe_name), winpipe.GENERIC_READ | winpipe.GENERIC_WRITE, 0, None,
                                winpipe.OPEN_EXISTING, winpipe.SECURITY_SQOS_PRESENT | winpipe.SECURITY_IDENTIFICATION, None)
    assert first not in (None, winpipe.INVALID_HANDLE_VALUE)
    server.start()
    server.ready.wait()
    hung_up = threading.Timer(0.3, lambda: winpipe._CloseHandle(first))  # the first hook says nothing and goes
    hung_up.start()
    try:
        said = events.deliver({"type": "show"}, timeout=5)
    finally:
        hung_up.join()
        server.close()
    assert said == events.SENT and server.received[0] == b"" and events.parse_lines(server.received[1]) == [{"type": "show"}]


def test_nothing_there_reads_absent_and_a_closed_door_foreign(pipe_name):
    assert events.deliver({"type": "show"}, timeout=0.2) == events.ABSENT
    server = Squatter(pipe_name, access="D:(A;;GA;;;SY)")  # only SYSTEM may open it: not your Chatmon
    try:
        assert events.deliver({"type": "show"}, timeout=0.2) == events.FOREIGN
    finally:
        for handle in server.handles:
            winpipe.release(handle)


def test_a_server_that_never_answers_doesnt_hold_the_hook(pipe_name):
    """It takes the message but never says ok: the hook gives up waiting for the answer in its time."""
    import time

    handle = winpipe._CreateNamedPipe(winpipe.full_name(pipe_name), winpipe.PIPE_ACCESS_DUPLEX, 0, 1, 4096, 4096, 0, None)
    try:
        start = time.monotonic()
        said = events.deliver({"type": "show"}, timeout=0.5)
        assert said == events.SENT and time.monotonic() - start < 3
    finally:
        winpipe.release(handle)
