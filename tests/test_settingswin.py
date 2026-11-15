"""The Settings window on its own (M7-03): the AI tab's key field and Test, the Accessibility tab, reminders' own
snooze, "almost empty" kept below "low", and only what changed handed back. The companion's side (keys into the
keychain, settings applied at once) is in test_app_m7.py."""

import pytest
from PyQt6.QtGui import QKeySequence

from chatmon.settingswin import TABS, SettingsWindow

VALUES = {
    "name": "Pip", "companion": "penguin", "size": 120, "walk": True, "sleep_after_minutes": 10, "autostart": False,
    "bubble_style": "match", "bubble_effects": True, "check_updates": True, "brain": "", "timeout_seconds": 180,
    "show_replies": False, "keep_chats": True, "context_tokens": 48000, "instructions": "", "memory": [],
    "breaks_every": 60, "snooze": 10, "focus": 25, "battery_low": 20, "battery_critical": 10, "disk_full": 90,
    "updates_heads_up": True, "updates_every_hours": 6, "break_reminders": True, "focus_done": True, "read_aloud": True,
    "reminder_snooze": 10, "text_scale": 100, "bubble_time": "normal", "reduced_motion": "system", "accessible_ask_box": "auto",
    "sound": True, "volume": 70, "cues": {"needs-you": True, "reminder": True, "focus-done": True, "done": False, "success": False,
                                          "error": False, "pop": False},
    "hotkey": "", "follow_screen": False, "api_key": None,
}
CHOICES = {
    "companions": [("penguin", "Penguin")], "bubble_styles": [("match", "Match")],
    "brains": [("", "Automatic"), ("claude", "Claude Code"), ("anthropic-api", "Anthropic API")],
    "keys": {"anthropic-api": {"said": "Its key comes from ANTHROPIC_API_KEY.", "saved": False}}, "key_store": "memory only",
}


@pytest.fixture
def window(qapp):
    w = SettingsWindow(dict(VALUES), CHOICES)
    w.show()
    got = []
    w.saved.connect(got.append)
    w.got = got
    yield w
    w.close()
    w.deleteLater()


def test_nothing_changed_hands_back_nothing(window):
    window._save()
    assert window.got == [{}]


def test_the_key_field_shows_only_for_an_api_brain_and_a_key_typed_is_handed_back_once(window):
    w = window
    assert w.key.isHidden()  # Automatic: no key
    w.brain.setCurrentIndex(w.brain.findData("claude"))
    assert w.key.isHidden()  # a command-line tool: none either
    w.brain.setCurrentIndex(w.brain.findData("anthropic-api"))
    assert not w.key.isHidden() and "ANTHROPIC_API_KEY" in w.key_status.text() and "memory only" in w.key_status.text()
    assert w.key.echoMode() == w.key.EchoMode.Password and not w.remove_key_button.isEnabled()  # nothing saved to remove
    w.key.setText("  sk-test  ")
    w._save()
    assert w.got == [{"brain": "anthropic-api", "api_key": ("anthropic-api", "sk-test")}] and w.key.text() == ""


def test_test_and_remove_key_ask_the_companion(window):
    w = window
    asked, removed = [], []
    w.test_requested.connect(lambda name, key: asked.append((name, key)))
    w.remove_key.connect(removed.append)
    w.test_button.click()
    assert asked == [("", "")] and w.test_result.text() == "Asking…" and not w.test_button.isEnabled()
    w.show_test(False, "Anthropic API: invalid x-api-key (HTTP 401).", 0.4)
    assert w.test_result.text() == "✕ Anthropic API: invalid x-api-key (HTTP 401)." and w.test_button.isEnabled()
    w.brain.setCurrentIndex(w.brain.findData("anthropic-api"))
    w.key.setText("sk-typed")
    w.test_button.click()
    assert asked[-1] == ("anthropic-api", "sk-typed")  # tried with the key typed, before it's saved
    w.show_key_status("anthropic-api", "", {"said": "A key is saved in memory only.", "saved": True})
    assert w.remove_key_button.isEnabled()
    w.remove_key_button.click()
    assert removed == ["anthropic-api"]
    w.show_key_status("anthropic-api", "Removed from memory only.", {"said": "No key yet.", "saved": False})
    assert w.key_status.text() == "Removed from memory only. No key yet." and not w.remove_key_button.isEnabled()


def test_the_accessibility_tab_hands_back_what_was_set(window):
    w = window
    w.show_tab("accessibility")
    assert w.tabs.currentIndex() == TABS.index("accessibility") == w.tabs.count() - 1
    w.text_scale.setCurrentIndex(w.text_scale.findData(150))
    w.bubble_time.setCurrentIndex(w.bubble_time.findData("until closed"))
    w.reduced_motion.setCurrentIndex(w.reduced_motion.findData("on"))
    w.accessible_ask_box.setCurrentIndex(w.accessible_ask_box.findData("on"))
    w.hotkey.setKeySequence(QKeySequence("Ctrl+Alt+Space"))
    w.volume.setValue(40)
    w.cues["done"].setChecked(True)
    w.read_aloud.setChecked(False)
    w._save()
    assert w.got == [{
        "text_scale": 150, "bubble_time": "until closed", "reduced_motion": "on", "accessible_ask_box": "on", "hotkey": "Ctrl+Alt+Space",
        "volume": 40, "cues": {**VALUES["cues"], "done": True}, "read_aloud": False,
    }]


def test_one_switch_turns_every_sound_off(window):
    w = window
    w.sound.setChecked(False)
    assert not w.volume.isEnabled() and not any(box.isEnabled() for box in w.cues.values())
    w._save()
    assert w.got == [{"sound": False}]


def test_the_alerts_sounds_are_on_and_the_rest_off_by_default(qapp):
    w = SettingsWindow({k: v for k, v in VALUES.items() if k != "cues"}, CHOICES)  # given nothing: Chatmon's defaults
    assert {name for name, box in w.cues.items() if box.isChecked()} == {"needs-you", "reminder", "focus-done"}
    w.deleteLater()


def test_reminders_have_their_own_snooze_and_almost_empty_stays_below_low(window):
    w = window
    w.reminder_snooze.setValue(25)
    w.battery_low.setValue(8)
    assert w.battery_critical.maximum() == 7 and w.battery_critical.value() == 7  # was 10: kept below 8
    w.battery_low.setValue(0)  # battery warnings off: no limit
    assert w.battery_critical.maximum() == 50
    w._save()
    assert w.got == [{"reminder_snooze": 25, "battery_low": 0, "battery_critical": 7}]


def test_backup_and_bring_back_ask_the_companion(window):
    w = window
    backups, restores = [], []
    w.backup_requested.connect(backups.append)
    w.restore_requested.connect(lambda: restores.append(1))
    w.backup_chats.setChecked(False)
    next(b for b in w.findChildren(type(w.test_button)) if b.text() == "Back up…").click()
    next(b for b in w.findChildren(type(w.test_button)) if b.text() == "Bring back…").click()
    assert backups == [False] and restores == [1]


def test_the_language_is_the_systems_or_one_chatmon_has_and_applies_at_the_next_start(qapp):
    """M8's setting: "System default", then each language Chatmon can be shown in, by its own name."""
    w = SettingsWindow({**VALUES, "language": ""}, {**CHOICES, "languages": ["en", "de"]})
    got = []
    w.saved.connect(got.append)
    assert [w.language.itemData(i) for i in range(w.language.count())] == ["", "en", "de"]
    assert w.language.itemText(0) == "System default" and w.language.itemText(2) == "Deutsch"
    w.language.setCurrentIndex(2)
    w._save()
    assert got == [{"language": "de"}]
    w.deleteLater()
