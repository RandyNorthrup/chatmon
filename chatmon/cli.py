"""Command line: start Chatmon, or talk to the one that's running."""

from __future__ import annotations

import json
import os
import sys
import threading

from . import __version__, events, paths

USAGE = """\
usage: chatmon [command]

  (no command)               start Chatmon
  hooks                      list the AI agents found here and whether they're connected
  hooks connect AGENT|all    let an agent tell your chatmon what it's doing
  hooks disconnect AGENT|all take that back out of the agent's settings
  hooks show AGENT|any       how to connect one by hand
  notify [EVENT] [JSON]      tell your chatmon what an agent is doing (hooks run this)
      --source NAME          who it's from: claude, codex, muse, gemini...
      --stdin                read the hook's JSON payload from stdin
      --message TEXT         what to show
      EVENT is one of: working, needs-you, done, success, error, idle;
      left out, it's worked out from the payload
  say TEXT                   make it say something
  remind WHEN [to] TEXT      set a reminder: remind in 20m to stretch
  quit                       close the chatmon that's running
  autostart on|off           start it when you log in
  --version
"""

STDIN_LIMIT = 256 * 1024  # bytes of hook payload to read at most
STDIN_WAIT = 0.5  # seconds to wait for it


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    paths.migrate()  # settings and state from before the rename, the first time it runs
    if not args:
        from .app import run

        return run()
    command, rest = args[0], args[1:]
    if command in ("-h", "--help", "help"):
        print(USAGE, end="")
        return 0
    if command == "--version":
        print(__version__)
        return 0
    if command == "notify":
        return notify(rest)
    if command == "say":
        return _send({"type": "say", "text": " ".join(rest)})
    if command == "remind":
        return _send({"type": "remind", "text": " ".join(rest)})
    if command == "quit":
        return _send({"type": "quit"})
    if command == "hooks":
        return hooks(rest)
    if command == "autostart" and rest and rest[0] in ("on", "off"):
        from . import autostart

        autostart.set_enabled(rest[0] == "on")
        print(f"Autostart {rest[0]}: {autostart.where()}")
        return 0
    print(USAGE, end="", file=sys.stderr)
    return 2


def _send(message: dict) -> int:
    if events.send(message):
        return 0
    print("Chatmon isn't running. Start it with: chatmon", file=sys.stderr)
    return 1


def _json(text: str) -> dict:
    try:
        value = json.loads(text)
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def _read_stdin() -> str:
    """The hook's payload, without ever hanging on a stdin nobody closes."""
    if sys.stdin is None or sys.stdin.isatty():
        return ""
    chunks: list[bytes] = []

    def read() -> None:
        try:
            chunks.append(sys.stdin.buffer.read(STDIN_LIMIT))
        except (OSError, ValueError):
            pass

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    reader.join(STDIN_WAIT)
    return chunks[0].decode("utf-8", errors="replace") if chunks else ""


def notify(args: list[str]) -> int:
    """For hooks: never fails, never waits long, never prints."""
    if os.environ.get(events.INTERNAL_ENV):
        return 0
    event = source = message = None
    payload: dict = {}
    read_stdin = False
    it = iter(args)
    for arg in it:
        if arg == "--source":
            source = next(it, None)
        elif arg == "--message":
            message = next(it, None)
        elif arg == "--stdin":
            read_stdin = True
        elif arg.lstrip().startswith("{"):
            payload = _json(arg)
        elif event is None:
            event = arg
        elif message is None:
            message = arg
    if read_stdin:
        payload = _json(_read_stdin()) or payload
    msg = events.event_from(event, payload, source=_real_source(source), message=message)
    if msg:
        events.send(msg)
    return 0


# Agents that also run Claude Code's hooks say who they really are in their environment.
_BORROWERS = (("GROK_HOOK_EVENT", "grok"), ("CURSOR_VERSION", "cursor"), ("DEVIN_PROJECT_DIR", "devin"))


def _real_source(source: str | None) -> str | None:
    if source in (None, "claude"):
        for var, name in _BORROWERS:
            if os.environ.get(var):
                return name
    return source


def hooks(args: list[str]) -> int:
    from . import agents

    paths.windows_environment()  # run by the installer, from before it put chatmon on PATH
    action = args[0] if args else "list"
    target = args[1] if len(args) > 1 else None
    if action == "list":
        for agent in agents.AGENTS:
            print(f"  {agent.name:<10} {agent.label:<20} {agent.status()}")
        print("\nConnect one with: chatmon hooks connect NAME   (or: all)")
        return 0
    if action == "show":
        agent = agents.find(target or "")
        print(agent.manual() if agent else agents.generic())
        return 0
    if action not in ("connect", "disconnect") or not target:
        print(USAGE, end="", file=sys.stderr)
        return 2
    if target == "all":  # connecting, every agent found here; disconnecting, only those connected: nobody else's file is touched
        chosen = [a for a in agents.AGENTS if (a.detected() if action == "connect" else a.connected())]
        if not chosen:
            print("No coding agents found here." if action == "connect" else "No coding agents are connected.")
    else:
        chosen = [agents.find(target)]
    if chosen == [None]:
        print(f"Unknown agent {target!r}. Known: {', '.join(a.name for a in agents.AGENTS)}", file=sys.stderr)
        return 2
    failed = 0
    for agent in chosen:
        try:
            print(agent.connect() if action == "connect" else agent.disconnect())
        except (agents.AgentError, OSError) as exc:
            failed += 1
            print(f"{agent.label}: {exc}", file=sys.stderr)
    return 1 if failed else 0
