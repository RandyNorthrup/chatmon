# What's new in Chatmon

Each version's changes, newest first: what Chatmon shows after it updates, and each release's notes.

## 0.10.0

### New
- **Answers appear as they're written**, with who is answering, the seconds so far, and **Stop**. Closing the ask box no longer throws an answer away: it finishes, stays in the chat, and a bubble says it's ready with **Read**. A second question asked meanwhile waits its turn instead of replacing the first.
- **When a question fails, Chatmon says what to do**: what the provider said and its status, with **Try again**, **Ask another brain** and **Settings**. No connection says you look offline; a model server that isn't running says so.
- **API keys in your system's keychain** (Windows Credential Manager, the macOS Keychain, GNOME Keyring, KWallet or KeePassXC), saved from Settings › AI, and **Test** asks a brain "Say OK" and shows how long it took. Keys never appear in Chatmon's files, a backup or an error.
- **A shortcut opens the ask box from any app**: Ctrl+Alt+Space (Ctrl+Shift+Space on macOS), or one you choose. On Wayland your desktop asks first where it supports app shortcuts; elsewhere, bind `chatmon ask` in your desktop's keyboard settings.
- **Sounds** for something that needs you, a reminder and the end of a focus session. An agent finishing, a success, an error and a soft pop can be turned on too. Each has its own switch, there's a volume and one switch for all, and nothing sounds during Do Not Disturb, Focus, a full-screen app or a focus session.
- **An Accessibility tab in Settings**: text size, how long bubbles stay (up to "until I close them"), sounds, the shortcut, less movement, the ask box as its own window for screen readers, reading aloud, Magnifier following bubbles (Windows) and speech in macOS's own voice while Chatmon is in the background.
- **Reminders understand days and dates** ("friday at 3pm", "next mon", "dec 3", "2026-12-03 15:30", "tonight at 8"), and "at 3" means whichever 3 o'clock comes next. They can repeat ("every weekday at 9"). When Chatmon can't tell when you mean, it asks instead of guessing.
- **Reminders wait for you**: one that comes due stays until you press **Done** or snooze it (your own length, or **Later**: 5 minutes to tomorrow morning), even across a restart. Each reminder in the menu can be edited, made to repeat or cancelled.
- **Agents at a glance**: the tray's tooltip and the chatmon's name for screen readers say what each agent is doing, a badge by the chatmon and a dot on the tray icon show when one needs you, *agents* says it in the box, and `chatmon status` prints it in a terminal.
- **A Chats window with search**; the menu keeps the newest. Each chat remembers its brain, and **Ask another brain** asks the last question again.
- **Back up and move**: Settings › Chats can save your settings, memory, notes, reminders and (if you like) chats to one file and bring them back on another computer. Keys are never in a backup, and a backup is checked before anything changes.
- **Clipboard actions** in the menu: Explain, Summarize, Translate or Fix what you copied. The clipboard is read only when you pick one.
- **Recent messages** in the menu shows bubbles again, and a click on your chatmon brings back one that went by while you were away. A focus session ends with one "While you focused" bubble for what waited.
- **Copy** under every answer and code block. Ctrl+1 to Ctrl+9 press a bubble's buttons while you type.
- **The ask box takes several lines** (Shift+Enter for a new one; pastes keep their line breaks), opens at your newest question, separates turns with a line, and can be made bigger. Code wraps on a tinted panel, coloured to match the bubble style.
- **Long messages fit on screen**, ending in "…" with **More**. Bubbles stay long enough to read, wait while you point at them, and their links can be clicked.
- **Windows:** notifications are Windows' own, with buttons, in Action Center; a reminder stays on screen until you answer it. Magnifier pans to new bubbles.
- **Your chatmon can follow you to another monitor** (Windows, macOS, X11).
- **Settings shows how your desktop set the shortcut**: on Wayland, where the desktop has the last word, Settings › Accessibility names the keys it chose.
- **The first unlock of the day** says what's waiting: today's reminders, agents waiting for you, updates.
- `chatmon ask [TEXT]` opens the ask box, filled in, with the keyboard in it (on macOS 14 and later too, from a script or a launcher); `chatmon status` prints the brain, your reminders and your agents.
- **Chatmon keeps a log** of what went wrong, `chatmon.log` in its state folder, readable only by you; **Open the log** opens it, and `CHATMON_DEBUG=1` keeps the details. No key, chat or typed text ever goes into it: a provider that repeats your key has it blanked out.
- **Chatmon can be translated**: every word it shows, in its bubbles, menus, Settings and the `chatmon` command, comes from a translation when there's one for your language, or the one you pick in Settings, and Qt's own buttons follow it. Only English ships so far, and a new language is a single file. Times and dates follow your system's regional settings.

### Changes
- **Chat search yields between batches**, and recently opened conversations have a bounded cache that is released when chats are deleted or cleared. Repeated AI tests in Settings release their network objects when finished or cancelled.
- **Fragmented streamed answers take less work to parse**: an unfinished line is extended and searched only where new bytes arrived.
- **The menu is tidier**: Companion, Bubble style, Walk around and Start when I log in are under **Appearance**, focus and notes share one menu, and **Reload settings file** is under **Help & updates**.
- **Far less power when idle**: the chatmon's clock sleeps until the next thing on it changes (about 100 wake-ups a minute standing still, down from 1,800), and nothing is drawn while the screen is locked, asleep or off. It moves at your screen's own refresh rate, and animated bubble edges rest after a loop.
- **Every bubble style meets WCAG AA contrast**, the plain style follows your desktop's colours (high contrast included), every control shows a focus outline, and text follows your desktop's font size.
- **High contrast and reduced motion are followed on every platform**, Linux and macOS included, and changes apply at once. With reduced motion the chatmon holds still poses and skips its waves, hops and peeks.
- **The Wayland overlay draws only what's shown**: its buffers are the size of the chatmon and its bubble, under 8 MB instead of 63 MB on a 4K screen at 2x, and a drag shows the new place and pixels in the same frame.
- **Overlay menus work from the keyboard** (Esc, arrows, Home/End, Page Up/Down, Left/Right, Enter, letters), scroll when long, and wait a moment before switching submenus. Shortcuts in the ask box work under Russian, Greek and other non-Latin layouts.
- **Screen readers**: on Windows, Narrator, NVDA and JAWS hear Chatmon directly while it's in front; VoiceOver no longer misses what's said in the background, or the greeting: it says them a moment after you come to Chatmon, and typing in the ask box works with VoiceOver on; Linux read-aloud notifications stay out of the history and carry the bubble's buttons. A generated password is never read out.
- **Linux finds a screen reader again** with at-spi2-core 2.62 (which dropped the old signal): Orca, Odilia, Fenrir, or GNOME's screen-reader setting, and starting or stopping one moves the ask box to a window, or back, at once.
- **Do Not Disturb** is respected with dunst, mako, SwayNotificationCenter and xfce4-notifyd too. On Linux the chatmon draws less on battery; on macOS, in Low Power Mode.
- **Messages are never lost**: a bubble with buttons stays until you answer it, alerts and reminders are never dropped, and anything that arrives meanwhile waits its turn. During a focus session, agents' and scripts' messages wait until it's over.
- **Windows:** settings, state and chats moved from the roaming profile to this computer (`%LOCALAPPDATA%\chatmon`), automatically, the first time this version starts.
- **Attached text** stays with its chat so you can carry on after a restart, sent again only to the brain you first gave it to. Nothing is written with **Keep chat history** off, and **Clear chat history** removes it.
- **Settings that are wrong in `config.toml` are named**, one by one, and the rest still apply. A damaged state or memory file is kept aside and the last good copy used, and Chatmon says so.
- `timeout_seconds` is now how long a brain may go without a word, so long answers aren't cut off.
- After 15 minutes the ask box opens on a new chat and says so: *carry on* goes back to the last one.
- The `penguin-companion` command is gone; use `chatmon`. Hooks set up under the old name still move over the first time Chatmon runs.

### Security
- **Answer size limits cover every transport**, including streamed events, model lists, command output, diagnostics and answer files. Command-line errors redact the brain's key before reaching the screen. Failure logs retain only the brain and HTTP status, so a provider that quotes your question or attachment cannot put it in the log. Cancelling a stream also stops pieces already parsed from its current network chunk.
- **An answer can no longer make Chatmon read a file or reach a network share** by naming it as a picture or in HTML. Pictures in answers show as "[image]" and HTML as text.
- **Linux and macOS:** installing an update has the system itself check the release's signed checksums and its version, so it installs only a newer Chatmon signed with its release key, whatever it's handed. **macOS:** the installer adds the `chatmon` command only to a `/usr/local/bin` that belongs to the system.
- **Windows:** hooks reach Chatmon in a way that never lets whoever holds its address act as you; each connection is checked to come from your own processes; revoked signing certificates are refused; the update's installer runs from a copy nothing can change before it starts; uninstalling for everyone no longer runs agents' programs as an administrator.
- **Command-line brains get only the environment variables they need**, not your other keys. Claude Code runs with no MCP servers. Automatic uses only a model server running under your account, or one you've confirmed, and a brain that can read your files never sees other brains' answers.
- **Files Chatmon keeps are private from the moment they're made** and reach the disk before they replace old ones. Backups of agents' settings are private too, and only the newest five are kept. Files on network drives and mounts can't be attached.
- Releases appear only once every file is attached, and each file carries a build attestation (`gh attestation verify <file> --repo RandyNorthrup/chatmon`).

### Fixes
- **Agent badges can be cleared**: click a number to open Notifications, mark alerts as read, or clear one or all stale statuses. Closing an agent alert acknowledges that notice, and an old alert cannot clear a newer one. The same controls work from the keyboard in the tray or companion menu; reminders keep Done and Snooze.
- Renaming your chatmon in Settings works even when the settings file names it.
- Opening the ask box never waits to work out which brain will answer; cancelling an answer never freezes the screen, and on Windows no longer risks ending unrelated programs.
- The menu no longer rebuilds itself every minute while a countdown shows.
- A system update check that hangs is stopped after a minute; changing how often to look applies at once; "almost empty" battery stays below "low".
- `chatmon remind` with a time it can't read says so and exits with status 2.
- "in 2 hours" is two real hours, even across a daylight-saving change.
- Codex settings with an array of arrays across lines can be connected.
- With two monitors on X11, a full-screen app on the other monitor no longer hides the chatmon; with X11 display scaling, clicks land exactly on it.
- On sway, the ask box keeps the keyboard until you close it; before, typing could go to the window behind it. A copy from the ask box pastes at once into Chatmon's own windows, and with a screen reader the chatmon's menu still works from the keyboard and bubbles no longer cover the ask box.
- **KDE Plasma:** closing the ask box gives the keyboard back to the window you were typing in (before, typing went nowhere until you clicked one), so a full-screen video comes back in front of the chatmon too, and what you copy in the ask box pastes into Chatmon's own windows. When a monitor is unplugged and the desktop moves the one left, the chatmon follows at once (on sway too).
- **Hyprland:** dragging the chatmon quickly no longer drops it on the way, or opens the ask box instead.
- **Windows:** notification banners show while Chatmon runs. Windows took the chatmon's overlay for a full-screen app, so it showed no app's banners, and Chatmon held its own bubbles back as if you were in one.
- Hovering a walking chatmon stops it mid-step instead of snapping it round.
- The fairy style's highlighted button label could not be seen.
- pip and pipx installs include the sounds and offline phrases.
- **macOS:** reminders and bubbles keep their time while Chatmon's windows are out of sight; App Nap no longer holds them back.
- *status* no longer waits on finding a brain, and a sound still playing at quit finishes cleanly.
- Quitting stops everything Chatmon had waiting: no update check, agent look or late answer runs after it.
- A repeating reminder reads "Every day at 9:00 AM", and one-of-a-kind counts read right ("1 minute", "1 hook script").

## 0.9.2

### Fixes
- **Coding agents' news is heard in the order it was sent**, even when your computer is too busy for Chatmon to answer within the half second an agent's hook waits. Before, an agent's **done** could be heard before its **working**, leaving your chatmon showing it as still at work.

## 0.9.1

### Fixes
- **+** and **History** in the chat open their menus. Except on the Wayland overlay, clicking them showed nothing, so **Paste from the clipboard** and earlier chats couldn't be reached from the chat.
- **macOS:** pasting into the chat counts as your own paste where macOS asks before an app reads the clipboard (macOS 15.4 and later can, and Apple means to make it the default): **Cmd+V**, **Paste** in the field's right-click menu and **+** › **Paste from the clipboard** paste without a prompt. Before, macOS asked at every paste, and as the right-click menu opened; choosing **Paste** in that menu then quit Chatmon.
- **macOS:** the chat's menus (right-click in the field, **+** and **History**) are macOS's own.

## 0.9.0

### New
- **Your chatmon offers to connect the coding agents it finds**: a bubble naming them, with **Connect** and **Not now**. Once you've answered, it doesn't ask again; if you were away and the bubble went unanswered, it asks next time Chatmon starts. Agents you install later are offered when they turn up. **AI agents** in the menu still changes them any time.
- **Windows:** the installer can connect the coding agents it finds (**Connect the coding agents found here**, under the PATH choice; off unless you tick it). An update installing itself never connects one.
- When Claude Code switches Chatmon's plugin off after it was connected (a window that was open when you connected it saves its settings over the plugin's), your chatmon says so once, with **Switch on**.

### Fixes
- **Claude Code installed only as the VS Code extension** (or Cursor's, or Windsurf's) connects: Chatmon uses the command line that the extension carries when there's no `claude` on PATH. Before, Claude Code showed as found but connecting it said it wasn't installed. With no command line anywhere, connecting now says how to add the plugin from Claude Code itself.
- **Windows:** Chatmon started by its installer finds itself on PATH, so connecting agents from it works straight away, Claude Code included, and hooks run chatmon by name.
- **Windows:** uninstalling Chatmon disconnects the coding agents connected to it. Before, they went on running a chatmon that was gone: Codex at the end of every turn.
- `chatmon hooks disconnect all` touches only the agents that are connected. Before, it also rewrote (with a backup) the settings of an agent that had hooks of its own but none of Chatmon's.

## 0.8.0

### New
- **Screen readers.** With a screen reader running, each bubble and answer is read out: by Orca itself (Orca 49 or later), by VoiceOver while Chatmon is the app in front, and as a system notification where there's no other way (Narrator, NVDA and JAWS read those on Windows). A bubble's buttons are read out too, and typing one in the chat presses it, also just after the chat opened over the bubble. Settings has it under **General**, on unless you turn it off.
- The chat's controls have names a screen reader says: the conversation, the question, **Attach**, **Close**, and each attachment's **Remove**. The chatmon's window, where it's a window, is named Chatmon, and describes the bubble it's showing.

## 0.7.0

### New
- **Chats remember the whole conversation.** Follow-ups and questions about anything said earlier work however long a chat gets, with every brain alike. A brain gets the latest turns word for word, a summary of the earlier part (made once, by the brain you're asking, and kept with the chat), and the earlier turns that bear on your question, word for word. How much is sent is up to you (`[chats] context_tokens`), and never more than the model can take: a model server's own limit is asked for, and a brain that says a question was too long is asked again, with less.
- **Instructions for every chat**, and **instructions for one chat** (its menu, under **Chats**): how to answer, what you do, what language. Every brain gets them with every question.
- **Memory.** *Remember that I use Arch*, and every brain you ask knows it, in every chat. *What do you remember* lists it; *forget that …* takes it out. Only what you say, in so many words: nothing is picked out of your chats.
- **Settings, in a window.** **Settings…** in the menu (or *settings* in the chat): the name, companion, size, walking, bubble style, the brain, chats, your instructions and memory, breaks and focus, and the heads-up thresholds, without editing a file. What you set there is kept, and wins over the settings file, which still works.
- **Ask about what you attached, later.** Text you attach is kept with its chat (readable by you alone), so you can come back to it after Chatmon restarts. It goes only to the brain you gave it to.

### Changes
- **Break reminders and focus alerts can be turned off**, in Settings or by saying *breaks off* or *focus alerts off* (and *… on* to bring them back). Turned off, your break interval is kept for when you turn them on again.
- **Walk around** in the menu is remembered after a restart, as Settings remembers it.
- The chatmon stops walking while the pointer is over it, so it's easy to click, and carries on when the pointer leaves.
- **Linux:** the app's entry has **Bring out Chatmon** and **Quit Chatmon** in the launcher and dock.
- **Linux:** in power-saver mode, the chatmon draws less often.
- **Linux:** waiting updates are counted through PackageKit on systems whose package manager Chatmon doesn't ask itself.
- **Hyprland:** the screen locking counts as a break with hyprlock too, which doesn't tell logind.
- **Wayland:** where the chatmon is an overlay (Hyprland, Sway, KDE...), Chatmon's own windows, Settings and dialogs, are Wayland windows, sharp at any scale, no longer drawn through XWayland.
- **Wayland:** files, pictures and text dragged onto the open chat are attached, on Hyprland, Sway and other compositors with the overlay, as they are elsewhere.
- **Linux:** attaching files and saving a chat use your desktop's own file chooser (through its portal), on Hyprland and Sway too.
- **Windows 11:** bubbles wait while Focus is on, as they do for a full-screen app or a presentation.
- **Windows:** nothing is drawn while the screen is locked or the display is off, and in Energy Saver (battery saver) the chatmon draws less often, as it does in Linux's power-saver mode.
- **Windows:** attachments dragged out of Outlook, files out of a zip folder, and pictures out of a browser attach when dropped on the chat or pasted into it, as files on disk do.
- **macOS:** bubbles wait while a full-screen app is over the chatmon, as they do on Windows and Linux, and come once you're back. Something that needs you waits too: macOS lets only apps signed with an Apple Developer ID send notifications.
- **macOS:** **Start when I log in** makes Chatmon one of your Login Items, listed by name in System Settings › General › Login Items, and turning it off there shows in the menu too. Started at login by an older version, it moves over by itself.
- **macOS:** the menu bar icon is the companion's silhouette, drawn in the menu bar's own colour, light or dark.

### Fixes
- **Privacy:** Codex and Muse Code no longer keep a session of each question you ask them through Chatmon, and OpenAI's and xAI's APIs are asked not to store your questions (they keep them 30 days otherwise). Anthropic's API reads a chat's earlier turns from its cache, at a fraction of the price.
- **Linux:** something that needs you, under a full-screen app, reaches you as a notification on every desktop, with or without a tray. With no tray (GNOME, out of the box), Chatmon says once where its menu is.
- **Linux:** a laptop with two batteries gets its battery warnings for both together, as the desktop's battery icon shows them, not for the first alone.
- **Windows:** the file dialogs for attaching files and saving a chat open above the chatmon, never under it.
- **Windows:** an update's signature is checked by Windows itself, without PowerShell, so updates install on PCs where PowerShell is blocked.
- **macOS:** hooks and the `chatmon` command reach Chatmon whatever the length of your user name; past about 37 characters, its socket's address was too long for macOS.
- **macOS:** Chatmon says it needs macOS 13 or later, and says why when macOS asks whether it may reach a model server on your network.

## 0.6.0

### New
- **Chats you can come back to.** Your chats are kept on this computer, readable by you alone. **History** in the chat, or **Chats** in the menu, picks one up where you left off, and the whole conversation scrolls like a chat app's. Rename a chat, pin it to the top, save it as Markdown, or delete it.
- **Attach files, pictures and text.** The **+** in the chat, Ctrl+V, or dropping files on it. Text goes to every brain; pictures and PDFs to the ones that can read them, and a brain that can't says so first.
- **Much more without any AI.** Sums, unit conversions, the time and date, days until a day, coins and dice, passwords, notes, a stopwatch, and reminders by number. Ask me *help* to see it all. These are answered right away, never sent anywhere, and never become part of a chat.
- **Keeps out of your way.** Bubbles wait while a full-screen app, a presentation or Do Not Disturb is on, and the chatmon steps out of a full-screen app's way. Something that needs you still reaches you, as a system notification.
- **Breaks know when you're away.** Time away from the keyboard counts, locked or not, and so does the computer sleeping, on Windows, macOS and Linux.
- **Follows your accessibility settings.** Reduced motion stills the bubbles and the walking; high contrast uses plain bubbles in your desktop's colours, unless you've chosen otherwise.
- **Updates in one click.** Chatmon checks for a new version once a day, downloads it, and checks that it's the real one before it asks to install it. Turn it off under **Help & updates** in the menu.
- **What's new.** After an update, Chatmon shows what changed. **Help & updates → What's new** shows it again.
- **Report a problem** from the menu opens a GitHub issue with your Chatmon version and system filled in. When something goes wrong, Chatmon offers to report it.
- **Signed for Windows.** The installer, its uninstaller and Chatmon's own programs are signed by Randy Northrup, so Windows can tell where they came from.

### Changes
- **macOS:** the chatmon is on every Space, takes the keyboard only when you open the chat, and finds your AI tools and keys when started from Finder or at login. It also counts the system updates waiting.
- **Linux:** starting at login and the password prompt for updates follow the desktop's standards, and updates waiting are counted on Fedora, Arch and openSUSE too. Time away counts as a break on every desktop: the screen locking and the computer sleeping (through logind, GNOME and KDE), and time without input (on Hyprland, Sway, KDE and GNOME too).
- **Windows:** Chatmon has its own identity in Windows, Remote Desktop gets a Chatmon of its own, and a restart to finish Windows updates gets a heads-up.
- On Windows, Chatmon is compiled with Nuitka: the installer is about a sixth smaller.

### Fixes
- *Remind me how decorators work* is a question for the AI, not a reminder without a time.
- **macOS:** clicking the menu-bar icon no longer hides or brings out the chatmon.
- Two Chatmons started at the same moment can no longer take each other's place.
- **Windows:** the chatmon no longer vanishes when the pointer crosses it, it takes clicks again afterwards, and it no longer freezes for a few seconds at its first bubble.
- A bubble's first button (**OK**, a reminder's **Snooze**) takes clicks on Windows and macOS.

## 0.5.1

### Fixes
- On a slow or busy computer, every message from a hook or `chatmon quit` is heard, even with 60 arriving at once.
- macOS starts faster: no D-Bus lookup, and fewer checks on your agents in the first seconds.

## 0.5.0

### New
- **Installers** for Windows, macOS (Apple silicon and Intel), Ubuntu, Debian and Fedora. Chatmon starts from the Start menu, Launchpad or your app menu.
- `chatmon quit` closes the running Chatmon after it saves.

### Fixes
- Windows: an installed Chatmon no longer passes its own DLLs on to the programs it starts.

## 0.4.1

### Fixes
- **Security, Windows:** hooks check that Chatmon's pipe belongs to you before they send anything.
- Windows: connected agents show as connected, hooks run from any shell, no console window at login, and the menu no longer freezes.
- Unplugging the chatmon's monitor, or changing its scale, no longer breaks it.
- Logging off or shutting down saves your state.

## 0.4.0

### New
- **Model, effort and thinking** for the brain in use, picked from the menu and remembered for each brain.
- Each provider's current models.

### Fixes
- **Security:** images in answers aren't loaded, the hooks' socket is private, redirects are never followed, and malformed messages can't crash Chatmon.

## 0.3.0

### New
- Penguin companion is now **Chatmon**, with four new friends: a fire red panda, a ghost rabbit, a fairy axolotl and a leaf pangolin.
- **Painted chat bubbles**, one animated style for each chatmon.

### Changes
- About half the CPU while a bubble is showing, and while walking.
