"""Your chats with your chatmon, kept on this computer so you can come back to one and carry on.

Each chat is a JSON file of its own, readable by you alone, in a folder that stays on this computer (on Windows,
the local app-data folder, never the roaming one a domain copies to its server). What's kept is the conversation:
your questions (with the text of what you attached, so a brain can be asked about it later; pictures and PDFs by
name only), the answers and which brain gave them, the chat's own instructions, and a summary of its earlier part
once it's longer than a brain is sent at once. Attached text goes again only to the brain it was first sent to,
and a brain that can read your files is never handed another brain's answers. Nothing leaves your computer but
what you ask a brain. "Keep chat history" off (the menu, or `[chats] keep = false`) keeps chats in memory only,
and "Clear chat history" deletes them all.
"""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import paths
from .settings import private_dir, write_private

MAX_FILE = 64 * 2**20  # bytes: a chat file bigger than this isn't read (it isn't one of ours)
MAX_INSTRUCTIONS = 4000  # characters of a chat's own instructions
TITLE_LENGTH = 60
_ID = re.compile(r"[0-9a-f]{32}")


@dataclass
class Message:
    role: str  # "user" or "assistant"
    text: str  # what's shown: the question as typed, or the answer
    at: float = field(default_factory=time.time)
    sent: str = ""  # a question as the brain got it, with the text attached to it: only ever sent to that brain
    attached: list[str] = field(default_factory=list)  # names of what was attached
    brain: str = ""  # who answered (an answer), or who was asked (a question): the brain's label, as shown
    by: str = ""  # the same brain's name (its key in [ai.brains]), which two brains never share; "" in older chats


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
    instructions: str = ""  # yours, for this chat: sent with each question in it, before the ones for every chat
    summary: str = ""  # the conversation's earlier part, in short: what a brain gets in place of it (context.py)
    summarized: int = 0  # how many of the first (question, answer) pairs the summary stands for
    summary_by: str = ""  # made for one brain that reads files, from its own answers alone (its name); "": from all
    brain: str = ""  # the name of the brain that answered last: carrying the chat on asks it again

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
        if message.role == "assistant" and message.by:
            self.brain = message.by

    def history(self, brain: str = "", *, name: str = "", own_only: bool = False, before: int | None = None) -> list[tuple[str, str]]:
        """(question, answer) pairs, as the brain labelled `brain` (named `name`) is reminded of them: with the text
        attached to a question only if that's the brain it went to (nothing goes to a brain you didn't give it to);
        otherwise what was attached, by name.

        `own_only`, for a brain that can read files on this computer: another brain's answer is left out (one could
        carry an attached file's instructions to it), with a word in its place so the turns still count the same.
        `before`: only the turns before that message (asking another brain the same question)."""
        out, question = [], None
        for m in self.messages[:before]:
            if m.role == "user":
                if m.sent and _same(m, brain, name):
                    question = m.sent
                else:
                    question = m.text + (f"\n\n(Attached then: {', '.join(m.attached)})" if m.attached else "")
            elif m.role == "assistant" and question is not None:
                out.append((question, m.text if not own_only or _same(m, brain, name) else OTHER_ANSWER))
                question = None
        return out

    def summary_for(self, name: str, own_only: bool = False) -> tuple[str, int]:
        """(summary, pairs it stands for) to give the brain named `name`: none for a brain that reads files unless
        it was made from that brain's own answers (history's `own_only`), as a summary of every brain's answers
        could carry what one of them was told."""
        if own_only and self.summary_by != name:
            return "", 0
        return self.summary, self.summarized

    def set_summary(self, summary: str, covers: int, by: str = "") -> None:
        """A new summary of the first `covers` pairs; `by`: the brain it was made for from its own answers alone."""
        self.summary, self.summarized, self.summary_by = summary, covers, by

    def last_question(self) -> tuple[int, Message] | None:
        """The latest question in this chat and where it is, to ask another brain the same: send it (its `sent`
        text only if you choose to give that brain what was attached) after `history(..., before=index)`."""
        for i in range(len(self.messages) - 1, -1, -1):
            if self.messages[i].role == "user":
                return i, self.messages[i]
        return None


OTHER_ANSWER = "(Another AI answered this; its answer isn't passed on here.)"


def _same(m: Message, label: str, name: str) -> bool:
    """Is `m` from (or for) this brain? By name where the chat recorded one, else by label (older chats)."""
    if m.by and name:
        return m.by == name
    return bool(label) and m.brain == label


def title_for(text: str) -> str:
    line = " ".join(text.split())
    return line if len(line) <= TITLE_LENGTH else line[: TITLE_LENGTH - 1].rstrip() + "…"


def folder() -> Path:
    """Where chats are kept: made readable by you alone, with chats from where an older Chatmon kept them moved in."""
    path = _home()
    old = _roaming()
    if old is not None and old.is_dir() and not path.exists():
        _move(old, path)
    return private_dir(path)


def _home() -> Path:
    if sys.platform != "win32":
        return paths.state_dir() / "chats"  # Linux's XDG state folder and macOS's Application Support stay here
    # Windows: the local app-data folder, which a roaming profile never copies to a server. It's always inside your
    # profile; if it isn't (a profile moved for a test, say), the profile's own AppData\Local, not somebody else's.
    profile = Path(os.environ.get("USERPROFILE") or Path.home())
    local = Path(os.environ.get("LOCALAPPDATA") or profile / "AppData" / "Local")
    if not local.is_relative_to(profile):
        local = profile / "AppData" / "Local"
    return local / paths.APP / "chats"


def _roaming() -> Path | None:
    """Where chats were kept before 0.10 on Windows: the roaming app-data folder."""
    return paths.state_dir() / "chats" if sys.platform == "win32" else None


def _move(old: Path, new: Path) -> None:
    private_dir(new.parent)
    try:
        os.replace(old, new)  # the same disk: a rename
        return
    except OSError:
        pass
    private_dir(new)
    for item in old.glob("*.json"):  # another disk (a redirected profile): one at a time
        try:
            shutil.move(str(item), str(new / item.name))
        except OSError:
            continue


_LATEST = 4102444800.0  # 2100-01-01: any time past this in a file is nonsense


def _time(value: object) -> float:
    try:
        t = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return t if 0 <= t <= _LATEST else 0.0


def from_json(data: object) -> Chat | None:
    """A chat read back (a file of ours, or a backup's), or None if it isn't one; anything odd in it is left out,
    never fatal."""
    try:
        if not isinstance(data, dict) or not _ID.fullmatch(str(data.get("id", ""))):
            return None
        messages = []
        raw = data.get("messages")
        for m in raw if isinstance(raw, list) else []:
            if isinstance(m, dict) and m.get("role") in ("user", "assistant") and isinstance(m.get("text"), str):
                names = m.get("attached")
                sent = m.get("sent")
                messages.append(
                    Message(
                        m["role"], m["text"], _time(m.get("at")), sent if isinstance(sent, str) and m["role"] == "user" else "",
                        [n for n in names if isinstance(n, str)] if isinstance(names, list) else [], str(m.get("brain") or ""),
                        str(m.get("by") or "")[:200],
                    )
                )
        summarized = data.get("summarized")
        return Chat(
            str(data["id"]), str(data.get("title") or "")[:200], _time(data.get("created")), _time(data.get("updated")), messages,
            data.get("pinned") is True, data.get("named") is True,
            instructions=str(data.get("instructions") or "")[:MAX_INSTRUCTIONS],
            summary=str(data.get("summary") or ""),
            summarized=summarized if isinstance(summarized, int) and not isinstance(summarized, bool) and summarized > 0 else 0,
            summary_by=str(data.get("summary_by") or "")[:200],
            brain=str(data.get("brain") or "")[:200],
        )
    except (TypeError, ValueError, OverflowError, AttributeError):
        return None


def to_json(chat: Chat) -> dict:
    """A chat as its file keeps it (and a backup): from_json reads it back."""
    data = asdict(chat)
    data.pop("keep", None)
    for m in data["messages"]:
        if not m.get("sent") or m["sent"] == m["text"]:
            m.pop("sent", None)  # nothing attached: the question is its text
        if not m.get("by"):
            m.pop("by", None)
    return data


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
        """Keep `chat` on this computer; a chat begun while history was off (`keep` off) is never written."""
        if not chat.messages or not chat.keep:
            return
        write_private(self._file(chat.id), json.dumps(to_json(chat), ensure_ascii=False))

    def load(self, chat_id: str) -> Chat | None:
        try:
            path = self._file(chat_id)
            info = path.stat()
            seen = self._read.get(chat_id)
            if seen and seen[:2] == (info.st_mtime_ns, info.st_size):
                return copy.deepcopy(seen[2])
            chat = None if info.st_size > MAX_FILE else from_json(json.loads(path.read_text(encoding="utf-8")))
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
        """Delete every chat (where an older Chatmon kept them too); how many went."""
        gone = 0
        old = _roaming() if self._root is None else None
        for root in [self.root()] + ([old] if old is not None and old.is_dir() else []):
            try:
                for path in root.glob("*.json"):
                    if _ID.fullmatch(path.stem):
                        path.unlink(missing_ok=True)
                        gone += 1
                for path in root.glob("*.tmp"):
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
