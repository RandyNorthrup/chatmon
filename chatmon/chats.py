"""Your chats with your chatmon, kept on this computer so you can come back to one and carry on.

Each chat is a JSON file of its own in Chatmon's state folder, readable by you alone. What's kept is what
you'd see: your questions (with the text you attached, which is part of what was asked), the answers, and
the names of pictures and PDFs, never the files themselves. Nothing leaves your computer but what you ask
a brain. "Keep chat history" off (the menu, or `[chats] keep = false`) keeps chats in memory only, and
"Clear chat history" deletes them all.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import paths
from .settings import private

MAX_FILE = 8 * 2**20  # bytes: a chat file bigger than this isn't read (it isn't one of ours)
TITLE_LENGTH = 60
_ID = re.compile(r"[0-9a-f]{32}")


@dataclass
class Message:
    role: str  # "user" or "assistant"
    text: str  # what's shown: the question as typed, or the answer
    at: float = field(default_factory=time.time)
    sent: str = ""  # a question as the brain got it (with attached text), when that differs from `text`
    attached: list[str] = field(default_factory=list)  # names of what was attached
    brain: str = ""  # who answered


@dataclass
class Chat:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    title: str = ""
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)
    messages: list[Message] = field(default_factory=list)
    pinned: bool = False  # kept at the top of the list
    named: bool = False  # its title is one you gave it

    def rename(self, title: str) -> None:
        self.title, self.named = title_for(title), True

    def markdown(self) -> str:
        """The chat as a Markdown document, to keep or share."""
        from datetime import datetime

        lines = [f"# {self.title or 'A chat with Chatmon'}", "", f"*{datetime.fromtimestamp(self.created):%A %d %B %Y, %H:%M}*", ""]
        for m in self.messages:
            if m.role == "user":
                lines += [f"**You:** {m.text}" if m.text else "**You:**", ""]
                if m.attached:
                    lines += [f"*Attached: {', '.join(m.attached)}*", ""]
            else:
                lines += [f"**{m.brain or 'Chatmon'}:**", "", m.text, ""]
        return "\n".join(lines)

    def add(self, message: Message) -> None:
        self.messages.append(message)
        self.updated = message.at
        if not self.title and message.role == "user":
            self.title = title_for(message.text or ", ".join(message.attached))

    def history(self) -> list[tuple[str, str]]:
        """(question, answer) pairs, as a brain is reminded of them."""
        out, question = [], None
        for m in self.messages:
            if m.role == "user":
                question = m.sent or m.text
                if m.attached and not m.sent:
                    question += f"\n\n(Attached: {', '.join(m.attached)})"
            elif m.role == "assistant" and question is not None:
                out.append((question, m.text))
                question = None
        return out


def title_for(text: str) -> str:
    line = " ".join(text.split())
    return line if len(line) <= TITLE_LENGTH else line[: TITLE_LENGTH - 1].rstrip() + "…"


def folder() -> Path:
    path = paths.state_dir() / "chats"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        os.chmod(path, 0o700)
    return path


def _from_json(data: object) -> Chat | None:
    """A chat read back, or None if the file isn't one (anything odd in it is left out, not fatal)."""
    if not isinstance(data, dict) or not _ID.fullmatch(str(data.get("id", ""))):
        return None
    messages = []
    for m in data.get("messages") or []:
        if isinstance(m, dict) and m.get("role") in ("user", "assistant") and isinstance(m.get("text"), str):
            messages.append(
                Message(
                    m["role"], m["text"], float(m.get("at") or 0), str(m.get("sent") or ""),
                    [str(n) for n in m.get("attached") or [] if isinstance(n, str)], str(m.get("brain") or ""),
                )
            )
    try:
        return Chat(
            str(data["id"]), str(data.get("title") or ""), float(data.get("created") or 0), float(data.get("updated") or 0), messages,
            data.get("pinned") is True, data.get("named") is True,
        )
    except (TypeError, ValueError):
        return None


class ChatBook:
    """The chats kept on this computer."""

    def __init__(self, root: Path | None = None):
        self._root = root

    def root(self) -> Path:
        return self._root or folder()

    def _file(self, chat_id: str) -> Path:
        if not _ID.fullmatch(chat_id):  # never a path of anyone's making
            raise ValueError("not a chat id")
        return self.root() / f"{chat_id}.json"

    def save(self, chat: Chat) -> None:
        if not chat.messages:
            return
        path = self._file(chat.id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(chat), ensure_ascii=False), encoding="utf-8")
        private(tmp)
        os.replace(tmp, path)

    def load(self, chat_id: str) -> Chat | None:
        try:
            path = self._file(chat_id)
            if path.stat().st_size > MAX_FILE:
                return None
            return _from_json(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, RecursionError):
            return None

    def recent(self, limit: int = 60) -> list[Chat]:
        """Pinned chats, then the most recently talked in, newest first."""
        try:
            files = [p for p in self.root().glob("*.json") if _ID.fullmatch(p.stem)]
        except OSError:
            return []
        files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
        chats = []
        for path in files:
            chat = self.load(path.stem)
            if chat is not None and chat.messages:
                chats.append(chat)
            if len(chats) >= limit:
                break
        return sorted(chats, key=lambda c: (c.pinned, c.updated), reverse=True)

    def delete(self, chat_id: str) -> None:
        try:
            self._file(chat_id).unlink(missing_ok=True)
        except (OSError, ValueError):
            pass

    def clear(self) -> int:
        """Delete every chat; how many went."""
        gone = 0
        try:
            for path in self.root().glob("*.json"):
                if _ID.fullmatch(path.stem):
                    path.unlink(missing_ok=True)
                    gone += 1
            for path in self.root().glob("*.tmp"):
                path.unlink(missing_ok=True)
        except OSError:
            pass
        return gone


def when(t: float, now: float | None = None) -> str:
    """"just now", "5 min ago", "today 3:04 PM", "yesterday", "Mon Nov 10"..."""
    from datetime import datetime, timedelta

    now = time.time() if now is None else now
    if now - t < 60:
        return "just now"
    if now - t < 3600:
        return f"{int((now - t) // 60)} min ago"
    d, n = datetime.fromtimestamp(t), datetime.fromtimestamp(now)
    if d.date() == n.date():
        return f"today {(d.hour % 12) or 12}:{d.minute:02d} {'AM' if d.hour < 12 else 'PM'}"
    if d.date() == n.date() - timedelta(days=1):
        return "yesterday"
    return f"{d:%a %b} {d.day}"
