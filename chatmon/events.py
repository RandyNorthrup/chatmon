"""The little protocol that lets hooks, scripts and a second launch talk to
the running companion: one JSON object per line over a local socket."""

from __future__ import annotations

import json
import os
import socket
import sys
import time
from typing import Any

from . import paths

# Set in the environment of the AI tools the companion itself runs, so their
# hooks don't make the penguin react to its own questions.
INTERNAL_ENV = "CHATMON_INTERNAL"

EVENTS = {
    "working": ("working", "start", "started", "busy", "thinking", "prompt"),
    "needs-you": ("needs-you", "needs_you", "attention", "permission", "input", "waiting", "notification", "alert"),
    "done": ("done", "stop", "stopped", "finished", "complete", "completed", "turn-complete"),
    "success": ("success", "celebrate", "passed", "merged"),
    "error": ("error", "failed", "failure"),
    "idle": ("idle", "reset", "clear", "end"),
}
_ALIASES = {alias: name for name, aliases in EVENTS.items() for alias in aliases}

# Event names in hook payloads: Claude Code's hook_event_name, Codex's notify
# type, and the BeforeAgent/AfterAgent style other CLIs use.
_PAYLOAD_EVENTS = {
    "UserPromptSubmit": "working",
    "Notification": "needs-you",
    "Stop": "done",
    "SessionEnd": "idle",
    "BeforeAgent": "working",
    "AfterAgent": "done",
    "agent-turn-complete": "done",
}

# Where agents put a human-readable message: Claude Code, Codex, Grok, Gemini. Never the prompt.
_MESSAGE_KEYS = ("message", "last-assistant-message", "last_assistant_message", "lastAssistantMessage", "prompt_response")


def normalize(name: str | None) -> str | None:
    if not name:
        return None
    return _ALIASES.get(name.strip().lower())


def event_from(
    event: str | None, payload: dict[str, Any] | None = None, *, source: str | None = None, message: str | None = None
) -> dict[str, Any] | None:
    """The message to send for a hook call, or None if there's nothing to say."""
    payload = payload or {}
    if payload.get("subagentType") or payload.get("subagent_type"):
        return None  # a helper inside the agent, not the agent you're talking to
    name = normalize(event)
    if name is None and event is None:
        hook = payload.get("hook_event_name") or payload.get("type")
        name = _PAYLOAD_EVENTS.get(str(hook)) if hook else None
    if name is None:
        return None
    if message is None:
        nested = payload.get("notification") if isinstance(payload.get("notification"), dict) else {}  # Cline
        for value in [payload.get(key) for key in _MESSAGE_KEYS] + [nested.get("message")]:
            if isinstance(value, str) and value.strip():
                message = value.strip()
                break
    return {"type": "event", "event": name, "source": source or "agent", "message": message or ""}


ACK = b"ok\n"  # the companion's reply to each message, so a sender knows it arrived
MAX_MESSAGE = 64 * 1024  # bytes; anything longer is dropped
_LIMITS = {"type": 20, "event": 20, "source": 40, "message": 2000, "text": 2000}


# What `deliver` found at the companion's address.
SENT = "sent"
ABSENT = "absent"  # nothing listening there: Chatmon isn't running
FOREIGN = "foreign"  # something run by another user holds the address; it was told nothing


def send(message: dict[str, Any], timeout: float = 0.5) -> bool:
    """Deliver a message to the running companion. False if it isn't running.

    Waits (up to `timeout`) for the companion to say it got the message
    before hanging up; on Windows, hanging up first can lose it."""
    return deliver(message, timeout) == SENT


def deliver(message: dict[str, Any], timeout: float = 0.5) -> str:
    """Like `send`, but says what it found: SENT, ABSENT or FOREIGN."""
    data = (json.dumps(message) + "\n").encode("utf-8")
    if sys.platform == "win32":
        return _send_pipe(data, timeout)
    name = paths.server_name()
    try:
        if os.stat(name).st_uid != os.getuid():
            return FOREIGN  # someone else's socket: never tell them what our agents are doing
        with _connect(name, timeout) as sock:
            sock.sendall(data)
            try:
                sock.recv(len(ACK))
            except OSError:
                pass  # sent; the companion was just slow to answer
        return SENT
    except OSError:
        return ABSENT


QUEUE_FULL_WAIT = 1.0  # seconds a sender keeps trying while the companion's queue of new connections is full


# A full queue of connections: EAGAIN on Linux; macOS and the BSDs refuse instead, as they do when nobody
# listens (a socket file left by a crash), so there a refusal is tried again for a moment too.
_QUEUE_FULL: tuple[type[OSError], ...] = (BlockingIOError,) if sys.platform.startswith("linux") else (BlockingIOError, ConnectionRefusedError)


def _connect(name: str, timeout: float) -> socket.socket:
    """A connection to the companion's socket. When its queue of connections not yet taken is full (about
    fifty, while it's busy drawing: several agents' hooks at once), that isn't nobody there: try again for
    a moment instead of saying it isn't running. No socket at all fails at once, as before."""
    deadline = time.monotonic() + QUEUE_FULL_WAIT
    while True:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect(name)
            return sock
        except _QUEUE_FULL:
            sock.close()
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.02)
        except BaseException:
            sock.close()
            raise


def _send_pipe(data: bytes, timeout: float) -> str:
    from PyQt6.QtNetwork import QLocalSocket

    from . import winpipe

    ms = int(timeout * 1000)
    sock = QLocalSocket()
    sock.connectToServer(paths.server_name())
    if not sock.waitForConnected(ms):
        # Your own Chatmon always lets you in, so a pipe that turns you away is someone else's.
        return FOREIGN if sock.error() == QLocalSocket.LocalSocketError.SocketAccessError else ABSENT
    # Pipe names are first come, first served, for every user on the PC: check whose this one is
    # before saying anything, on the very handle we'd say it through.
    if not winpipe.server_is_me(int(sock.socketDescriptor())):
        sock.abort()
        return FOREIGN
    sock.write(data)
    sock.waitForBytesWritten(ms)
    sock.waitForReadyRead(ms)
    sock.disconnectFromServer()
    return SENT


def clean(message: dict[str, Any]) -> dict[str, Any]:
    """Only the fields the companion uses, as strings of sensible length."""
    out = {}
    for key, limit in _LIMITS.items():
        value = message.get(key)
        if isinstance(value, str):
            out[key] = value[:limit]
    return out


def parse_lines(data: bytes) -> list[dict[str, Any]]:
    out = []
    for line in data.decode("utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except (ValueError, RecursionError):  # not JSON, or nested too deep to read
            continue
        if isinstance(value, dict):
            out.append(value)
    return out
