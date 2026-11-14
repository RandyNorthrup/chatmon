"""The offline command table on its own: phrases to commands, and what the pure parts say. No Qt."""

import time

from chatmon import commands, memory, reminders
from chatmon.commands import Table

# What the inline chain in app.py answered before the table (0.9.2): each phrase, and what it did.
BEFORE = {
    "help": ("help", "what can you do", "commands"),
    "status": ("status", "battery", "system status", "how's my computer"),
    "stop-focus": ("stop focus", "end focus", "cancel focus"),
    "hide": ("hide", "go hide", "go away"),
    "new-chat": ("new chat", "/new", "reset"),
    "rename-chat": ("rename chat", "rename this chat", "name this chat"),
    "breaks-off": ("breaks off", "no breaks", "stop break reminders", "break reminders off"),
    "breaks-on": ("breaks on", "break reminders on"),
    "focus-alerts-off": ("focus alerts off", "focus notifications off"),
    "focus-alerts-on": ("focus alerts on", "focus notifications on"),
    "settings": ("settings", "preferences", "options", "open settings"),
    "history": ("history", "chats", "my chats", "chat history"),
    "whats-new": ("what's new", "whats new", "what is new", "changes", "changelog", "release notes"),
    "update": ("check for updates", "update", "updates", "update yourself", "install update"),
    "report": ("report a problem", "report a bug", "report bug", "bug", "report"),
    "idea": ("suggest an idea", "feature request", "suggest a feature", "idea"),
    "version": ("version", "what version", "which version"),
}


def test_the_same_phrases_run_the_same_commands():
    table = Table()
    found = {phrase: table.find(phrase) for phrases in BEFORE.values() for phrase in phrases}
    assert len(found) == 60  # every phrase, none twice
    assert found == {phrase: cid for cid, phrases in BEFORE.items() for phrase in phrases}
    assert set(commands.COMMANDS) == set(commands.PHRASES) == set(BEFORE)  # every command has a phrase and a doer


def test_a_phrase_is_found_as_typed_give_or_take_case_and_punctuation():
    table = Table()
    assert table.find("Help?") == "help" and table.find("  STATUS.  ") == "status" and table.find("What's new!") == "whats-new"
    assert table.find("what  version") == "version"  # spaces inside count once
    for question in ("help me write a poem", "is there an update for numpy", "status of my order", "", "?"):
        assert table.find(question) is None


def test_another_languages_phrases_join_english_which_stays():
    table = Table({"help": ["aide", "Qu'est-ce que tu sais faire ?"], "hide": ["help"], "no-such-command": ["bonjour"]})
    assert table.find("aide") == "help" and table.find("qu'est-ce que tu sais faire") == "help"
    assert table.find("help") == "help"  # English wins where they share a phrase
    assert table.find("hide") == "hide" and table.find("bonjour") is None  # an id it doesn't know is left out
    assert Table().find("aide") is None  # and only that table has them


def test_status_lines_say_battery_disks_reminders_and_brain():
    now = time.time()
    upcoming = [reminders.Reminder(now + 300, "stretch"), reminders.Reminder(now + 600, "pasta", "timer")]
    lines = commands.status_lines((47.6, True), [("/", 81.2), ("/home", 40.0)], upcoming, now, "Claude Code", "model opus")
    assert lines == [
        "- Battery: 48% (plugged in)", "- Disk for /: 81% full", "- Disk for /home: 40% full",
        "- Reminder in 5 min: stretch", "- Timer in 10 min: pasta", "- Brain: Claude Code (model opus)",
    ]
    assert commands.status_lines(None, [], [], now, None, "ignored") == ["- No reminders set", "- Brain: none"]
    many = [reminders.Reminder(now + 60 * i, f"r{i}") for i in range(1, 9)]
    assert len([line for line in commands.status_lines(None, [], many, now, "X") if "Reminder" in line]) == 5


def test_memory_replies(tmp_path):
    mind = memory.Memory([], tmp_path / "memory.json")
    assert commands.memory_reply(mind, "list", "").startswith("Nothing yet")
    assert "I'll remember that: *I use Arch*" in commands.memory_reply(mind, "remember", "I use Arch.")
    assert "- I use Arch" in commands.memory_reply(mind, "list", "")
    assert commands.memory_reply(mind, "forget", "nothing like it").startswith("I don't remember")
    assert commands.memory_reply(mind, "forget", "I use Arch") == "Forgotten: *I use Arch*."
    commands.memory_reply(mind, "remember", "a")
    assert commands.memory_reply(mind, "forget-all", "") == "Forgotten, all 1 of them."
    assert commands.memory_reply(mind, "forget-all", "") == "There was nothing to forget."


def test_the_stopwatch_reads_as_a_clock():
    assert commands.offline_clock(245) == "4:05" and commands.offline_clock(3729) == "1:02:09" and commands.offline_clock(-3) == "0:00"
    assert commands.offline_clock(245, seconds=False) == "4 min" and commands.offline_clock(3729, seconds=False) == "1:02 h"
