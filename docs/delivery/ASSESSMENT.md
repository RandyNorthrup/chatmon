# Chatmon assessment, 2026-11-14

The brief for the improvement work planned in [ROADMAP.md](ROADMAP.md). Five read-only reviews of `main` at
`5d20c55` (0.9.2 plus two commits) covered:

- rendering and performance;
- security;
- the app core and UX;
- platform integration and accessibility;
- code health, tests and CI.

Line numbers refer to that commit. Every finding has a stable ID, and the milestone that owns it is the prefix. A
**✓** marks a finding the coordinator reproduced or traced in the code; the rest were reported from reading the code
and are re-checked by their milestone before they are changed. **Done when** is the observable outcome a milestone's
acceptance criteria must cover.

Owner decisions taken on 2026-11-14 are recorded in [ROADMAP.md](ROADMAP.md#owner-decisions).

## M0: Companion architecture and app-core fixes (`app.py`, `cli.py`)

- **M0-01 ✓ Messages can be dropped.** `_held` and `_waiting` keep only the last 5 (`app.py:323`, `341`, `445`) and
  are lost on quit. `say()` replaces a bubble with buttons or no timeout ("Focus done", "Delete chat?", the break
  prompt) as soon as any other message arrives (`app.py:318-329`; `penguin.py:446`).
  **Done when:**
  - A Qt-free message queue orders messages by priority: alert, then reminder, then a bubble with buttons or no
    timeout, then a plain bubble.
  - It never drops an alert, a reminder or a bubble with buttons; plain bubbles are merged or dropped first.
  - A visible bubble with buttons is never replaced by a lower-priority message.
  - Every bubble gets a short minimum time on screen.
  - Quiet times and Focus hold the queue.
  - The queue has unit tests in the style of `behavior.py`.
- **M0-02 ✓ A new question cancels the one being answered.** `Asker.ask` calls `cancel()` first
  (`brains.py:964`), `submit` has no busy check (`app.py:934-982`), and the first question vanishes from the transcript
  (`app.py:1055`). The `_asking` tuple, the `_asked` dict and the `_folding` 7-tuple read by position
  (`app.py:130`, `1009`, `1016`, `1025`, `1038`) become one pending-question object.
  **Done when:**
  - A question asked while another is pending is held, with "Still answering, Esc to stop" shown.
  - Offline commands still run meanwhile.
  - Both questions end up in the transcript.
- **M0-03 Menus are rebuilt every minute.** This happens while a countdown shows (`app.py:1850-1851`, `1362-1363`).
  Each rebuild re-checks the agents, which starts `claude plugin list` and `muse plugins list`, and copies every saved
  chat into up to about 1,400 actions (`agents.py:349`, `542`; `chats.py:183-199`; `app.py:603-633`).
  **Done when:**
  - Menus are built when they open, in a `menus.py`.
  - Clock ticks update only the time labels.
  - Agents are re-checked only when the menu opens.
  - The Chats submenu is built from light data (id, title, updated, pinned), without copying chats.
- **M0-04 The top menu is cluttered.** It has 16–19 items, mixing tasks with appearance and setup (`app.py:1818-1867`),
  and chats nest 3–4 levels deep.
  **Done when:**
  - The top menu is Ask, Chats, Remind, Focus and Notes, Brain, AI agents, Hide, Settings…, Help & updates and Quit.
  - Companion, Bubble style, Walk around and Start when I log in are under one Appearance submenu.
  - Reload settings file is under Help.
- **M0-05 Offline commands are an inline chain of English phrases.** `_local` and `_kept` (`app.py:1109-1252`, mccabe
  complexity 24 and 17) move to a command table that M5's per-language phrase data can drive.
  **Done when** the same commands answer the same phrases, through a table with tests.
- **M0-06 The screen's thread waits.**
  - `_brain()` waits by default in `open_ask`, `submit` and `status` (`app.py:523`, `961`, `1287`); in `open_ask` the
    result only fills in a hint.
  - Battery and disk reads run every 60 s on the screen's thread (`heads_up.py:59-69`; `app.py:1431`).
  
  **Done when** `open_ask` doesn't wait, and the battery and disk reads go through the existing `Background`.
- **M0-07 The companion's name prefers `config.toml` over state** (`app.py:261` vs `2302`, `2350`), so renaming in
  Settings does nothing on screen when the file has a name. **Done when** state wins, as the README says.
- **M0-08 System update checks have no timeout** (`app.py:1438-1458`, `1502-1504`). **Done when:**
  - A check is killed after about 60 s and counts as 0.
  - Each round's results are tagged, so a late result is ignored.
- **M0-09 Generated passwords are read out** through a notification on Windows when a screen reader runs
  (`app.py:1103-1107`, `395-400`), so they stay in the notification history.
  **Done when** a password reply is read out only as "Password made; it's in the box".
- **M0-10 Hook connections are unbounded.** The 64 KB cap is checked after `readAll` (`app.py:1658-1684`).
  **Done when** connections are capped and `setReadBufferSize(MAX_MESSAGE + 1)` is set.
- **M0-11 `chatmon remind <something it can't parse>` is silently dropped and exits 0** (`app.py:1721-1726`;
  `cli.py:55-56`). **Done when** the CLI parses the reminder first (reminders.py has no Qt), prints the problem and
  exits 2.
- **M0-12 There's no way to open the ask box from outside.** **Done when:**
  - `chatmon ask [TEXT]` opens it, prefilled and focused.
  - On Windows the CLI calls `AllowSetForegroundWindow` before sending.
  - `chatmon status` prints agent states, reminders and the brain in use.
- **M0-13 The log file is created at the umask** (`app.py:2461-2479`, `2475`). **Done when** it is created 0600 on
  POSIX.

## M1A: Security, updates, IPC and packaging (`updates.py`, `wintrust.py`, `events.py`, `winpipe.py`, `paths.py`, `agents.py`, `attachments.py`, `packaging/`)

- **M1A-01 The root updater installs any "chatmon" package whose hash the caller gives.**
  `packaging/linux/install-update` checks only a caller-supplied SHA-256 (lines 22-30; `updates.py:224-243`), and macOS
  works the same way behind osascript.
  **Done when:**
  - The root side verifies the signed `SHA256SUMS` and its signature itself, with the key in root-owned
    `/usr/lib/chatmon`, run with `python3 -I`.
  - It requires a version newer than the one installed.
  - macOS uses a root-owned helper inside Chatmon.app.
- **M1A-02 The macOS postinstall has a race.** Root writes a mktemp file inside `/usr/local/bin`
  (`packaging/macos/scripts/postinstall:17-24`), which may be user-owned.
  **Done when** it refuses a non-root-owned or group/world-writable directory, and builds the file in a root-only
  `mktemp -d` before `mv`.
- **M1A-03 The Windows pipe client allows impersonation.** It connects before checking the owner, and
  `QLocalSocket`'s `CreateFile` lacks `SECURITY_SQOS_PRESENT` (`events.py:147-156`).
  **Done when** the pipe is opened with `CreateFileW(… SECURITY_SQOS_PRESENT|SECURITY_IDENTIFICATION)`, then checked
  and written on that handle.
- **M1A-04 An elevated uninstall runs agents' tools from user-writable paths.** `hooks disconnect all` finds `claude`
  and `muse` through those paths (`packaging/windows/chatmon.iss:180-188`).
  **Done when** elevated processes only edit files and never start agents' CLIs.
- **M1A-05 Revoked certificates pass** (`wintrust.py:132`, `WTD_REVOKE_NONE`). **Done when:**
  - Revocation is checked.
  - An offline revocation lookup is retried later, never passed silently.
  - An actually revoked certificate fails.
- **M1A-06 The installer can be swapped before launch.** The verified installer runs from user-writable
  `%LOCALAPPDATA%\chatmon\updates` (`updates.py:445-459`).
  **Done when** it is copied to a fresh `mkdtemp` and verified there, or a deny-write handle is held from the check
  through the launch.
- **M1A-07 Agent config backups are readable and pile up.** They keep the original's mode and never stop accumulating
  (`agents.py:77-82`). **Done when** backups are created 0600 (`O_CREAT|O_EXCL`) and only the last 5 per file are kept.
- **M1A-08 ✓ Valid Codex configs are refused.** The Codex `config.toml` table-header regex matches a nested-array line
  such as `  [1, 2],` (`agents.py:483`). **Done when** they are accepted, with property tests showing connect then
  disconnect leaves every other key unchanged.
- **M1A-09 Attachments open files before checking them, and miss some network paths.** They open before the `S_ISREG`
  check, and only `\\` and `//` count as network paths (`attachments.py:137-149`).
  **Done when:**
  - `os.stat` runs before opening, and `fstat` after.
  - Mapped network drives (Windows `GetDriveTypeW`), NFS, CIFS, GVFS and FUSE (Linux `statfs`), and non-local mounts
    (macOS `MNT_LOCAL`) are refused.
- **M1A-10 `winpipe.client_is_me` is never called,** despite its docstring (`winpipe.py:148`). **Done when** it is
  called on accept, or the docstring is made true.
- **M1A-11 Chat files roam on Windows.** State is in Roaming `%APPDATA%`.
  **Done when** chats and other state live under `%LOCALAPPDATA%\chatmon`, with a one-time migration that leaves
  nothing behind in Roaming.
- **M1A-12 Updater tests are thin.** `install_kind()` and the install and relaunch code (`updates.py:76-102`,
  `427-512`) are untested. **Done when** both are covered by tests.

## M1B: Brains, chats and stored data (`brains.py`, `chats.py`, `memory.py`, `settings.py`, new `keychain.py`, new `backup.py`)

- **M1B-01 Every command-line brain inherits the whole environment** (`brains.py:1033-1036`).
  **Done when** a brain's environment is an allowlist: PATH, home, app-data and temp folders, SystemRoot, locale,
  proxy variables, `CHATMON_INTERNAL`, plus each brain's own auth variables.
- **M1B-02 Claude Code's `--tools ""` covers only its built-in tools,** so MCP servers may still load
  (`brains.py:46`).
  **Done when** the brain adds `--strict-mcp-config` (and `--permission-mode default`), checked against the installed
  CLI's `--help`.
- **M1B-03 Automatic trusts any server listening on ports 11434, 1234, 9931 or 8000** (`brains.py:97-100`, `426-427`).
  **Done when** a local server is auto-picked only if its socket belongs to the user (Linux `/proc/net/tcp` owner,
  Windows `GetExtendedTcpTable` owning process), or the user has confirmed it once.
- **M1B-04 Prompt injection can cross brains.** Brains with file tools get other brains' earlier answers
  (`brains.py:57`, `66`, `84-91`; `app.py:1007`, `1017`).
  **Done when** brains that aren't `tools_off` are not sent earlier answers from other brains.
- **M1B-05 `chatmon-ask-*` prompt files are left in TEMP** when Chatmon is killed (`brains.py:1018`, `1077-1084`).
  **Done when** stale ones are removed at startup.
- **M1B-06 ✓ `config.toml` values aren't checked** (`settings.py:206-217`).
  - `size = "big"` stops Chatmon from starting.
  - `breaks.every_minutes = "60"` raises a TypeError every 30 s.
  - A huge `updates_every_hours` overflows QTimer.
  
  **Done when:**
  - Each key is coerced to the type and a sane range of its default, falling back per key.
  - Bad keys are reported through `config_error`.
- **M1B-07 A damaged `state.json` is quietly replaced.** If it can't be parsed, `State.load` starts empty and the next
  save overwrites it. Saves don't flush (`settings.py:227-247`; `chats.py:173`; `memory.py:96-101`).
  **Done when:**
  - Saves flush before the swap.
  - A bad file is renamed `*.bad-<time>`.
  - The last good `.bak` is used, and the user is told.
- **M1B-08 Files are written first and chmod'ed afterwards.** Temp files start at the umask mode, and the state folder
  is created 0755 (`settings.py:189-193`, `245-246`; `memory.py:99-100`).
  **Done when** files are created 0600 with `os.open`, and the state and config folders are 0700.
- **M1B-09 HTTP errors are unreadable.** The HTTP status is never read, so errors show as "the answer wasn't in the
  expected shape" (`brains.py:1128-1148`).
  **Done when** a status of 400 or above shows error, message or detail plus the status, with a hint:
  - 401 or 403: check the key variable.
  - 429: rate limited.
  - 5xx: the provider is having trouble.
  - Host not found: offline.
- **M1B-10 Cancelling a command-line answer on Windows freezes the screen for up to 6 s.** `taskkill` (5 s timeout)
  plus a 1 s wait run on the screen's thread (`brains.py:928-933`, `997`).
  **Done when** cancelling never blocks.
- **M1B-11 Finding the brain blocks.** With no command-line tool installed, up to 4 ports are probed at 0.15 s each
  (`brains.py:286-323`). **Done when** there is a non-blocking lookup API with a cached result.
- **M1B-12 There are no streaming answers.** **Done when:**
  - The Anthropic Messages, OpenAI Responses, OpenAI Chat Completions and Gemini APIs stream.
  - Claude Code streams through `--output-format stream-json`.
  - Partial answers are emitted as they arrive.
  - Cancelling stops the stream.
- **M1B-13 API keys can only come from environment variables.** **Done when:**
  - A `keychain.py` stores and reads keys in the OS store without new dependencies: Windows Credential Manager through
    `CredWriteW` and `CredReadW`, the macOS Keychain through Security.framework, and the Linux Secret Service through
    QtDBus.
  - Brains use a stored key when the environment variable is absent.
  - Keys are never logged.
- **M1B-14 There's no way to test a brain.** **Done when** a test call asks "Say OK" and returns the time taken or the
  clearer error from M1B-09.
- **M1B-15 Brain per chat.** **Done when** a chat records its brain and carrying it on uses that brain, and there is an
  API to ask another brain the same question.
- **M1B-16 Back up and move.** **Done when** `backup.py` exports Settings changes, memory, notes, reminders and
  (optionally) chats to one zip, and imports it with validation. Keys are never exported.
- **M1B-17 Attached text is kept with the chat.** Owner decision: keep it, and correct the README. **Done when:**
  - Attached text saved with a chat is re-sent only to the brain it was first given to.
  - With **Keep chat history** off nothing is written.
  - **Clear chat history** removes it.

## M2: Bubbles and the ask box (`bubble.py`, `bubbleart.py`, `styles.py`, new `highlight.py`)

- **M2-01 ✓ Answers can make Chatmon read files.** Qt loads Markdown images and HTML resources inside `setMarkdown`
  (`bubble.py:173`, `705`), before `without_images` runs. An answer can make Chatmon read files, make an SMB connection
  on Windows that leaks the user's NTLM hash, or hang on `/dev/zero`.
  **Done when:**
  - Every `QTextDocument` the bubbles and ask box use returns an empty resource for every URL.
  - Markdown is set with `MarkdownNoHTML`.
  - A test shows a `file:` image is never read.
- **M2-02 Code blocks don't wrap.** Fenced blocks are non-breaking, so they're cut off in the ask box and paint over the
  bubble's border (`bubble.py:173-183`, `479`, `316`).
  **Done when:**
  - Code blocks wrap, with a tinted background and padding.
  - Heading sizes are capped.
- **M2-03 Speech bubbles have no maximum height,** and the button row never wraps (`bubble.py:167-212`; `191-195`).
  **Done when:**
  - Height is capped at about 40% of the screen, with "…" and a **More** button that opens the full text in the ask
    box.
  - Buttons wrap onto another row.
- **M2-04 Titles are clipped mid-letter.** They are drawn on one line with no wrap or ellipsis (`bubble.py:307`).
  **Done when** they are elided or wrapped, with the height measured.
- **M2-05 The plain style fails high contrast.** It is the style high contrast switches to, but keeps a fixed cyan
  `#26b8d9`, with white on cyan at about 2.3:1 (`styles.py:46`, `56`; `bubble.py:320-323`, `775`, `783`). Fairy-style
  links are about 3.2:1.
  **Done when:**
  - The plain style takes Highlight, HighlightedText, Link, Button and ButtonText from the palette.
  - Every style's text and link pairs reach 4.5:1.
- **M2-06 Focus is invisible.** The ask box has no `:focus` styles (`bubble.py:784-792`).
  **Done when** History, New chat, ✕, +, chips and the field show a 2 px focus outline.
- **M2-07 Text sizes are fixed.** Fixed point sizes and widths ignore the desktop's font size (`bubble.py:94-98`, `171`,
  `308`, `318`, `434`, `441`, `778-791`).
  **Done when:**
  - Text is the larger of the current size and the app font, scaled by an optional text-size factor.
  - Widths derive from font metrics.
- **M2-08 Bubble timing ignores the reader.** Bubbles expire on a fixed clock whatever their length, and hover doesn't
  pause them (`bubble.py:163`, `222-226`).
  **Done when:**
  - Expiry is at least 4 s plus about 0.3 s per word, or "until closed".
  - A bubble can be paused while hovered.
- **M2-09 Links in bubbles can't be clicked** (`bubble.py:233-242`). **Done when** they can, through
  `documentLayout().anchorAt()`, with only safe schemes.
- **M2-10 Long answers open on their last lines** (`bubble.py:715-716`). **Done when** they open at the start of the
  newest exchange.
- **M2-11 The ask box is a fixed size** (380×320). **Done when:**
  - It can grow to about 55% of the screen height, with an expand toggle reported to its owner.
  - Turns are separated by a rule or tint.
- **M2-12 ✓ Pasted code loses its line breaks.** The field is a single line, and a paste under 8 lines is joined with
  spaces (`bubble.py:335`, `657-658`; `attachments.py:201-203`).
  **Done when:**
  - The field takes several lines: Enter sends, Shift+Enter adds a line.
  - A paste keeps its line breaks.
- **M2-13 Animated bubble art never stops.** It costs 1.6–17 ms per frame (`bubble.py:43`, `151-155`, `544-548`), and
  power saving never reaches `AskBox._frames`.
  **Done when:**
  - The effects run for 1–2 loop periods, then settle on the still picture.
  - They restart on hover or a new message.
  - Power saving shows the still picture.
- **M2-14 The animated ask box repaints all of itself 30 times a second** (`bubble.py:451-453`). **Done when** only the
  animated ring is updated.
- **M2-15 Bubble art is redrawn as the notch moves.** Art caches are keyed by `round(tip_x)` (`bubbleart.py:997`, `1068`,
  `1086`, `1187-1191`, `316`, `354`).
  **Done when** the still picture and border are cached per size, with the notch drawn separately.
- **M2-16 There are no copy buttons.** **Done when** each answer and each code block has a Copy action, emitted as a
  signal.
- **M2-17 There's no code highlighting.** **Done when** a small `QSyntaxHighlighter` colours keywords, strings, comments
  and numbers in code blocks, themed by bubble style.
- **M2-18 The ask box can't show progress or be stopped.** **Done when:**
  - A busy state shows the brain's name and elapsed seconds.
  - A Stop button emits a signal.
  - Partial (streamed) text can be shown.
- **M2-19 The ask box appears and disappears instantly.** **Done when** it fades, unless reduced motion is on.
- **M2-20 Fairy links and selection have low contrast.** **Done when** every style's link and selection colours reach
  4.5:1 against their bubble.

## M3: The stage, sprites and the overlay (`penguin.py`, `sprites.py`, `behavior.py`, `stagemenu.py`, `clickthrough.py`, `layer.py`, `wayland.py`, `xkb.py`, `companions.py`)

- **M3-01 ✓ The stage timer never sleeps.** It runs at 30 Hz or more (20 in power saving) while idle, hidden, covered
  and locked (`penguin.py:51-53`, `790-797`, `79-84`, `495-499`).
  **Done when:**
  - A single-shot timer is set to the next actual change.
  - It runs at about 1 Hz or stops while covered, hidden or not drawing.
  - On Windows and macOS the pointer is polled at full rate only near the chatmon.
- **M3-02 The timer ignores the display's refresh rate.** It runs every 16 ms whatever the display, positions are
  rounded to logical pixels, and drags redraw only on ticks (`penguin.py:51-52`, `696`, `795`).
  **Done when:**
  - The interval follows `QScreen.refreshRate()`.
  - Positions are in device pixels.
  - Drags redraw on pointer moves.
- **M3-03 Frames are stored twice when the scale isn't 1** (`sprites.py:98-100`, `29`). **Done when:**
  - The ratio is set on the QImage before `fromImage`.
  - Hit tests use an alpha mask.
  - The previous scale's frames are kept for drags between monitors.
- **M3-04 The overlay's buffers are full-screen,** about 33 MB each at 4K and 2x, up to 3 of them (`layer.py:128`,
  `1263-1269`). **Done when** the overlay uses at most 2 buffers, sized to what's shown where the protocol allows.
- **M3-05 ✓ Overlay menus have no keyboard support.** Overlay menus ignore keys, Esc closes the ask box but leaves the
  menu open and catching clicks screen-wide, and `close_menu()` is never called (`penguin.py:601-615`, `575`;
  `stagemenu.py:35-38`).
  **Done when:**
  - An open menu takes the keys: Esc closes it, arrows and Home/End move, Left/Right close and open submenus, Enter
    picks, and a letter jumps.
  - The highlighted row is outlined.
- **M3-06 Long overlay menus run off screen,** and submenus switch on diagonal moves (`stagemenu.py:159-168`, `95-98`).
  **Done when:**
  - Height is capped, with scroll arrows and the wheel.
  - Submenus open after a 250 ms hover delay.
  - The menu rebuilds only when the hovered item changes.
- **M3-07 Overlay menu text has low contrast.** Section headers are drawn at alpha 110 and the hover is a 70-alpha
  tint (`stagemenu.py:174-176`, `184`, `201-203`). **Done when** headers reach 4.5:1 and hover and focus are solid.
- **M3-08 Overlay menus ignore the font size.** Rows are a fixed 26 px (`stagemenu.py:23`, `134-157`). **Done when** a
  row's height is `max(26, fm.height() + 8)`.
- **M3-09 Shortcuts fail on non-Latin layouts on the overlay** (`xkb.py:204-207`). **Done when:**
  - With Ctrl or Alt held, a non-Latin keysym falls back to the key's Latin symbol from another layout.
  - Ctrl+V, Ctrl+C, Ctrl+X, Ctrl+A and Ctrl+Z work under a Russian layout.
- **M3-10 The X11 input shape uses logical pixels,** so the clickable area shrinks and shifts at scales other than 1
  (`clickthrough.py:57-64`). **Done when** it is scaled by `devicePixelRatioF()` and rounded outward.
- **M3-11 Reduced motion only stops walking and the bubble edges** (`behavior.py:302-306`, `329-330`, `149`, `188`,
  `197-203`, `291-295`).
  **Done when:**
  - Looping moods hold a single pose.
  - Needs-you shows a still pose with a static badge.
  - Waves, hops and peeks are skipped.
  - A drop lands at once.
- **M3-12 Hovering mid-walk swaps to the front-facing frame** (`behavior.py:208-210`). **Done when** the current walk
  frame holds, or the turn plays.
- **M3-13 Agent state shows only in the pose.** **Done when** the stage can draw a small badge by the creature with the
  number of agents working or needing you, coloured by state and with a shape cue, not colour alone.
- **M3-14 The overlay ask box is probably invisible to screen readers** (`penguin.py:156-169`). **Done when** the stage
  can run unhosted, with the ask box as a normal Qt window and real menus, for a screen reader.
- **M3-15 The stage stays on the screen it started on.** **Done when** it can follow the pointer's screen, as an
  option.

## M4A: Platform awareness and screen readers (`presence.py`, `a11y.py`, `macnative.py`, `linuxsession.py`, `sysnotify.py`, `heads_up.py`, `portal.py`, `winlock.py`)

- **M4A-01 ✓ High contrast is never detected in the Linux packages.** It is read only through the Qt 6.10 API
  (`presence.py:393-403`), and Ubuntu 24.04 has 6.6.
  **Done when:**
  - The portal's `org.freedesktop.appearance contrast` is read.
  - Then GNOME's `org.gnome.desktop.a11y.interface high-contrast`.
  - On macOS, `accessibilityDisplayShouldIncreaseContrast`.
- **M4A-02 On Linux, `covered()` ignores which screen the stage is on** (`presence.py:368-379`, `249-253`). **Done
  when** a full-screen window on another monitor doesn't count.
- **M4A-03 macOS has no sleep, wake or screen-sleep watchers** (`app.py:1392-1410`). **Done when** `NSWorkspace`
  observers emit sleep, wake, screens-sleep and screens-wake, using `macnative.py`'s runtime-class pattern.
- **M4A-04 Settings are polled.** Reduced motion is polled every 30 s with a blocking D-Bus call (`presence.py:386-391`).
  **Done when** changes come from the portal's `SettingChanged`, Qt's `contrastPreferenceChanged`, and
  `WM_SETTINGCHANGE` through winlock's filter.
- **M4A-05 Do Not Disturb isn't seen on Hyprland and Sway.** **Done when** the DND state of swaync, dunst (`paused`),
  mako modes and xfce4-notifyd is read.
- **M4A-06 Power saving is Windows-only.** **Done when** macOS Low Power Mode and UPower `OnBattery` feed power saving.
- **M4A-07 The Linux screen-reader fallback floods the notification history** (`sysnotify.py:19-22`). **Done when:**
  - Read-aloud notifications are `transient` and replace each other.
  - Held alerts use urgency 2.
  - Buttons are notification actions, with `ActionInvoked` reported.
- **M4A-08 VoiceOver drops announcements while Chatmon isn't in front** (`a11y.py:11-12`, `160-183`). **Done when**
  they are held until Chatmon is activated, or spoken by an opt-in speech fallback.
- **M4A-09 Windows screen readers get toasts.** Narrator, NVDA and JAWS are reached through notifications. **Done
  when** announcements go through UI Automation notifications (`QAccessibleAnnouncementEvent` on Qt 6.8+, or
  `UiaRaiseNotificationEvent`), with the notification only as a fallback.
- **M4A-10 Battery checks block.** Up to 3 blocking D-Bus calls run every 60 s (`heads_up.py:59-69`;
  `presence.py:169`). **Done when** heads-up readings can run off the screen's thread.
- **M4A-11 Linux keeps drawing while locked.** **Done when** `SessionWatcher` reports the lock so the stage can stop
  drawing.

## M4B: Hotkey, sound and Windows notifications (new `hotkey.py`, new `sound.py`, new `wintoast.py`, `winfocus.py`, `chatmon/sounds/`)

- **M4B-01 There's no global hotkey.** **Done when** `hotkey.py` registers a configurable shortcut:
  - `RegisterHotKey` on Windows, on its own message-only window.
  - `RegisterEventHotKey` on macOS.
  - `XGrabKey` on X11.
  - The GlobalShortcuts portal on Wayland.
  - It reports a failure to register, for example a conflict.
- **M4B-02 There's no sound.** **Done when** `sound.py` plays the packaged cues:
  - It uses `QSoundEffect` when QtMultimedia is present, and otherwise `PlaySound` on Windows, `NSSound` on macOS, and
    `pw-play`, `paplay` or `canberra-gtk-play` on Linux.
  - It is silent during quiet times.
  - It has a volume setting.
  - Every cue can be turned on or off.
- **M4B-03 Windows notifications are tray balloons.** **Done when** WinRT toasts through combase carry action buttons
  and the reminder scenario, using the existing app ID (`app.py:34`, `2580`), with the tray balloon as a fallback.
- **M4B-04 Windows Magnifier doesn't follow bubbles.** **Done when**, as an option, the system caret is placed on the
  stage window at a new bubble, so Magnifier pans to it.

## M5: Reminders, offline answers and locale (`reminders.py`, `offline.py`, `context.py`, new phrase data)

- **M5-01 ✓ A due reminder is removed before it has been seen** (`app.py:1320-1323`; `reminders.py`). **Done when:**
  - A fired reminder stays in the book, marked fired, until it is done or snoozed.
  - Unacknowledged reminders come back at start.
- **M5-02 Reminder phrases are misread** (`reminders.py:57-81`, `64-76`, `56`, `116`).
  - "friday at 3pm" lands on today.
  - "at 3" means 3 AM.
  - "in 2 hours" uses wall-clock time, so it is wrong across daylight saving.
  
  **Done when:**
  - Weekdays, "next mon", "dec 3" and ISO dates are parsed.
  - A bare hour of 12 or less takes whichever of h and h+12 comes next.
  - Leftover date words return an "ambiguous" result.
  - "in …" is computed as epoch plus seconds.
- **M5-03 Reminders can't repeat.** **Done when** "every day", "every weekday" and "every monday at 9" repeat, and are
  rescheduled when they fire.
- **M5-04 There's one fixed snooze, borrowed from breaks.** **Done when:**
  - Snooze offers 5 min, 15 min, 1 h and tomorrow at 9 AM.
  - Reminders have their own snooze setting.
  - A reminder can be edited, its text and time.
- **M5-05 Times are always 12-hour and English** (`reminders.py:132-149`; `offline.py:229-234`; `chats.py:62`, `239`,
  `242`). **Done when** times and dates are formatted with `QLocale`.
- **M5-06 The offline phrases are English in code.** **Done when:**
  - The offline commands' phrases are per-language data.
  - English is always accepted.
  - Help lists the commands in the active language.
- **M5-07 There are no property tests for the parsers.** **Done when** Hypothesis tests cover:
  - The calculator: only ValueError or OverflowError, bounded time, within `_MAX_DIGITS`.
  - `parse_when`: `now < due ≤ now + LONGEST`, across daylight saving.
- **M5-08 There's no *agents* command.** **Done when** a pure function formats agent states and their durations for an
  *agents* command and `chatmon status`.

## M6A: CI, tooling and repo hygiene (`.github/`, `pyproject.toml` tool sections, `packaging/requirements*`, `packaging/build.py`, `SECURITY.md`, `CONTRIBUTING.md`)

- **M6A-01 `ci.yml` isn't pinned or bounded.** **Done when:**
  - Actions are pinned to commit SHAs, with `persist-credentials: false`.
  - Every job has `timeout-minutes`.
  - A PR concurrency group cancels in-progress runs, and pushes run only on `main`.
  - ruff, pytest and Qt versions are pinned.
  - Tests run with `pytest-timeout`, `-rs`, `filterwarnings = error` and `--strict-markers`.
  - `wayland-protocols` and `libwayland-dev` are installed.
- **M6A-02 Nothing keeps dependencies up to date.** **Done when** Dependabot covers `github-actions` and `pip`, with a
  14-day cooldown.
- **M6A-03 ✓ The distribution's PyQt is never tested** (Ubuntu 24.04 has 6.6). **Done when** the whole suite runs in
  ubuntu:24.04, debian:trixie and fedora:44 containers on their own PyQt6.
- **M6A-04 Coverage isn't measured in CI.** **Done when:**
  - Coverage from every OS job is combined and written to the job summary.
  - A `fail_under` is set from the measured baseline.
- **M6A-05 CI doesn't test what ships.** **Done when:**
  - A Python 3.14 leg is constrained by `packaging/requirements.txt`, the shipped Qt.
  - An `ubuntu-24.04-arm` leg runs.
- **M6A-06 Build dependencies aren't locked.** **Done when:**
  - Build dependencies are hash-locked and installed with `--require-hashes`.
  - setuptools is pinned.
  - `SOURCE_DATE_EPOCH` is set.
- **M6A-07 Releases are published before their files are attached** (`packages.yml:9-10`, `447-454`). **Done when:**
  - A tag push uploads to a draft release, which is published at the end.
  - `actions/attest-build-provenance` runs.
- **M6A-08 Nothing checks what ships in the wheel.** **Done when:**
  - A test checks that every tracked non-.py file under `chatmon/` matches a package-data glob.
  - The wheel job runs `twine check`.
- **M6A-09 The old name is still installed.** The `penguin-companion` console script and the root `penguin-companion`
  file were kept "for one release" at 0.3.0. **Done when** both are removed, keeping the migration code until 1.0.
- **M6A-10 Contributor files are missing.** **Done when:**
  - `SECURITY.md` and `CONTRIBUTING.md` exist.
  - The issue template has a contact link to security advisories.
  - A pinned `dev` extra exists.
- **M6A-11 One test runs a real 19-second Windows Update search** and passes whatever happens (`tests/test_windows.py:609-617`).
  **Done when** it is opt-in behind an environment variable.
- **M6A-12 Workflows aren't linted.** **Done when** CI runs actionlint and zizmor on them.
- **M6A-13 There's no type checker** (313 errors in 30 files). **Done when:**
  - mypy is configured, with `--platform` legs.
  - The 17 clean modules are gated now, and the rest listed as exemptions.
- **M6A-14 Release notes point at main.** `packaging/build.py:54` tells people to pipx install from main. **Done when**
  they pin `@v{version}`.
- **M6A-15 Test jobs download all the art.** **Done when** test jobs use a sparse checkout without `art/` and `docs/`.

## M7: Integration (`app.py`, `settingswin.py`, `cli.py` wiring; after wave 1)

These wire the APIs that the M1–M5 milestones add, and add what exists only at the app level. Each wave-1 plan lists
its integration notes.

- **M7-01 Answers.** **Done when:**
  - Streamed answers are shown as they arrive.
  - Closing the ask box lets the answer finish in the background, followed by a bubble "<brain> answered: Read".
  - A Stop button and elapsed seconds are shown.
- **M7-02 Failures.** **Done when:**
  - A failed question offers **Try again**, **Ask <next brain>** and **Settings**.
  - A pick that fell back to Automatic is announced once.
  - At first run, after naming, the chatmon says which brain will answer, or how to set one up.
- **M7-03 Settings window.** **Done when:**
  - The AI tab has a key field for the chosen API brain, stored in the keychain, and a **Test** button.
  - There is an Accessibility tab with text size, how long bubbles stay (including "until I close them"), sounds and
    their volume, the hotkey, reduced motion, and the accessible ask-box mode.
  - Reminders have their own snooze setting.
  - The update-check interval applies without a restart.
  - "Almost empty" stays below "low".
- **M7-04 Reminders in the app.** **Done when:**
  - Reminder bubbles offer snooze choices, with edit and repeat in the menu.
  - Unacknowledged reminders are restored at start.
- **M7-05 Focus.** **Done when** an active focus session holds non-alert bubbles and shows one "While you focused: …"
  summary at the end.
- **M7-06 Missed messages.** **Done when** a "Recent messages" menu, and a click on the chatmon after a missed message,
  bring back recent bubbles.
- **M7-07 Agents at a glance.** **Done when** the tray tooltip and the stage's accessible description name agent
  states, the badge (M3-13) is fed, the needs-you tray icon has a badge, and the *agents* and *status* commands are
  wired up.
- **M7-08 Quick actions.** **Done when** Explain, Summarize, Translate and Fix the clipboard each attach the clipboard,
  on the user's action, and prefill a prompt.
- **M7-09 Chats.** **Done when:**
  - A Chats window with search replaces the per-chat submenus.
  - Brain per chat and "Ask another brain" are offered.
  - Export and import are under Settings.
- **M7-10 Copy and keys.** **Done when:**
  - Copy is wired for answers and code blocks.
  - Ctrl+1–9 press a bubble's buttons while the ask box is open.
  - A button label typed after its bubble expired is still answerable within `ANSWERABLE_FOR`.
- **M7-11 Platform wiring.** **Done when:**
  - Linux lock and macOS sleep stop drawing.
  - Power saving reaches the ask box.
  - High-contrast and reduced-motion change events apply live.
  - With a screen reader, the overlay's ask box runs as a window.
  - Sounds play on alerts.
  - Toasts replace balloons.
  - The hotkey opens the ask box.
  - "Follow me" across monitors is a setting.
- **M7-12 A new chat starts without a word after 15 idle minutes** (`app.py:507-508`). **Done when** the empty box says
  "New chat · carry on with the last one".
- **M7-13 A first-unlock hello.** **Done when** one bubble names today's reminders, agents still waiting and updates
  pending.

## M8: Translation plumbing (every module with user-facing strings; after M7)

- **M8-01 There's no translation layer.** About 400 user-facing strings exist, plus the help text. **Done when:**
  - They go through gettext, with `ngettext` for plurals.
  - Sentences built from fragments become whole-sentence templates (`app.py:807`, `1224`, `1251`, `98-100`,
    `2041-2046`).
  - Qt's own translations load.
  - Only English ships, and adding a language is a `.po` file.

## M6B: Static analysis and logging (every module; after M8)

- **M6B-01 ruff checks only F, E9 and B.** **Done when:**
  - ruff adds UP, C4, PIE, PERF, RUF (ignoring RUF001-003), S (except S101, ignored in tests), DTZ, BLE, and C90 with
    `max-complexity = 15`.
  - Every finding is fixed, or suppressed per line with a reason.
- **M6B-02 Most modules fail mypy.** **Done when** mypy's exemptions are removed module by module until every module
  passes.
- **M6B-03 There's no logging.** There are 27 `print()` calls, a hand-made log file, and 82 `except` blocks that swallow
  errors. **Done when:**
  - `logging` writes through a `RotatingFileHandler`.
  - `CHATMON_DEBUG` sets the level.
  - Swallowed errors are logged at debug level.
  - Keys and chat text are never logged.

## M9: Sounds (`chatmon/sounds/`, `art/sounds/`, the flow-skill sound flow)

- **M9-01 There are no sound assets.** **Done when:**
  - Short cues ship: needs-you, reminder, focus done, done, success, error, and a soft pop for a plain bubble.
  - Each is a 44.1 kHz WAV under 1 s (a reminder up to 2 s) and loudness-matched.
  - They come from the owner's own synthesized sounds or ElevenLabs Sound Effects (paid plan, commercial use).
  - Each one's origin and licence is in `art/sounds/SOURCES.md`.
- **M9-02 Sound creation isn't repeatable.** **Done when** creating, checking and installing Chatmon sounds is a flow in
  the owner's flow skill.
