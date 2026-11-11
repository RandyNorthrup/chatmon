"""Connecting Chatmon to AI coding agents, so your chatmon reacts while they work.

Each agent has its own way of running a command when something happens.
Connecting writes Chatmon's `notify` command into that agent's own settings;
disconnecting takes it out again. Every change is something you ask for, is
made after a backup of the file it changes, and only ever touches entries that
run chatmon (or penguin-companion, its old name).

Hooks connected under the old name still work (penguin-companion stays as an
alias for now); `migrate()` swaps them for chatmon's, and the app does that for
each agent when it starts.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

from . import paths

MARK = "chatmon"  # every command we add contains this; it's how we find ours again
LEGACY_MARK = "penguin-companion"  # what the commands contained before the rename


def _runs(name: str) -> re.Pattern:
    """`name notify`, the command we add: the program on its own (any folder, quotes, .exe, or run as
    `python -m name`), then notify. Never a word that merely contains it, like chatmonitor."""
    module = name.replace("-", "_")
    # A space, or the next item of a list or a quoted command line: "chatmon", "notify" / 'chatmon.exe' 'notify'.
    between = r"""["']?(?:\s*,\s*|\s+)["']?"""
    # .exe in any case: Windows finds chatmon.EXE, in PATHEXT's capitals.
    return re.compile(rf"""(?:^|[\s/\\"'=])(?:{re.escape(name)}|{re.escape(module)})(?i:\.exe|\.py)?{between}notify(?:\s|$|["',\]])""")


_OURS = _runs(MARK)
_LEGACY = _runs(LEGACY_MARK)


def is_ours(text: str) -> bool:
    return bool(_OURS.search(text) or _LEGACY.search(text))


def is_legacy(text: str) -> bool:
    """A command added under the old name, still to be swapped for chatmon's."""
    return bool(_LEGACY.search(text)) and not _OURS.search(text)


class AgentError(Exception):
    pass


def hook_program() -> list[str]:
    """How a hook runs Chatmon. On Windows, by name when it's on your PATH: agents run hooks there through
    PowerShell, cmd or Git Bash, and a full path doesn't get through all three (bash drops its backslashes,
    PowerShell won't run a quoted one), where the name does, as in the Claude Code plugin."""
    if sys.platform == "win32" and shutil.which(paths.APP):
        return [paths.APP]
    return paths.command_line()


def notify_argv(event: str, source: str, stdin: bool = True) -> list[str]:
    return hook_program() + ["notify", event, "--source", source] + (["--stdin"] if stdin else [])


def shell_line(argv: list[str]) -> str:
    return subprocess.list2cmdline(argv) if sys.platform == "win32" else shlex.join(argv)


def backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    copy = path.with_name(f"{path.name}.chatmon-backup-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(path, copy)
    return copy


def write_atomic(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Replace `path` with `text` all at once. The new copy is made with the old one's permissions from the
    start (a new file: readable by you alone), never briefly open to others: these files can hold tokens."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".chatmon-tmp")
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    tmp.unlink(missing_ok=True)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as fh:
            fh.write(text)
        os.chmod(tmp, mode)  # O_CREAT's mode passes through the umask
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def load_json(path: Path) -> dict:
    """A settings file's contents; refuses (rather than overwrites) anything that isn't a JSON object."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except ValueError as exc:
        raise AgentError(f"{path} isn't valid JSON ({exc}); not touching it.") from None
    if not isinstance(data, dict):
        raise AgentError(f"{path} isn't a JSON object; not touching it.")
    return data


def _home_env(var: str, default: Path) -> Path:
    value = os.environ.get(var)
    return Path(value).expanduser() if value else default


class Agent:
    name = ""
    label = ""
    command = ""  # its command-line program, if it has one

    def config_path(self) -> Path | None:
        return None

    def detected(self) -> bool:
        path = self.config_path()
        return bool(self.command and paths.which(self.command)) or bool(path and path.parent.exists())

    def connected(self) -> bool:
        raise NotImplementedError

    def status(self) -> str:
        if self.connected():
            return "connected"
        return "found" if self.detected() else "not found"

    def connect(self) -> str:
        raise NotImplementedError

    def disconnect(self) -> str:
        raise NotImplementedError

    def manual(self) -> str:
        raise NotImplementedError

    def legacy(self) -> bool:
        """Connected under the old name, penguin-companion."""
        return False

    def migrate(self) -> str:
        """Swap hooks connected under the old name for chatmon's; nothing if there are none."""
        return self.connect() if self.legacy() else ""


class JsonHooks(Agent):
    """Agents whose settings file has Claude Code's shape:
    {"hooks": {"Event": [{"matcher": ..., "hooks": [{"type": "command", "command": "..."}]}]}}"""

    events: dict[str, str] = {}  # the agent's event name: ours
    matchers: dict[str, str] = {}  # the agent's event name: which of its kind to catch

    def _load(self) -> dict:
        return load_json(self.config_path())

    def hook(self, ours: str) -> dict:
        return {"type": "command", "command": shell_line(notify_argv(ours, self.name))}

    def _entry(self, event: str, ours: str) -> dict:
        group = {"hooks": [self.hook(ours)]}
        return {"matcher": self.matchers[event], **group} if event in self.matchers else group

    @staticmethod
    def _is_ours(group) -> bool:
        return isinstance(group, dict) and any(is_ours(str(h.get("command", ""))) for h in group.get("hooks", []) if isinstance(h, dict))

    def _groups(self) -> list:
        try:
            hooks = self._load().get("hooks") or {}
        except AgentError:
            return []
        return [g for event in self.events for g in hooks.get(event) or []] if isinstance(hooks, dict) else []

    def connected(self) -> bool:
        return any(self._is_ours(g) for g in self._groups())

    def legacy(self) -> bool:
        return any(self._is_ours(g) and is_legacy(json.dumps(g)) for g in self._groups())

    def connect(self) -> str:
        data = self._load()
        hooks = data.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise AgentError(f'"hooks" in {self.config_path()} isn\'t an object; not touching it.')
        for event, ours in self.events.items():
            groups = [g for g in (hooks.get(event) or []) if not self._is_ours(g)]
            hooks[event] = groups + [self._entry(event, ours)]
        saved = backup(self.config_path())
        write_atomic(self.config_path(), json.dumps(data, indent=2) + "\n")
        return self._report("Connected", saved)

    def disconnect(self) -> str:
        data = self._load()
        hooks = data.get("hooks")
        if not isinstance(hooks, dict):
            return f"{self.label} wasn't connected."
        for event in list(hooks):
            if isinstance(hooks[event], list):
                kept = [g for g in hooks[event] if not self._is_ours(g)]
                if kept:
                    hooks[event] = kept
                else:
                    del hooks[event]
        if not hooks:
            del data["hooks"]
        saved = backup(self.config_path())
        write_atomic(self.config_path(), json.dumps(data, indent=2) + "\n")
        return self._report("Disconnected", saved)

    def _report(self, what: str, saved: Path | None) -> str:
        note = f" (backup: {saved})" if saved else ""
        return f"{what} {self.label}: {self.config_path()}{note}"

    def manual(self) -> str:
        snippet = {"hooks": {event: [self._entry(event, ours)] for event, ours in self.events.items()}}
        return f"Merge into {self.config_path()}:\n{json.dumps(snippet, indent=2)}"


# No console window for a command-line tool run from the app: there's none of ours for it to share.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _run_json(argv: list[str], what: str) -> object:
    """Run another tool's command line and read its --json output."""
    program = shutil.which(argv[0])  # on Windows, also finds an npm install's claude.cmd, which running "claude" wouldn't
    if not program:
        raise AgentError(f"{what} isn't installed.")
    paths.restore_dll_search()
    try:
        proc = subprocess.run(
            [program, *argv[1:]], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, creationflags=_NO_WINDOW
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AgentError(f"{' '.join(argv[:3])} failed: {exc}") from None
    if proc.returncode != 0:
        raise AgentError(f"{' '.join(argv[:3])} failed: {(proc.stderr or proc.stdout).strip()[-300:]}")
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    for text in (proc.stdout, lines[-1] if lines else ""):
        try:
            return json.loads(text)
        except ValueError:
            continue
    return {}


def _needs_on_path() -> None:
    if not shutil.which(paths.APP):
        raise AgentError(
            f"{paths.APP} has to be on your PATH for agent plugins to find it. Install it with "
            f"`pipx install git+https://github.com/RandyNorthrup/chatmon`, or link the launcher: ln -s <repo>/bin/{paths.APP} ~/.local/bin/"
        )


class ClaudeCode(Agent):
    """Claude Code gets Chatmon's hooks from a plugin, which Claude Code
    manages itself; editing its settings file under a running Claude Code
    can be undone the next time it saves."""

    name, label, command = "claude", "Claude Code", "claude"
    MARKETPLACE = "chatmon"
    PLUGIN = "chatmon@chatmon"
    LEGACY_MARKETPLACE = "penguin-companion"
    LEGACY_PLUGIN = "penguin-companion@penguin-companion"

    def config_path(self) -> Path:
        return _home_env("CLAUDE_CONFIG_DIR", Path.home() / ".claude") / "settings.json"

    @staticmethod
    def packaged_marketplace() -> Path:
        """The marketplace and plugin as they ship, inside the installed package."""
        return Path(__file__).resolve().parent / "integrations" / "claude"

    @staticmethod
    def marketplace_dir() -> Path:
        """Where Claude Code reads the marketplace from: a copy in Chatmon's state folder. Claude Code
        drops a marketplace whose folder has gone, and its plugin with it, so it must not be the
        package's own folder, which an upgrade, a reinstall or a rename takes away."""
        return paths.state_dir() / "integrations" / "claude-marketplace"

    def _publish(self) -> Path:
        """Copy the marketplace as this version ships it to where Claude Code reads it."""
        folder = self.marketplace_dir()
        if folder.exists():
            shutil.rmtree(folder)
        shutil.copytree(self.packaged_marketplace(), folder)
        return folder

    def _plugins(self) -> list:
        found = _run_json(["claude", "plugin", "list", "--json"], self.label)
        return found if isinstance(found, list) else []

    def _mine(self, plugin: str | None = None) -> dict | None:
        """Our plugin as Claude Code lists it: chatmon's, else the one from before the rename."""
        found = {p.get("id"): p for p in self._plugins() if isinstance(p, dict)}
        if plugin is not None:
            return found.get(plugin)
        return found.get(self.PLUGIN) or found.get(self.LEGACY_PLUGIN)

    def connected(self) -> bool:
        try:
            mine = self._mine()
        except AgentError:
            return False
        return bool(mine and mine.get("enabled", True))

    def legacy(self) -> bool:
        try:
            return self._mine(self.LEGACY_PLUGIN) is not None
        except AgentError:
            return False

    def migrate(self) -> str:
        if not self.legacy():
            return ""
        was_on = bool((self._mine(self.LEGACY_PLUGIN) or {}).get("enabled", True))
        if was_on:
            _needs_on_path()  # before anything is removed: the new plugin runs `chatmon` by name
        self._remove(self.LEGACY_PLUGIN, self.LEGACY_MARKETPLACE)
        if not was_on:  # it was switched off: leave it off, under the new name too
            return f"Removed Claude Code's {self.LEGACY_PLUGIN} plugin (it was off)"
        return self.connect()

    def _remove(self, plugin: str, marketplace: str) -> None:
        if self._mine(plugin) is not None:
            _run_json(["claude", "plugin", "uninstall", plugin, "--scope", "user", "--json"], self.label)
        try:
            _run_json(["claude", "plugin", "marketplace", "remove", marketplace, "--json"], self.label)
        except AgentError:
            pass

    def status(self) -> str:
        try:
            mine = self._mine()  # once: each look starts Claude Code's command line, a second or so
        except AgentError:
            mine = None
        if mine:
            return "connected" if mine.get("enabled", True) else "installed but off"
        return "found" if self.detected() else "not found"

    def connect(self) -> str:
        _needs_on_path()
        folder = self._publish()
        markets = _run_json(["claude", "plugin", "marketplace", "list", "--json"], self.label)
        names = {m.get("name") for m in markets} if isinstance(markets, list) else set()
        if self.MARKETPLACE not in names:
            _run_json(["claude", "plugin", "marketplace", "add", str(folder), "--json"], self.label)
        mine = self._mine(self.PLUGIN)
        if mine is None:
            _run_json(["claude", "plugin", "install", self.PLUGIN, "--scope", "user", "--json"], self.label)
        elif not mine.get("enabled", True):
            _run_json(["claude", "plugin", "enable", self.PLUGIN, "--scope", "user", "--json"], self.label)
        return (
            f"Connected Claude Code: the {self.PLUGIN} plugin is installed and on. It takes effect in new "
            "Claude Code sessions; a session that's open now can switch it off again when it saves its "
            "settings, so connect again after closing those if `chatmon hooks` says it's off."
        )

    def disconnect(self) -> str:
        self._remove(self.PLUGIN, self.MARKETPLACE)
        if self.legacy():
            self._remove(self.LEGACY_PLUGIN, self.LEGACY_MARKETPLACE)
        return f"Disconnected Claude Code: uninstalled the {self.PLUGIN} plugin"

    def manual(self) -> str:
        return (
            "In Claude Code, run:\n"
            "  /plugin install chatmon --marketplace RandyNorthrup/chatmon\n"
            f"or from a terminal:\n"
            f"  claude plugin marketplace add {self.packaged_marketplace()}\n"
            f"  claude plugin install {self.PLUGIN}\n"
            f"The plugin runs `{paths.APP} notify ...`, so {paths.APP} has to be on your PATH."
        )


class Codex(Agent):
    """Codex runs one `notify` program, with a JSON summary, when a turn ends."""

    name, label, command = "codex", "Codex", "codex"
    _LINE = re.compile(r"^\s*notify\s*=.*$", re.M)

    def config_path(self) -> Path:
        return _home_env("CODEX_HOME", Path.home() / ".codex") / "config.toml"

    def _argv(self) -> list[str]:
        return notify_argv("done", self.name, stdin=False)

    def _text(self) -> str:
        path = self.config_path()
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def _parse(self, text: str) -> dict:
        try:
            return tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            raise AgentError(f"{self.config_path()} isn't valid TOML ({exc}); not touching it.") from None

    def connected(self) -> bool:
        try:
            current = self._parse(self._text()).get("notify")
        except AgentError:
            return False
        return isinstance(current, list) and is_ours(" ".join(map(str, current)))

    def legacy(self) -> bool:
        try:
            current = self._parse(self._text()).get("notify")
        except AgentError:
            return False
        return isinstance(current, list) and is_legacy(" ".join(map(str, current)))

    def connect(self) -> str:
        text = self._text()
        current = self._parse(text).get("notify")
        if current and not is_ours(" ".join(map(str, current))):
            raise AgentError(
                f"Codex already runs {current!r} when a turn ends, and it takes only one program. "
                f"Not replacing it; see `chatmon hooks show codex` to do it by hand."
            )
        line = "notify = [" + ", ".join(json.dumps(a) for a in self._argv()) + "]"
        text = self._LINE.sub(lambda m: "" if is_ours(m.group(0)) else m.group(0), text)
        header = re.search(r"^\s*\[", text, re.M)  # a top-level key has to come before the first table
        at = header.start() if header else len(text)
        before, after = text[:at].rstrip("\n"), text[at:]
        new = (before + "\n" if before.strip() else "") + line + "\n" + ("\n" + after if after else "")
        if self._parse(new).get("notify") != self._argv():
            raise AgentError("Couldn't add the notify line cleanly; not touching the file.")
        saved = backup(self.config_path())
        write_atomic(self.config_path(), new)
        return f"Connected Codex: {self.config_path()}" + (f" (backup: {saved})" if saved else "")

    def disconnect(self) -> str:
        text = self._text()
        ours = [m for m in self._LINE.finditer(text) if is_ours(m.group(0))]
        if not ours:
            return "Codex wasn't connected."
        new = self._LINE.sub(lambda m: "" if is_ours(m.group(0)) else m.group(0), text)
        new = re.sub(r"\A\n+", "", new)
        self._parse(new)
        saved = backup(self.config_path())
        write_atomic(self.config_path(), new)
        return f"Disconnected Codex: {self.config_path()} (backup: {saved})"

    def manual(self) -> str:
        line = "notify = [" + ", ".join(json.dumps(a) for a in self._argv()) + "]"
        return f"Add near the top of {self.config_path()}, before any [table]:\n{line}"


class Muse(Agent):
    """Muse Code takes hooks from plugins: we install a small one."""

    name, label, command = "muse", "Muse Code", "muse"
    PLUGIN = "chatmon"
    LEGACY_PLUGIN = "penguin-companion"
    events = {"UserPromptSubmit": "working", "PermissionRequest": "needs-you", "Notification": "needs-you", "Stop": "done", "Interrupt": "idle"}

    def bundle_dir(self) -> Path:
        return paths.state_dir() / "integrations" / "muse-plugin"

    def manifest(self) -> dict:
        hooks = [
            {"id": f"{ours}-{event.lower()}", "event": event, "command": notify_argv(ours, self.name), "timeoutMs": 3000, "async": True}
            for event, ours in self.events.items()
        ]
        return {
            "schemaVersion": 1,
            "name": self.PLUGIN,
            "displayName": "Chatmon",
            "version": "1.0.0",
            "description": "Lets your chatmon react while Muse works.",
            "compat": {"source": "native", "manifestDir": ".muse-plugin"},
            "capabilities": {"skills": [], "commands": [], "hooks": hooks, "mcpServers": [], "reminders": []},
        }

    def _muse(self, *args: str) -> dict:
        found = _run_json(["muse", "plugins", *args, "--json"], self.label)
        return found if isinstance(found, dict) else {}

    def _installed(self) -> set[str]:
        try:
            plugins = self._muse("list").get("plugins", [])
        except AgentError:
            return set()
        return {(p.get("plugin") or {}).get("id") for p in plugins if isinstance(p, dict)}

    def connected(self) -> bool:
        return bool({self.PLUGIN, self.LEGACY_PLUGIN} & self._installed())

    def legacy(self) -> bool:
        return self.LEGACY_PLUGIN in self._installed()

    def connect(self) -> str:
        folder = self.bundle_dir()
        write_atomic(folder / ".muse-plugin" / "plugin.json", json.dumps(self.manifest(), indent=2) + "\n")
        installed = self._installed()
        if self.LEGACY_PLUGIN in installed:
            self._muse("remove", self.LEGACY_PLUGIN)
        if self.PLUGIN in installed:
            self._muse("remove", self.PLUGIN)
        self._muse("install", str(folder), "--scope", "user")
        self._muse("approve", self.PLUGIN)
        return f"Connected Muse Code: installed and approved its {self.PLUGIN} plugin (from {folder})"

    def disconnect(self) -> str:
        installed = self._installed() & {self.PLUGIN, self.LEGACY_PLUGIN}
        if not installed:
            return "Muse Code wasn't connected."
        for plugin in sorted(installed):
            self._muse("remove", plugin)
        return f"Disconnected Muse Code: removed its {self.PLUGIN} plugin"

    def manual(self) -> str:
        return (
            f"Save this as <folder>/.muse-plugin/plugin.json, then run\n"
            f"  muse plugins install <folder> --scope user && muse plugins approve {self.PLUGIN}\n"
            f"{json.dumps(self.manifest(), indent=2)}"
        )


class Gemini(JsonHooks):
    name, label, command = "gemini", "Gemini CLI", "gemini"
    events = {"BeforeAgent": "working", "Notification": "needs-you", "AfterAgent": "done"}

    def config_path(self) -> Path:
        return _home_env("GEMINI_CLI_HOME", Path.home()) / ".gemini" / "settings.json"

    def hook(self, ours: str) -> dict:
        return {"name": f"chatmon-{ours}", **super().hook(ours), "timeout": 5000}  # Gemini's timeouts are in ms


class Qwen(JsonHooks):
    name, label, command = "qwen", "Qwen Code", "qwen"
    events = {"UserPromptSubmit": "working", "Notification": "needs-you", "Stop": "done"}
    matchers = {"Notification": "permission_prompt"}

    def config_path(self) -> Path:
        return Path.home() / ".qwen" / "settings.json"


class Devin(JsonHooks):
    name, label, command = "devin", "Devin CLI", "devin"
    events = {"UserPromptSubmit": "working", "Stop": "done"}

    def config_path(self) -> Path:
        if sys.platform == "win32":
            return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "devin" / "config.json"
        return _home_env("XDG_CONFIG_HOME", Path.home() / ".config") / "devin" / "config.json"


class OwnFile(Agent):
    """Agents that read every hooks file in a folder: Chatmon gets a file of its own (chatmon.json; before
    the rename, penguin-companion.json)."""

    def content(self) -> dict:
        raise NotImplementedError

    def legacy_path(self) -> Path:
        return self.config_path().with_name(f"{LEGACY_MARK}.json")

    def _ours(self, path: Path) -> bool:
        return path.exists() and is_ours(path.read_text(encoding="utf-8", errors="replace"))

    def connected(self) -> bool:
        return self._ours(self.config_path()) or self._ours(self.legacy_path())

    def legacy(self) -> bool:
        return self._ours(self.legacy_path())

    def connect(self) -> str:
        write_atomic(self.config_path(), json.dumps(self.content(), indent=2) + "\n")
        if self.legacy():
            self.legacy_path().unlink()
        return f"Connected {self.label}: {self.config_path()}"

    def disconnect(self) -> str:
        found = [path for path in (self.config_path(), self.legacy_path()) if self._ours(path)]
        if not found:
            return f"{self.label} wasn't connected."
        for path in found:
            path.unlink()
        return f"Disconnected {self.label}: removed {', '.join(map(str, found))}"

    def manual(self) -> str:
        return f"Save as {self.config_path()}:\n{json.dumps(self.content(), indent=2)}"


class Grok(OwnFile):
    name, label, command = "grok", "Grok", "grok"

    def config_path(self) -> Path:
        return _home_env("GROK_HOME", Path.home() / ".grok") / "hooks" / f"{MARK}.json"

    def detected(self) -> bool:
        return bool(paths.which("grok")) or self.config_path().parent.parent.exists()

    def content(self) -> dict:
        def group(ours: str, matcher: str | None = None) -> list:
            entry = {"hooks": [{"type": "command", "command": shell_line(notify_argv(ours, self.name)), "timeout": 5}]}
            return [{"matcher": matcher, **entry} if matcher else entry]

        return {
            "hooks": {
                "UserPromptSubmit": group("working"),
                "Notification": group("needs-you", "permission_prompt"),
                "Stop": group("done"),
                "StopFailure": group("done"),
                "StopCancelled": group("idle"),
            }
        }


class Copilot(OwnFile):
    name, label, command = "copilot", "GitHub Copilot CLI", "copilot"

    def config_path(self) -> Path:
        return _home_env("COPILOT_HOME", Path.home() / ".copilot") / "hooks" / f"{MARK}.json"

    def detected(self) -> bool:
        return bool(paths.which("copilot")) or self.config_path().parent.parent.exists()

    def content(self) -> dict:
        def hook(ours: str, matcher: str | None = None) -> list:
            entry = {"type": "command", "command": shell_line(notify_argv(ours, self.name)), "timeoutSec": 5}
            return [{**entry, "matcher": matcher} if matcher else entry]

        # PascalCase keys, so the payload carries hook_event_name.
        return {
            "version": 1,
            "hooks": {
                "UserPromptSubmit": hook("working"),
                "notification": hook("needs-you", "permission_prompt|elicitation_dialog"),
                "Stop": hook("done"),
            },
        }


class Cursor(Agent):
    """Cursor's ~/.cursor/hooks.json: {"version": 1, "hooks": {"event": [{"command": ...}]}}."""

    name, label, command = "cursor", "Cursor", "cursor"
    events = {"beforeSubmitPrompt": "working", "stop": "done"}

    def config_path(self) -> Path:
        return Path.home() / ".cursor" / "hooks.json"

    def _load(self) -> dict:
        return load_json(self.config_path())

    @staticmethod
    def _is_ours(entry) -> bool:
        return isinstance(entry, dict) and is_ours(str(entry.get("command", "")))

    def _entry(self, ours: str) -> dict:
        return {"command": shell_line(notify_argv(ours, self.name)), "timeout": 5}

    def _entries(self) -> list:
        try:
            hooks = self._load().get("hooks") or {}
        except AgentError:
            return []
        return [e for event in self.events for e in hooks.get(event) or []] if isinstance(hooks, dict) else []

    def connected(self) -> bool:
        return any(self._is_ours(e) for e in self._entries())

    def legacy(self) -> bool:
        return any(self._is_ours(e) and is_legacy(str(e.get("command", ""))) for e in self._entries())

    def connect(self) -> str:
        data = self._load()
        data.setdefault("version", 1)
        hooks = data.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise AgentError(f'"hooks" in {self.config_path()} isn\'t an object; not touching it.')
        for event, ours in self.events.items():
            hooks[event] = [e for e in hooks.get(event) or [] if not self._is_ours(e)] + [self._entry(ours)]
        saved = backup(self.config_path())
        write_atomic(self.config_path(), json.dumps(data, indent=2) + "\n")
        return f"Connected Cursor: {self.config_path()}" + (f" (backup: {saved})" if saved else "")

    def disconnect(self) -> str:
        data = self._load()
        hooks = data.get("hooks")
        if not isinstance(hooks, dict) or not self.connected():
            return "Cursor wasn't connected."
        for event in list(hooks):
            if isinstance(hooks[event], list):
                kept = [e for e in hooks[event] if not self._is_ours(e)]
                if kept:
                    hooks[event] = kept
                else:
                    del hooks[event]
        saved = backup(self.config_path())
        write_atomic(self.config_path(), json.dumps(data, indent=2) + "\n")
        return f"Disconnected Cursor: {self.config_path()} (backup: {saved})"

    def manual(self) -> str:
        snippet = {"version": 1, "hooks": {event: [self._entry(ours)] for event, ours in self.events.items()}}
        return f"Merge into {self.config_path()}:\n{json.dumps(snippet, indent=2)}"


class Cline(Agent):
    """Cline runs the executable named after each event in ~/Documents/Cline/Hooks."""

    name, label, command = "cline", "Cline", "cline"
    events = {"UserPromptSubmit": "working", "TaskComplete": "done", "TaskCancel": "idle"}

    def config_path(self) -> Path:
        return Path.home() / "Documents" / "Cline" / "Hooks"

    def detected(self) -> bool:
        return bool(paths.which("cline")) or self.config_path().parent.exists()

    def _file(self, event: str) -> Path:
        return self.config_path() / (f"{event}.ps1" if sys.platform == "win32" else event)

    def _script(self, ours: str) -> str:
        if sys.platform == "win32":
            argv = notify_argv(ours, self.name, stdin=False)
            quoted = " ".join("'" + a.replace("'", "''") + "'" for a in argv)  # PowerShell single quotes
            return f"# {MARK}\n& {quoted}\nexit 0\n"
        return f"#!/bin/sh\n# {MARK}\n{shell_line(notify_argv(ours, self.name))} || true\n"

    def _text(self, event: str) -> str | None:
        path = self._file(event)
        return path.read_text(encoding="utf-8-sig", errors="replace") if path.exists() else None

    def connected(self) -> bool:
        return any(is_ours(self._text(e) or "") for e in self.events)

    def legacy(self) -> bool:
        return any(is_legacy(self._text(e) or "") for e in self.events)

    def connect(self) -> str:
        taken = [e for e in self.events if self._text(e) is not None and not is_ours(self._text(e))]
        if taken:
            raise AgentError(f"You already have Cline hooks for {', '.join(taken)}; not replacing them. See `chatmon hooks show cline`.")
        for event, ours in self.events.items():
            path = self._file(event)
            backup(path)
            # With a BOM: Windows PowerShell 5.1 reads a script without one in the ANSI code page, which
            # would garble a path like C:\Users\José.
            write_atomic(path, self._script(ours), encoding="utf-8-sig" if path.suffix == ".ps1" else "utf-8")
            if sys.platform != "win32":
                path.chmod(0o700)
        return f"Connected Cline: hook scripts in {self.config_path()} (Cline's \"Enable Hooks\" setting has to be on)"

    def disconnect(self) -> str:
        removed = 0
        for event in self.events:
            path = self._file(event)
            if is_ours(self._text(event) or ""):
                backup(path)
                path.unlink()
                removed += 1
        return f"Disconnected Cline: removed {removed} hook scripts" if removed else "Cline wasn't connected."

    def manual(self) -> str:
        parts = [f"In {self.config_path()}, one executable file per event:"]
        for event, ours in self.events.items():
            parts.append(f"--- {self._file(event).name}\n{self._script(ours)}")
        return "\n".join(parts)


AGENTS: list[Agent] = [ClaudeCode(), Codex(), Gemini(), Muse(), Grok(), Copilot(), Cursor(), Cline(), Qwen(), Devin()]


def find(name: str) -> Agent | None:
    return next((a for a in AGENTS if a.name == name), None)


def generic() -> str:
    cmd = shell_line(hook_program())
    return (
        "Any other agent or script: have its hooks run\n"
        f"  {cmd} notify working   --source NAME    # started on something\n"
        f"  {cmd} notify needs-you --source NAME 'Approve the deploy?'\n"
        f"  {cmd} notify done      --source NAME    # finished\n"
        "Add --stdin if the hook hands over a JSON payload on stdin. The command prints nothing\n"
        "and always succeeds, so it can't block or change what the agent does.\n\n"
        "Aider:  aider --notifications-command '" + cmd + " notify done --source aider'\n"
        "Kiro:   add a Shell Command hook on Prompt Submit / Agent Stop that runs the lines above.\n"
        "OpenCode, Amp: these take JavaScript plugins; have one run the lines above on their events."
    )
