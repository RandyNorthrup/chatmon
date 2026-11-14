"""Asking a brain, in the whole app: answers that stream in, finish after the box closes and can be stopped (M7-01);
failures that say what to do next, and which brain answers never a surprise (M7-02); the brain found without waiting
(M0's note 7); which of the chat a brain is given (M1B's note 7); a brain per chat, and another brain (M7-09)."""

import time

import pytest

from app_harness import PretendBrain, make_companion, spin, until


@pytest.fixture
def companion(tmp_path, monkeypatch):
    yield from make_companion(tmp_path, monkeypatch)


def shown(c) -> str:
    return c.ask_box.answer.toPlainText()


def labels(c) -> list[str]:
    return [b.label for b in c.stage.bubble.buttons]


def api(name: str, label: str):
    """An API brain that's set up (a key in the settings), never asked for real here."""
    from chatmon import brains

    return brains.Brain(name, "anthropic", label=label, model="m", api_key="k", api_key_env=f"{name.upper()}_KEY")


# -- M7-01: answers


def test_an_answer_shows_as_it_streams_in_and_survives_the_box_being_drawn_again(companion, monkeypatch):
    c = companion
    brain = PretendBrain(c, monkeypatch)
    c.open_ask()
    c.submit("Name a cat")
    assert "Pretend API is thinking" in shown(c)
    c._partial("Mo")
    c._partial("chi, or ")
    assert c.questions.current.partial == "Mochi, or "
    box = c.ask_box  # if this fails, which part of "the box shows the chat" didn't hold
    assert until(lambda: "Mochi, or" in shown(c), 10), (box.isVisible(), box.entry.isVisible(), box.history_button.isVisible(), shown(c))
    assert "thinking" not in shown(c)  # under the question, in order
    c.submit("5 km in miles")  # the chat is drawn again for an answer of Chatmon's own
    c._partial("Biscuit")
    assert until(lambda: "Mochi, or Biscuit" in shown(c)) and "3.107 miles" in shown(c)  # all of it, not just the newest piece
    c.ask_box.dismiss()
    c.open_ask()  # closed and opened again
    assert until(lambda: "Mochi, or Biscuit" in shown(c))
    brain.answer("Mochi, or Biscuit.")
    assert shown(c).count("Mochi, or Biscuit") == 1 and c.chat.messages[-1].text == "Mochi, or Biscuit."


def test_closing_the_box_lets_the_answer_finish_and_a_bubble_says_it_came(companion, monkeypatch):
    """Closing the box used to stop the answer and drop the question waiting: now both go on, and Read shows them."""
    c = companion
    brain = PretendBrain(c, monkeypatch)
    spin(1.8)
    c.stage.dismiss_message()  # the greeting, out of the way
    c.open_ask()
    c.submit("first")
    c.submit("second")
    c.ask_box.dismiss()  # Esc
    assert c.questions.current is not None and c.questions.current.text == "first"  # still on its way
    brain.answer("one")
    assert [m.text for m in c.chat.messages] == ["first", "one"] and brain.asked[-1][1] == "second"  # and the next went
    assert until(lambda: c.stage.bubble.title == "Pretend API answered") and labels(c) == ["Read"]
    brain.answer("two")
    assert [m.text for m in c.chat.messages][-2:] == ["second", "two"]
    assert until(lambda: c.stage.bubble.title == "Pretend API answered") and len([m for m in c.messages.waiting if m.key == "answered"]) == 0
    assert c.stage.press_button("Read")
    assert c.ask_box.isVisible() and "two" in shown(c) and "one" in shown(c)
    brain.answer("late")  # nothing on its way: nothing happens
    assert len(c.chat.messages) == 4


def test_the_box_says_who_is_answering_and_stop_ends_it(companion, monkeypatch):
    c = companion
    brain = PretendBrain(c, monkeypatch)
    c.open_ask()
    assert not c.ask_box.busy.isVisibleTo(c.ask_box)
    c.submit("first")
    assert c.ask_box.busy.isVisibleTo(c.ask_box) and c.ask_box.busy_label.text().startswith("Pretend API is answering")
    assert c.questions.current.started > 0
    c.submit("second")
    c._partial("Half an ans")
    c.ask_box.stop_button.click()  # what came so far stays, marked; the one waiting goes
    assert [(m.role, m.text) for m in c.chat.messages] == [("user", "first"), ("assistant", "Half an ans\n\n*(Stopped here.)*")]
    assert brain.asked[-1][1] == "second" and c.ask_box.busy.isVisibleTo(c.ask_box)
    c.ask_box.stop_button.click()  # nothing came of this one: it goes back in the box
    assert c.ask_box.entry.text() == "second" and len(c.chat.messages) == 2
    assert c.questions.current is None and not c.ask_box.busy.isVisibleTo(c.ask_box)
    c.ask_box.entry.clear()
    c.submit("third")
    brain.answer("done")
    assert not c.ask_box.busy.isVisibleTo(c.ask_box)


def test_leaving_the_chat_still_drops_its_question(companion, monkeypatch):
    c = companion
    brain = PretendBrain(c, monkeypatch)
    c.open_ask()
    c.submit("first")
    c._new_chat()
    assert c.questions.current is None and not c.ask_box.busy.isVisibleTo(c.ask_box)
    brain.answer("for the old chat")
    assert c.chat.messages == []


# -- M7-02: failures, and which brain answers


def test_a_failed_question_offers_to_try_again_ask_the_next_brain_or_open_settings(companion, monkeypatch):
    c = companion
    brain = PretendBrain(c, monkeypatch)
    monkeypatch.setattr(c, "brains", {"pretend": brain.brain, "other": api("other", "Other API")})
    spin(1.8)
    c.stage.dismiss_message()
    c.open_ask()
    c.submit("explain")
    c._failed("Pretend API: invalid x-api-key (HTTP 401). Check its key.")
    assert c.ask_box.entry.text() == "explain"  # back in the box, as before
    assert until(lambda: c.stage.bubble.title == "Pretend API couldn't answer")
    assert labels(c) == ["Try again", "Ask Other API", "Settings"] and "HTTP 401" in c.stage.bubble.doc.toPlainText()
    assert c.stage.press_button("Ask Other API")
    assert c.questions.current.brain.name == "other" and c.ask_box.entry.text() == "" and brain.asked[-1][1] == "explain"
    c._failed("Other API took too long to answer.")
    assert until(lambda: c.stage.bubble.title == "Other API couldn't answer")
    assert c.stage.press_button("Try again")
    assert c.questions.current.brain.name == "other"  # the same brain, again
    c._failed("Other API took too long to answer.")
    assert until(lambda: c.stage.bubble.title == "Other API couldn't answer")
    assert labels(c) == ["Try again", "Ask Pretend API", "Settings"]
    assert c.stage.press_button("Settings")
    assert c._settings_window.isVisible() and c._settings_window.tabs.currentIndex() == 1  # the AI tab
    c._settings_window.close()


def test_with_no_other_brain_a_failure_offers_only_try_again_and_settings(companion, monkeypatch):
    c = companion
    brain = PretendBrain(c, monkeypatch)
    monkeypatch.setattr(c, "brains", {"pretend": brain.brain})
    spin(1.8)
    c.stage.dismiss_message()
    c.ask_box.dismiss()
    c.submit("explain")  # the box closed: the bubble says so all the same
    c._failed("Pretend API took too long to answer.")
    assert until(lambda: c.stage.bubble.title == "Pretend API couldn't answer") and labels(c) == ["Try again", "Settings"]


def test_a_brain_picked_that_cant_answer_is_announced_once_for_that_pick(companion, monkeypatch):
    from chatmon import brains

    c = companion
    brain = PretendBrain(c, monkeypatch)
    gone = brains.Brain("gone", "command", label="Gone Tool", command=["no-such-tool-for-chatmon-tests"])
    monkeypatch.setattr(c, "brains", {"pretend": brain.brain, "gone": gone})
    spin(1.8)
    c.stage.dismiss_message()
    c._pick_brain("gone")
    c.open_ask()
    c.submit("one")
    assert until(lambda: c.stage.bubble.title == "Gone Tool isn't available")
    assert "no-such-tool-for-chatmon-tests not found, so Pretend API answers for now" in c.stage.bubble.doc.toPlainText()
    c.stage.dismiss_message()
    brain.answer("1")
    c.submit("two")
    spin(0.5)
    assert c.stage.bubble.title == "Gone Tool isn't available" and not c.stage.message_visible()  # not again
    assert [m for _, m in c.recent_messages() if m.title == "Gone Tool isn't available"].__len__() == 1
    brain.answer("2")
    c._pick_brain("gone")  # picked again: said again
    c.submit("three")
    assert until(lambda: c.stage.message_visible() and c.stage.bubble.title == "Gone Tool isn't available")


def test_after_naming_it_says_which_brain_will_answer_or_how_to_set_one_up(companion, monkeypatch):
    c = companion
    PretendBrain(c, monkeypatch)
    c._asking_name = True
    c.open_ask(focus=False)
    c.submit("Pip")
    assert until(lambda: c.stage.bubble.title == "Pip! I love it.")
    assert "Your questions go to Pretend API" in c.stage.bubble.doc.toPlainText()
    monkeypatch.setattr(c, "_find_brain", lambda then: then(None))
    c._asking_name = True
    c.open_ask(focus=False)
    c.submit("Pippa")
    assert until(lambda: c.stage.bubble.title == "Pippa! I love it.")
    assert "No AI is set up yet" in c.stage.bubble.doc.toPlainText() and "Settings › AI" in c.stage.bubble.doc.toPlainText()


SERVER = "http://localhost:1"


@pytest.fixture
def server_here_not_yours(monkeypatch):
    """A model server listening here, run by someone else (as far as Automatic can tell)."""
    from chatmon import brains

    for name in ("_confirmed", "_unsure", "_unsure_owner"):
        monkeypatch.setattr(brains, name, set())
    monkeypatch.setattr(brains, "_owned", {SERVER: (time.monotonic() + 3600, False)})  # not yours, and known not to be
    monkeypatch.setattr(brains, "reachable", lambda url, timeout=0.15, wait=True: url == SERVER)
    return brains.Brain("someones", "openai", label="Someone's server", url=SERVER, model="m", local=True)


def test_a_model_server_that_isnt_yours_is_offered_once_and_kept_once_confirmed(companion, monkeypatch, server_here_not_yours):
    from chatmon import brains

    c = companion
    asked = []
    monkeypatch.setattr(c, "brains", {"someones": server_here_not_yours})
    monkeypatch.setattr(c.asker, "ask", lambda brain, *a, **k: asked.append(brain.name))
    spin(1.8)
    c.stage.dismiss_message()
    c.open_ask()
    c.submit("hello")
    assert "I haven't found an AI to ask yet" in shown(c) and asked == []  # Automatic left it alone
    assert until(lambda: c.stage.bubble.title == "Use the model server at localhost:1?") and labels(c) == ["Use it", "Not now"]
    c.stage.press_button("Not now")
    c.submit("hello again")
    spin(0.5)
    assert not c.stage.message_visible()  # once a run
    c._server_offered.clear()
    c.submit("and again")
    assert until(lambda: c.stage.bubble.title == "Use the model server at localhost:1?")
    c.stage.press_button("Use it")
    assert c.state.get("trusted_servers") == ["localhost:1"] and brains.trusted(SERVER)
    c.submit("now?")
    assert until(lambda: asked == ["someones"])
    brains._confirmed.clear()  # as at the next start: handed back from state
    c._trust_saved_servers()
    assert brains.trusted(SERVER)


# -- M0's note 7: never waiting for the brain on the screen's thread


def test_asking_never_waits_on_the_screens_thread_to_find_the_brain(companion, monkeypatch):
    from chatmon import brains

    c = companion
    for name in ("_confirmed", "_unsure", "_unsure_owner"):
        monkeypatch.setattr(brains, name, set())
    monkeypatch.setattr(brains, "_reachable", {})
    monkeypatch.setattr(brains, "_owned", {})

    def slow_look(url, timeout):  # a port nobody answers on takes seconds on Windows: here, a server found slowly
        time.sleep(0.6)
        brains._reachable[url] = (time.monotonic(), True)
        return True

    monkeypatch.setattr(brains, "_look", slow_look)
    monkeypatch.setattr(brains, "_look_owner", lambda url: brains._owned.__setitem__(url, (time.monotonic(), True)) or True)
    local = brains.Brain("mine", "openai", label="My server", url="http://localhost:2", model="m", local=True)
    monkeypatch.setattr(c, "brains", {"mine": local})
    asked = []
    monkeypatch.setattr(c.asker, "ask", lambda brain, system, history, question, *a, **k: asked.append((brain.name, question)))
    c.open_ask()
    started = time.monotonic()
    c.submit("hello")
    assert time.monotonic() - started < 0.4  # it didn't wait for the look
    assert until(lambda: asked == [("mine", "hello")])  # asked once the thread had looked


# -- M1B's note 7: a brain that reads files is never handed another brain's answers


def test_a_brain_that_reads_files_gets_only_its_own_answers_and_summaries(companion, monkeypatch):
    from chatmon import chats

    c = companion
    first = PretendBrain(c, monkeypatch)
    c.open_ask()
    c.submit("q1")
    first.answer("an answer from the API")
    tool = PretendBrain(c, monkeypatch, kind="command", tools_off=False, name="tool", label="A tool")
    c.submit("q2")
    assert tool.asked[-1][0] == [("q1", chats.OTHER_ANSWER)]  # the API's answer isn't passed on
    tool.answer("the tool's answer")
    first = PretendBrain(c, monkeypatch)
    c.submit("q3")
    assert first.asked[-1][0] == [("q1", "an answer from the API"), ("q2", "the tool's answer")]  # an API sees it all
    c.chat.set_summary("everything so far", 2)
    assert c.chat.summary_for("tool", own_only=True) == ("", 0)  # made from every brain's answers: not for the tool


# -- M7-09 and M1B's note 8: a brain per chat, and another brain


def test_a_chat_keeps_its_brain_and_another_brain_can_answer_the_last_question(companion, monkeypatch):
    c = companion
    first = PretendBrain(c, monkeypatch)
    c.open_ask()
    c.submit("Name a cat")
    first.answer("Mochi.")
    assert c.chat.brain == "pretend" and [m.by for m in c.chat.messages] == ["pretend", "pretend"]
    other = PretendBrain(c, monkeypatch, name="other", label="Other API")
    c._ask_other("other")
    assert other.asked[-1][:2] == ([], "Name a cat")  # the same question, with the chat before it (none)
    other.answer("Biscuit.")
    assert [(m.text, m.by) for m in c.chat.messages][-2:] == [("Name a cat", "other"), ("Biscuit.", "other")]
    assert c.chat.brain == "other"  # carrying on asks the brain that answered last


def test_carrying_a_chat_on_asks_its_own_brain_before_the_one_picked(companion, monkeypatch):
    from chatmon import brains

    c = companion
    for name in ("_unsure", "_unsure_owner"):  # nothing left to look at by earlier tests: the answer comes at once
        monkeypatch.setattr(brains, name, set())
    a, b = api("pretend", "Pretend API"), api("other", "Other API")
    monkeypatch.setattr(c, "brains", {"pretend": a, "other": b})
    c.state.set("brain", "other")
    found = []
    c._find_brain(found.append)
    c.chat.brain = "pretend"
    c._find_brain(found.append)
    assert [x.name for x in found] == ["other", "pretend"]
