# Penguin companion

An electric penguin that lives along the bottom of your screen. It wanders
about, naps when you ignore it, peeks out from behind the taskbar, and helps:

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
- **Pick your companion.** The penguin has four siblings: a fire red panda, a
  ghost rabbit, a fairy axolotl and a leaf pangolin. Right-click it, open
  **Companion** and choose; it changes on the spot, and its chat bubbles
  change to match.

It runs on Linux, Windows and macOS.

## Install

You need Python 3.11 or newer.

```sh
pipx install git+https://github.com/RandyNorthrup/penguin-companion
penguin-companion
```

Without pipx: `python3 -m pip install --user git+https://github.com/RandyNorthrup/penguin-companion`.
Or run it from a clone, with PyQt6 installed (`python3 -m pip install PyQt6`, or
`sudo apt install python3-pyqt6` on Debian and Ubuntu):

```sh
git clone https://github.com/RandyNorthrup/penguin-companion
cd penguin-companion
./penguin-companion          # Windows: py penguin-companion
```

Agent hooks call `penguin-companion` by name, so if you run it from a clone,
put the launcher on your PATH: `ln -s "$PWD/penguin-companion" ~/.local/bin/`.
For battery levels on Windows and macOS, also install `psutil`.

The first time, it asks what it should be called. Right-click it and tick
**Start when I log in** to keep it around.

## Using it

| You                              | It                                                       |
| -------------------------------- | -------------------------------------------------------- |
| Click it                         | Opens the ask box (or wakes up, or answers an alert)     |
| Drag it                          | Comes along; let go and it drops back to the taskbar    |
| Right-click it, or the tray icon | The menu: ask, remind, focus timer, reminders, brain, companion, bubble style, AI agents, walk, hide, settings |
| Click the tray icon              | Hides it, or brings it back                              |

Besides questions, the ask box understands *help*, *status* (battery, disks,
reminders), *hide*, *new chat*, and the reminder, timer and focus phrases above.

## Companions and bubbles

**Companion** in the menu swaps the creature at once: the electric penguin
(the default), the fire red panda, the ghost rabbit (it floats), the fairy
axolotl or the leaf pangolin. Each has the same twelve animations and does
everything the penguin does. **Bubble style** starts on **Match companion**
(electric for the penguin, fire, ghost, fairy and leaf for the others); pick a
style by name there and it stays whichever companion you choose. Both are
remembered, and both can be set in the settings file (`companion`,
`bubble_style`). A name the settings don't know is the penguin.

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

## AI agents: let them tell the penguin what they're doing

Right-click the penguin, open **AI agents**, and tick the ones you use; or from
a terminal:

```sh
penguin-companion hooks                 # what's here and what's connected
penguin-companion hooks connect claude  # or: codex, gemini, muse, grok, copilot, cursor, cline, qwen, devin, all
penguin-companion hooks disconnect claude
penguin-companion hooks show cursor     # how to do it by hand
```

| Agent              | How it's connected                                                    |
| ------------------ | --------------------------------------------------------------------- |
| Claude Code        | A Claude Code plugin, installed with `claude plugin`                  |
| Codex              | Its `notify` program, in `~/.codex/config.toml`                       |
| Gemini CLI         | Hooks in `~/.gemini/settings.json`                                    |
| Muse Code          | A Muse plugin, installed and approved with `muse plugins`             |
| Grok               | Its own file, `~/.grok/hooks/penguin-companion.json`                  |
| GitHub Copilot CLI | Its own file, `~/.copilot/hooks/penguin-companion.json`               |
| Cursor             | Hooks in `~/.cursor/hooks.json`                                       |
| Cline              | Hook scripts in `~/Documents/Cline/Hooks` (turn on Cline's "Enable Hooks") |
| Qwen Code          | Hooks in `~/.qwen/settings.json`                                      |
| Devin CLI          | Hooks in `~/.config/devin/config.json`                                |

In Claude Code you can also add the plugin yourself:
`/plugin install penguin-companion --marketplace RandyNorthrup/penguin-companion`.

For anything else (Aider, Kiro, OpenCode, Amp, a CI script), have it run
`penguin-companion notify working|needs-you|done|success|error --source NAME`;
`penguin-companion hooks show any` has the details.

| Event       | The penguin                                                        |
| ----------- | ------------------------------------------------------------------ |
| `working`   | Thinks; after a minute, charges up                                 |
| `needs-you` | Flaps and says what the agent is waiting for, until you click OK   |
| `done`      | Hops and says it finished                                          |
| `success`   | Fires a little beam                                                |
| `error`     | Says something went wrong                                          |

`penguin-companion say TEXT` and `penguin-companion remind in 10m to stretch`
work from any script too.

## Privacy and security

- **Nothing is collected.** No telemetry, no accounts, no network calls of its
  own. The only thing that leaves your computer is a question you type, sent
  to the brain you chose. Conversations live in memory and are gone when the
  penguin quits or after 15 minutes idle.
- **Agents' replies stay off the screen** unless you set
  `agents.show_replies = true`; they can hold code or secrets you'd rather not
  have on show during a screen share. The penguin shows what an agent is
  waiting for, and never your prompts.
- **Connecting an agent is always your choice.** Each connection backs up the
  file it changes first (`<file>.penguin-backup-<time>`), touches only entries
  that run `penguin-companion`, refuses to edit a file it can't parse, never
  replaces something of yours (Codex allows only one `notify` program, Cline
  one script per event), and comes out again with `hooks disconnect`.
- **Hooks can't get in an agent's way.** `notify` prints nothing, always
  succeeds, finishes within about a second even if the agent never closes its
  input, and returns at once if the penguin isn't running. The AI tools the penguin runs for your own
  questions carry `PENGUIN_COMPANION_INTERNAL=1`, so their hooks don't make it
  react to itself.
- **Only you can talk to it.** Hooks reach it through a local socket (a named
  pipe on Windows) open to your user account alone; messages are size-limited.
- **Keys** are read from environment variables (or `${VAR}` in a header) and
  are never written to logs. API keys only travel over HTTPS; plain HTTP is
  allowed only to a server on this computer. Settings and state files are
  readable by you alone.
- **Links** in answers open in your browser only if they're web or mail
  links.

Found a security problem? Please open a private
[security advisory](https://github.com/RandyNorthrup/penguin-companion/security/advisories/new).

## Settings

`config.toml`, created on first run with every setting explained: the name,
size, walking, how soon it naps, the companion and its bubble style, brains,
whether agents' replies show, break and
focus lengths, and heads-up thresholds. **Edit settings…** in the menu opens it;
**Reload settings** applies it. It lives in `~/.config/penguin-companion/` on
Linux, `~/Library/Application Support/penguin-companion/` on macOS and
`%APPDATA%\penguin-companion\` on Windows. Next to it, `state.json` keeps the
name, reminders and the penguin's spot on the screen.

## How it's put together

The penguin and its message bubbles are drawn on one see-through surface over
the screen, so moving them never moves a window: no lag, no trails. Clicks go
through it everywhere except the penguin and what it's showing you.

- **Wayland** (Hyprland, KDE Plasma, Sway, niri and the other desktops with the
  layer-shell protocol): the surface is a layer-shell overlay, above panels, with
  an input region for the clicks. Everything the penguin shows is drawn on it:
  its bubbles, its menus and the ask box, so none of it is an XWayland window
  that the desktop would put underneath, decorate with its borders, or keep the
  keyboard from. The overlay takes the keyboard only while the ask box is open,
  and reads it with libxkbcommon, so your layout, dead keys and compose work;
  input methods (fcitx5, IBus) work through the compositor's text-input
  protocol, and copy, cut, paste and middle-click paste through its clipboard
  and primary selection. Qt can't make a layer-shell surface, so the penguin
  talks to the compositor itself, with a small Wayland client of its own (no
  extra libraries).
- **X11**, and **GNOME on Wayland** (no layer-shell there; it runs through
  XWayland, whose X input shapes GNOME reads): a window over the screen with an
  X input shape. The ask box is a window of its own.
- **Windows and macOS**: a window over the screen that takes the mouse only
  while it's over the penguin.

`PENGUIN_COMPANION_STAGE=window` keeps the X11 way on a Wayland desktop, and
`PENGUIN_COMPANION_DEBUG=1` logs the overlay's keyboard focus to the terminal,
should either ever be needed.

| File                              | What                                                   |
| --------------------------------- | ------------------------------------------------------ |
| `penguin_companion/behavior.py`   | What it does from moment to moment (no Qt; tested)     |
| `penguin_companion/penguin.py`    | The stage: drawing, the mouse, and the ask box when it's on the overlay |
| `penguin_companion/layer.py`      | The stage's Wayland overlay (layer shell)              |
| `penguin_companion/wayland.py`    | The Wayland wire protocol, just enough for the overlay |
| `penguin_companion/xkb.py`        | The keyboard on the overlay, through libxkbcommon      |
| `penguin_companion/stagemenu.py`  | Menus drawn on the stage                               |
| `penguin_companion/clickthrough.py` | Clicks through the stage window (X11, Windows, macOS) |
| `penguin_companion/companions.py` | The companions you can pick, and where each one's strips are |
| `penguin_companion/sprites.py`    | One companion's animation strips, cut into frames for the screen |
| `penguin_companion/bubble.py`     | Message bubbles and the ask box                        |
| `penguin_companion/app.py`        | Ties it together: menu, tray, reminders, heads-ups, hooks |
| `penguin_companion/brains.py`     | The AI brains                                          |
| `penguin_companion/agents.py`     | Connecting coding agents                               |
| `penguin_companion/integrations/` | The Claude Code plugin                                 |
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
