"""What the penguin is doing from moment to moment.

Pure Python, no Qt: the window asks `tick()` which frame to draw and where,
and tells the behaviour what happened (a click, a drag, an agent at work).
Times are seconds on any monotonic clock.

Moods, highest first: hidden, alert, talk, think (an answer on its way),
attend (you're typing to it), work (an agent is busy: think, then charge),
sleep, and ambient (wandering, idling, the odd wave). One-off reactions (a
hop, a wave, a beam) play out before the mood takes over again, unless the
new mood is alert or hidden.

`next_change()` says when the frame will next look different, so whoever
draws it can sleep until then; `on_change` is called whenever something it's
told could change the frame sooner. With reduced motion, moods hold one pose
and waves, hops and peeks don't play.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import dataclass

# Frames of the `turn` strip: 0 side right, 1 three-quarter right, 2 front,
# 3 three-quarter left, 4 side left, 5 side left with a little hop. Any change
# of stance plays the part of the strip between the two.
TURN = {
    ("right", "front"): [0, 1, 2],
    ("front", "right"): [2, 1, 0],
    ("left", "front"): [4, 3, 2],
    ("front", "left"): [2, 3, 4],
    ("right", "left"): [0, 1, 2, 3, 4],
    ("left", "right"): [4, 3, 2, 1, 0],
}
TURN_FPS = 10
TURN_HOP = 5  # side left with a little hop: now and then, when it stops while facing left

# `idle`: 0 relaxed, 1 a breath, 2 eyes half shut, 3 shut, 4 half open, 5 relaxed.
# It holds still and blinks every few seconds, not every loop of the strip.
IDLE_BLINK = [2, 3, 4]
IDLE_FPS = 10
# `think`: frames 0-4 are thinking; 5 is "got it!", shown once when the answer arrives.
THINK_LOOP = [0, 1, 2, 3, 4]
THINK_GOT_IT = 5
STILL_SKIPS = ("wave", "hop", "peek")  # the reactions reduced motion leaves out
MAX_DT = 0.25  # s: the longest step a walk or fall takes at once, however late a tick comes
LATE = 0.001  # s past a frame's start, so a tick at that time is surely on the new frame


@dataclass
class Clip:
    anim: str | None  # None draws nothing (hidden between peeks)
    frames: list[int]
    fps: float
    loop: bool = False
    mirror: bool = False
    duration: float | None = None  # loops: how long to play; None until something changes
    stance: str = "front"  # "front", "right" or "left" while this clip plays
    reaction: bool = False


@dataclass
class Frame:
    anim: str | None
    index: int
    mirror: bool
    x: float
    lift: float


class Behavior:
    WALK_MIN = 120.0  # shortest walk, px
    WALK_MAX = 700.0  # longest walk, px
    CHARGE_AFTER = 60.0  # seconds of agent work before thinking turns to charging
    GRAVITY = 2600.0  # px/s² when dropped

    def __init__(
        self,
        anims: dict[str, tuple[int, float, bool]],
        *,
        now: float,
        x: float = 600.0,
        rng: random.Random | None = None,
        walk: bool = True,
        sleep_after: float = 600.0,
        speed: float = 48.0,
    ):
        self.anims = anims
        self.rng = rng or random.Random()
        self.walk_enabled = walk
        self.sleep_after = sleep_after
        self.speed = speed
        self.x = x
        self.left, self.right = 0.0, 1920.0
        self.lift = 0.0
        self.stance = "front"
        self.held = self.falling = False
        self.on_change: Callable[[], None] | None = None  # told when something could change the frame sooner
        self._hovered = False
        self._waiting = False  # a walk is waiting under the pointer (see tick)
        self.reduced_motion = False
        self.hidden = self.alert = self.talking = self.thinking = self.attending = False
        self.working_since: float | None = None
        self.asleep = False
        self.last_interaction = now
        self.mood = "ambient"
        self._vy = 0.0
        self._target: float | None = None
        self._queue: list[Clip] = []
        self._last = now
        self._start(Clip("wave", self._all("wave"), self._fps("wave"), reaction=True), now)

    # -- what the outside world tells it

    @property
    def hovered(self) -> bool:
        """The pointer is over it: a walk waits, holding its step, until the pointer leaves."""
        return self._hovered

    @hovered.setter
    def hovered(self, on: bool) -> None:
        if on != self._hovered:
            self._hovered = on
            self._changed()

    def set_reduced_motion(self, on: bool, now: float) -> None:
        """The system (or you) asks for less movement: moods hold one pose, waves, hops and peeks are left
        out, and a drop lands at once. Walking is the app's to decide, as you may still ask for it."""
        if on == self.reduced_motion:
            return
        self.reduced_motion = on
        if not self.held:
            if on and self.falling:
                self.lift, self.falling = 0.0, False
            self._plan(self.wanted_mood(now), now)
        self._changed()

    def set_floor(self, left: float, right: float) -> None:
        self.left, self.right = left, max(left, right)
        if not self.held:
            self.x = min(max(self.x, self.left), self.right)
        if self._target is not None:
            self._target = min(max(self._target, self.left), self.right)

    def set_alert(self, on: bool, now: float) -> None:
        self._flag("alert", on, now)

    def set_talking(self, on: bool, now: float) -> None:
        self._flag("talking", on, now)

    def set_thinking(self, on: bool, now: float) -> None:
        self._flag("thinking", on, now)

    def set_attending(self, on: bool, now: float) -> None:
        self._flag("attending", on, now)

    def set_walk(self, on: bool, now: float) -> None:
        """Walk around or not. Turning it off stops a walk under way, or one
        about to start after its turn, rather than letting it finish."""
        self.walk_enabled = on
        walking = self._target is not None or any(c.anim == "walk" for c in [self._clip, *self._queue])
        if not on and walking and not self.held:
            self._plan(self.wanted_mood(now), now)
        self._changed()

    def set_hidden(self, on: bool, now: float) -> None:
        self.hidden = on
        if not on:
            self.asleep = False
            self.last_interaction = now
        self._changed()

    def set_working(self, on: bool, now: float) -> None:
        if on and self.working_since is None:
            self.working_since = now
            self.wake(now)
        elif not on:
            self.working_since = None
        self._changed()

    def wake(self, now: float) -> None:
        """Attention of any kind: resets the sleep timer and wakes it up."""
        self.last_interaction = now
        if self.asleep and not self.hidden:
            self.asleep = False
            if self.reduced_motion:
                self._plan(self.wanted_mood(now), now)  # awake, without the stretch and the hop
            else:
                self._play([Clip("sleep", [2, 1, 0], 6, reaction=True), Clip("hop", self._all("hop"), self._fps("hop"), reaction=True)], now)
        self._changed()

    def poke(self, now: float) -> None:
        if self.asleep:
            self.wake(now)
        else:
            self.last_interaction = now
            self.react("wave", now)

    def react(self, anim: str, now: float, times: int = 1) -> None:
        """Play a one-off (hop, wave, beam...) then carry on."""
        if self.held or self.falling or self.hidden or (self.reduced_motion and anim in STILL_SKIPS):
            return
        self._changed()
        if anim == "beam":
            side = self.stance if self.stance in ("left", "right") else "right"
            clips = self._turn(side)
            clips.append(Clip("beam", self._all("beam"), self._fps("beam"), mirror=side == "left", stance=side))
        else:
            clips = self._to_front()
            clips.append(Clip(anim, self._all(anim) * times, self._fps(anim)))
        if self.reduced_motion:  # straight to it, without turning first
            clips = [c for c in clips if c.anim != "turn"]
        for clip in clips:
            clip.reaction = True
        self._play(clips, now)

    def hold(self, x: float, lift: float, now: float) -> None:
        """Being dragged by the mouse."""
        self.held, self.falling = True, False
        self.x, self.lift = x, max(0.0, lift)
        self._target, self._queue = None, []
        self.asleep = False
        self.last_interaction = now
        self._changed()

    def release(self, now: float) -> None:
        self.held = False
        self.x = min(max(self.x, self.left), self.right)
        self.stance = "front"
        if self.reduced_motion:
            self.lift = 0.0  # down at once, no fall and no hop
            self._plan(self.wanted_mood(now), now)
        elif self.lift > 0:
            self.falling, self._vy = True, 0.0
        else:
            self._play([Clip("hop", [4, 5], 9, reaction=True)], now)
        self._changed()

    # -- the frame to draw

    def tick(self, now: float) -> Frame:
        elapsed = max(0.0, now - self._last)
        dt = min(elapsed, MAX_DT)
        self._last = now
        if self._waiting and not (self._hovered and self._clip.anim == "walk"):
            # The pointer has gone: the walk carries on from here, not from where it would have been.
            self._waiting = False
            self._clip_start += elapsed
            dt = 0.0
        if self.held:
            return Frame("hop", 2, False, self.x, self.lift)
        if self.falling:
            self._vy += self.GRAVITY * dt
            self.lift -= self._vy * dt
            if self.lift > 0:
                return Frame("hop", 3, False, self.x, self.lift)
            self.lift, self.falling = 0.0, False
            self._play([Clip("hop", [4, 5], 9, reaction=True)], now)
        wanted = self.wanted_mood(now)
        if wanted != self.mood and (not self._clip.reaction or wanted in ("alert", "hidden")):
            self._plan(wanted, now)
        clip = self._clip
        if clip.anim == "walk" and self._hovered:
            # It stops mid-step, facing the way it walked, and the walk's own clock waits (all the time since
            # the last tick, however long): it carries on with the same step when the pointer leaves.
            self._waiting = True
            self._clip_start += elapsed
            n = int((now - self._clip_start) * clip.fps)
            return Frame("walk", clip.frames[n % len(clip.frames)], clip.mirror, self.x, self.lift)
        if clip.anim == "walk" and self._target is not None:
            step = self.speed * dt
            if abs(self._target - self.x) <= step:
                self.x, self._target = self._target, None
                self._advance(now)
            else:
                self.x += step if self._target > self.x else -step
        elif self._finished(now):
            self._advance(now)
        clip = self._clip
        n = int((now - self._clip_start) * clip.fps)
        return Frame(clip.anim, self._index(clip, n), clip.mirror, self.x, self.lift)

    def next_change(self, now: float) -> float:
        """The soonest time (the clock tick() is given) its frame could look different: `now` while it moves
        all the time (walking, falling), math.inf while nothing changes until it's told something (held by
        the mouse, a walk waiting under the pointer, a pose held for good). A clip's repeated frames (an
        idle stance held for seconds before a blink) are one change, not one per frame."""
        if self.held:
            return math.inf
        if self.falling:
            return now
        due = self._mood_due(now)
        clip = self._clip
        if clip.anim == "walk" and self._hovered:
            return due
        if clip.anim == "walk" and self._target is not None:
            return now
        if clip.loop:
            end = self._clip_start + clip.duration if clip.duration is not None else math.inf
        else:
            end = self._clip_start + len(clip.frames) / clip.fps
        return min(due, end + LATE, self._next_frame(now))

    def _index(self, clip: Clip, n: int) -> int:
        return clip.frames[n % len(clip.frames)] if clip.loop else clip.frames[min(n, len(clip.frames) - 1)]

    def _next_frame(self, now: float) -> float:
        """When the clip playing next shows a different frame, within one round of it."""
        clip = self._clip
        n = max(0, int((now - self._clip_start) * clip.fps))
        current = self._index(clip, n)
        for k in range(n + 1, n + 1 + len(clip.frames)):
            if not clip.loop and k >= len(clip.frames):
                break  # its end is the change
            if self._index(clip, k) != current:
                return self._clip_start + k / clip.fps + LATE
        return math.inf

    def _mood_due(self, now: float) -> float:
        """When the mood would change by itself, with nothing said: thinking turns to charging, or it falls
        asleep. Only times still to come: one already past waits on the clip playing, whose end counts."""
        due = math.inf
        if self.working_since is not None and self.working_since + self.CHARGE_AFTER > now:
            due = self.working_since + self.CHARGE_AFTER
        if self.sleep_after > 0 and not self.asleep and self.last_interaction + self.sleep_after > now:
            due = min(due, self.last_interaction + self.sleep_after)
        return due + LATE

    def wanted_mood(self, now: float) -> str:
        if self.hidden:
            return "hidden"
        if self.alert:
            return "alert"
        if self.talking:
            return "talk"
        if self.thinking:
            return "think"
        if self.attending:
            return "attend"
        if self.working_since is not None:
            return "charge" if now - self.working_since >= self.CHARGE_AFTER else "think"
        if self.asleep or (self.sleep_after > 0 and now - self.last_interaction >= self.sleep_after):
            return "sleep"
        return "ambient"

    # -- planning

    def _changed(self) -> None:
        if self.on_change is not None:
            self.on_change()

    def _flag(self, name: str, on: bool, now: float) -> None:
        if getattr(self, name) != on:
            setattr(self, name, on)
            if on:
                self.wake(now)
            self._changed()

    def _all(self, anim: str) -> list[int]:
        return list(range(self.anims[anim][0]))

    def _fps(self, anim: str) -> float:
        return self.anims[anim][1]

    def _turn(self, to: str) -> list[Clip]:
        if self.stance == to:
            return []
        return [Clip("turn", list(TURN[(self.stance, to)]), TURN_FPS, stance=to)]

    def _to_front(self) -> list[Clip]:
        return self._turn("front")

    def _start(self, clip: Clip, now: float) -> None:
        self._clip, self._clip_start = clip, now
        self.stance = clip.stance
        self._waiting = False

    def _play(self, clips: list[Clip], now: float) -> None:
        self._target = None
        self._queue = clips[1:]
        self._start(clips[0], now)

    def _finished(self, now: float) -> bool:
        clip, elapsed = self._clip, now - self._clip_start
        if clip.loop:
            return clip.duration is not None and elapsed >= clip.duration
        return elapsed >= len(clip.frames) / clip.fps

    def _advance(self, now: float) -> None:
        if self._queue:
            self._start(self._queue.pop(0), now)
        else:
            self._plan(self.wanted_mood(now), now)

    def _plan(self, mood: str, now: float) -> None:
        previous, self.mood = self.mood, mood
        self._target = None
        clips: list[Clip] = []
        if previous == "hidden" and mood != "hidden":
            clips.append(Clip("peek", [0, 1, 2, 4], 8))
        if mood == "hidden":
            if previous != "hidden":
                clips.append(Clip("peek", [4, 2, 1, 0], 8))
            clips.append(Clip(None, [0], 1, loop=True, duration=self.rng.uniform(20, 60)))
            clips.append(Clip("peek", self._all("peek"), self._fps("peek")))
        elif mood == "sleep":
            self.asleep = True
            clips += self._to_front()
            clips += [Clip("sleep", [0, 1, 2], self._fps("sleep")), Clip("sleep", [3, 4, 5], self._fps("sleep"), loop=True)]
        elif mood == "think":
            clips += self._to_front() + [Clip("think", self._think_loop(), self._fps("think"), loop=True)]
        elif mood in ("alert", "talk", "charge"):
            clips += self._to_front()
            if mood == "talk" and previous == "think" and self._has("think", THINK_GOT_IT):
                clips.append(Clip("think", [THINK_GOT_IT], 2))  # "got it!" for half a second
            clips.append(Clip(mood, self._all(mood), self._fps(mood), loop=True))
        elif mood == "attend":
            clips += self._to_front() + [self._idle()]
        else:
            clips += self._ambient()
        if self.reduced_motion:
            clips = self._still(clips)
        target = self._target
        self._play(clips, now)
        self._target = target

    @staticmethod
    def _still(clips: list[Clip]) -> list[Clip]:
        """The plan with reduced motion: the one-off clips (turns, peeks, waves, nodding off, "got it!") left
        out, and each looping mood held on its first pose. A walk you asked for still walks."""
        still = [
            c if c.anim in (None, "walk") else Clip(c.anim, c.frames[:1], c.fps, loop=True, mirror=c.mirror, duration=c.duration, stance=c.stance)
            for c in clips
            if c.loop
        ]
        return still or [Clip("idle", [0], IDLE_FPS, loop=True)]

    def _ambient(self) -> list[Clip]:
        roll = self.rng.random()
        if self.walk_enabled and roll < 0.5 and self.right - self.left >= self.WALK_MIN:
            target = self._pick_target()
            side = "right" if target > self.x else "left"
            frames, fps, _ = self.anims["walk"]
            clips = self._turn(side)
            clips.append(Clip("walk", list(range(frames)), fps, loop=True, mirror=side == "left", stance=side))
            self._target = target
            return clips
        clips = []
        if self.stance == "left" and roll >= 0.85 and self._has("turn", TURN_HOP):
            clips.append(Clip("turn", [TURN_HOP], 5, stance="left"))
        clips += self._to_front()
        if roll < 0.58:
            clips.append(Clip("wave", self._all("wave"), self._fps("wave")))
        clips.append(self._idle(duration=self.rng.uniform(4, 10)))
        return clips

    def _has(self, anim: str, frame: int) -> bool:
        return anim in self.anims and self.anims[anim][0] > frame

    def _think_loop(self) -> list[int]:
        """Thinking, without the "got it!" frame (that waits for the answer)."""
        if self._has("think", THINK_GOT_IT):
            return list(THINK_LOOP)
        return self._all("think")

    def _idle(self, duration: float | None = None) -> Clip:
        """Stand still for 3-5 s, blink, and go round again."""
        if not self._has("idle", max(IDLE_BLINK)):
            return Clip("idle", self._all("idle"), self._fps("idle"), loop=True, duration=duration)
        hold = round(self.rng.uniform(3, 5) * IDLE_FPS)
        return Clip("idle", [0] * hold + IDLE_BLINK, IDLE_FPS, loop=True, duration=duration)

    def _pick_target(self) -> float:
        lo = max(self.left, self.x - self.WALK_MAX)
        hi = min(self.right, self.x + self.WALK_MAX)
        for _ in range(8):
            target = self.rng.uniform(lo, hi)
            if abs(target - self.x) >= self.WALK_MIN:
                return target
        return self.left if self.x - self.left > self.right - self.x else self.right
