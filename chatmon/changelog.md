# What's new in Chatmon

Each version's changes, newest first: what Chatmon shows after it updates, and each release's notes.

## 0.6.0

### New
- **Updates in one click.** Chatmon checks for a new version once a day, downloads it, and checks that it's the real one before it asks to install it. Turn it off under **Help & updates** in the menu.
- **What's new.** After an update, Chatmon shows what changed. **Help & updates → What's new** shows it again.
- **Report a problem** from the menu opens a GitHub issue with your Chatmon version and system filled in. When something goes wrong, Chatmon offers to report it.
- **Signed for Windows.** The installer, its uninstaller and Chatmon's own programs are signed by Randy Northrup, so Windows can tell where they came from.

### Changes
- On Windows, Chatmon is compiled with Nuitka: the installer is about a sixth smaller.

### Fixes
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
