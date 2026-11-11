"""Your chats with your chatmon, kept on this computer so you can come back to one and carry on.

Each chat is a JSON file of its own in Chatmon's state folder, readable by you alone. What's kept is what
you saw: your questions, the answers, and the names of what you attached, never the files or text
themselves. Attached text is sent again with later questions only to the brain it was first sent to, and
only until Chatmon quits. Nothing leaves your computer but what you ask
a brain. "Keep chat history" off (the menu, or `[chats] keep = false`) keeps chats in memory only, and
"Clear chat history" deletes them all.
"""

from __future__ import annotations

import copy
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
    sent: str = ""  # a question as the brain got it (with attached text): in memory only, never saved
    attached: list[str] = field(default_factory=list)  # names of what was attached
    brain: str = ""  # who answered (an answer), or who was asked (a question)


@dataclass
class Chat:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    title: str = ""
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)
    messages: list[Message] = field(default_factory=list)
    pinned: bool = False  # kept at the top of the list
    named: bool = False  # its title is one you gave it
    keep: bool = True  # saved as it goes (not saved itself): off for a chat begun while history was off

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

    def history(self, brain: str = "") -> list[tuple[str, str]]:
        """(question, answer) pairs, as `brain` is reminded of them: with the text attached to a question only
        if that's the brain it went to, this run (nothing goes to a brain you didn't give it to); otherwise
        what was attached, by name."""
        out, question = [], None
        for m in self.messages:
            if m.role == "user":
                if m.sent and brain and m.brain == brain:
                    question = m.sent
                else:
                    question = m.text + (f"\n\n(Attached then: {', '.join(m.attached)})" if m.attached else "")
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


_LATEST = 4102444800.0  # 2100-01-01: any time past this in a file is nonsense


def _time(value: object) -> float:
    try:
        t = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return t if 0 <= t <= _LATEST else 0.0


def _from_json(data: object) -> Chat | None:
    """A chat read back, or None if the file isn't one; anything odd in it is left out, never fatal."""
    try:
        if not isinstance(data, dict) or not _ID.fullmatch(str(data.get("id", ""))):
            return None
        messages = []
        raw = data.get("messages")
        for m in raw if isinstance(raw, list) else []:
            if isinstance(m, dict) and m.get("role") in ("user", "assistant") and isinstance(m.get("text"), str):
                names = m.get("attached")
                messages.append(
                    Message(
                        m["role"], m["text"], _time(m.get("at")), "",
                        [n for n in names if isinstance(n, str)] if isinstance(names, list) else [], str(m.get("brain") or ""),
                    )
                )
        return Chat(
            str(data["id"]), str(data.get("title") or "")[:200], _time(data.get("created")), _time(data.get("updated")), messages,
            data.get("pinned") is True, data.get("named") is True,
        )
    except (TypeError, ValueError, OverflowError, AttributeError):
        return None


class ChatBook:
    """The chats kept on this computer."""

    def __init__(self, root: Path | None = None):
        self._root = root
        self._read: dict[str, tuple[int, int, Chat | None]] = {}  # chat id: (mtime, size, as read): read once

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
        data = asdict(chat)
        data.pop("keep", None)
        for m in data["messages"]:
            m.pop("sent", None)  # attached text: never on disk
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        private(tmp)
        os.replace(tmp, path)

    def load(self, chat_id: str) -> Chat | None:
        try:
            path = self._file(chat_id)
            info = path.stat()
            seen = self._read.get(chat_id)
            if seen and seen[:2] == (info.st_mtime_ns, info.st_size):
                return copy.deepcopy(seen[2])
            chat = None if info.st_size > MAX_FILE else _from_json(json.loads(path.read_text(encoding="utf-8")))
            self._read[chat_id] = (info.st_mtime_ns, info.st_size, chat)
            return copy.deepcopy(chat)
        except (OSError, ValueError, RecursionError):
            return None

    def recent(self, limit: int = 200) -> list[Chat]:
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
    t = _time(t)
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
