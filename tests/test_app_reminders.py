"""Reminders in the whole app (M7-04, M5's reminder contract with M0's queue): an alert that waits until it's done or
snoozed, back after a restart, changed and repeated from the menu; and a focus session that ends with one summary of
what waited (M7-05)."""

import time
from datetime import datetime, timedelta

import pytest

from app_harness import make_companion, spin, until
from chatmon import reminders


@pytest.fixture
def companion(tmp_path, monkeypatch):
    yield from make_companion(tmp_path, monkeypatch)


def labels(c) -> list[str]:
    return [b.label for b in c.stage.bubble.buttons]


def saved(c) -> list[dict]:
    from chatmon.settings import State

    return State.load(c.state.path).get("reminders")


def out_of_the_way(c) -> None:
    spin(1.8)  # the greeting, once it's been up long enough to read
    c.stage.dismiss_message()


def test_a_reminder_that_comes_due_waits_until_done_or_snoozed(companion):
    c = companion
    out_of_the_way(c)
    r = c.reminders.add(time.time() - 1, "stretch")
    c._check_reminders()
    assert until(lambda: c.stage.bubble.title == "Reminder") and c._alert_key == f"reminder:{r.id}"
    assert labels(c) == ["Done", "Snooze 10 min", "Later…"] and "stretch" in c.stage.bubble.doc.toPlainText()
    assert c.reminders.get(r.id).fired and saved(c)[0]["fired"] is True  # kept, fired, until it's seen to
    c._check_reminders()
    assert not c.messages.waiting  # once
    assert c.stage.press_button("Snooze 10 min")
    snoozed = c.reminders.get(r.id)
    assert not snoozed.fired and abs(snoozed.due - (time.time() + 600)) < 5 and saved(c)[0]["due"] == snoozed.due
    snoozed.due = time.time() - 1
    c._check_reminders()
    assert until(lambda: c._alert_key == f"reminder:{r.id}")
    assert c.stage.press_button("Done")
    assert c.reminders.get(r.id) is None and saved(c) == []  # done: a one-off goes


def test_a_repeating_reminder_moves_on_when_done_and_later_offers_every_snooze(companion):
    c = companion
    out_of_the_way(c)
    rep = c.reminders.add(time.time() - 1, "stand up", repeat="daily@09:00")
    c._check_reminders()
    assert until(lambda: c.stage.bubble.title == "Reminder")
    rule = reminders.describe_repeat("daily@09:00")
    # Its first letter made a capital, the rest as written ("9:00 AM", and a translation's own capitals): not str.capitalize().
    assert rule[:1].upper() + rule[1:] in c.stage.bubble.doc.toPlainText()
    assert c.stage.press_button("Done")
    moved = c.reminders.get(rep.id)
    assert moved is not None and not moved.fired and datetime.fromtimestamp(moved.due).hour == 9 and moved.due > time.time()
    one = c.reminders.add(time.time() - 1, "call Sam")
    c._check_reminders()
    assert until(lambda: c._alert_key == f"reminder:{one.id}")
    assert c.stage.press_button("Later…")
    assert until(lambda: c.stage.bubble.title == "Snooze until…")
    assert labels(c)[:4] == ["10 min", "5 min", "15 min", "1 hour"] and labels(c)[4].startswith("Tomorrow at") and labels(c)[5] == "Done"
    assert c.stage.press_button("1 hour")
    assert abs(c.reminders.get(one.id).due - (time.time() + 3600)) < 5


def test_reminders_snooze_by_their_own_setting_not_the_breaks(companion):
    c = companion
    out_of_the_way(c)
    c._override(("reminders", "snooze_minutes"), 25)
    c.state.save()
    c.reload(quietly=True)
    r = c.reminders.add(time.time() - 1, "stretch")
    c._check_reminders()
    assert until(lambda: c._alert_key == f"reminder:{r.id}") and labels(c)[1] == "Snooze 25 min"
    assert c.config["breaks"]["snooze_minutes"] == 10  # breaks keep theirs


def test_reminders_fired_and_not_done_come_back_at_the_next_start(companion):
    from PyQt6.QtNetwork import QLocalServer

    from chatmon import app as appmod

    c = companion
    r = c.reminders.add(time.time() - 60, "call Sam")
    c.reminders.fire(time.time())
    c.reminders.add(time.time() - 30, "25-minute focus", "focus")  # a session that ended while Chatmon was off
    c.save()
    again = appmod.Companion(c.app, QLocalServer())  # the next start, from the same files
    try:
        assert again._alert_key == f"reminder:{r.id}" and again.stage.bubble.title == "Reminder"
        assert again.reminders.focus() is None and not again.messages.holding("focus")  # over, not holding bubbles forever
    finally:
        again.quit()


def reminder_item(c, text):
    c.menus.fill()
    sub = next(a.menu() for a in c.menu.actions() if a.text().startswith("Reminders ("))
    return next(a.menu() for a in sub.actions() if a.menu() is not None and text in a.text())


def test_each_reminder_in_the_menu_can_be_changed_repeated_or_cancelled(companion):
    c = companion
    r = c.reminders.add(time.time() + 3600, "call Sam")
    c.save()
    item = reminder_item(c, "call Sam")
    assert [a.text() for a in item.actions() if a.text()] == ["Edit…", "Repeat", "Cancel it"]
    repeat = next(a.menu() for a in item.actions() if a.text() == "Repeat")
    rules = [a.text() for a in repeat.actions()]
    at = datetime.fromtimestamp(r.due).strftime("%H:%M")
    shown = [reminders.describe_repeat(rule) for rule in (f"daily@{at}", f"weekdays@{at}")]
    assert rules == ["Never", *(s[:1].upper() + s[1:] for s in shown)] + rules[3:]  # "9:00 AM" as written, not str.capitalize()
    next(a for a in repeat.actions() if a.text().startswith("Every weekday")).trigger()
    assert c.reminders.get(r.id).repeat == f"weekdays@{at}" and saved(c)[0]["repeat"] == f"weekdays@{at}"
    next(a for a in reminder_item(c, "call Sam").actions() if a.text() == "Repeat").menu().actions()[0].trigger()  # Never
    assert c.reminders.get(r.id).repeat is None

    next(a for a in reminder_item(c, "call Sam").actions() if a.text() == "Edit…").trigger()
    assert c.ask_box.title.text() == "Change this reminder" and c.ask_box.entry.text() == "call Sam"
    c.submit("call Sam and Alex on 3/4")  # a day that can't be told: said, and nothing changes
    assert "day and month come in either order" in c.ask_box.answer.toPlainText() and c.ask_box.isVisible()
    assert c.reminders.get(r.id).text == "call Sam" and c.ask_box.entry.text() == "call Sam and Alex on 3/4"
    c.ask_box.entry.clear()
    c.submit("call Sam and Alex tomorrow at 5pm")
    changed = c.reminders.get(r.id)
    tomorrow = (datetime.now() + timedelta(days=1)).replace(hour=17, minute=0, second=0, microsecond=0)
    assert changed.text == "call Sam and Alex" and datetime.fromtimestamp(changed.due) == tomorrow and not c.ask_box.isVisible()
    assert until(lambda: c.stage.bubble.title == "Reminder changed")
    next(a for a in reminder_item(c, "call Sam and Alex").actions() if a.text() == "Edit…").trigger()
    c.submit("just words")  # words alone: the time stays
    assert c.reminders.get(r.id).text == "just words" and datetime.fromtimestamp(c.reminders.get(r.id).due) == tomorrow

    fired = c.reminders.add(time.time() - 5, "was due")
    c.reminders.fire(time.time())
    item = reminder_item(c, "was due")
    assert [a.text() for a in item.actions() if a.text()][:2] == ["Done", "Snooze"]
    next(a for a in item.actions() if a.text() == "Cancel it").trigger()
    assert c.reminders.get(fired.id) is None


def test_adding_a_reminder_keeps_its_repeat_and_explains_an_unclear_time(companion):
    c = companion
    out_of_the_way(c)
    c.open_ask()
    c.submit("remind me every weekday at 9 to stand up")
    r = next(r for r in c.reminders.upcoming() if r.text == "stand up")
    assert r.repeat == "weekdays@09:00" and reminders.describe_repeat(r.repeat) in c.ask_box.answer.toPlainText()
    c.submit("remind me friday tomorrow to call Sam")
    assert "I couldn't tell when" in c.ask_box.answer.toPlainText() and "friday tomorrow" in c.ask_box.answer.toPlainText()
    c.submit("reminders")
    assert f"({reminders.describe_repeat('weekdays@09:00')})" in c.ask_box.answer.toPlainText()
    c.ask_box.dismiss()
    c.handle({"type": "remind", "text": "every monday at 9 to plan the week"})
    assert next(r for r in c.reminders.upcoming() if r.text == "plan the week").repeat == "mon@09:00"
    assert until(lambda: c.stage.bubble.title == "Reminder set") and reminders.describe_repeat("mon@09:00") in c.stage.bubble.doc.toPlainText()
    c.handle({"type": "remind", "text": "on 3/4 to call Sam"})  # a script's own message, unclear: said, not set
    assert until(lambda: c.stage.bubble.title == "Reminder not set")
    assert not any(r.text == "call Sam" for r in c.reminders.upcoming())


def test_a_focus_session_that_ends_says_so_then_sums_up_what_waited(companion):
    c = companion
    out_of_the_way(c)
    c.start_focus(25)
    c.stage.dismiss_message()
    c.handle({"type": "say", "text": "Backup finished."})
    c.say("Chatmon 9.9 is ready", "Downloaded.", [("Update now", None), ("Later", None)], timeout_s=90, background=True)
    spin(0.3)
    assert len(c.messages.held("focus")) == 2 and not c.stage.message_visible()
    c.reminders.focus().due = time.time() - 1
    c._check_reminders()
    assert until(lambda: c.stage.bubble.title == "Focus session done!") and c.reminders.focus() is None
    c.stage.press_button("Done")
    assert until(lambda: c.stage.bubble.title in ("While you focused", "Chatmon 9.9 is ready"))
    seen = [c.stage.bubble.title]
    if seen[0] == "While you focused":
        assert "Backup finished." in c.stage.bubble.doc.toPlainText()
    c.stage.dismiss_message()
    assert until(lambda: c.stage.bubble.title != seen[0] and c.stage.message_visible())
    assert {seen[0], c.stage.bubble.title} == {"While you focused", "Chatmon 9.9 is ready"}  # the summary, and the one with buttons
