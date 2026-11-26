"""Settings you edit (config.toml) and state the companion keeps (state.json), and how Chatmon writes every file
it keeps: readable by you alone from the moment it exists, on the disk before it replaces the old one."""

from __future__ import annotations

import copy
import json
import logging
import math
import os
import sys
import time
import tomllib
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from . import paths
from .i18n import _

logger = logging.getLogger(__name__)

DEFAULTS: dict[str, Any] = {
    "name": "",
    "language": "",  # i18n.SETTING: a language code ("de", "pt_BR"); empty follows the system
    "size": 120,
    "walk": True,
    "sleep_after_minutes": 10,
    "companion": "penguin",
    "bubble_style": "match",
    "bubble_effects": True,
    # Opens the ask box from anywhere. On macOS Qt's Ctrl is Command, and Command+Option+Space is Finder's search.
    "hotkey": "Ctrl+Shift+Space" if sys.platform == "darwin" else "Ctrl+Alt+Space",
    "follow_screen": False,
    "ai": {"brain": "auto", "timeout_seconds": 180, "brains": {}},
    "agents": {"show_replies": False},
    "updates": {"check": True},
    "chats": {"keep": True, "context_tokens": 48000, "instructions": ""},
    "breaks": {"remind": True, "every_minutes": 60, "snooze_minutes": 10},
    "reminders": {"snooze_minutes": 10},
    "focus": {"minutes": 25, "tell_when_done": True},
    "accessibility": {"read_aloud": True, "text_scale": 100, "bubble_time": "normal", "reduced_motion": "system", "accessible_ask_box": "auto",
                      "magnifier_follows": True, "speech_fallback": False},
    # Sounds for alerts only, until you turn others on; one switch turns them all off (owner, 2026-11-14).
    "sound": {
        "enabled": True,
        "volume": 70,
        "cues": {"needs-you": True, "reminder": True, "focus-done": True, "done": False, "success": False, "error": False, "pop": False},
    },
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

# The language Chatmon speaks: a code such as "de" or "pt_BR". Empty: your system's.
language = ""

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

# A key combination that opens the ask box from anywhere. Left out, it's
# "Ctrl+Alt+Space" ("Ctrl+Shift+Space" on macOS, where Ctrl is Command); "" for none.
# hotkey = "Ctrl+Alt+Space"

# Follow the pointer to another monitor.
follow_screen = false

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

[reminders]
# How long a reminder's own Snooze puts it off, in minutes (breaks have theirs).
snooze_minutes = 10

[focus]
minutes = 25
# Say when a focus session ends.
tell_when_done = true

[accessibility]
# With a screen reader running (Orca, VoiceOver, NVDA, JAWS, Narrator), have it
# read out each bubble and answer, and what to type to press a bubble's buttons.
read_aloud = true
# Text size in bubbles and the ask box, in percent (75 to 300), on top of your
# desktop's own font size.
text_scale = 100
# How long bubbles stay: "normal", "longer", "much longer" or "until closed".
bubble_time = "normal"
# Less movement (no walking, no animated edges, no fades): "system" follows
# your desktop's setting, "on" or "off" decide.
reduced_motion = "system"
# The ask box as a window of its own, which screen readers find, where Chatmon
# draws its own overlay (Wayland): "auto" (when a screen reader runs), "on", "off".
accessible_ask_box = "auto"
# Windows: Magnifier, when it's running, goes to each bubble as it shows.
magnifier_follows = true
# macOS: say announcements in macOS's own voice while Chatmon is in the background
# (VoiceOver would otherwise hold them until you come back to Chatmon).
speech_fallback = false

[sound]
# One switch for every sound.
enabled = true
volume = 70               # percent
# Which sounds play. Alerts are on; the rest are off until you turn them on.
# None play during Do Not Disturb, Focus, a full-screen app or a focus session.
[sound.cues]
needs-you = true
reminder = true
focus-done = true
done = false
success = false
error = false
pop = false               # every other bubble

[heads_up]
battery_low = 20          # percent; 0 turns battery warnings off
battery_critical = 10
disk_full_percent = 90    # 0 turns disk warnings off
updates = true            # say when system updates are waiting
updates_every_hours = 6
"""


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
        if sys.platform != "win32" and hasattr(os, "fchmod"):  # POSIX (mypy reads the platform; a test pretending to be Linux on Windows has no fchmod before 3.13)
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
        except OSError as exc:
            logger.debug("couldn't open %s to sync the rename: %s", path.parent, exc)
            return
        try:
            os.fsync(folder)
        except OSError as exc:
            logger.debug("couldn't sync the rename in %s: %s", path.parent, exc)
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
    except OSError as exc:
        logger.debug("couldn't read %s: %s", path, exc)
        raw = None
    data = _parsed(raw, valid)
    backup = path.with_name(path.name + BACKUP)
    if data is not None:
        try:
            if raw is not None and (not backup.exists() or backup.read_bytes() != raw):  # raw is there whenever data is
                write_private(backup, raw.decode("utf-8"))
        except OSError as exc:
            logger.debug("couldn't keep a backup of %s: %s", path, exc)  # no backup this time: the file itself is fine
        return data, None
    kept = _set_aside(path)
    try:
        good = _parsed(backup.read_bytes(), valid)
        when = datetime.fromtimestamp(backup.stat().st_mtime).strftime("%Y-%m-%d %H:%M")  # noqa: DTZ006 - the copy's time on your clock
    except OSError as exc:
        logger.debug("couldn't go back to %s: %s", backup, exc)
        good, when = None, ""
    if good is not None:
        if kept:
            said = _("{file} was damaged, so I kept it as {kept} and went back to the copy from {when}.")
        else:
            said = _("{file} was damaged, so I couldn't even move it aside and went back to the copy from {when}.")
        return good, said.format(file=path.name, kept=kept.name if kept else "", when=when)
    if kept:
        said = _("{file} was damaged, so I kept it as {kept} and started it afresh.")
    else:
        said = _("{file} was damaged, so I couldn't even move it aside and started it afresh.")
    return None, said.format(file=path.name, kept=kept.name if kept else "")


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
    "reminders.snooze_minutes": (1, 120),
    "focus.minutes": (1, 240),
    "accessibility.text_scale": (75, 300),
    "sound.volume": (0, 100),
    "heads_up.battery_low": (0, 90),
    "heads_up.battery_critical": (0, 90),
    "heads_up.disk_full_percent": (0, 99),
    "heads_up.updates_every_hours": (1, 168),
}
# The words a setting may be (anything else is the default, and said).
CHOICES: dict[str, tuple[str, ...]] = {
    "accessibility.bubble_time": ("normal", "longer", "much longer", "until closed"),
    "accessibility.reduced_motion": ("system", "on", "off"),
    "accessibility.accessible_ask_box": ("auto", "on", "off"),
}
_TRUE = {"true", "yes", "on", "1"}
_FALSE = {"false", "no", "off", "0"}


def coerce(config: dict, defaults: dict | None = None) -> tuple[dict, list[str]]:
    """`config` with each setting Chatmon knows made the type of its default and kept in its range, and a sentence
    for each one that wasn't (per setting: one bad value never costs the others). Tables Chatmon doesn't know the
    keys of (your own brains) are passed on as they are, each brain checked to be a table."""
    problems: list[str] = []
    out = _coerce(config, DEFAULTS if defaults is None else defaults, "", problems)
    heads_up = out.get("heads_up")
    if isinstance(heads_up, dict) and 0 < heads_up.get("battery_low", 0) <= heads_up.get("battery_critical", 0):
        heads_up["battery_critical"] = heads_up["battery_low"] - 1  # "almost empty" stays below "low"
        # Translators: heads_up.battery_critical and battery_low are names in the settings file, as they are.
        problems.append(_("heads_up.battery_critical should be below battery_low, so it's {value} for now").format(value=heads_up["battery_critical"]))
    brains = out.get("ai", {}).get("brains")
    if isinstance(brains, dict):
        for name in [n for n, spec in brains.items() if not isinstance(spec, dict)]:
            # Translators: {setting} is a name in the settings file (ai.brains.my-tool); a table is TOML's [section].
            problems.append(_("{setting} isn't a table, so it's left out").format(setting=f"ai.brains.{name}"))
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
                problems.append(_("{setting} should be a table, so it's the default for now").format(setting=name))
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
        # Translators: "true" and "false" are what to write in the settings file, as they are.
        problems.append(_("{setting} should be true or false, so it's {value} for now").format(setting=name, value=str(default).lower()))
        return default
    if isinstance(default, int):
        number = _number(value)
        if number is None:
            problems.append(_("{setting} should be a number, so it's {value} for now").format(setting=name, value=default))
            return default
        low, high = RANGES.get(name, (-(2**31), 2**31 - 1))
        if not low <= number <= high:
            kept = min(max(number, low), high)
            problems.append(_("{setting} can be {low} to {high}, so it's {value} for now").format(setting=name, low=low, high=high, value=kept))
            return kept
        return number
    if isinstance(default, str):
        if isinstance(value, str) and (name not in CHOICES or value in CHOICES[name]):
            return value
        if isinstance(value, str):
            # Translators: {choices} are the words the settings file takes, quoted, as they are.
            choices = ", ".join(repr(c) for c in CHOICES[name])
            problems.append(_("{setting} should be {choices}, so it's {value} for now").format(setting=name, choices=choices, value=repr(default)))
        else:
            problems.append(_("{setting} should be text in quotes, so it's the default for now").format(setting=name))
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


def read_config(path: Path | None = None) -> tuple[dict, list[str], str | None]:
    """The settings; a sentence for each value that was wrong (that setting is its default, the rest apply); and why
    the file couldn't be read at all (then every setting is its default), or None."""
    path = path or paths.config_file()
    private_dir(path.parent)
    if not path.exists():
        write_private(path, TEMPLATE)
    try:
        user = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        return copy.deepcopy(DEFAULTS), [], f"{path.name}: {exc}"
    config, problems = coerce(merge(DEFAULTS, user))
    return config, problems, None


def load_config(path: Path | None = None) -> tuple[dict, str | None]:
    """The settings, and a message if the file could not be read or some of its values were wrong."""
    config, problems, unreadable = read_config(path)
    if unreadable:
        return config, unreadable
    return config, (f"{(path or paths.config_file()).name}: " + "; ".join(problems) + ".") if problems else None


class State:
    """Small JSON file for what the companion remembers between runs. `problem`: a sentence for you when the file
    was damaged and had to be recovered (read_kept)."""

    def __init__(self, path: Path, data: dict, problem: str | None = None):
        self.path = path
        self.data = data
        self.problem = problem

    @classmethod
    def load(cls, path: Path | None = None) -> State:
        path = path or paths.state_file()
        data, problem = read_kept(path, lambda d: isinstance(d, dict))
        return cls(path, data or {}, problem)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def save(self) -> None:
        write_private(self.path, json.dumps(self.data, indent=1))
