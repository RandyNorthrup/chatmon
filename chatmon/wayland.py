"""Just enough of the Wayland wire protocol for the stage's overlay surface.

Qt (as shipped with PyQt6) can't make a layer-shell surface, the only way a
Wayland client gets an always-on-top overlay that clicks pass through. So the
stage opens a second, small connection to the compositor of its own and speaks
the protocol directly: no libwayland, no new dependencies.

This module is the wire format and the connection; layer.py builds the surface
on it. Opcodes and signatures follow wayland.xml and the protocol XML files
(tests/test_wayland.py checks them against the files when they're installed).
"""

from __future__ import annotations

import array
import collections
import os
import select
import socket
import struct
import time
from typing import Callable

DISPLAY_ID = 1
HEADER = struct.Struct("<II")
MAX_FDS = 28  # per recvmsg, as libwayland
_CLOEXEC = getattr(socket, "MSG_CMSG_CLOEXEC", 0)  # file descriptors we're sent never leak into the AI tools we run

# A request or event signature is a string of argument codes:
#   i int, u uint, f fixed (a float on our side), s string, o object id (0 or
#   None for null), n new id, a array (bytes), h file descriptor. An event's
#   file descriptors travel beside its bytes: its handler takes them with
#   Connection.take_fd(), in order.


class WaylandError(Exception):
    pass


def _pad(n: int) -> int:
    return (n + 3) & ~3


_FIXED: dict[str, struct.Struct | None] = {}
_MANY: dict[tuple[str, int], struct.Struct] = {}  # a batch of one request (`Connection.requests`), by its length  # a signature of fixed-size arguments only: its whole request, packed at once


def _fixed(sig: str) -> struct.Struct | None:
    if sig not in _FIXED:
        _FIXED[sig] = struct.Struct("<II" + "".join("i" if c in "if" else "I" for c in sig)) if all(c in "iunof" for c in sig) else None
    return _FIXED[sig]


def encode(object_id: int, opcode: int, sig: str, args) -> tuple[bytes, list[int]]:
    """One request: the bytes, and the file descriptors that go with them."""
    if len(sig) != len(args):
        raise ValueError(f"signature {sig!r} wants {len(sig)} arguments, got {len(args)}")
    fixed = _fixed(sig)
    if fixed is not None:  # most requests: a few numbers and ids, every frame
        values = [round(v * 256) if c == "f" else (v or 0) if c in "uno" else v for c, v in zip(sig, args, strict=True)]
        return fixed.pack(object_id, (fixed.size << 16) | opcode, *values), []
    body = bytearray()
    fds: list[int] = []
    for code, value in zip(sig, args, strict=True):
        if code == "i":
            body += struct.pack("<i", value)
        elif code in "uno":
            body += struct.pack("<I", value or 0)
        elif code == "f":
            body += struct.pack("<i", round(value * 256))
        elif code == "s":
            if value is None:
                body += struct.pack("<I", 0)
            else:
                raw = value.encode() + b"\0"
                body += struct.pack("<I", len(raw)) + raw + b"\0" * (_pad(len(raw)) - len(raw))
        elif code == "a":
            body += struct.pack("<I", len(value)) + value + b"\0" * (_pad(len(value)) - len(value))
        elif code == "h":
            fds.append(value)
        else:
            raise ValueError(f"unknown argument code {code!r}")
    size = HEADER.size + len(body)
    return HEADER.pack(object_id, (size << 16) | opcode) + bytes(body), fds


def decode(sig: str, data: bytes) -> list:
    """An event's arguments, except file descriptors (see Connection.take_fd)."""
    out: list = []
    at = 0
    for code in sig:
        if code == "i":
            out.append(struct.unpack_from("<i", data, at)[0])
            at += 4
        elif code in "uno":
            out.append(struct.unpack_from("<I", data, at)[0])
            at += 4
        elif code == "f":
            out.append(struct.unpack_from("<i", data, at)[0] / 256)
            at += 4
        elif code == "h":
            continue  # not in the bytes
        elif code in "sa":
            length = struct.unpack_from("<I", data, at)[0]
            at += 4
            raw = bytes(data[at : at + length])
            at += _pad(length)
            if code == "s":
                out.append(raw[:-1].decode("utf-8", errors="replace") if length else None)
            else:
                out.append(raw)
        else:
            raise ValueError(f"unknown argument code {code!r}")
    return out


def socket_path(env=os.environ) -> str | None:
    display = env.get("WAYLAND_DISPLAY")
    if not display:
        return None
    if os.path.isabs(display):
        return display
    runtime = env.get("XDG_RUNTIME_DIR")
    return os.path.join(runtime, display) if runtime else None


Handler = Callable[[int, bytes], None]  # (opcode, argument bytes)


class Connection:
    """A client connection: object ids, requests out, events in.

    Events are handed to the handler registered for their object; events for
    objects nobody listens to are skipped, which the message size makes safe.
    """

    def __init__(self, sock: socket.socket):
        self.sock = sock
        sock.setblocking(False)
        self._next_id = DISPLAY_ID + 1
        self._free_ids: list[int] = []
        self._handlers: dict[int, Handler] = {DISPLAY_ID: self._display_event}
        self._in = bytearray()
        self._out = bytearray()
        self._out_fds: list[int] = []  # ours to close once sent
        self._in_fds: collections.deque[int] = collections.deque()  # received, not yet taken
        self.error: str | None = None
        self.closed = False

    @classmethod
    def open(cls, env=os.environ) -> Connection | None:
        path = socket_path(env)
        if not path:
            return None
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM | socket.SOCK_CLOEXEC)
        try:
            sock.connect(path)
        except OSError:
            sock.close()
            return None
        return cls(sock)

    def fileno(self) -> int:
        return self.sock.fileno()

    # -- objects

    def new_id(self, handler: Handler | None = None) -> int:
        oid = self._free_ids.pop() if self._free_ids else self._next_id
        if oid == self._next_id:
            self._next_id += 1
        if handler is not None:
            self._handlers[oid] = handler
        return oid

    def listen(self, oid: int, handler: Handler) -> None:
        self._handlers[oid] = handler

    def forget(self, oid: int) -> None:
        """Stop listening to a destroyed object; its id comes back with delete_id."""
        self._handlers.pop(oid, None)

    # -- requests

    def request(self, oid: int, opcode: int, sig: str = "", *args) -> None:
        if self.closed:
            return
        data, fds = encode(oid, opcode, sig, args)
        self._out += data
        self._out_fds += [os.dup(fd) for fd in fds]

    def requests(self, oid: int, opcode: int, sig: str, rows) -> None:
        """The same request with each row of arguments: packed in one go (fixed-size arguments only)."""
        fixed = _fixed(sig)
        if fixed is None or "f" in sig:
            for args in rows:
                self.request(oid, opcode, sig, *args)
            return
        if self.closed:
            return
        head = (oid, (fixed.size << 16) | opcode)
        rows = list(rows)
        many = _MANY.get((sig, len(rows)))
        if many is None:
            many = _MANY[(sig, len(rows))] = struct.Struct("<" + fixed.format[1:] * len(rows))
            if len(_MANY) > 64:
                _MANY.clear()
        self._out += many.pack(*[v for args in rows for v in (*head, *args)])

    def flush(self) -> bool:
        """Send what's queued without blocking; True once it's all gone."""
        while self._out and not self.closed:
            try:
                if self._out_fds:
                    sent = self.sock.sendmsg([self._out], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", self._out_fds))])
                    for fd in self._out_fds:
                        os.close(fd)
                    self._out_fds = []
                else:
                    sent = self.sock.send(self._out)
            except (BlockingIOError, InterruptedError):
                return False
            except OSError as exc:
                self._lost(f"sending: {exc}")
                return False
            del self._out[:sent]
        return not self._out

    # -- events

    def read(self) -> bool:
        """Read and dispatch whatever has arrived; False once the connection is gone."""
        while not self.closed:
            try:
                data, ancdata, _flags, _addr = self.sock.recvmsg(65536, socket.CMSG_SPACE(MAX_FDS * 4), _CLOEXEC)
            except (BlockingIOError, InterruptedError):
                break
            except OSError as exc:
                self._lost(f"reading: {exc}")
                break
            for level, kind, payload in ancdata:
                if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                    fds = array.array("i")
                    fds.frombytes(payload[: len(payload) - len(payload) % fds.itemsize])
                    self._in_fds.extend(fds)
            if not data:
                self._lost("the compositor closed the connection")
                break
            self._in += data
            self._dispatch()
        return not self.closed

    def _dispatch(self) -> None:
        while len(self._in) >= HEADER.size and not self.closed:
            oid, word = HEADER.unpack_from(self._in)
            size, opcode = word >> 16, word & 0xFFFF
            if size < HEADER.size:
                self._lost("a malformed message")
                return
            if len(self._in) < size:
                return
            args = bytes(self._in[HEADER.size : size])
            del self._in[:size]
            handler = self._handlers.get(oid)
            if handler is not None:
                handler(opcode, args)
        # A file descriptor nobody took belonged to an event nobody listens to.
        while len(self._in_fds) > MAX_FDS:
            os.close(self._in_fds.popleft())

    def take_fd(self) -> int:
        """The next file descriptor that came with an event; the caller closes it."""
        if not self._in_fds:
            raise WaylandError("an event was missing its file descriptor")
        return self._in_fds.popleft()
    def _display_event(self, opcode: int, args: bytes) -> None:
        if opcode == 0:  # error
            oid, code, message = decode("ous", args)
            self._lost(f"protocol error on object {oid} (code {code}): {message}")
        elif opcode == 1:  # delete_id
            (oid,) = decode("u", args)
            self._handlers.pop(oid, None)
            self._free_ids.append(oid)

    def _lost(self, why: str) -> None:
        if self.error is None:
            self.error = why
        self.closed = True

    # -- setup

    def roundtrip(self, timeout: float = 2.0) -> bool:
        """Block until the compositor has handled everything sent so far."""
        done: list[bool] = []
        callback = self.new_id(lambda opcode, args: done.append(True))
        self.request(DISPLAY_ID, 0, "n", callback)  # wl_display.sync
        deadline = time.monotonic() + timeout
        while not done and not self.closed:
            left = deadline - time.monotonic()
            if left <= 0:
                return False
            want_write = not self.flush()
            readable, _, _ = select.select([self.sock], [self.sock] if want_write else [], [], left)
            if readable:
                self.read()
        return bool(done)

    def close(self) -> None:
        for fd in self._out_fds + list(self._in_fds):
            os.close(fd)
        self._out_fds = []
        self._in_fds.clear()
        self.closed = True
        self.sock.close()
