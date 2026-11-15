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
from .i18n import N_, _, ngettext


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
PASSWORD_MADE = N_("Password made; it's in the box.")  # said as _(PASSWORD_MADE)


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
        c._offline(text, made, spoken=_(PASSWORD_MADE) if "`" in made else None)
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
            c._offline(text, _("Timer set: **{text}**, done {when}.").format(text=r.text, when=when))
        elif r.repeat:
            said = _("I'll remind you {repeat}, first {when}: **{text}**").format(repeat=reminders.describe_repeat(r.repeat), when=when, text=r.text)
            c._offline(text, said)
        else:
            c._offline(text, _("I'll remind you {when}: **{text}**").format(when=when, text=r.text))
        c.behavior.react("hop", c._now())


# -- memory: remembered for every chat, as you asked, and forgotten again (memory.py)


# Translators (for the replies below): the words between asterisks are what to type, as Chatmon reads them; use
# your language's phrase only where chatmon/phrases/ has one for it.
def memory_reply(mind: memory.Memory, kind: str, what: str) -> str:
    if kind == "remember":
        refused = mind.add(what)
        return refused or _("I'll remember that: *{thing}*. Every brain you ask gets it with each question.").format(thing=what.strip(" ."))
    if kind == "forget":
        gone = mind.forget(what)
        if not gone:
            return _("I don't remember anything like that. *What do you remember* lists it all.")
        return _("Forgotten: {things}.").format(things="; ".join(f"*{g}*" for g in gone))
    if kind == "forget-all":
        n = len(mind.items)
        mind.clear()
        return ngettext("Forgotten, all {n} of them.", "Forgotten, all {n} of them.", n).format(n=n) if n else _("There was nothing to forget.")
    if not mind.items:
        return _("Nothing yet. Tell me *remember that …* and I'll keep it for every chat.")
    listed = "\n".join(f"- {i.text}" for i in mind.items)
    return _("What I remember, for every chat:\n\n{things}\n\n*Forget that …* takes one out.").format(things=listed)


# -- notes, the stopwatch, and reminders by number: what Chatmon keeps

MAX_NOTES = 200
MAX_NOTE = 2000  # characters


def offline_clock(elapsed: float, seconds: bool = True) -> str:
    """How long the stopwatch has run: "4:05", "1:02:09"; without `seconds`, "4 min", "1:02 h" (for the menu)."""
    s = int(max(0, elapsed))
    h, m, sec = s // 3600, s // 60 % 60, s % 60
    if not seconds:
        return _("{hours}:{minutes} h").format(hours=h, minutes=f"{m:02d}") if h else _("{minutes} min").format(minutes=m)
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
    return handler(c, asked.arg) if handler else _("Hmm.")


def _note(c, arg: str) -> str:
    current = notes(c.state)
    if len(current) >= MAX_NOTES:
        return _("I keep {count} notes at most: *delete note 1* makes room.").format(count=MAX_NOTES)
    current.append({"text": arg[:MAX_NOTE], "at": time.time()})
    _set_notes(c, current)
    c.behavior.react("hop", c._now())
    return _("Noted (note {n}). *delete note {n}* takes it back.").format(n=len(current))


def _list_notes(c, _arg: str) -> str:
    current = notes(c.state)
    return "\n".join(f"{i}. {n['text']}" for i, n in enumerate(current, 1)) if current else _("No notes yet: *note: buy milk* makes one.")


def _delete_note(c, arg: str) -> str:
    current, i = notes(c.state), int(arg)
    if not 1 <= i <= len(current):
        if current:
            return ngettext("There's no note {i}. You have {n}.", "There's no note {i}. You have {n}.", len(current)).format(i=i, n=len(current))
        return _("There's no note {i}.").format(i=i)
    gone = current.pop(i - 1)
    _set_notes(c, current)
    return _("Deleted note {i}: {text}").format(i=i, text=gone["text"][:80])


def _clear_notes(c, _arg: str) -> str:
    n = len(notes(c.state))
    _set_notes(c, [])
    return ngettext("Deleted {n} note.", "Deleted {n} notes.", n).format(n=n)


def _stopwatch(c, _arg: str) -> str:
    if c._stopwatch is None:
        c._stopwatch = c._now()
        c._menu_changed()
        return _("Stopwatch started. *stop stopwatch* stops it.")
    return _("Stopwatch: **{time}** and counting.").format(time=offline_clock(c._now() - c._stopwatch))


def _stop_stopwatch(c, _arg: str) -> str:
    if c._stopwatch is None:
        return _("The stopwatch isn't running: *stopwatch* starts it.")
    took, c._stopwatch = c._now() - c._stopwatch, None
    c._menu_changed()
    return _("Stopwatch stopped at **{time}**.").format(time=offline_clock(took))


def _upcoming(c) -> list[reminders.Reminder]:
    return [r for r in c.reminders.upcoming() if r.kind != "focus"]


def _list_reminders(c, _arg: str) -> str:
    upcoming = _upcoming(c)
    if not upcoming:
        return _("No reminders or timers set.")
    return "\n".join(f"{i}. {reminder_line(r, time.time())}" for i, r in enumerate(upcoming, 1))


# Each kind's line, once and with how it repeats: whole sentences, never "Reminder" put before a phrase.
# Translators: {when} is "in 5 min", "at 3:00 PM", "tomorrow at 9:00 AM" or "was due at 9:00 AM"; {repeat} "every weekday at 9:00 AM".
_LINES = {
    "reminder": (N_("Reminder {when}: {text}"), N_("Reminder {when}: {text} ({repeat})")),
    "timer": (N_("Timer {when}: {text}"), N_("Timer {when}: {text} ({repeat})")),
    "focus": (N_("Focus {when}: {text}"), N_("Focus {when}: {text} ({repeat})")),
}


def reminder_line(r: reminders.Reminder, now: float) -> str:
    """"Reminder in 5 min: stretch", "Reminder was due at 9:00 AM: stand up (every weekday at 9:00 AM)"."""
    once, repeating = _LINES.get(r.kind, _LINES["reminder"])
    words = {"when": reminders.describe(r.due, now), "text": r.text}
    if r.repeat:
        return _(repeating).format(repeat=reminders.describe_repeat(r.repeat), **words)
    return _(once).format(**words)


def _cancel_reminder(c, arg: str) -> str:
    upcoming, i = _upcoming(c), int(arg)
    if not 1 <= i <= len(upcoming):
        return _("There's no reminder {i}: *reminders* lists them.").format(i=i)
    c._cancel(upcoming[i - 1].id)
    return _("Cancelled: {text}").format(text=upcoming[i - 1].text)


def _clear_reminders(c, _arg: str) -> str:
    upcoming = _upcoming(c)
    for r in upcoming:
        c.reminders.cancel(r.id)
    c.save()
    return ngettext("Cancelled {n} reminder.", "Cancelled {n} reminders.", len(upcoming)).format(n=len(upcoming))


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
        charge = f"{battery[0]:.0f}"
        lines.append("- " + (_("Battery: {percent}% (plugged in)") if battery[1] else _("Battery: {percent}%")).format(percent=charge))
    for folder, percent in disks:
        lines.append("- " + _("Disk for {folder}: {percent}% full").format(folder=folder, percent=f"{percent:.0f}"))
    for r in upcoming[:5]:
        lines.append(f"- {reminder_line(r, now)}")
    if not upcoming:
        lines.append("- " + _("No reminders set"))
    if not brain:
        lines.append("- " + _("Brain: none"))
    elif brain_detail:
        lines.append("- " + _("Brain: {brain} ({detail})").format(brain=brain, detail=brain_detail))
    else:
        lines.append("- " + _("Brain: {brain}").format(brain=brain))
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
    c._offline(text, _("Focus stopped."))


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
    c._offline(text, _("Break reminders are on.") if on else _("No more break reminders. *Breaks on* brings them back."))


def _set_focus_alerts(c, text: str, on: bool) -> None:
    c._override(("focus", "tell_when_done"), on)
    c.state.save()
    c.config["focus"]["tell_when_done"] = on
    c._offline(text, _("I'll say when a focus session ends.") if on else _("Focus sessions will end quietly. *Focus alerts on* brings it back."))


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
    c.ask_box.set_answer(_("Opening a problem report in your browser…"))
    c.report_problem()


def _idea(c, _text: str) -> None:
    from . import report

    c.ask_box.set_answer(_("Opening an idea form in your browser…"))
    c.report_problem(report.IDEA)


def _version(c, text: str) -> None:
    c._offline(text, _("I'm Chatmon {version}.").format(version=__version__))


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
