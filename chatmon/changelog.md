# What's new in Chatmon

Each version's changes, newest first: what Chatmon shows after it updates, and each release's notes.

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

### Fixes
- **Privacy:** Codex and Muse Code no longer keep a session of each question you ask them through Chatmon, and OpenAI's and xAI's APIs are asked not to store your questions (they keep them 30 days otherwise). Anthropic's API reads a chat's earlier turns from its cache, at a fraction of the price.
- **Linux:** something that needs you, under a full-screen app, reaches you as a notification on every desktop, with or without a tray. With no tray (GNOME, out of the box), Chatmon says once where its menu is.
- **Linux:** a laptop with two batteries gets its battery warnings for both together, as the desktop's battery icon shows them, not for the first alone.
- **Windows:** the file dialogs for attaching files and saving a chat open above the chatmon, never under it.
- **Windows:** an update's signature is checked by Windows itself, without PowerShell, so updates install on PCs where PowerShell is blocked.

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
