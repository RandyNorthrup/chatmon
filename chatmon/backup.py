"""Back up and move: what you've set and kept with Chatmon, in one zip file to keep or to take to another computer.

A backup holds your Settings changes, what your chatmon remembers, your notes, your reminders and, if you like, your
chats. It never holds an API key: not the keychain's (keychain.py), not config.toml (which can carry keys inline, so
it isn't in a backup at all), and anything in the state that's named like a key or a token is left out on the way in
and on the way out.

Reading one back checks all of it first: what files are in it, how big each is, that it's a Chatmon backup of a
version this Chatmon knows, and the shape of every part. One thing wrong and nothing is changed.
"""

from __future__ import annotations

import json
import os
import re
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import chats
from .chats import Chat, ChatBook
from .i18n import _, join, ngettext
from .memory import MAX_ITEMS, MAX_LENGTH, Item, Memory
from .settings import State, private_dir

FORMAT = "chatmon-backup"
VERSION = 1
MANIFEST = "chatmon-backup.json"
PARTS = ("settings.json", "memory.json", "notes.json", "reminders.json")
CHAT_FILE = re.compile(r"chats/[0-9a-f]{32}\.json")

# The state's keys that are Settings changes: what you set in Settings or Chatmon's menu. Never its own bookkeeping
# (when it last looked for updates, the version it last saw, where it stood on the screen, what agents said).
SETTINGS_KEYS = (
    "settings", "name", "companion", "bubble_style", "bubble_effects", "brain", "brain_options", "keep_chats",
    "instructions", "context_tokens", "check_updates",
)
_SECRET = re.compile(r"(api[_-]?key|key$|token|secret|password|passwd|credential)", re.I)  # a name a key could go by

MAX_ZIP = 512 * 2**20  # bytes of a backup file, at most
MAX_PART = chats.MAX_FILE  # bytes of one part once unpacked
MAX_TOTAL = 1024 * 2**20  # bytes of everything once unpacked
MAX_RATIO = 200  # unpacked to packed, past which a part is a zip bomb (Chatmon's own JSON packs to about a fifth)
MAX_CHATS = 20_000
MAX_NOTES = 200  # app.py's Companion.MAX_NOTES
MAX_NOTE = 2000
MAX_REMINDERS = 1000


class BackupError(Exception):
    """A backup that can't be made or read: a sentence saying why."""


@dataclass
class Contents:
    """What a backup holds, checked."""

    settings: dict[str, Any] = field(default_factory=dict)
    memory: list[Item] = field(default_factory=list)
    notes: list[dict] = field(default_factory=list)
    reminders: list[dict] = field(default_factory=list)
    chats: list[Chat] = field(default_factory=list)
    made: str = ""

    def summary(self) -> str:
        parts = [_("your settings")] if self.settings else []
        if self.memory:
            parts.append(ngettext("{n} thing remembered", "{n} things remembered", len(self.memory)).format(n=len(self.memory)))
        if self.notes:
            parts.append(ngettext("{n} note", "{n} notes", len(self.notes)).format(n=len(self.notes)))
        if self.reminders:
            parts.append(ngettext("{n} reminder", "{n} reminders", len(self.reminders)).format(n=len(self.reminders)))
        if self.chats:
            parts.append(ngettext("{n} chat", "{n} chats", len(self.chats)).format(n=len(self.chats)))
        return join(parts) if parts else _("nothing")


def default_name(now: float | None = None) -> str:
    return time.strftime("chatmon-backup-%Y-%m-%d.zip", time.localtime(now))


def gather(state: State, memory: Memory, book: ChatBook | None = None) -> Contents:
    """What a backup made now would hold (`book`: also the chats kept on this computer)."""
    settings = {k: _no_secrets(state.get(k)) for k in SETTINGS_KEYS if state.get(k) is not None}
    notes = state.get("notes") if isinstance(state.get("notes"), list) else []
    reminders = state.get("reminders") if isinstance(state.get("reminders"), list) else []
    return Contents(
        settings=settings,
        memory=list(memory.items),
        notes=[n for n in notes if isinstance(n, dict) and isinstance(n.get("text"), str)],
        reminders=[checked for checked in map(_reminder, reminders) if checked],
        chats=book.recent(limit=MAX_CHATS) if book is not None else [],
    )


def export(path: Path, state: State, memory: Memory, book: ChatBook | None = None) -> Contents:
    """Write a backup to `path` (readable by you alone: it holds your chats and notes); what went in it.
    `book`: the chats too; None leaves them out."""
    contents = gather(state, memory, book)
    from . import __version__

    made = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    manifest = {
        "format": FORMAT, "version": VERSION, "chatmon": __version__, "made": made,
        "contains": [p.removesuffix(".json") for p in PARTS] + (["chats"] if book is not None else []),
    }
    path = Path(path)
    if not path.parent.exists():
        private_dir(path.parent)  # a folder made for it is yours alone, like the file
    tmp = path.with_name(path.name + ".tmp")
    tmp.unlink(missing_ok=True)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    try:
        with os.fdopen(fd, "wb") as out, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(MANIFEST, json.dumps(manifest, indent=1))
            zf.writestr("settings.json", json.dumps(contents.settings, indent=1, ensure_ascii=False))
            zf.writestr("memory.json", json.dumps([{"text": i.text, "at": i.at} for i in contents.memory], indent=1, ensure_ascii=False))
            zf.writestr("notes.json", json.dumps(contents.notes, indent=1, ensure_ascii=False))
            zf.writestr("reminders.json", json.dumps(contents.reminders, indent=1, ensure_ascii=False))
            for chat in contents.chats:
                zf.writestr(f"chats/{chat.id}.json", json.dumps(chats.to_json(chat), ensure_ascii=False))
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    contents.made = made
    return contents


def read(path: Path) -> Contents:
    """Everything in the backup at `path`, checked; BackupError (and nothing read) if any of it isn't right."""
    path = Path(path)
    try:
        if path.stat().st_size > MAX_ZIP:
            raise BackupError(_("{file} is too big to be a Chatmon backup").format(file=path.name))
        zf = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise BackupError(_("{file} isn't a Chatmon backup ({error}: it can't be opened as a zip file)").format(file=path.name, error=exc.__class__.__name__)) from None
    with zf:
        infos = zf.infolist()
        names = [i.filename for i in infos if not i.is_dir()]
        strange = [n for n in names if n != MANIFEST and n not in PARTS and not CHAT_FILE.fullmatch(n)]
        if strange or len(names) != len(set(names)) or any(i.is_dir() and i.filename != "chats/" for i in infos):
            what = ", ".join(strange[:3]) or _("a name twice")
            raise BackupError(_("{file} holds things a Chatmon backup doesn't ({what}), so nothing was read").format(file=path.name, what=what))
        if MANIFEST not in names:
            raise BackupError(_("{file} isn't a Chatmon backup (it has no {part})").format(file=path.name, part=MANIFEST))
        if sum(1 for n in names if n.startswith("chats/")) > MAX_CHATS:
            raise BackupError(_("{file} holds more chats than Chatmon keeps").format(file=path.name))
        total = 0
        loaded: dict[str, Any] = {}
        for info in infos:
            if info.is_dir():
                continue
            if info.file_size > MAX_PART or (info.file_size > 2**20 and info.file_size > MAX_RATIO * max(info.compress_size, 1)):
                raise BackupError(_("{part} in {file} unpacks far bigger than any Chatmon file, so nothing was read").format(part=info.filename, file=path.name))
            with zf.open(info) as part:
                raw = part.read(MAX_PART + 1)  # the size the zip claims isn't trusted: what's read is counted
            total += len(raw)
            if len(raw) > MAX_PART or total > MAX_TOTAL:
                raise BackupError(_("{file} unpacks far bigger than any Chatmon backup, so nothing was read").format(file=path.name))
            try:
                loaded[info.filename] = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError, RecursionError):
                raise BackupError(_("{part} in {file} is damaged, so nothing was read").format(part=info.filename, file=path.name)) from None
    return _checked(loaded, path.name)


def _checked(loaded: dict[str, Any], name: str) -> Contents:
    manifest = loaded[MANIFEST]
    if not isinstance(manifest, dict) or manifest.get("format") != FORMAT or not isinstance(manifest.get("version"), int):
        raise BackupError(_("{file} isn't a Chatmon backup").format(file=name))
    if manifest["version"] > VERSION:
        raise BackupError(_("{file} was made by a newer Chatmon: update this one, then bring it back").format(file=name))
    out = Contents(made=str(manifest.get("made") or "")[:40])
    settings = loaded.get("settings.json", {})
    if not isinstance(settings, dict):
        raise BackupError(_("the settings in {file} aren't in the right shape, so nothing was read").format(file=name))
    out.settings = {k: _no_secrets(v) for k, v in settings.items() if k in SETTINGS_KEYS}
    memory = loaded.get("memory.json", [])
    misshapen = _("what's remembered in {file} isn't in the right shape, so nothing was read").format(file=name)
    if not isinstance(memory, list) or len(memory) > MAX_ITEMS:
        raise BackupError(misshapen)
    for m in memory:
        if not (isinstance(m, dict) and isinstance(m.get("text"), str) and m["text"].strip() and len(m["text"]) <= MAX_LENGTH):
            raise BackupError(misshapen)
        out.memory.append(Item(m["text"].strip(), _time(m.get("at"))))
    notes = loaded.get("notes.json", [])
    if not isinstance(notes, list) or len(notes) > MAX_NOTES or not all(isinstance(n, dict) and isinstance(n.get("text"), str) for n in notes):
        raise BackupError(_("the notes in {file} aren't in the right shape, so nothing was read").format(file=name))
    out.notes = [{"text": n["text"][:MAX_NOTE], "at": _time(n.get("at"))} for n in notes]
    reminders = loaded.get("reminders.json", [])
    misshapen = _("the reminders in {file} aren't in the right shape, so nothing was read").format(file=name)
    if not isinstance(reminders, list) or len(reminders) > MAX_REMINDERS:
        raise BackupError(misshapen)
    for r in reminders:
        checked = _reminder(r)
        if checked is None:
            raise BackupError(misshapen)
        out.reminders.append(checked)
    for filename, data in loaded.items():
        if filename.startswith("chats/"):
            chat = chats.from_json(data)
            if chat is None or f"chats/{chat.id}.json" != filename:
                raise BackupError(_("{part} in {file} isn't a chat, so nothing was read").format(part=filename, file=name))
            out.chats.append(chat)
    return out


def bring_back(contents: Contents, state: State, memory: Memory, book: ChatBook | None = None) -> str:
    """Put a checked backup in place: its settings, memory, notes and reminders replace these (as on a new computer);
    its chats join those here, a chat in both kept as it was last talked in. Saved at once. Says what came back.
    The running app then reads its settings and reminders again (see Integration notes)."""
    for key, value in contents.settings.items():
        state.set(key, value)
    state.set("notes", contents.notes)
    state.set("reminders", contents.reminders)
    memory.items = list(contents.memory)
    memory.save()
    state.save()
    if book is not None:
        for chat in contents.chats:
            here = book.load(chat.id)
            if here is None or here.updated <= chat.updated:
                book.save(chat)
    return _("Brought back {what}.").format(what=contents.summary())


def _reminder(r: Any) -> dict | None:
    """A reminder as the state keeps it (reminders.py): a time due and its text, and any other plain values it has."""
    if not isinstance(r, dict) or not isinstance(r.get("text"), str) or isinstance(r.get("due"), bool) or not isinstance(r.get("due"), (int, float)):
        return None
    return {k: v for k, v in r.items() if isinstance(k, str) and (v is None or isinstance(v, (str, int, float, bool)))}


def _time(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value < 4102444800 else 0.0


def _no_secrets(value: Any) -> Any:
    """`value` with everything named like a key or a token taken out, at any depth."""
    if isinstance(value, dict):
        return {k: _no_secrets(v) for k, v in value.items() if not (isinstance(k, str) and _SECRET.search(k))}
    if isinstance(value, list):
        return [_no_secrets(v) for v in value]
    return value
