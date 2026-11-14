"""The question on its way to a brain, and the one waiting behind it.

A brain answers one question at a time: `brains.Asker` drops a question still being answered when it's asked
another. So a question asked meanwhile waits here until the first is answered (or fails), then goes; past
`MAX_WAITING` it's refused, and stays in the box to send later. Each question carries what asking it again
needs: the brain it went to, whether it has been asked once more already with less, how much was sent, and the
summing up of the chat's earlier part that has to happen first (`fold`).

No Qt here: the app sends, and says when an answer came.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MAX_WAITING = 1  # questions waiting behind the one being answered


@dataclass
class Fold:
    """The chat's earlier part is being summed up before the question can go: how many of its question-and-
    answer pairs the summary will stand for, and the room (in tokens) the question had."""

    covers: int
    room: int


@dataclass
class Question:
    chat_id: str
    text: str
    attached: list = field(default_factory=list)
    brain: Any = None  # the brain it goes to, picked when it was asked
    retried: bool = False  # asked once more already, with less (too long for the brain)
    tokens: int = 0  # how much it went with, as counted (to say how much is too much)
    fold: Fold | None = None

    def asked(self) -> str:
        """What the brain is asked: the question, or a word about what's attached when it's all there is."""
        return self.text or "Have a look at what I attached."


class Questions:
    def __init__(self) -> None:
        self.current: Question | None = None  # on its way
        self.waiting: list[Question] = []
        self.failure: tuple[str, str] | None = None  # (question, why) the last one that failed, until the next is asked

    def full(self) -> bool:
        return self.current is not None and len(self.waiting) >= MAX_WAITING

    def ask(self, question: Question) -> bool:
        """True: it goes now. False: it waits for the one on its way. Refused (ValueError) when `full()`."""
        if self.full():
            raise ValueError("too many questions waiting")
        self.failure = None
        if self.current is None:
            self.current = question
            return True
        self.waiting.append(question)
        return False

    def answering(self, chat_id: str) -> Question | None:
        """The question on its way, if it was asked in `chat_id` (an answer for a chat since left goes nowhere)."""
        return self.current if self.current is not None and self.current.chat_id == chat_id else None

    def finish(self) -> Question | None:
        """The question on its way was answered, or failed: the next one, now on its way, if any."""
        self.current = self.waiting.pop(0) if self.waiting else None
        return self.current

    def drop(self) -> None:
        """Leaving the chat, or closing the box: nothing is on its way any more."""
        self.current = None
        self.waiting.clear()
        self.failure = None


def tail(questions: Questions, thinking: str) -> list[str]:
    """The part of the transcript still to be answered, as Markdown: the last failure, the question on its way
    (with `thinking`, what the brain is doing about it), and those waiting."""
    parts = []
    if questions.failure is not None:
        text, why = questions.failure
        parts.append(f"**You:** {text}\n\n*Hmm, that didn't work.* {why}")
    if questions.current is not None:
        parts.append(f"{_you(questions.current)}\n\n*{thinking}*")
    for waiting in questions.waiting:
        parts.append(f"{_you(waiting)}\n\n*Still answering, Esc to stop. This one is next.*")
    return parts


def _you(question: Question) -> str:
    """The question as the chat shows it once answered: what was attached by name, never its contents."""
    line = f"**You:** {question.text}" if question.text else "**You:**"
    return line + (f"\n\n*Attached: {', '.join(a.name for a in question.attached)}*" if question.attached else "")
