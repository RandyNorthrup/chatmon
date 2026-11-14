"""A pretend provider on this computer, for the tests that ask brains questions: it answers each POST with what a
test gave it (a status, headers, and the body in pieces, each written and flushed on its own), records what it was
sent, and notices when the asker hangs up. Plain HTTP to 127.0.0.1 is the one place check_url lets a key go."""

from __future__ import annotations

import http.server
import json
import threading
import time
from dataclasses import dataclass, field


@dataclass
class Reply:
    status: int = 200
    headers: dict[str, str] = field(default_factory=lambda: {"content-type": "text/event-stream"})
    pieces: list[bytes] = field(default_factory=list)
    gap_s: float = 0.02  # between pieces, so each arrives on its own
    hold: threading.Event | None = None  # after the first piece, wait for this (a stream still being written)


def sse(*events: dict | str, named: bool = False) -> list[bytes]:
    """Server-Sent Events, one per piece: a dict as JSON (with an `event:` line of its type if `named`), a str as is."""
    out = []
    for e in events:
        data = e if isinstance(e, str) else json.dumps(e)
        head = f"event: {e['type']}\n" if named and isinstance(e, dict) and "type" in e else ""
        out.append(f"{head}data: {data}\n\n".encode())
    return out


class Provider:
    def __init__(self):
        self.replies: list[Reply] = []
        self.asked: list[dict] = []  # each request: path, headers (lower-case), body (JSON)
        self.hung_up = threading.Event()
        provider = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self):
                length = int(self.headers.get("content-length") or 0)
                raw = self.rfile.read(length)
                provider.asked.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": json.loads(raw or b"{}")})
                reply = provider.replies.pop(0) if provider.replies else Reply(500, {}, [b"no reply set"])
                self.send_response(reply.status)
                for name, value in reply.headers.items():
                    self.send_header(name, value)
                self.send_header("connection", "close")
                if "content-length" not in reply.headers:
                    self.send_header("transfer-encoding", "chunked")
                self.end_headers()
                try:
                    for i, piece in enumerate(reply.pieces):
                        self._piece(piece, "content-length" not in reply.headers)
                        if i == 0 and reply.hold is not None:
                            reply.hold.wait(10)
                            for _ in range(50):  # the asker hung up: writing now fails within a few tries
                                self._piece(b": still here\n\n", True)
                                time.sleep(0.05)
                        time.sleep(reply.gap_s)
                    if "content-length" not in reply.headers:
                        self.wfile.write(b"0\r\n\r\n")
                        self.wfile.flush()
                except OSError:
                    provider.hung_up.set()

            do_GET = do_POST

            def _piece(self, piece: bytes, chunked: bool) -> None:
                self.wfile.write(f"{len(piece):x}\r\n".encode() + piece + b"\r\n" if chunked else piece)
                self.wfile.flush()

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def json_reply(status: int, body: dict | list | str) -> Reply:
    raw = body.encode() if isinstance(body, str) else json.dumps(body).encode()
    kind = "text/plain" if isinstance(body, str) else "application/json"
    return Reply(status, {"content-type": kind, "content-length": str(len(raw))}, [raw])


def ask(asker, brain, question: str = "q", timeout_s: float = 10, wait_s: float = 10) -> dict:
    """Ask, and spin Qt's loop until it answers or fails: what came, in order."""
    from PyQt6.QtCore import QEventLoop, QTimer

    got: dict = {"partial": [], "answered": None, "failed": None}
    loop = QEventLoop()
    asker.partial.connect(got["partial"].append)
    asker.answered.connect(lambda text: (got.__setitem__("answered", text), loop.quit()))
    asker.failed.connect(lambda text: (got.__setitem__("failed", text), loop.quit()))
    QTimer.singleShot(int(wait_s * 1000), loop.quit)
    asker.ask(brain, "S", [], question, timeout_s)
    loop.exec()
    return got


def spin(seconds: float) -> None:
    from PyQt6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(int(seconds * 1000), loop.quit)
    loop.exec()
