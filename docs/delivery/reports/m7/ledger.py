"""M7's quality ledger, built from the records below and the receipts in receipts.json.

usage: python ledger.py PLAN.md OUT.md   (OUT: the plan's prose followed by the one quality-ledger block)

The requirements, acceptance criteria and tasks live here so a receipt can be added from a real run (receipts.json,
written from the validator's snapshot and the run's log) without hand-editing the plan's JSON. The plan itself is
still the one canonical record: this only writes it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

ENV = json.loads((HERE / "context.json").read_text(encoding="utf-8"))

WORK = {
    "id": "M7",
    "title": "Integration: wiring wave 1 into the app, the settings window and the command line",
    "scope_revision": 1,
    "brief": "docs/delivery/ASSESSMENT.md",
    "brief_reason": None,
    "rules": [
        {"path": "docs/delivery/ROADMAP.md", "revision": "81af7c7"},
        {"path": "pyproject.toml", "revision": "81af7c7"},
    ],
    "inputs": ["tests/conftest.py", "tests/drills/run.py"],
    "environment": ENV,
}

# (requirement id, statement, priority, [(acceptance id, given, when, then)])
REQS: list[tuple[str, str, str, list[tuple[str, str, str, str]]]] = [
    ("M7-CI", "Windows CI's failing smoke and ask-box tests pass for the right reason (coordinator's finding)", "critical", [
        ("AC-CI-1", "The computer the tests run on reports a full-screen app, a presentation or reduced motion",
         "A smoke test's companion runs", "Bubbles from the background show and it walks: its desk readings are the test's own"),
        ("AC-CI-2", "A bubble showing, and a better-placed message waiting that can't push it aside",
         "Newer news of the bubble showing, or something you did, arrives", "It takes over (after the minimum, if it came on its own); nothing waits behind what can't show"),
        ("AC-CI-3", "The ask box's effects have settled and the clock hasn't moved since it woke",
         "New words arrive", "Its frames start, rising from the still picture"),
    ]),
    ("M7-01", "Answers stream in, finish after the box closes, and can be stopped", "critical", [
        ("AC-01-1", "A brain streams an answer", "Pieces arrive, the box is redrawn, closed and opened again",
         "The text so far shows under the question, in order, and survives each redraw"),
        ("AC-01-2", "A question on its way", "The ask box is closed",
         "The answer still arrives, is kept in the chat, and a bubble '<brain> answered' with Read opens the box at it"),
        ("AC-01-3", "A question on its way", "It's sent, answered, fails or Stop is pressed",
         "The box shows who is answering and for how long while it's on its way; Stop cancels it, keeps what came so far (or puts the question back), and the question waiting goes"),
    ]),
    ("M7-02", "Failures say what to do next, and which brain answers is never a surprise", "critical", [
        ("AC-02-1", "A question failed", "The failure arrives (box open or closed)",
         "A bubble offers Try again, Ask <next brain> and Settings, and each does that"),
        ("AC-02-2", "The brain picked in the menu isn't available", "Questions are asked",
         "The fallback is announced once, not on every question, and again after the pick changes"),
        ("AC-02-3", "The first run", "The chatmon is named", "It says which brain will answer, or how to set one up"),
        ("AC-02-4", "A model server is running here that isn't yours, and nothing else answers", "A question is asked",
         "It offers 'Use the model server at host:port?' once; Use it confirms it and keeps it for later starts"),
    ]),
    ("M7-03", "The settings window covers keys, a test, accessibility, reminders' snooze, and applies at once", "critical", [
        ("AC-03-1", "An API brain is chosen in the AI tab", "A key is typed and Saved, removed, or Test is pressed",
         "The key goes to the keychain (never state or config.toml) or is removed, and Test shows the time taken or the error"),
        ("AC-03-2", "The Accessibility tab", "Text size, how long bubbles stay (until I close them included), sounds and volume, the hotkey, reduced motion and the accessible ask box are set and saved",
         "They're kept, and text size, bubble timing and reduced motion apply at once"),
        ("AC-03-3", "Reminders", "Their snooze is set in the window or reminders.snooze_minutes", "Reminder snoozes use it; breaks keep their own"),
        ("AC-03-4", "Chatmon runs", "The update-check interval is changed", "The timer takes the new interval without a restart"),
        ("AC-03-5", "Battery warnings", "'Almost empty' is set at or above 'low'", "It's kept below 'low', in the window and from the file"),
    ]),
    ("M7-04", "Reminders wait until done or snoozed, can be edited and repeat, across restarts", "critical", [
        ("AC-04-1", "A reminder comes due", "Its bubble shows",
         "It's an alert keyed reminder:<id> with Done, Snooze <own> and Later; Done acknowledges (a repeat moves on), snoozes put it off; saved each time"),
        ("AC-04-2", "Reminders fired and not done when Chatmon quit", "It starts", "Each is shown again; a focus session that ended is over, not held"),
        ("AC-04-3", "A reminder in the menu", "Edit, Repeat or Cancel is chosen",
         "Edit opens the box prefilled and applies new words or time; Repeat sets a described rule or Never"),
        ("AC-04-4", "A reminder is added in the box, by a script or by chatmon remind", "It repeats, or its time is unclear",
         "The repeat is kept and described; an unclear time is explained (the CLI prints it and exits 2)"),
    ]),
    ("M7-05", "A focus session ends with one summary of what waited", "normal", [
        ("AC-05-1", "Bubbles from the background held during a focus session", "The session ends (or is stopped)",
         "One 'While you focused' bubble lists the plain ones; ones with buttons follow in turn; nothing is lost"),
    ]),
    ("M7-06", "Missed messages can be brought back", "normal", [
        ("AC-06-1", "Bubbles were shown", "Recent messages is opened from the menu", "It lists them, and picking one shows it again"),
        ("AC-06-2", "A bubble timed out while you were away, or was dropped", "You click the chatmon", "It's brought back"),
    ]),
    ("M7-07", "Agents at a glance", "normal", [
        ("AC-07-1", "Agents working or needing you", "Their state changes",
         "The tray's tooltip and the stage's accessible name say each one's state, and the tray icon has a badge while one needs you"),
        ("AC-07-2", "Agents working or waiting", "agents is asked", "Each agent's state and for how long is answered here"),
        ("AC-07-3", "Chatmon running, with agents' states", "chatmon status is run",
         "It prints the live states from the running Chatmon (its own status answer); not running, what's on disk"),
    ]),
    ("M7-08", "Quick actions on the clipboard", "normal", [
        ("AC-08-1", "Text or a picture on the clipboard", "Explain, Summarize, Translate or Fix is chosen",
         "The clipboard is attached then (never before) and the box opens with that prompt typed in"),
    ]),
    ("M7-09", "Chats: a window with search, a brain per chat, another brain, backup", "critical", [
        ("AC-09-1", "Saved chats", "Chats is opened",
         "A window lists them with search (titles and words in them) and carries on, renames, pins, saves and deletes; the menu shows recent chats and All chats, not a submenu per chat"),
        ("AC-09-2", "A chat answered by one brain", "It's carried on, or Ask another brain is chosen",
         "It goes to the chat's brain; another brain is asked the last question with the history before it, and its answer kept as its own"),
        ("AC-09-3", "Settings", "Back up or Bring back is chosen",
         "A zip is written and its contents said; a backup is checked, its contents confirmed, brought back and everything read again"),
        ("AC-09-4", "Many saved chats", "The menu or window lists them", "Only each chat's id, title, time and pin are read (cached by file), never copies of every message"),
    ]),
    ("M7-10", "Copy and keys", "normal", [
        ("AC-10-1", "An answer or code block", "Copy is clicked", "Its text is on the clipboard (the overlay's own where Chatmon draws one)"),
        ("AC-10-2", "A bubble with buttons and the ask box open", "Ctrl+1 to Ctrl+9 is pressed", "That button is pressed"),
        ("AC-10-3", "A bubble with buttons that expired or was closed", "A button's label is typed in the box",
         "It's pressed within ANSWERABLE_FOR, and not after"),
    ]),
    ("M7-11", "Platform wiring that wave 1 made possible", "normal", [
        ("AC-11-1", "The session locks (logind, Hyprland) or the power saver is on", "Chatmon hears it",
         "Nothing is drawn while locked; the bubble and the ask box show their still pictures while saving power"),
        ("AC-11-2", "The desktop's colours or reduced motion change", "Chatmon hears it", "The bubble styles are set again at once and the ask box stops fading"),
        ("AC-11-3", "Sound settings (alerts only by default)", "A cue is due",
         "It plays only when sound is on, the cue is on, and it isn't Do Not Disturb, Focus or full screen; one call to sound.play once M4B lands"),
    ]),
    ("M7-12", "A new chat after 15 idle minutes says so", "normal", [
        ("AC-12-1", "A chat last used over 15 minutes ago", "The box opens",
         "A new chat says 'New chat · carry on with the last one', and carry on goes back to it; a question on its way is never dropped by this"),
    ]),
    ("M7-13", "A first-unlock hello", "normal", [
        ("AC-13-1", "Today's reminders, agents waiting or updates pending", "The screen is unlocked the first time today",
         "One bubble names them; not again that day; nothing to say, no bubble"),
    ]),
    ("INT-M0", "M0's integration notes: phrases, non-blocking brain, connections, foreground", "normal", [
        ("AC-M0-6", "Commands in M5's phrase data", "A phrase is typed", "The command table finds it by M5's ids; help is offline.help_text"),
        ("AC-M0-7", "Model servers not yet looked at", "A question is submitted", "The box never waits for the brain: it's looked for off the screen's thread, then asked"),
        ("AC-M0-8", "A connection to Chatmon's pipe on Windows", "It's accepted", "A connection from a process that isn't yours is aborted"),
        ("AC-M0-10", "chatmon ask on Windows with Chatmon running", "It runs", "Only Chatmon's own process is allowed to come forward when its id is known"),
    ]),
    ("INT-M1B", "M1B's integration notes: brains that read files, settings problems, damaged files, test isolation", "critical", [
        ("AC-M1B-7", "A brain that can read files", "It's asked in a chat other brains answered",
         "It gets only its own answers and a summary made from them; a summary made for it is marked as such"),
        ("AC-M1B-9", "config.toml or Settings with wrong values", "Chatmon starts or reloads",
         "Each wrong setting is named and the rest apply; an unreadable file says the defaults are used"),
        ("AC-M1B-10", "A damaged state or memory file was recovered", "Chatmon starts", "A bubble says what happened"),
    ]),
    ("INT-M2", "M2's integration notes: More, remembered size, hint, line breaks", "normal", [
        ("AC-M2-1", "A cut-short bubble, the bigger box, a multi-line question",
         "More is pressed, the box is made bigger and reopened, a question with line breaks is asked",
         "More opens the whole text in the box; the size is remembered; the hint says Shift+Enter; the question keeps its lines"),
    ]),
    ("INT-M5", "M5's integration notes outside reminders: dates in chats follow the locale", "low", [
        ("AC-M5-1", "A chat's date and 'today 3:04 PM'", "They're shown", "They follow the locale's clock and dates (localefmt)"),
    ]),
]

T = "tests/"
C = "chatmon/"
# (task id, purpose, [acceptance], [depends], [(path, action)])
TASKS: list[tuple[str, str, list[str], list[str], list[tuple[str, str]]]] = [
    ("TASK-CI", "Isolate smoke companions from the host desktop; queue considers every ready message; ask box draws while effects play",
     ["AC-CI-1", "AC-CI-2", "AC-CI-3"], [],
     [(C + "messages.py", "modify"), (C + "bubble.py", "modify"), (T + "test_app_smoke.py", "modify"), (T + "test_messages.py", "modify"), (T + "test_bubble_styles.py", "modify")]),
    ("TASK-HARNESS", "Share the smoke companion fixture (and an in-memory keychain) with the new app test files",
     ["AC-CI-1"], ["TASK-CI"], [(T + "app_harness.py", "create"), (T + "test_app_smoke.py", "modify")]),
    ("TASK-ANSWERS", "Stream partial answers, keep answering after the box closes, busy row and Stop",
     ["AC-01-1", "AC-01-2", "AC-01-3"], ["TASK-HARNESS"],
     [(C + "app.py", "modify"), (C + "asking.py", "modify"), (T + "test_app_answers.py", "create"), (T + "test_asking.py", "modify")]),
    ("TASK-FAILURES", "Failure bubble, fallback announced once, first-run brain line, non-blocking brain lookup, untrusted server offer",
     ["AC-02-1", "AC-02-2", "AC-02-3", "AC-02-4", "AC-M0-7"], ["TASK-ANSWERS"], [(C + "app.py", "modify"), (T + "test_app_answers.py", "modify")]),
    ("TASK-CONTEXT", "Own-only history for brains that read files; brain per chat; ask another brain",
     ["AC-M1B-7", "AC-09-2"], ["TASK-FAILURES"], [(C + "app.py", "modify"), (C + "asking.py", "modify"), (C + "menus.py", "modify"), (T + "test_app_answers.py", "modify")]),
    ("TASK-SETTINGS", "Settings window: key and Test, Accessibility tab, reminders' snooze, battery order; live update interval",
     ["AC-03-1", "AC-03-2", "AC-03-3", "AC-03-4", "AC-03-5"], ["TASK-HARNESS"],
     [(C + "settingswin.py", "modify"), (C + "settings.py", "modify"), (C + "app.py", "modify"), (T + "test_settingswin.py", "create"), (T + "test_settings.py", "modify")]),
    ("TASK-STARTUP", "Per-setting problems with overrides and brains coerced; damaged files said at start",
     ["AC-M1B-9", "AC-M1B-10"], ["TASK-SETTINGS"], [(C + "settings.py", "modify"), (C + "app.py", "modify"), (T + "test_app_m7.py", "create")]),
    ("TASK-REMINDERS", "Reminder alerts with Done and snoozes, restored at start, Edit and Repeat in the menu, repeats when adding, pop_due gone",
     ["AC-04-1", "AC-04-2", "AC-04-3", "AC-04-4"], ["TASK-SETTINGS"],
     [(C + "app.py", "modify"), (C + "commands.py", "modify"), (C + "menus.py", "modify"), (C + "cli.py", "modify"), (C + "reminders.py", "modify"),
      (T + "test_app_reminders.py", "create"), (T + "test_reminders.py", "modify"), (T + "test_cli.py", "modify")]),
    ("TASK-FOCUS", "One 'While you focused' summary at a focus session's end", ["AC-05-1"], ["TASK-REMINDERS"],
     [(C + "app.py", "modify"), (C + "messages.py", "modify"), (T + "test_app_reminders.py", "modify"), (T + "test_messages.py", "modify")]),
    ("TASK-MISSED", "Recent messages menu and bringing back missed bubbles", ["AC-06-1", "AC-06-2"], ["TASK-HARNESS"],
     [(C + "app.py", "modify"), (C + "menus.py", "modify"), (C + "messages.py", "modify"), (T + "test_app_m7.py", "modify")]),
    ("TASK-AGENTS", "Agent states in the tray and the stage's name, a badge, the agents command, live states in chatmon status",
     ["AC-07-1", "AC-07-2", "AC-07-3"], ["TASK-COMMANDS"],
     [(C + "app.py", "modify"), (C + "cli.py", "modify"), (C + "events.py", "modify"), (C + "winpipe.py", "modify"), (C + "commands.py", "modify"),
      (T + "test_app_m7.py", "modify"), (T + "test_cli.py", "modify")]),
    ("TASK-QUICK", "Clipboard quick actions", ["AC-08-1"], ["TASK-HARNESS"], [(C + "app.py", "modify"), (C + "menus.py", "modify"), (T + "test_app_m7.py", "modify")]),
    ("TASK-CHATS", "Chats window with search, light listing, menu of recent chats, backup in Settings, locale dates",
     ["AC-09-1", "AC-09-3", "AC-09-4", "AC-M5-1"], ["TASK-CONTEXT", "TASK-SETTINGS"],
     [(C + "chats.py", "modify"), (C + "chatswin.py", "create"), (C + "menus.py", "modify"), (C + "app.py", "modify"), (C + "settingswin.py", "modify"),
      (T + "test_chatswin.py", "create"), (T + "test_chats.py", "modify")]),
    ("TASK-KEYS", "Copy wired; Ctrl+1-9; typed labels after a bubble closed", ["AC-10-1", "AC-10-2", "AC-10-3"], ["TASK-HARNESS"],
     [(C + "app.py", "modify"), (T + "test_app_m7.py", "modify")]),
    ("TASK-PLATFORM", "Lock stops drawing, power saving to bubble and box, palette and motion changes applied, sound and other plumbing",
     ["AC-11-1", "AC-11-2", "AC-11-3"], ["TASK-SETTINGS"], [(C + "app.py", "modify"), (T + "test_app_m7.py", "modify")]),
    ("TASK-NEWCHAT", "New chat after 15 idle minutes, said, with carry on", ["AC-12-1"], ["TASK-COMMANDS"],
     [(C + "app.py", "modify"), (C + "commands.py", "modify"), (T + "test_app_m7.py", "modify")]),
    ("TASK-HELLO", "A first-unlock hello", ["AC-13-1"], ["TASK-REMINDERS"], [(C + "app.py", "modify"), (T + "test_app_m7.py", "modify")]),
    ("TASK-COMMANDS", "Command table on M5's phrase ids, help from offline.help_text", ["AC-M0-6"], ["TASK-HARNESS"],
     [(C + "commands.py", "modify"), (T + "test_commands.py", "modify")]),
    ("TASK-IPC", "Windows connections checked with client_is_me; chatmon ask lets only Chatmon come forward",
     ["AC-M0-8", "AC-M0-10"], ["TASK-AGENTS"], [(C + "app.py", "modify"), (C + "cli.py", "modify"), (T + "test_cli.py", "modify"), (T + "test_app_m7.py", "modify")]),
    ("TASK-M2NOTES", "More to show_notes, remembered size, hint, multi-line questions kept", ["AC-M2-1"], ["TASK-ANSWERS"],
     [(C + "app.py", "modify"), (T + "test_app_m7.py", "modify")]),
]


def ledger(receipts: list[dict], status: dict[str, str], checkpoint: dict | None, blockers: dict[str, str]) -> dict:
    requirements, acceptance = [], []
    for rid, statement, priority, criteria in REQS:
        requirements.append({"id": rid, "statement": statement, "priority": priority, "acceptance": [c[0] for c in criteria], "superseded_by": None})
        for aid, given, when, then in criteria:
            acceptance.append({"id": aid, "requirement": rid, "given": given, "when": when, "then": then, "checks": ["behavior", "red"], "manual_reason": None})
    tasks = []
    for tid, purpose, acs, deps, changes in TASKS:
        tasks.append({
            "id": tid, "purpose": purpose, "acceptance": acs, "depends_on": deps,
            "changes": [{"path": p, "action": a} for p, a in changes],
            "status": status.get(tid, "planned"),
            "evidence": [r["id"] for r in receipts if set(r["acceptance"]) & set(acs) and r["status"] == "pass"],
            "blocker": blockers.get(tid), "superseded_by": None,
        })
    return {"schema_version": 1, "work": WORK, "requirements": requirements, "acceptance": acceptance, "tasks": tasks,
            "evidence": receipts, "checkpoint": checkpoint}


FENCE = "```quality-ledger"


def main() -> int:
    """PLAN is read for its prose (everything before its ledger block, if it has one); OUT gets that prose and the
    ledger as the records here and receipts.json make it (a candidate for update-delivery.py)."""
    plan, out = Path(sys.argv[1]), Path(sys.argv[2])
    prose = plan.read_text(encoding="utf-8").split(FENCE)[0].rstrip()
    state = json.loads((HERE / "receipts.json").read_text(encoding="utf-8")) if (HERE / "receipts.json").exists() else {}
    block = ledger(state.get("receipts", []), state.get("status", {}), state.get("checkpoint"), state.get("blockers", {}))
    out.write_text(prose + f"\n\n{FENCE}\n" + json.dumps(block, indent=2, ensure_ascii=False) + "\n```\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
