"""What you've asked your chatmon to remember about you, for every chat: "remember that I use Arch".

Kept on this computer in one file, readable by you alone, and sent with every question to whichever brain you
ask (that's what it's for). Only what you tell it in so many words is kept: nothing is picked out of your
chats for you. "What do you remember" lists it; "forget that I use Arch", the menu or Settings take it out.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

from . import paths
from .settings import read_kept, write_private

MAX_ITEMS = 100
MAX_LENGTH = 500  # characters of one thing to remember
MAX_FILE = 2**20  # bytes: a memory file bigger than this isn't one of ours, and is kept aside, never written over

# "remember that …", "remember: …", "remember I …", "remember my …" (never "remember to …": that's a reminder's,
# and "remember when we …?" is a question for the AI).
_REMEMBER = re.compile(r"^(?:please\s+)?remember(?:\s+that\b|\s*:)\s*(.+)$|^(?:please\s+)?remember\s+((?:i|i'm|i've|my|we|we're|our)\b.+)$", re.I | re.S)
_FORGET = re.compile(r"^(?:please\s+)?forget(?:\s+that\b|\s*:)\s*(.+)$", re.I | re.S)  # "forget about it, …" is the AI's
_LIST = re.compile(r"^(?:what do you remember(?: about me)?|what have you remembered|your memory|memory)\??$", re.I)
_FORGET_ALL = re.compile(r"^forget everything(?: about me)?$", re.I)


@dataclass
class Item:
    text: str
    at: float


def path() -> Path:
    return paths.state_dir() / "memory.json"


class Memory:
    def __init__(self, items: list[Item], where: Path, problem: str | None = None):
        self.items, self.where = items, where
        self.problem = problem  # a sentence for you when the file was damaged and had to be recovered

    @classmethod
    def load(cls, where: Path | None = None) -> Memory:
        where = where or path()
        items = []
        data, problem = read_kept(where, lambda d: isinstance(d, list), MAX_FILE)
        for d in data or []:
            if isinstance(d, dict) and isinstance(d.get("text"), str) and d["text"].strip():
                at = d.get("at")
                items.append(Item(d["text"].strip()[:MAX_LENGTH], float(at) if isinstance(at, (int, float)) else 0.0))
        return cls(items[:MAX_ITEMS], where, problem)

    def texts(self) -> list[str]:
        return [i.text for i in self.items]

    def add(self, text: str) -> str | None:
        """Remember `text`; why not, if it isn't."""
        text = " ".join(text.split()).strip(" .")
        if not text:
            return "There's nothing there to remember."
        if len(text) > MAX_LENGTH:
            return f"That's a lot to remember at once: up to {MAX_LENGTH} characters, please."
        if any(i.text.lower() == text.lower() for i in self.items):
            return None
        if len(self.items) >= MAX_ITEMS:
            return f"I remember {MAX_ITEMS} things already. Forget one first (*what do you remember* lists them)."
        self.items.append(Item(text, time.time()))
        self.save()
        return None

    def forget(self, words: str) -> list[str]:
        """Forget what best matches `words` (the whole of it, or each item holding all its words); what went."""
        wanted = {w for w in re.findall(r"\w+", words.lower()) if len(w) > 1}
        exact = [i for i in self.items if i.text.lower().strip(" .") == words.lower().strip(" .")]
        gone = exact or [i for i in self.items if wanted and wanted <= set(re.findall(r"\w+", i.text.lower()))]
        if gone:
            self.items = [i for i in self.items if i not in gone]
            self.save()
        return [i.text for i in gone]

    def remove(self, index: int) -> None:
        if 0 <= index < len(self.items):
            del self.items[index]
            self.save()

    def clear(self) -> None:
        self.items = []
        self.save()

    def save(self) -> None:
        write_private(self.where, json.dumps([{"text": i.text, "at": i.at} for i in self.items], ensure_ascii=False, indent=1))


def command(text: str) -> tuple[str, str] | None:
    """("remember", what), ("forget", what), ("forget-all", ""), ("list", ""), or None: not about memory."""
    text = text.strip()
    if _LIST.match(text):
        return "list", ""
    if _FORGET_ALL.match(text):
        return "forget-all", ""
    m = _REMEMBER.match(text)
    if m:
        return "remember", (m.group(1) or m.group(2)).strip()
    m = _FORGET.match(text)
    if m:
        return "forget", m.group(1).strip()
    return None
