"""Chatmon's log: what went wrong, and when, kept in a small file in the state folder.

Each module logs through its own `logging.getLogger(__name__)`. `setup()`, called once as Chatmon starts, sends
what Chatmon's loggers say to chatmon.log in the state folder (readable and writable only by you on Linux and
macOS). Past 1 MB the log starts over, the last one kept as chatmon.log.old. Problems go to stderr as well when
there is one, so starting Chatmon from a terminal still shows them. CHATMON_DEBUG, set to anything, logs the
details too: every error Chatmon carries on past, and the overlay's focus changes.

A log says what failed, never what it held: no key, chat text, prompt, attachment or clipboard goes into one.
Should a key slip into an error message all the same, anything shaped like a provider's key is blanked out as the
line is written.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import re
import sys
from pathlib import Path

from . import paths

DEBUG_ENV = "CHATMON_DEBUG"
LIMIT = 1_000_000  # bytes; past this the log starts over, the last one kept as chatmon.log.old
FILE_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
CONSOLE_FORMAT = f"{paths.APP}: %(message)s"

# Providers' key shapes (OpenAI, Anthropic, OpenRouter: sk-…; Google: AIza…; xAI: xai-…; Groq: gsk_…), and whatever
# follows "Bearer". Long enough that ordinary words never match.
_KEYS = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|AIza[A-Za-z0-9_-]{30,}|xai-[A-Za-z0-9_-]{20,}|gsk_[A-Za-z0-9]{20,})|(?<=[Bb]earer )[A-Za-z0-9._~+/=-]{8,}")
BLANKED = "…"

_installed: list[logging.Handler] = []  # what setup() added, so reset() takes away only that


def debugging() -> bool:
    """Is CHATMON_DEBUG set (to anything at all, as the overlay's own switch always was)?"""
    return bool(os.environ.get(DEBUG_ENV))


def log_file() -> Path:
    return paths.state_dir() / f"{paths.APP}.log"


def blank_keys(text: str) -> str:
    return _KEYS.sub(BLANKED, text)


class _Blanking(logging.Formatter):
    """Formats a record, its traceback included, then blanks anything shaped like a key."""

    def format(self, record: logging.LogRecord) -> str:
        return blank_keys(super().format(record))


def _private(path: str, flags: int) -> int:
    """Open the log for `open()`: made readable only by you, made so if an older Chatmon made it at the umask,
    and never through a symbolic link someone left in its place."""
    fd = os.open(path, flags | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
    except OSError:
        os.close(fd)
        raise
    return fd


class _PrivateRotatingFile(logging.handlers.RotatingFileHandler):
    """chatmon.log, private, kept under LIMIT bytes with one older log beside it as chatmon.log.old."""

    def __init__(self, path: Path):
        super().__init__(path, maxBytes=LIMIT, backupCount=1, encoding="utf-8", errors="replace")
        self.namer = _old_name

    def _open(self):
        return open(self.baseFilename, self.mode, encoding=self.encoding, errors=self.errors, opener=_private)


def _old_name(default: str) -> str:
    """The name a full log is moved to: chatmon.log.old, as Chatmon has always kept it, not logging's .log.1."""
    return default.removesuffix(".1") + ".old"


def setup() -> Path | None:
    """Send Chatmon's logging to its log file, and problems to stderr too when there is one; the log's path, or
    None when the state folder can't be written (Chatmon runs on, with nothing kept). Called again, it starts over."""
    reset()
    level = logging.DEBUG if debugging() else logging.INFO
    root = logging.getLogger(paths.APP)
    root.setLevel(level)
    path = log_file()
    kept: _PrivateRotatingFile | None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        kept = _PrivateRotatingFile(path)
    except OSError:
        kept = None
    else:
        kept.setFormatter(_Blanking(FILE_FORMAT))
        _install(root, kept)
    if sys.stderr is not None:
        console = logging.StreamHandler(sys.stderr)
        console.setLevel(level if debugging() else logging.WARNING)
        console.setFormatter(_Blanking(CONSOLE_FORMAT))
        _install(root, console)
    return path if kept is not None else None


def _install(root: logging.Logger, handler: logging.Handler) -> None:
    root.addHandler(handler)
    _installed.append(handler)


def reset() -> None:
    """Take away and close what setup() added (the tests use it)."""
    root = logging.getLogger(paths.APP)
    while _installed:
        handler = _installed.pop()
        root.removeHandler(handler)
        handler.close()
    root.setLevel(logging.NOTSET)
