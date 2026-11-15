"""What Chatmon does by itself, without any AI.

`run(c, text)` tries each kind in turn: memory (*remember that …*), reminders, timers and focus, what Chatmon keeps
(notes, the stopwatch, reminders by number), answers worked out here (offline.py: sums, units, dates, chance,
passwords), and last the fixed commands found by their phrases (`Table`, from the phrase data in chatmon/phrases/:
the person's language, with English always understood).

No Qt here: each command acts through the companion `c` it's given.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from datetime import datetime

from . import __version__, memory, offline, reminders


class Table:
    """The fixed commands Chatmon keeps here, found by their phrases in the phrase data (offline.phrases: one file per
    language, keyed by the same command ids, with English always understood). A phrase for a command that isn't kept
    here (*time*, *notes*: answered elsewhere) finds nothing. `phrases`: a language's (offline.load_phrases), else the
    person's own (offline.phrases())."""

    def __init__(self, phrases: offline.Phrases | None = None):
        self.phrases = phrases or offline.phrases()

    def find(self, text: str) -> str | None:
        command = self.phrases.command(text)
        return command if command in COMMANDS else None


# What a screen reader hears of a password made: never the password, which a system notification would keep.
PASSWORD_MADE = "Password made; it's in the box."


def run(c, text: str, table: Table | None = None) -> bool:
    """Do what `text` asks, if it's something Chatmon does by itself: True if it was. Anything else is the AI's."""
    asked = memory.command(text)
    if asked is not None:
        c._offline(text, memory_reply(c.memory, *asked))
        c._menu_changed()
        return True
    command = reminders.parse_command(text, datetime.now())
    if command is not None and command.kind == "unclear":
        rest = re.match(r"^(?:please\s+)?remind me\b[\s,:]*(.*)$", text.strip(), re.I | re.S)
        if rest and offline.reminder_or_question(rest.group(1)):
            return False  # "remind me how decorators work": a question, not a reminder
    if command is not None:
        _remind(c, text, command)
        return True
    kept_asked = offline.parse_kept(text)
    if kept_asked is not None:
        c._offline(text, kept(c, kept_asked))
        return True
    made = offline.password(text)
    if made is not None:  # shown in the box once; a screen reader is told only that it's there
        c._offline(text, made, spoken=PASSWORD_MADE if "`" in made else None)
        return True
    reply = offline.answer(text, datetime.now())
    if reply is not None:
        c._offline(text, reply)
        return True
    command_id = (table or Table()).find(text)
    return command_id is not None and COMMANDS[command_id](c, text) is not False


def _remind(c, text: str, command: reminders.Command) -> None:
    if command.kind == "unclear":
        c._offline(text, reminders.explain(command))
    elif command.kind == "focus":
        c.ask_box.dismiss()
        c.start_focus(command.minutes or float(c.config["focus"]["minutes"]))
    else:
        r = c.reminders.add(command.due.timestamp(), command.text, command.kind, repeat=command.repeat)
        c.save()
        when = reminders.describe(r.due, time.time())
        if r.kind == "timer":
            c._offline(text, f"Timer set: **{r.text}**, done {when}.")
        elif r.repeat:
            c._offline(text, f"I'll remind you {reminders.describe_repeat(r.repeat)}, first {when}: **{r.text}**")
        else:
            c._offline(text, f"I'll remind you {when}: **{r.text}**")
        c.behavior.react("hop", c._now())


# -- memory: remembered for every chat, as you asked, and forgotten again (memory.py)


def memory_reply(mind: memory.Memory, kind: str, what: str) -> str:
    if kind == "remember":
        refused = mind.add(what)
        return refused or f"I'll remember that: *{what.strip(' .')}*. Every brain you ask gets it with each question."
    if kind == "forget":
        gone = mind.forget(what)
        if not gone:
            return "I don't remember anything like that. *What do you remember* lists it all."
        return "Forgotten: " + "; ".join(f"*{g}*" for g in gone) + "."
    if kind == "forget-all":
        n = len(mind.items)
        mind.clear()
        return f"Forgotten, all {n} of them." if n else "There was nothing to forget."
    if not mind.items:
        return "Nothing yet. Tell me *remember that …* and I'll keep it for every chat."
    listed = "\n".join(f"- {i.text}" for i in mind.items)
    return f"What I remember, for every chat:\n\n{listed}\n\n*Forget that …* takes one out."


# -- notes, the stopwatch, and reminders by number: what Chatmon keeps

MAX_NOTES = 200
MAX_NOTE = 2000  # characters


def offline_clock(elapsed: float, seconds: bool = True) -> str:
    """How long the stopwatch has run: "4:05", "1:02:09"; without `seconds`, "4 min", "1:02 h" (for the menu)."""
    s = int(max(0, elapsed))
    h, m, sec = s // 3600, s // 60 % 60, s % 60
    if not seconds:
        return f"{h}:{m:02d} h" if h else f"{m} min"
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def notes(state) -> list[dict]:
    """The notes kept in `state`, each a dict with its text."""
    kept_notes = state.get("notes")
    return [n for n in kept_notes if isinstance(n, dict) and isinstance(n.get("text"), str)] if isinstance(kept_notes, list) else []


def _set_notes(c, new: list[dict]) -> None:
    c.state.set("notes", new)
    c.state.save()
    c._menu_changed()


def kept(c, asked: offline.Asked) -> str:
    """Notes, the stopwatch and reminders: do what's asked, say what was done."""
    handler = _KEPT.get(asked.kind)
    return handler(c, asked.arg) if handler else "Hmm."


def _note(c, arg: str) -> str:
    current = notes(c.state)
    if len(current) >= MAX_NOTES:
        return f"I keep {MAX_NOTES} notes at most: *delete note 1* makes room."
    current.append({"text": arg[:MAX_NOTE], "at": time.time()})
    _set_notes(c, current)
    c.behavior.react("hop", c._now())
    return f"Noted (note {len(current)}). *delete note {len(current)}* takes it back."


def _list_notes(c, _arg: str) -> str:
    current = notes(c.state)
    return "\n".join(f"{i}. {n['text']}" for i, n in enumerate(current, 1)) if current else "No notes yet: *note: buy milk* makes one."


def _delete_note(c, arg: str) -> str:
    current, i = notes(c.state), int(arg)
    if not 1 <= i <= len(current):
        return f"There's no note {i}." + (f" You have {len(current)}." if current else "")
    gone = current.pop(i - 1)
    _set_notes(c, current)
    return f"Deleted note {i}: {gone['text'][:80]}"


def _clear_notes(c, _arg: str) -> str:
    n = len(notes(c.state))
    _set_notes(c, [])
    return f"Deleted {n} note{'s' if n != 1 else ''}."


def _stopwatch(c, _arg: str) -> str:
    if c._stopwatch is None:
        c._stopwatch = c._now()
        c._menu_changed()
        return "Stopwatch started. *stop stopwatch* stops it."
    return f"Stopwatch: **{offline_clock(c._now() - c._stopwatch)}** and counting."


def _stop_stopwatch(c, _arg: str) -> str:
    if c._stopwatch is None:
        return "The stopwatch isn't running: *stopwatch* starts it."
    took, c._stopwatch = c._now() - c._stopwatch, None
    c._menu_changed()
    return f"Stopwatch stopped at **{offline_clock(took)}**."


def _upcoming(c) -> list[reminders.Reminder]:
    return [r for r in c.reminders.upcoming() if r.kind != "focus"]


def _list_reminders(c, _arg: str) -> str:
    upcoming = _upcoming(c)
    if not upcoming:
        return "No reminders or timers set."
    return "\n".join(f"{i}. {reminder_line(r, time.time())}" for i, r in enumerate(upcoming, 1))


def reminder_line(r: reminders.Reminder, now: float) -> str:
    """"Reminder in 5 min: stretch", "Reminder was due at 9:00 AM: stand up (every weekday at 9:00 AM)"."""
    again = f" ({reminders.describe_repeat(r.repeat)})" if r.repeat else ""
    return f"{r.kind.capitalize()} {reminders.describe(r.due, now)}: {r.text}{again}"


def _cancel_reminder(c, arg: str) -> str:
    upcoming, i = _upcoming(c), int(arg)
    if not 1 <= i <= len(upcoming):
        return f"There's no reminder {i}: *reminders* lists them."
    c._cancel(upcoming[i - 1].id)
    return f"Cancelled: {upcoming[i - 1].text}"


def _clear_reminders(c, _arg: str) -> str:
    upcoming = _upcoming(c)
    for r in upcoming:
        c.reminders.cancel(r.id)
    c.save()
    return f"Cancelled {len(upcoming)} reminder{'s' if len(upcoming) != 1 else ''}."


_KEPT: dict[str, Callable[..., str]] = {
    "note": _note, "notes": _list_notes, "delete note": _delete_note, "clear notes": _clear_notes,
    "stopwatch": _stopwatch, "stop stopwatch": _stop_stopwatch,
    "reminders": _list_reminders, "cancel reminder": _cancel_reminder, "clear reminders": _clear_reminders,
}


# -- your computer


def brain_in_use(loaded: dict, config: dict, state, wait: bool = True):
    """The brain a question goes to (the one picked from the menu, else the settings', else the first found), with
    the model, effort and thinking picked for it. `wait` off: as far as can be told without waiting."""
    from . import brains

    brain = brains.choose(loaded, config["ai"]["brain"], state.get("brain"), wait)
    return brain.with_options(dict((state.get("brain_options") or {}).get(brain.name) or {})) if brain else None



def status_lines(battery: tuple[float, bool] | None, disks: list[tuple[str, float]], upcoming: list[reminders.Reminder], now: float,
                 brain: str | None, brain_detail: str = "") -> list[str]:
    """The *status* command's lines (and `chatmon status`'s): battery, disks, the next few reminders, and the brain
    in use (`brain`: its label, or None for none)."""
    lines = []
    if battery:
        lines.append(f"- Battery: {battery[0]:.0f}%{' (plugged in)' if battery[1] else ''}")
    for folder, percent in disks:
        lines.append(f"- Disk for {folder}: {percent:.0f}% full")
    for r in upcoming[:5]:
        lines.append(f"- {reminder_line(r, now)}")
    if not upcoming:
        lines.append("- No reminders set")
    lines.append(f"- Brain: {brain or 'none'}" + (f" ({brain_detail})" if brain and brain_detail else ""))
    return lines


# -- the table's commands: each acts, and returns False only when it doesn't apply after all


def _help(c, text: str) -> None:
    c._offline(text, offline.help_text())


def _agents(c, text: str) -> None:
    c._offline(text, c.agents_report())


def _status(c, text: str) -> None:
    c._show_status(text)


def _stop_focus(c, text: str) -> None:
    c.stop_focus()
    c._offline(text, "Focus stopped.")


def _hide(c, _text: str) -> None:
    c.ask_box.dismiss()
    c.set_hidden(True)


def _new_chat(c, _text: str) -> None:
    c._new_chat()


def _rename_chat(c, _text: str) -> bool:
    if not c.chat.messages:
        return False  # nothing to name yet: a question after all
    c._ask_new_name(c.chat.id)
    return True


def _set_breaks(c, text: str, on: bool) -> None:
    c._override(("breaks", "remind"), on)
    c.state.save()
    c.config["breaks"]["remind"] = on
    c._offline(text, "Break reminders are on." if on else "No more break reminders. *Breaks on* brings them back.")


def _set_focus_alerts(c, text: str, on: bool) -> None:
    c._override(("focus", "tell_when_done"), on)
    c.state.save()
    c.config["focus"]["tell_when_done"] = on
    c._offline(text, "I'll say when a focus session ends." if on else "Focus sessions will end quietly. *Focus alerts on* brings it back.")


def _settings(c, _text: str) -> None:
    c.ask_box.dismiss()
    c.open_settings()


def _history(c, _text: str) -> None:
    c._show_history()


def _whats_new(c, _text: str) -> None:
    c.show_whats_new()


def _update(c, _text: str) -> None:
    c.ask_box.dismiss()
    if c.updater.ready:
        c._update_now()
    else:
        c.check_for_updates()


def _report(c, _text: str) -> None:
    c.ask_box.set_answer("Opening a problem report in your browser…")
    c.report_problem()


def _idea(c, _text: str) -> None:
    from . import report

    c.ask_box.set_answer("Opening an idea form in your browser…")
    c.report_problem(report.IDEA)


def _version(c, text: str) -> None:
    c._offline(text, f"I'm Chatmon {__version__}.")


def _carry_on(c, _text: str) -> bool:
    return c._carry_on()  # only just after a new chat was started for you: otherwise it's asking the AI to go on


COMMANDS: dict[str, Callable[..., bool | None]] = {  # keyed by the phrase data's command ids (chatmon/phrases/en.json)
    "help": _help, "status": _status, "agents": _agents, "stop focus": _stop_focus, "hide": _hide, "new chat": _new_chat,
    "rename chat": _rename_chat,
    "breaks off": lambda c, text: _set_breaks(c, text, False), "breaks on": lambda c, text: _set_breaks(c, text, True),
    "focus alerts off": lambda c, text: _set_focus_alerts(c, text, False),
    "focus alerts on": lambda c, text: _set_focus_alerts(c, text, True),
    "settings": _settings, "history": _history, "what's new": _whats_new, "check for updates": _update,
    "report a problem": _report, "suggest an idea": _idea, "version": _version, "carry on": _carry_on,
}
