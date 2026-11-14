"""Settings you edit (config.toml) and state the companion keeps (state.json), and how Chatmon writes every file
it keeps: readable by you alone from the moment it exists, on the disk before it replaces the old one."""

from __future__ import annotations

import copy
import json
import math
import os
import time
import tomllib
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from . import paths

DEFAULTS: dict[str, Any] = {
    "name": "",
    "size": 120,
    "walk": True,
    "sleep_after_minutes": 10,
    "companion": "penguin",
    "bubble_style": "match",
    "bubble_effects": True,
    "ai": {"brain": "auto", "timeout_seconds": 180, "brains": {}},
    "agents": {"show_replies": False},
    "updates": {"check": True},
    "chats": {"keep": True, "context_tokens": 48000, "instructions": ""},
    "breaks": {"remind": True, "every_minutes": 60, "snooze_minutes": 10},
    "focus": {"minutes": 25, "tell_when_done": True},
    "accessibility": {"read_aloud": True},
    "heads_up": {
        "battery_low": 20,
        "battery_critical": 10,
        "disk_full_percent": 90,
        "updates": True,
        "updates_every_hours": 6,
    },
}

TEMPLATE = """\
# Chatmon settings. Most of these are in Settings (the menu's "Settings…"),
# and what you set there wins over this file. Save this file, then pick
# "Reload settings file" from your
# chatmon's menu (right-click it), or restart it.

# What your companion is called. Empty: it asks the first time it runs.
name = ""

# Height of your chatmon on screen, in pixels.
size = 120

# Wander along the bottom of the screen.
walk = true

# Fall asleep after this many minutes without any attention (0: never).
sleep_after_minutes = 10

# Which chatmon it is: "penguin" (the electric penguin), "fire-red-panda",
# "ghost-rabbit", "fairy-axolotl" or "leaf-pangolin". The menu's "Companion"
# overrides this.
companion = "penguin"

# How its chat bubbles look: "match" (the companion's own style), or always
# "electric" (navy glass, crackling cyan edge), "fire" (ember edge, low flames
# along the top), "ghost" (frosted, violet mist), "fairy" (blush opal, glints),
# "leaf" (ivy, and a caterpillar crawling along it) or "plain" (your desktop's
# own colours). The menu's "Bubble style" overrides this.
bubble_style = "match"

# Animate the bubbles' edges. false keeps the style but holds it still.
bubble_effects = true

[ai]
# Which brain answers your questions. "auto" uses the first AI command-line
# tool you're signed in to (claude, codex, gemini, muse, grok, copilot) or a
# model server running on this computer (ollama, lmstudio, llamacpp, vllm).
# APIs are billed per question, so "auto" never picks one: name it here or pick
# it from the menu (anthropic-api, openai-api, gemini-api, xai-api, meta-api,
# mistral-api, deepseek-api, groq-api, together-api, fireworks-api,
# cerebras-api, perplexity-api, openrouter, bedrock-api), or one of your own.
brain = "auto"
# How long a brain may go without sending anything before Chatmon gives up on
# it, in seconds. An answer that keeps arriving is never cut off.
timeout_seconds = 180

# Add your own brain, or change a built-in one by using its name.
#
# A command brain gets the question on stdin, or in a file whose path replaces
# a "{prompt_file}" argument, or as a "{prompt}" argument itself; it answers on
# stdout, or in the file named by an "{output_file}" argument. It's given only
# what programs need of your environment (PATH, your folders, locale, proxy),
# never your other keys: name the variables it signs in with in "env" ("*" at
# the end of a name stands for any ending):
#
# [ai.brains.my-tool]
# type = "command"
# command = ["my-tool", "--quiet"]
# env = ["MY_TOOL_TOKEN", "MY_TOOL_*"]
#
# An HTTP brain speaks the Anthropic Messages API (type = "anthropic"),
# OpenAI's Responses API (type = "responses") or the OpenAI Chat Completions API
# (type = "openai") that most providers accept. Keys come from environment
# variables, or from your system's keychain once you save one in Settings;
# "${VAR}" in a header is read from the environment too. Plain HTTP is refused
# except to this computer. Answers stream in as they're written; stream = false
# turns that off for a server that can't.
#
# [ai.brains.my-provider]
# type = "openai"
# url = "https://api.example.com/v1"
# model = "some-model"
# api_key_env = "MY_PROVIDER_API_KEY"
#
# Azure OpenAI / AI Foundry (model is your deployment's name):
#
# [ai.brains.azure]
# type = "responses"
# url = "https://YOUR-RESOURCE.openai.azure.com/openai/v1"
# model = "your-deployment"
# api_key_env = "AZURE_OPENAI_API_KEY"
#
# Model, effort and thinking are easiest to change from the menu (Brain, then
# Model, Effort and Thinking for the brain in use); what you pick there is
# remembered for each brain. To set them here instead, or for your own brains:
#
# [ai.brains.openai-api]
# model = "gpt-6.1-terra"
# effort = "medium"        # how hard it thinks; "" leaves it to the model
# thinking = "off"         # "auto" (the model's own default), "on" or "off"
#
# Your own brain can offer the same choices in the menu:
#
# [ai.brains.my-provider]
# models = ["fast-model", "smart-model"]
# efforts = ["low", "medium", "high"]           # sent as reasoning_effort
# thinking_fields = { off = { "reasoning_effort" = "none" } }
#
# and a command brain takes them as arguments ("{model}", "{effort}"):
#
# [ai.brains.my-tool]
# model_args = ["--model", "{model}"]
# effort_args = ["--effort", "{effort}"]
# efforts = ["low", "high"]
# thinking_args = { off = ["--no-thinking"] }

[agents]
# Show the last words of an agent's reply when it finishes. Off by default:
# replies can hold code or secrets you'd rather not have on screen.
show_replies = false

[chats]
# Keep your chats on this computer, so you can come back to one and carry on
# (the menu's "Chats", or "History" in the ask box). They're readable by you
# alone, and "Clear chat history" deletes them. Text you attach is kept with
# its chat, so you can ask about it later (it goes only to the brain you gave
# it to); pictures and PDFs only by name. The menu's "Keep chat history"
# overrides this.
keep = true
# How much of a chat a brain is sent with each question, at most, in tokens
# (about 3.5 characters each). Past this, the earlier part goes as a summary,
# with the turns that bear on your question word for word. More costs more
# with an API. A model's own limit always comes first.
context_tokens = 48000
# Your instructions for every chat, sent with every question to every brain:
# how to answer, what you do, what language. Settings has these too.
instructions = ""

[updates]
# Look for a new Chatmon once a day, download it, check it's the real one, and
# ask before installing it. Only the request for the latest release is sent, to
# GitHub. The menu's "Help & updates" overrides this.
check = true

[breaks]
# Nudge you to take a break after this many minutes at the screen.
remind = true
every_minutes = 60
snooze_minutes = 10

[focus]
minutes = 25
# Say when a focus session ends.
tell_when_done = true

[accessibility]
# With a screen reader running (Orca, VoiceOver, NVDA, JAWS, Narrator), have it
# read out each bubble and answer, and what to type to press a bubble's buttons.
read_aloud = true

[heads_up]
battery_low = 20          # percent; 0 turns battery warnings off
battery_critical = 10
disk_full_percent = 90    # 0 turns disk warnings off
updates = true            # say when system updates are waiting
updates_every_hours = 6
"""


def private(path: Path) -> None:
    """Readable by you alone (settings can hold API keys)."""
    if os.name == "posix":
        os.chmod(path, 0o600)


def private_dir(path: Path) -> Path:
    """One of Chatmon's folders, open to you alone (0700): made so, and made so again if it wasn't."""
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        os.chmod(path, 0o700)
    return path


def write_private(path: Path, text: str) -> None:
    """Replace `path` with `text`, all at once. The new file is created readable by you alone (never at the umask's
    mode first and narrowed afterwards), and it's on the disk before it takes the old one's place: a crash or a
    power cut leaves the old file or the new one, never half of one."""
    private_dir(path.parent)
    tmp = path.with_name(path.name + ".tmp")
    tmp.unlink(missing_ok=True)  # one left from before, at whatever mode it was made: never written through
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(tmp, flags, 0o600)
    try:
        if os.name == "posix":
            os.fchmod(fd, 0o600)  # the umask can take bits away from 0600, never add them; this puts back any it took
        data = memoryview(text.encode("utf-8"))
        while data:
            data = data[os.write(fd, data):]
        os.fsync(fd)
    except BaseException:
        os.close(fd)
        tmp.unlink(missing_ok=True)
        raise
    os.close(fd)
    os.replace(tmp, path)
    if os.name == "posix":  # the rename itself, on the disk too
        try:
            folder = os.open(path.parent, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(folder)
        except OSError:
            pass
        finally:
            os.close(folder)


BAD = ".bad-"  # a damaged file is kept as <name>.bad-<time>, for you (or a bug report) to look at
BACKUP = ".bak"  # the last copy of a file that was read and found good


def read_kept(path: Path, valid: Callable[[Any], bool], limit: int = 64 * 2**20) -> tuple[Any, str | None]:
    """The JSON kept in `path` (None: there's none yet), and a sentence for you if it had to be recovered.

    A file that can't be read, isn't JSON, is bigger than `limit` or isn't `valid` is never written over: it's kept
    as <name>.bad-<time>, and the last good copy (<name>.bak, made each time the file is read and found good) is used
    instead. A missing file is a first run (or one you deleted), never a reason to bring the backup back."""
    try:
        raw = path.read_bytes() if path.stat().st_size <= limit else None
    except FileNotFoundError:
        return None, None
    except OSError:
        raw = None
    data = _parsed(raw, valid)
    backup = path.with_name(path.name + BACKUP)
    if data is not None:
        try:
            if not backup.exists() or backup.read_bytes() != raw:
                write_private(backup, raw.decode("utf-8"))
        except OSError:
            pass  # no backup this time: the file itself is fine
        return data, None
    kept = _set_aside(path)
    where = f"kept it as {kept.name}" if kept else "couldn't even move it aside"
    try:
        good = _parsed(backup.read_bytes(), valid)
        when = datetime.fromtimestamp(backup.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    except OSError:
        good = None
    if good is not None:
        return good, f"{path.name} was damaged, so I {where} and went back to the copy from {when}."
    return None, f"{path.name} was damaged, so I {where} and started it afresh."


def _parsed(raw: bytes | None, valid: Callable[[Any], bool]) -> Any:
    if raw is None:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None
    return data if valid(data) else None


def _set_aside(path: Path) -> Path | None:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for n in range(100):
        kept = path.with_name(f"{path.name}{BAD}{stamp}" + (f"-{n}" if n else ""))
        if kept.exists():
            continue
        try:
            os.replace(path, kept)
        except OSError:
            return None
        return kept
    return None


def merge(base: dict, override: dict) -> dict:
    """`base` with `override` laid over it, recursing into tables."""
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
        else:
            out[key] = value
    return out


# The range each number may take: the Settings window's own (settingswin.py), and Chatmon's limits where it has none
# (a timer can't wait longer than about 24 days, so updates_every_hours stops at a week).
RANGES: dict[str, tuple[int, int]] = {
    "size": (60, 400),
    "sleep_after_minutes": (0, 240),
    "ai.timeout_seconds": (10, 1800),
    "chats.context_tokens": (2_000, 2_000_000),
    "breaks.every_minutes": (5, 480),
    "breaks.snooze_minutes": (1, 120),
    "focus.minutes": (1, 240),
    "heads_up.battery_low": (0, 90),
    "heads_up.battery_critical": (0, 90),
    "heads_up.disk_full_percent": (0, 99),
    "heads_up.updates_every_hours": (1, 168),
}
_TRUE = {"true", "yes", "on", "1"}
_FALSE = {"false", "no", "off", "0"}


def coerce(config: dict, defaults: dict | None = None) -> tuple[dict, list[str]]:
    """`config` with each setting Chatmon knows made the type of its default and kept in its range, and a sentence
    for each one that wasn't (per setting: one bad value never costs the others). Tables Chatmon doesn't know the
    keys of (your own brains) are passed on as they are, each brain checked to be a table."""
    problems: list[str] = []
    out = _coerce(config, DEFAULTS if defaults is None else defaults, "", problems)
    brains = out.get("ai", {}).get("brains")
    if isinstance(brains, dict):
        for name in [n for n, spec in brains.items() if not isinstance(spec, dict)]:
            problems.append(f"ai.brains.{name} isn't a table, so it's left out")
            del brains[name]
    return out, problems


def _coerce(config: dict, defaults: dict, prefix: str, problems: list[str]) -> dict:
    out = dict(config)
    for key, default in defaults.items():
        if key not in config:
            out[key] = copy.deepcopy(default)
            continue
        name, value = prefix + key, config[key]
        if isinstance(default, dict):
            if isinstance(value, dict):
                out[key] = _coerce(value, default, name + ".", problems)
            else:
                problems.append(f"{name} should be a table, so it's the default for now")
                out[key] = copy.deepcopy(default)
        else:
            out[key] = _value(name, value, default, problems)
    return out


def _value(name: str, value: Any, default: Any, problems: list[str]) -> Any:
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        word = str(value).strip().lower() if isinstance(value, (str, int)) else ""
        if word in _TRUE | _FALSE:
            return word in _TRUE
        problems.append(f"{name} should be true or false, so it's {str(default).lower()} for now")
        return default
    if isinstance(default, int):
        number = _number(value)
        if number is None:
            problems.append(f"{name} should be a number, so it's {default} for now")
            return default
        low, high = RANGES.get(name, (-(2**31), 2**31 - 1))
        if not low <= number <= high:
            kept = min(max(number, low), high)
            problems.append(f"{name} can be {low} to {high}, so it's {kept} for now")
            return kept
        return number
    if isinstance(default, str):
        if isinstance(value, str):
            return value
        problems.append(f"{name} should be text in quotes, so it's the default for now")
        return default
    return value


def _number(value: Any) -> int | None:
    """A whole number from a setting: 60, 60.0 or "60" (TOML keeps quotes as text); None if it isn't one."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            value = float(value.strip())
        except ValueError:
            return None
    if isinstance(value, float) and math.isfinite(value):
        return round(value)
    return None


def load_config(path: Path | None = None) -> tuple[dict, str | None]:
    """The settings, and a message if the file could not be read or some of its values were wrong."""
    path = path or paths.config_file()
    private_dir(path.parent)
    if not path.exists():
        write_private(path, TEMPLATE)
    try:
        user = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        return copy.deepcopy(DEFAULTS), f"{path.name}: {exc}"
    config, problems = coerce(merge(DEFAULTS, user))
    return config, (f"{path.name}: " + "; ".join(problems) + ".") if problems else None


class State:
    """Small JSON file for what the companion remembers between runs. `problem`: a sentence for you when the file
    was damaged and had to be recovered (read_kept)."""

    def __init__(self, path: Path, data: dict, problem: str | None = None):
        self.path = path
        self.data = data
        self.problem = problem

    @classmethod
    def load(cls, path: Path | None = None) -> "State":
        path = path or paths.state_file()
        data, problem = read_kept(path, lambda d: isinstance(d, dict))
        return cls(path, data or {}, problem)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def save(self) -> None:
        write_private(self.path, json.dumps(self.data, indent=1))
