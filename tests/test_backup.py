"""Back up and move (backup.py): one zip with Settings changes, memory, notes, reminders and chats; never a key; and
read back only when every part of it checks out."""

import json
import zipfile

import pytest

from chatmon import backup, chats, keychain, memory
from chatmon.settings import State

KEY = "sk-ant-never-in-a-backup-0123456789"


def _here(root):
    """A computer's worth of Chatmon: settings, memory, notes, reminders, two chats, and keys about."""
    state = State(root / "state.json", {
        "name": "Sparky", "companion": "fire-red-panda", "bubble_style": "fire", "brain": "anthropic-api",
        "brain_options": {"anthropic-api": {"model": "claude-haiku-5-5", "effort": "low"}},
        "settings": {"size": 150, "heads_up": {"battery_low": 30}, "ai": {"brains": {"mine": {"api_key": KEY, "url": "https://x"}}}},
        "instructions": "Be brief.", "keep_chats": True,
        "notes": [{"text": "buy milk", "at": 1700000000.0}],
        "reminders": [{"due": 1800000000.0, "text": "stand up", "kind": "reminder", "id": "ab12cd34", "acknowledged": False}],
        "x": 640, "update_checked": 1700000000.0, "seen_version": "0.9.2", "agent_status": {"claude": "found"},
        "token": KEY,
    })
    state.save()
    mem = memory.Memory([memory.Item("I use Arch", 1700000000.0)], root / "memory.json")
    mem.save()
    book = chats.ChatBook(root / "chats")
    for words in ("first", "second"):
        chat = chats.Chat()
        chat.add(chats.Message("user", f"{words} question", sent=f"{words} question\n[begin a.txt k]\nattached\n[end a.txt k]",
                               attached=["a.txt"], brain="Codex", by="codex"))
        chat.add(chats.Message("assistant", f"{words} answer", brain="Codex", by="codex"))
        book.save(chat)
    return state, mem, book


@pytest.fixture
def keys():
    store = keychain.InMemory()
    store.keys["anthropic-api"] = KEY
    before = keychain.use(store)
    yield store
    keychain.use(before)


def test_a_backup_moves_everything_to_another_computer(tmp_path, keys):
    state, mem, book = _here(tmp_path / "old")
    made = backup.export(tmp_path / "chatmon-backup.zip", state, mem, book)
    assert made.summary() == "your settings, 1 thing remembered, 1 note, 1 reminder and 2 chats"
    new_state, new_mem, new_book = State(tmp_path / "new" / "state.json", {"x": 10}), memory.Memory([], tmp_path / "new" / "memory.json"), chats.ChatBook(tmp_path / "new" / "chats")
    contents = backup.read(tmp_path / "chatmon-backup.zip")
    said = backup.bring_back(contents, new_state, new_mem, new_book)
    assert said == "Brought back your settings, 1 thing remembered, 1 note, 1 reminder and 2 chats."
    back = State.load(tmp_path / "new" / "state.json")
    for key in ("name", "companion", "bubble_style", "brain", "brain_options", "instructions", "keep_chats", "notes", "reminders"):
        assert back.get(key) == state.get(key), key
    assert back.get("settings")["size"] == 150 and back.get("settings")["heads_up"] == {"battery_low": 30}
    assert back.get("x") == 10 and back.get("seen_version") is None and back.get("agent_status") is None  # its own bookkeeping stays
    assert memory.Memory.load(tmp_path / "new" / "memory.json").texts() == ["I use Arch"]
    moved = {c.title: c for c in new_book.recent()}
    assert set(moved) == {"first question", "second question"} and moved["first question"].brain == "codex"
    assert "attached" in moved["first question"].history("Codex", name="codex")[0][0]  # with what was attached


def test_no_key_ever_goes_into_a_backup(tmp_path, keys):
    state, mem, book = _here(tmp_path)
    backup.export(tmp_path / "b.zip", state, mem, book)
    with zipfile.ZipFile(tmp_path / "b.zip") as zf:
        everything = b"".join(zf.read(n) for n in zf.namelist())
        names = zf.namelist()
    assert KEY.encode() not in everything and b"api_key" not in everything and b'"token"' not in everything
    assert "config.toml" not in names and sorted(n for n in names if not n.startswith("chats/")) == [
        "chatmon-backup.json", "memory.json", "notes.json", "reminders.json", "settings.json"]
    assert keys.keys == {"anthropic-api": KEY}  # and the keychain is left as it was


def test_chats_go_in_only_when_asked_and_the_file_is_yours_alone(tmp_path):
    import os
    import stat

    state, mem, book = _here(tmp_path)
    made = backup.export(tmp_path / "out" / "b.zip", state, mem)
    assert made.chats == [] and not [n for n in zipfile.ZipFile(tmp_path / "out" / "b.zip").namelist() if n.startswith("chats/")]
    if os.name == "posix":
        assert stat.S_IMODE((tmp_path / "out" / "b.zip").stat().st_mode) == 0o600


def _zip(path, files: dict, manifest: dict | None = None):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        if manifest is not False:
            zf.writestr("chatmon-backup.json", json.dumps(manifest or {"format": "chatmon-backup", "version": 1}))
        for name, data in files.items():
            zf.writestr(name, data if isinstance(data, (bytes, str)) else json.dumps(data))
    return path


@pytest.mark.parametrize(
    ("files", "manifest", "said"),
    [
        ({"../state.json": {}}, None, "holds things a Chatmon backup doesn't"),
        ({"chats/../../x.json": {}}, None, "holds things a Chatmon backup doesn't"),
        ({"config.toml": "api_key = 'x'"}, None, "holds things a Chatmon backup doesn't"),
        ({"settings.json": {}}, False, "has no chatmon-backup.json"),
        ({"settings.json": {}}, {"format": "chatmon-backup", "version": 2}, "made by a newer Chatmon"),
        ({"settings.json": {}}, {"format": "something-else", "version": 1}, "isn't a Chatmon backup"),
        ({"settings.json": "{not json"}, None, "settings.json in b.zip is damaged"),
        ({"memory.json": [{"text": 5}]}, None, "what's remembered in b.zip isn't in the right shape"),
        ({"notes.json": {"text": "x"}}, None, "the notes in b.zip aren't in the right shape"),
        ({"reminders.json": [{"due": "soon", "text": "x"}]}, None, "the reminders in b.zip aren't in the right shape"),
        ({"chats/" + "a" * 32 + ".json": {"id": "b" * 32, "messages": []}}, None, "isn't a chat"),
        ({"settings.json": b"[" + b" " * (65 * 2**20) + b"]"}, None, "unpacks far bigger"),
    ],
)
def test_a_backup_that_isnt_right_is_refused_whole_and_nothing_changes(tmp_path, files, manifest, said):
    state, mem, book = _here(tmp_path / "here")
    before = (tmp_path / "here" / "state.json").read_bytes(), (tmp_path / "here" / "memory.json").read_bytes()
    with pytest.raises(backup.BackupError, match=None) as refused:
        backup.read(_zip(tmp_path / "b.zip", files, manifest))
    assert said in str(refused.value), str(refused.value)
    assert ((tmp_path / "here" / "state.json").read_bytes(), (tmp_path / "here" / "memory.json").read_bytes()) == before


def test_what_isnt_a_zip_at_all_is_said(tmp_path):
    (tmp_path / "notes.zip").write_text("hello", encoding="utf-8")
    with pytest.raises(backup.BackupError, match="isn't a Chatmon backup"):
        backup.read(tmp_path / "notes.zip")
    with pytest.raises(backup.BackupError, match="isn't a Chatmon backup"):
        backup.read(tmp_path / "missing.zip")


def test_a_key_slipped_into_a_backup_by_hand_is_never_brought_back(tmp_path):
    settings = {"settings": {"ai": {"brains": {"mine": {"api_key": KEY, "url": "https://x"}}}}, "name": "Sparky", "seen_version": "9"}
    contents = backup.read(_zip(tmp_path / "b.zip", {"settings.json": settings}))
    assert contents.settings == {"settings": {"ai": {"brains": {"mine": {"url": "https://x"}}}}, "name": "Sparky"}


def test_a_chat_on_both_computers_keeps_the_one_talked_in_last(tmp_path):
    state, mem, book = _here(tmp_path / "old")
    chat = book.recent()[0]
    backup.export(tmp_path / "b.zip", state, mem, book)
    later = book.load(chat.id)
    later.add(chats.Message("user", "and since then?", at=chat.updated + 100))
    book.save(later)
    backup.bring_back(backup.read(tmp_path / "b.zip"), state, mem, book)
    assert book.load(chat.id).messages[-1].text == "and since then?"
