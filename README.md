# Chatmon

[![GitHub stars](https://img.shields.io/github/stars/RandyNorthrup/chatmon?style=flat&logo=github)](https://github.com/RandyNorthrup/chatmon/stargazers)
[![Downloads](https://img.shields.io/github/downloads/RandyNorthrup/chatmon/total?style=flat&logo=github)](https://github.com/RandyNorthrup/chatmon/releases)
[![Latest release](https://img.shields.io/github/v/release/RandyNorthrup/chatmon?style=flat)](https://github.com/RandyNorthrup/chatmon/releases/latest)
[![CI](https://github.com/RandyNorthrup/chatmon/actions/workflows/ci.yml/badge.svg)](https://github.com/RandyNorthrup/chatmon/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/github/license/RandyNorthrup/chatmon?style=flat)](LICENSE)

A chatmon is a little creature that lives along the bottom of your screen: an
electric penguin, a fire red panda, a ghost rabbit, a fairy axolotl or a leaf
pangolin. It wanders about, naps when you ignore it, peeks out from behind the
taskbar, and helps:

- **Ask it anything.** Click it and type. It answers with the AI you already
  use: an AI command-line tool you're signed in to (Claude Code, Codex, Gemini
  CLI, Muse Code, Grok, GitHub Copilot CLI), a model server on your own
  computer (Ollama, LM Studio, llama.cpp, vLLM), or an API: Anthropic, OpenAI,
  Gemini, xAI, Meta, Mistral, DeepSeek, Groq, Together, Fireworks, Cerebras,
  Perplexity, OpenRouter, Amazon Bedrock, Azure, or anything else that speaks
  the OpenAI or Anthropic API.
- **Keeps an eye on your coding agents.** It thinks while an agent works,
  charges up on long jobs, flaps for attention when one needs your approval,
  and hops when it's done. It connects to Claude Code, Codex, Gemini CLI, Muse
  Code, Grok, GitHub Copilot CLI, Cursor, Cline, Qwen Code and Devin, and to
  anything else that can run a command.
- **Reminders and timers**, typed the way you'd say them: *remind me in 20m to
  stretch*, *remind me at 3pm to call Sam*, *timer 10 min for the pasta*,
  *focus 50*. No AI needed.
- **Breaks.** A nudge after an hour at the screen; locking the screen for five
  minutes counts as a break.
- **Heads-ups.** A low battery, a disk filling up, system updates waiting.
- **Pick your chatmon.** Right-click it, open **Companion** and choose; it
  changes on the spot, and its chat bubbles change to match.

It runs on Linux, Windows and macOS.

## Install

You need Python 3.11 or newer.

```sh
pipx install git+https://github.com/RandyNorthrup/chatmon
chatmon
```

Without pipx: `python3 -m pip install --user git+https://github.com/RandyNorthrup/chatmon`.
Each [release](https://github.com/RandyNorthrup/chatmon/releases) also has the
wheel, for `pipx install chatmon-<version>-py3-none-any.whl`.
Or run it from a clone, with PyQt6 installed (`python3 -m pip install PyQt6`, or
`sudo apt install python3-pyqt6` on Debian and Ubuntu):

```sh
git clone https://github.com/RandyNorthrup/chatmon
cd chatmon
bin/chatmon          # Windows: py bin\chatmon
```

Agent hooks call `chatmon` by name, so if you run it from a clone, put the
launcher on your PATH: `ln -s "$PWD/bin/chatmon" ~/.local/bin/`.
For battery levels on Windows and macOS, also install `psutil`.

The first time, it asks what it should be called. Right-click it and tick
**Start when I log in** to keep it around.

### Coming from Penguin companion

Chatmon was called Penguin companion until 0.3.0. Quit the old one (right-click,
**Quit**), then swap the package:

```sh
pipx uninstall penguin-companion
pipx install git+https://github.com/RandyNorthrup/chatmon
chatmon
```

The first time it runs, Chatmon moves your settings, name and reminders over
from the `penguin-companion` folders, switches **Start when I log in** to the new
name, and swaps the hooks of any agents you connected for `chatmon` ones (Claude
Code gets the `chatmon` plugin in place of `penguin-companion`). Until then the
old hooks keep working: `penguin-companion` is still installed as another name
for `chatmon`, for this release.

Claude Code and Muse Code can drop the old plugin as soon as the old package is
uninstalled, before Chatmon gets to move it. If either shows unticked under
**AI agents** afterwards, tick it again (your chatmon reminds you on that first
run). From 0.3.0 on, Chatmon keeps its Claude Code marketplace in its own state
folder, so upgrades can't take it away again.

## Using it

| You                              | It                                                       |
| -------------------------------- | -------------------------------------------------------- |
| Click it                         | Opens the ask box (or wakes up, or answers an alert)     |
| Drag it                          | Comes along; let go and it drops back to the taskbar    |
| Right-click it, or the tray icon | The menu: ask, remind, focus timer, reminders, brain, companion, bubble style, AI agents, walk, hide, settings |
| Click the tray icon              | Hides it, or brings it back                              |

Besides questions, the ask box understands *help*, *status* (battery, disks,
reminders), *hide*, *new chat*, and the reminder, timer and focus phrases above.

## The chatmons and their bubbles

**Companion** in the menu swaps the creature at once. Each has the same twelve
animations, does everything the others do, and talks in chat bubbles of its
own:

| Chatmon          | Setting          | Its bubbles                                        |
| ---------------- | ---------------- | -------------------------------------------------- |
| Electric penguin (the default) | `penguin` | **Electric**: navy glass, lightning running round a cyan edge |
| Fire red panda   | `fire-red-panda` | **Fire**: an ember edge with low flames along the top |
| Ghost rabbit (it floats) | `ghost-rabbit` | **Ghost**: frosted, with violet mist drifting round it |
| Fairy axolotl    | `fairy-axolotl`  | **Fairy**: blush opal, with glints and sparkles    |
| Leaf pangolin    | `leaf-pangolin`  | **Leaf**: ivy, with a caterpillar crawling along it |

**Bubble style** starts on **Match companion**, which follows whichever chatmon
you pick. Choose a style by name there (or **Plain**, in your desktop's own
colours) and it stays put whichever chatmon you pick; **Animate bubbles** holds
the edges still. All of it is remembered, and can be set in the settings file
(`companion`, `bubble_style`, `bubble_effects`). A name the settings don't know
is the penguin.

## Brains: what answers your questions

**Automatic** (the default) uses the first of these it finds:

- an AI command-line tool you're signed in to: `claude`, `codex`, `gemini`,
  `muse`, `grok`, `copilot`. It runs in an empty folder of its own with its
  tools off or read-only, so a question can't touch your files;
- a model server running on this computer: Ollama, LM Studio, llama.cpp or
  vLLM, with whichever model it has loaded.

**APIs are billed per question, so Automatic never picks one**, even if its key
is set. Pick it under **Brain** in the menu, or name it in the settings:

| Brain            | Key in                     | Default model                |
| ---------------- | -------------------------- | ---------------------------- |
| `anthropic-api`  | `ANTHROPIC_API_KEY`        | `claude-opus-5-5`            |
| `openai-api`     | `OPENAI_API_KEY`           | `gpt-6.1-sol` (Responses API) |
| `gemini-api`     | `GEMINI_API_KEY`           | `gemini-3.8-flash`           |
| `xai-api`        | `XAI_API_KEY`              | `grok-4.7` (Responses API)   |
| `meta-api`       | `MODEL_API_KEY`            | `muse-spark-1.3`             |
| `mistral-api`    | `MISTRAL_API_KEY`          | `mistral-small-latest`       |
| `deepseek-api`   | `DEEPSEEK_API_KEY`         | `deepseek-v4-pro`            |
| `groq-api`       | `GROQ_API_KEY`             | `openai/gpt-oss-120b`        |
| `together-api`   | `TOGETHER_API_KEY`         | `moonshotai/Kimi-K3`         |
| `fireworks-api`  | `FIREWORKS_API_KEY`        | `accounts/fireworks/models/glm-5p3` |
| `cerebras-api`   | `CEREBRAS_API_KEY`         | `gpt-oss-120b`               |
| `perplexity-api` | `PERPLEXITY_API_KEY`       | `perplexity/sonar`, with web search |
| `openrouter`     | `OPENROUTER_API_KEY`       | `openrouter/auto`            |
| `bedrock-api`    | `AWS_BEARER_TOKEN_BEDROCK` and `AWS_REGION` | `global.openai.gpt-6.1-sol` |

Change any model, or add your own brain (any command that reads a question and
prints an answer, or any endpoint for the Anthropic Messages, OpenAI Responses
or OpenAI Chat Completions API, Azure included) in the settings file, which
has examples. The model names above were current in October 2026.

The Claude Code and Grok brains have been tried; the others follow their
tools' documented options.

## AI agents: let them tell your chatmon what they're doing

Right-click your chatmon, open **AI agents**, and tick the ones you use; or from
a terminal:

```sh
chatmon hooks                 # what's here and what's connected
chatmon hooks connect claude  # or: codex, gemini, muse, grok, copilot, cursor, cline, qwen, devin, all
chatmon hooks disconnect claude
chatmon hooks show cursor     # how to do it by hand
```

| Agent              | How it's connected                                                    |
| ------------------ | --------------------------------------------------------------------- |
| Claude Code        | A Claude Code plugin, installed with `claude plugin`                  |
| Codex              | Its `notify` program, in `~/.codex/config.toml`                       |
| Gemini CLI         | Hooks in `~/.gemini/settings.json`                                    |
| Muse Code          | A Muse plugin, installed and approved with `muse plugins`             |
| Grok               | Its own file, `~/.grok/hooks/chatmon.json`                            |
| GitHub Copilot CLI | Its own file, `~/.copilot/hooks/chatmon.json`                         |
| Cursor             | Hooks in `~/.cursor/hooks.json`                                       |
| Cline              | Hook scripts in `~/Documents/Cline/Hooks` (turn on Cline's "Enable Hooks") |
| Qwen Code          | Hooks in `~/.qwen/settings.json`                                      |
| Devin CLI          | Hooks in `~/.config/devin/config.json`                                |

In Claude Code you can also add the plugin yourself:
`/plugin install chatmon --marketplace RandyNorthrup/chatmon`.

For anything else (Aider, Kiro, OpenCode, Amp, a CI script), have it run
`chatmon notify working|needs-you|done|success|error --source NAME`;
`chatmon hooks show any` has the details.

| Event       | Your chatmon                                                       |
| ----------- | ------------------------------------------------------------------ |
| `working`   | Thinks; after a minute, charges up                                 |
| `needs-you` | Flaps and says what the agent is waiting for, until you click OK   |
| `done`      | Hops and says it finished                                          |
| `success`   | Fires a little beam                                                |
| `error`     | Says something went wrong                                          |

`chatmon say TEXT` and `chatmon remind in 10m to stretch`
work from any script too.

## Privacy and security

- **Nothing is collected.** No telemetry, no accounts, no network calls of its
  own. The only thing that leaves your computer is a question you type, sent
  to the brain you chose. Conversations live in memory and are gone when
  Chatmon quits or after 15 minutes idle.
- **Agents' replies stay off the screen** unless you set
  `agents.show_replies = true`; they can hold code or secrets you'd rather not
  have on show during a screen share. Your chatmon shows what an agent is
  waiting for, and never your prompts.
- **Connecting an agent is always your choice.** Each connection backs up the
  file it changes first (`<file>.chatmon-backup-<time>`), touches only entries
  that run `chatmon` (or `penguin-companion`, its old name), refuses to edit a file it can't parse, never
  replaces something of yours (Codex allows only one `notify` program, Cline
  one script per event), and comes out again with `hooks disconnect`.
- **Hooks can't get in an agent's way.** `notify` prints nothing, always
  succeeds, finishes within about a second even if the agent never closes its
  input, and returns at once if Chatmon isn't running. The AI tools Chatmon runs
  for your own questions carry `CHATMON_INTERNAL=1`, so their hooks don't make
  it react to itself.
- **Only you can talk to it.** Hooks reach it through a local socket (a named
  pipe on Windows) open to your user account alone; messages are size-limited.
- **Keys** are read from environment variables (or `${VAR}` in a header) and
  are never written to logs. API keys only travel over HTTPS; plain HTTP is
  allowed only to a server on this computer. Settings and state files are
  readable by you alone.
- **Links** in answers open in your browser only if they're web or mail
  links.

Found a security problem? Please open a private
[security advisory](https://github.com/RandyNorthrup/chatmon/security/advisories/new).

## Settings

`config.toml`, created on first run with every setting explained: the name,
size, walking, how soon it naps, the companion and its bubble style, brains,
whether agents' replies show, break and
focus lengths, and heads-up thresholds. **Edit settings…** in the menu opens it;
**Reload settings** applies it. It lives in `~/.config/chatmon/` on Linux,
`~/Library/Application Support/chatmon/` on macOS and `%APPDATA%\chatmon\` on
Windows. `state.json` (in `~/.local/state/chatmon/` on Linux, next to the
settings elsewhere) keeps the name, reminders, the chatmon you picked and its
spot on the screen.

## How it's put together

Your chatmon and its message bubbles are drawn on one see-through surface over
the screen, so moving them never moves a window: no lag, no trails. Clicks go
through it everywhere except the chatmon and what it's showing you.

- **Wayland** (Hyprland, KDE Plasma, Sway, niri and the other desktops with the
  layer-shell protocol): the surface is a layer-shell overlay, above panels, with
  an input region for the clicks (its layer is named `chatmon`, for compositor
rules). Everything the chatmon shows is drawn on it:
  its bubbles, its menus and the ask box, so none of it is an XWayland window
  that the desktop would put underneath, decorate with its borders, or keep the
  keyboard from. The overlay takes the keyboard only while the ask box is open,
  and reads it with libxkbcommon, so your layout, dead keys and compose work;
  input methods (fcitx5, IBus) work through the compositor's text-input
  protocol, and copy, cut, paste and middle-click paste through its clipboard
  and primary selection. Qt can't make a layer-shell surface, so Chatmon
  talks to the compositor itself, with a small Wayland client of its own (no
  extra libraries).
- **X11**, and **GNOME on Wayland** (no layer-shell there; it runs through
  XWayland, whose X input shapes GNOME reads): a window over the screen with an
  X input shape. The ask box is a window of its own.
- **Windows and macOS**: a window over the screen that takes the mouse only
  while it's over the chatmon.

`CHATMON_STAGE=window` keeps the X11 way on a Wayland desktop, and
`CHATMON_DEBUG=1` logs the overlay's keyboard focus to the terminal,
should either ever be needed.

| File                              | What                                                   |
| --------------------------------- | ------------------------------------------------------ |
| `chatmon/behavior.py`   | What it does from moment to moment (no Qt; tested)     |
| `chatmon/penguin.py`    | The stage: drawing, the mouse, and the ask box when it's on the overlay |
| `chatmon/layer.py`      | The stage's Wayland overlay (layer shell)              |
| `chatmon/wayland.py`    | The Wayland wire protocol, just enough for the overlay |
| `chatmon/xkb.py`        | The keyboard on the overlay, through libxkbcommon      |
| `chatmon/stagemenu.py`  | Menus drawn on the stage                               |
| `chatmon/clickthrough.py` | Clicks through the stage window (X11, Windows, macOS) |
| `chatmon/companions.py` | The companions you can pick, and where each one's strips are |
| `chatmon/sprites.py`    | One companion's animation strips, cut into frames for the screen |
| `chatmon/bubble.py`     | Message bubbles and the ask box                        |
| `chatmon/app.py`        | Ties it together: menu, tray, reminders, heads-ups, hooks |
| `chatmon/brains.py`     | The AI brains                                          |
| `chatmon/agents.py`     | Connecting coding agents                               |
| `chatmon/integrations/` | The Claude Code plugin                                 |
| `art/`                            | The characters, their image prompts, and the tools that cut and check the strips ([art/README.md](art/README.md)) |

The overlay is tested on Hyprland 0.57; KDE Plasma 6.4 (Wayland) was tested
with the window, before the overlay. CI runs the tests, including a headless run
of the whole app and the overlay against a pretend compositor, on Linux, Windows
and macOS with Python 3.11 and 3.15.

```sh
python3 -m pip install pytest ruff
python3 -m pytest && ruff check .
```

## License

MIT, for the code and the art. See [LICENSE](LICENSE).
