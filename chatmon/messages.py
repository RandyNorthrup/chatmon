"""Which bubble shows next, and which waits.

Everything Chatmon has to say goes through one queue, in order of how much it matters: an alert (something
needs you), then a reminder, then a *prompt* (a bubble with buttons, or one that stays until it's closed), then
a plain bubble; among equals, what answers something you did goes before what came on its own (`background`).

A bubble on screen gives way only to something that matters more, to newer news of the same thing (the same
`key`), to the next plain bubble if it's plain, or, if it came on its own, to the answer to something you just
did. What comes on its own waits until the bubble has been up `MIN_SHOWN` seconds, so a flurry of them can't
flash past; what you did shows at once. A prompt, reminder or alert pushed aside comes back once that's closed;
a plain bubble pushed aside has been seen and is gone. Plain bubbles waiting with the same key are merged, newest
wins, and past `PLAIN_LIMIT` the oldest plain one goes; nothing else is ever dropped.

Holds keep messages waiting: quiet times, a focus session. Each is a rule saying which messages may still show.

No Qt here: the app shows what `next()` hands it and says when a bubble closed. Times are monotonic seconds.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass, field

ALERT, REMINDER, PROMPT, PLAIN = 0, 1, 2, 3  # lower goes first
MIN_SHOWN = 2.0  # seconds a bubble stays up before something that came on its own may take its place
PLAIN_LIMIT = 5  # plain bubbles kept waiting; past that, the oldest goes

_order = itertools.count()


@dataclass(eq=False)
class Message:
    """A bubble to show. `buttons` are (label, action or None). `key` names what it's about, so newer news of the
    same thing replaces it. `alert`: shown as one (waving, above full-screen windows, until answered). `yours`:
    it came while you were using Chatmon. `background`: it came on its own (an agent, a script, a heads-up), not
    from something you did. `priority`, left out, is PROMPT for a bubble with buttons or no timeout, else PLAIN.
    `cue`: the sound it may make as it shows (the app decides whether it does)."""

    title: str
    text: str = ""
    buttons: list = field(default_factory=list)
    timeout_s: float | None = 12
    key: str | None = None
    priority: int | None = None
    alert: bool = False
    yours: bool = False
    background: bool = False
    cue: str | None = None
    seq: int = field(default_factory=lambda: next(_order))

    def __post_init__(self) -> None:
        self.buttons = list(self.buttons or [])
        if self.priority is None:
            self.priority = PROMPT if (self.buttons or self.timeout_s is None) else PLAIN


def _same(a: Message, b: Message) -> bool:
    """News of the same thing."""
    return a.key is not None and a.key == b.key


class MessageQueue:
    def __init__(self) -> None:
        self.waiting: list[Message] = []
        self.showing: Message | None = None
        self.shown_at = 0.0
        self._holds: dict[str, Callable[[Message], bool]] = {}

    # -- holds

    def hold(self, reason: str, passes: Callable[[Message], bool]) -> None:
        """Keep waiting every message `passes` says no to, until `release(reason)`. Setting it again replaces the
        rule (the situation it depends on changed)."""
        self._holds[reason] = passes

    def release(self, reason: str) -> None:
        self._holds.pop(reason, None)

    def holding(self, reason: str) -> bool:
        return reason in self._holds

    def passes(self, message: Message) -> bool:
        """No hold keeps it back."""
        return all(passes(message) for passes in self._holds.values())

    def held(self, reason: str | None = None) -> list[Message]:
        """What waits only because of holds (`reason`'s, or any)."""
        if reason is not None:
            rule = self._holds.get(reason)
            return [m for m in self.waiting if rule is not None and not rule(m)]
        return [m for m in self.waiting if not self.passes(m)]

    # -- in and out

    def add(self, message: Message) -> list[Message]:
        """Queue it. Waiting news of the same thing is replaced by it; past the limit, the oldest plain bubble goes.
        Returns the plain bubbles that went that way, never shown (the app can still offer them)."""
        if message.key is not None:
            self.waiting = [m for m in self.waiting if m.key != message.key]
        self.waiting.append(message)
        plain = [m for m in self.waiting if m.priority == PLAIN]
        dropped = plain[: max(0, len(plain) - PLAIN_LIMIT)]
        for gone in dropped:
            self.waiting.remove(gone)
        return dropped

    def take(self, which: Callable[[Message], bool]) -> list[Message]:
        """Take out of the queue every waiting message `which` says yes to, in the order they came: the app says
        them some other way (a focus session's summary)."""
        taken = sorted((m for m in self.waiting if which(m)), key=lambda m: m.seq)
        self.waiting = [m for m in self.waiting if m not in taken]
        return taken

    def withdraw(self, key: str) -> None:
        """What's waiting about `key` no longer stands (the agent got going again): it never shows."""
        self.waiting = [m for m in self.waiting if m.key != key]

    def closed(self) -> None:
        """The bubble on screen was closed, answered or timed out."""
        self.showing = None

    def _ready(self) -> list[Message]:
        """What no hold keeps back, best placed first. The best-placed one may not be able to show yet (the bubble
        on screen matters as much); one further down still may: newer news of what's showing, or what you did."""
        return sorted((m for m in self.waiting if self.passes(m)), key=lambda m: (m.priority, m.background, m.seq))

    def _earliest(self, message: Message, now: float) -> float:
        """The soonest `message` could take over: now, or once the bubble showing has been up MIN_SHOWN."""
        return max(now, self.shown_at + MIN_SHOWN) if message.background and self.showing is not None else now

    def _takes_over(self, best: Message, now: float) -> bool:
        showing = self.showing
        if showing is None:
            return True
        if best.background and now - self.shown_at < MIN_SHOWN:
            return False
        if _same(best, showing):
            return True
        mine, theirs = best.priority, showing.priority
        if mine is None or theirs is None:  # never: __post_init__ gives every message one
            return False
        return mine < theirs or (mine == theirs and (mine == PLAIN or (showing.background and not best.background)))

    def next(self, now: float, visible: bool = True) -> Message | None:
        """The message to show now, if any; it's then the one showing. `visible`: whether the bubble the queue
        thinks is showing is still on screen (one closed without `closed()` is forgotten)."""
        if not visible:
            self.showing = None
        best = next((m for m in self._ready() if self._takes_over(m, now)), None)
        if best is None:
            return None
        pushed = self.showing
        if pushed is not None and pushed.priority != PLAIN and not _same(best, pushed):
            self.waiting.append(pushed)  # back in line, where its order puts it, once this one's closed
        self.waiting.remove(best)
        self.showing, self.shown_at = best, now
        return best

    def wake_at(self, now: float) -> float | None:
        """When to call `next()` again for something waiting to show (None: not until a bubble closes, a message
        comes, or a hold changes)."""
        times = [at for m in self._ready() if self._takes_over(m, at := self._earliest(m, now))]
        return min(times) if times else None
