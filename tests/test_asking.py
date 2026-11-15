"""Questions on their way to a brain, on their own: one answered at a time, one waiting. No Qt."""

import pytest

from chatmon import asking
from chatmon.asking import Fold, Question, Questions


class Brain:
    label = "Pretend API"


class Attached:
    def __init__(self, name):
        self.name = name


def test_the_first_question_goes_and_the_next_waits_its_turn():
    qs = Questions()
    first, second = Question("chat", "cat?"), Question("chat", "dog?")
    assert qs.ask(first) is True and qs.current is first
    assert qs.ask(second) is False and qs.current is first and qs.waiting == [second]
    assert qs.full()
    with pytest.raises(ValueError):
        qs.ask(Question("chat", "fish?"))
    assert qs.finish() is second and qs.current is second and qs.waiting == []
    assert qs.finish() is None and qs.current is None and not qs.full()


def test_an_answer_belongs_to_the_chat_it_was_asked_in():
    qs = Questions()
    q = Question("chat-a", "cat?")
    qs.ask(q)
    assert qs.answering("chat-a") is q and qs.answering("chat-b") is None


def test_dropping_forgets_everything_on_its_way():
    qs = Questions()
    qs.ask(Question("chat", "cat?"))
    qs.ask(Question("chat", "dog?"))
    qs.failure = ("fish?", "no")
    qs.drop()
    assert qs.current is None and qs.waiting == [] and qs.failure is None and not qs.full()


def test_a_failure_is_shown_until_the_next_question():
    qs = Questions()
    qs.failure = ("cat?", "Pretend API took too long.")
    assert asking.tail(qs, "thinking") == ["**You:** cat?\n\n*Hmm, that didn't work.* Pretend API took too long."]
    qs.ask(Question("chat", "dog?"))
    assert qs.failure is None


def test_the_transcript_tail_shows_what_is_on_its_way_then_what_waits():
    qs = Questions()
    assert asking.tail(qs, "thinking") == []
    qs.ask(Question("chat", "cat?", [Attached("notes.txt"), Attached("photo.png")], Brain()))
    qs.ask(Question("chat", "", [Attached("log.txt")]))
    assert asking.tail(qs, "Pretend API is thinking…") == [
        "**You:** cat?\n\n*Attached: notes.txt, photo.png*\n\n*Pretend API is thinking…*",
        "**You:**\n\n*Attached: log.txt*\n\n*Waiting for the answer on its way: this one goes next (Stop ends that one).*",
    ]
    qs.current.partial = "A cat"  # its answer has started to come: drawn after the transcript, so no "thinking" any more
    assert asking.tail(qs, "Pretend API is thinking…")[0] == "**You:** cat?\n\n*Attached: notes.txt, photo.png*"


def test_a_question_keeps_its_lines_as_typed():
    """A question's line breaks used to be lost: Markdown runs lines of one paragraph together."""
    assert asking.typed("first line\nsecond line") == "first line\\\nsecond line"  # a backslash ends each line: a hard break
    assert asking.typed("one line") == "one line"
    qs = Questions()
    qs.ask(Question("chat", "a\nb", [], Brain()))
    assert asking.tail(qs, "thinking").pop().startswith("**You:** a\\\nb")


def test_a_question_carries_its_answer_so_far_when_it_started_and_what_goes_with_it():
    q = Question("chat", "hi")
    assert (q.partial, q.started, q.before) == ("", 0.0, None)  # nothing yet; the whole chat goes with it


def test_what_a_question_asks_and_what_asking_it_again_needs():
    q = Question("chat", "", [Attached("a.png")])
    assert q.asked() == "Have a look at what I attached." and Question("chat", "hi").asked() == "hi"
    assert (q.retried, q.tokens, q.fold) == (False, 0, None)
    q.fold = Fold(covers=12, room=6000)
    assert (q.fold.covers, q.fold.room) == (12, 6000)
