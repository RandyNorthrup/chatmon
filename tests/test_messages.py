"""The message queue on its own: which bubble shows next, and which waits. No Qt; times are made up."""

from chatmon.messages import ALERT, MIN_SHOWN, PLAIN, PLAIN_LIMIT, PROMPT, REMINDER, Message, MessageQueue


def plain(title, **kw):
    return Message(title, timeout_s=8, **kw)


def prompt(title, **kw):
    return Message(title, buttons=[("OK", None)], **kw)


def alert(title, key, **kw):
    """An alert comes on its own (an agent, a heads-up), as a reminder does."""
    return Message(title, buttons=[("OK", None)], timeout_s=None, key=key, priority=ALERT, alert=True, background=True, **kw)


def reminder(title, key, **kw):
    return Message(title, buttons=[("Done", None)], timeout_s=None, key=key, priority=REMINDER, alert=True, background=True, **kw)


def news(title, **kw):
    """A plain bubble that came on its own (an agent's, a script's)."""
    return plain(title, background=True, **kw)


def shown(q, now, visible=True):
    m = q.next(now, visible)
    return m.title if m else None


def drain(q, start=0.0):
    """Show each in turn, closing it as soon as it's up: the order they come in."""
    order, now = [], start
    while (m := q.next(now)) is not None:
        order.append(m.title)
        q.closed()
        now += 0.1
    return order


def test_a_bubbles_priority_comes_from_what_it_asks_of_you():
    assert plain("x").priority == PLAIN
    assert prompt("x").priority == PROMPT  # buttons
    assert Message("x", timeout_s=None).priority == PROMPT  # stays until closed
    assert alert("x", "k").priority == ALERT and reminder("x", "r").priority == REMINDER


def test_alerts_then_reminders_then_prompts_then_plain_bubbles():
    q = MessageQueue()
    for m in (plain("agent done"), prompt("delete chat?"), reminder("stretch", "reminder:1"), alert("claude needs you", "agent:claude"), plain("tests pass")):
        q.add(m)
    assert drain(q) == ["claude needs you", "stretch", "delete chat?", "agent done", "tests pass"]


def test_nothing_but_plain_bubbles_is_ever_dropped():
    q = MessageQueue()
    for i in range(20):
        q.add(alert(f"alert {i}", f"agent:{i}"))
        q.add(reminder(f"reminder {i}", f"reminder:{i}"))
        q.add(prompt(f"prompt {i}"))
        q.add(plain(f"plain {i}"))
    order = drain(q)
    assert [t for t in order if t.startswith("alert")] == [f"alert {i}" for i in range(20)]
    assert [t for t in order if t.startswith("reminder")] == [f"reminder {i}" for i in range(20)]
    assert [t for t in order if t.startswith("prompt")] == [f"prompt {i}" for i in range(20)]
    # Only the newest plain ones are left, oldest gone first.
    assert [t for t in order if t.startswith("plain")] == [f"plain {i}" for i in range(20 - PLAIN_LIMIT, 20)]


def test_waiting_news_of_the_same_thing_is_merged_newest_wins():
    q = MessageQueue()
    q.add(prompt("blocking"))
    assert shown(q, 0) == "blocking"
    q.add(plain("Claude finished", key="agent:claude"))
    q.add(plain("Codex finished", key="agent:codex"))
    q.add(plain("Claude: success!", key="agent:claude"))
    q.closed()
    assert drain(q, 1) == ["Codex finished", "Claude: success!"]


def test_a_bubble_with_buttons_is_never_replaced_by_anything_that_matters_as_much_or_less():
    q = MessageQueue()
    q.add(prompt("Focus done!"))
    assert shown(q, 0) == "Focus done!"
    q.add(plain("Claude finished"))
    q.add(news("Codex finished"))
    q.add(prompt("Update ready", background=True))
    for now in (1, MIN_SHOWN, 60, 600):
        assert q.next(now) is None and q.showing.title == "Focus done!"
    assert q.wake_at(600) is None  # nothing to look again for until it closes
    q.closed()
    assert shown(q, 601) == "Update ready"


def test_something_more_important_takes_over_after_the_minimum_and_the_bubble_comes_back():
    q = MessageQueue()
    q.add(prompt("Delete chat?"))
    assert shown(q, 0) == "Delete chat?"
    q.add(alert("Claude needs you", "agent:claude"))
    assert q.next(MIN_SHOWN - 0.1) is None  # not before it's been up the minimum
    assert q.wake_at(0.5) == MIN_SHOWN
    assert shown(q, MIN_SHOWN) == "Claude needs you"
    q.closed()
    assert shown(q, MIN_SHOWN + 1) == "Delete chat?"  # pushed aside, not lost


def test_a_plain_bubble_gives_way_to_the_next_plain_one_after_the_minimum_and_is_gone():
    q = MessageQueue()
    q.add(news("one"))
    assert shown(q, 0) == "one"
    q.add(news("two"))
    assert q.next(1.0) is None and q.wake_at(1.0) == MIN_SHOWN
    assert shown(q, MIN_SHOWN) == "two"
    q.closed()
    assert q.next(10) is None  # "one" was seen: it doesn't come back


def test_what_you_did_shows_at_once_and_goes_before_what_came_on_its_own():
    q = MessageQueue()
    q.add(news("Claude finished"))
    assert shown(q, 0) == "Claude finished"
    q.add(plain("Chat saved"))  # you saved it: no waiting for the minimum
    assert shown(q, 0.1) == "Chat saved"
    q.add(news("Codex finished"))
    q.add(plain("Settings reloaded"))
    q.closed()
    assert drain(q, 1) == ["Settings reloaded", "Codex finished"]


def test_your_prompt_takes_over_one_that_came_on_its_own_which_comes_back():
    q = MessageQueue()
    q.add(prompt("Shall I watch your coding agents?", background=True))
    assert shown(q, 0) == "Shall I watch your coding agents?"
    q.add(prompt("Delete chat?"))
    assert shown(q, 0.1) == "Delete chat?"
    q.add(prompt("Clear chat history?"))  # yours too: it waits for the one you're answering
    assert q.next(50) is None
    q.closed()
    assert drain(q, 51) == ["Clear chat history?", "Shall I watch your coding agents?"]  # yours first, then the one pushed aside


def test_newer_news_of_whats_showing_replaces_it_after_the_minimum():
    q = MessageQueue()
    q.add(alert("Claude needs you", "agent:claude", text="Approve?"))
    assert shown(q, 0) == "Claude needs you"
    q.add(alert("Claude needs you", "agent:claude", text="Approve the deploy?"))
    assert q.next(1) is None
    m = q.next(MIN_SHOWN)
    assert m.text == "Approve the deploy?"
    q.closed()
    assert q.next(10) is None  # the older one is gone, not queued behind


def test_an_alert_waits_for_the_alert_showing():
    q = MessageQueue()
    q.add(alert("Claude needs you", "agent:claude"))
    q.add(alert("Codex needs you", "agent:codex"))
    assert shown(q, 0) == "Claude needs you"
    assert q.next(100) is None
    q.closed()
    assert shown(q, 101) == "Codex needs you"


def test_what_no_longer_stands_is_withdrawn():
    q = MessageQueue()
    q.add(alert("Claude needs you", "agent:claude"))
    q.add(alert("Codex needs you", "agent:codex"))
    assert shown(q, 0) == "Claude needs you"
    q.withdraw("agent:codex")  # Codex got going again before it was seen
    q.closed()
    assert q.next(1) is None


def test_a_bubble_closed_behind_the_queues_back_is_forgotten():
    q = MessageQueue()
    q.add(prompt("first"))
    assert shown(q, 0) == "first"
    q.add(prompt("second"))
    assert q.next(10, visible=True) is None
    assert shown(q, 10, visible=False) == "second"  # the stage closed "first" itself


def test_quiet_holds_all_but_what_came_while_you_were_using_chatmon():
    q = MessageQueue()
    q.hold("quiet", lambda m: m.yours)
    q.add(plain("Claude finished"))
    q.add(prompt("Delete chat?", yours=True))
    assert drain(q) == ["Delete chat?"]
    assert [m.title for m in q.held("quiet")] == ["Claude finished"] and [m.title for m in q.held()] == ["Claude finished"]
    q.release("quiet")
    assert drain(q, 1) == ["Claude finished"]


def test_more_than_five_bubbles_held_through_quiet_are_all_kept_unless_plain():
    q = MessageQueue()
    q.hold("quiet", lambda m: False)
    for i in range(8):
        q.add(prompt(f"prompt {i}"))
    assert q.next(0) is None and len(q.held()) == 8
    q.release("quiet")
    assert drain(q, 1) == [f"prompt {i}" for i in range(8)]


def test_focus_holds_background_messages_below_reminders():
    q = MessageQueue()
    q.hold("focus", lambda m: not m.background or m.priority <= REMINDER)
    q.add(plain("Claude finished", background=True))
    q.add(prompt("Chatmon 1.2 is ready", background=True))
    q.add(plain("Chat saved"))  # what you did: shown
    q.add(alert("Claude needs you", "agent:claude"))
    q.add(reminder("stretch", "reminder:1"))
    assert drain(q) == ["Claude needs you", "stretch", "Chat saved"]
    assert {m.title for m in q.held("focus")} == {"Claude finished", "Chatmon 1.2 is ready"} and q.holding("focus")
    q.release("focus")
    assert not q.holding("focus")
    assert drain(q, 1) == ["Chatmon 1.2 is ready", "Claude finished"]


def test_a_hold_set_again_takes_the_new_rule():
    q = MessageQueue()
    q.hold("quiet", lambda m: False)  # a full-screen window covers the companion: even alerts wait
    q.add(alert("Reminder", "reminder:x"))
    assert q.next(0) is None
    q.hold("quiet", lambda m: m.alert)  # still quiet, but nothing covers it now
    assert shown(q, 1) == "Reminder"


def test_wake_at_says_when_to_look_again():
    q = MessageQueue()
    assert q.wake_at(0) is None
    q.add(news("one"))
    assert q.wake_at(5) == 5  # nothing showing: now
    q.next(5)
    assert q.wake_at(5) is None  # nothing else waiting
    q.add(news("two"))
    assert q.wake_at(6) == 5 + MIN_SHOWN
    assert q.wake_at(100) == 100  # past the minimum already
    q.add(prompt("Delete chat?", background=True))
    q.next(100)
    q.add(news("three"))
    assert q.wake_at(200) is None  # a prompt shows: nothing waiting can take its place
