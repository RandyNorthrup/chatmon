# Except handlers in chatmon/

Every `except` in `chatmon/`, read from the source with `ast` by `handlers_join2.py` and joined with the
classification made as each module was converted (phase A for all but the eight hub files, phase B for those).
**Logged**: the handler calls `logger` (debug for an error Chatmon carries on past, warning for one the person
should hear of, which used to be a stderr print). **Left**: the kinds in the plan's logging conventions
(convention 4): the exception is the answer, flow control, probing an API, the error reaches the person, a
routine per-item failure in a loop, or re-raised.

265 handlers: 108 logged, 157 left.

| Handler | Catches | Logged / left | Kind and reason |
|---|---|---|---|
| a11y.py:55 | `(OSError, AttributeError, ImportError, ValueError)` | logged | hidden (now logged): asking whether a screen reader runs failed; returns None (no reader). Logs only the exception |
| a11y.py:84 | `(ImportError, OSError)` | logged | hidden (now logged): winuia wouldn't load; falls back to the notification. Never logs the words |
| agents.py:103 | `FileExistsError` | left | flow: the backup's name is taken (two in one second), so the next name is tried |
| agents.py:110 | `BaseException` | left | re-raised: the half-written backup is removed first |
| agents.py:169 | `BaseException` | left | re-raised: the temporary copy is removed first |
| agents.py:180 | `ValueError` | left | reaches the person: AgentError "{file} isn't valid JSON (...); not touching it." |
| agents.py:283 | `AgentError` | logged | hidden: JsonHooks._groups reads an unreadable settings file as no hooks (not connected); the agent and the error, never the file's contents |
| agents.py:345 | `(OSError, subprocess.SubprocessError)` | left | reaches the person: AgentError "{command} failed: {error}" |
| agents.py:353 | `ValueError` | left | answer: the whole output or its last line, whichever is JSON |
| agents.py:418 | `OSError` | left | flow: no extensions folder, so that editor isn't installed |
| agents.py:475 | `AgentError` | logged | hidden: ClaudeCode.connected says False when Claude Code's command line can't be asked |
| agents.py:483 | `AgentError` | logged | hidden: ClaudeCode.legacy says False when it can't be asked |
| agents.py:503 | `AgentError` | logged | hidden: removing the marketplace fails and the disconnect or swap carries on |
| agents.py:509 | `AgentError` | logged | hidden: ClaudeCode.status carries on as if there were no plugin |
| agents.py:586 | `tomllib.TOMLDecodeError` | left | reaches the person: AgentError "{file} isn't valid TOML (...); not touching it." |
| agents.py:592 | `AgentError` | logged | hidden: Codex.connected says False for a config.toml it can't read |
| agents.py:600 | `AgentError` | logged | hidden: Codex.legacy says False for a config.toml it can't read |
| agents.py:623 | `tomllib.TOMLDecodeError` | left | answer: a candidate text without the notify line doesn't parse, so the next candidate |
| agents.py:653 | `tomllib.TOMLDecodeError` | left | reaches the person: the AgentError "Couldn't add the notify line cleanly" raised just after |
| agents.py:713 | `AgentError` | logged | hidden: Muse._installed says none installed when Muse Code can't be asked |
| agents.py:904 | `AgentError` | logged | hidden: Cursor._entries reads an unreadable hooks.json as no hooks |
| app.py:91 | `Exception` | logged | hidden (now logged): Background hands what failed to `then`, which says it; the traceback, which it doesn't show, goes to the debug log |
| app.py:1000 | `OSError` | logged | was a stderr print: saving the chat as Chatmon quits, a warning (nothing on screen to say it in by then) |
| app.py:1086 | `OSError` | left | reaches the person: "Couldn't save the chat" with the error |
| app.py:1235 | `ImportError` | left | probing: no QtDBus, so no portal file chooser (Qt's own is used) |
| app.py:1291 | `attachments.AttachError` | left | reaches the person: "Couldn't attach that" with the reason |
| app.py:1294 | `Exception` | logged | reaches the person, and an unexpected failure's traceback goes to the debug log |
| app.py:1465 | `(TypeError, ValueError)` | left | answer: whether the context size setting is a number; the default otherwise |
| app.py:1844 | `ValueError` | left | reaches the person: "That didn't change it: ..." in the box |
| app.py:1913 | `ImportError` | left | probing: no QtDBus, so no Linux session watcher |
| app.py:2437 | `(agents.AgentError, OSError)` | left | collected into the sentence that's logged as a warning just after (it was a stderr print) |
| app.py:2535 | `(agents.AgentError, OSError)` | left | reaches the person: each agent's error, said in the bubble |
| app.py:2919 | `OSError` | left | reaches the person: "Couldn't back up" with the error |
| app.py:2933 | `backup.BackupError` | left | reaches the person: "That backup can't be used" with the reason |
| app.py:3079 | `TypeError` | left | probing: the colour scheme signal was never connected (Qt older than 6.5) |
| app.py:3153 | `(OSError, OverflowError, ValueError)` | left | answer: a time outside what the platform's calendar can say has no day |
| app.py:3221 | `OSError` | logged | hidden (now logged): the instance lock can't be made (a read-only folder, a link there); Chatmon goes on without it |
| app.py:3229 | `OSError` | logged | flow when another Chatmon holds the lock (False, no log); any other error is logged and Chatmon goes on without it |
| app.py:3259 | `OSError` | logged | was a stderr print: claiming the pipe's name first on Windows; Qt listens on its own |
| app.py:3317 | `(AttributeError, OSError)` | logged | hidden (now logged): Windows' AppUserModelID couldn't be set |
| app.py:3324 | `OSError` | logged | was a stderr print: naming Chatmon for Windows' notifications |
| attachments.py:94 | `UnicodeDecodeError` | left | answer: probing whether bytes are UTF-16 text |
| attachments.py:100 | `UnicodeDecodeError` | left | answer: probing whether bytes are UTF-8 text (or cut mid-character) |
| attachments.py:177 | `(OSError, ValueError)` | logged | hidden: where the file is can't be told, so it's taken as on this computer; the error only, no path argument |
| attachments.py:252 | `AttributeError` | left | probing: libc has statfs$INODE64 on Intel Macs only |
| attachments.py:272 | `OSError` | left | reaches the person: AttachError "couldn't open {file} ({error})" |
| attachments.py:280 | `OSError` | left | reaches the person: AttachError "couldn't open {file} ({error})" |
| attachments.py:284 | `OSError` | left | reaches the person: AttachError "couldn't open {file} ({error})" |
| attachments.py:298 | `OSError` | left | reaches the person: AttachError "couldn't read {file} ({error})" |
| autostart.py:87 | `OSError` | left | answer: no Run value, so it doesn't start at login |
| autostart.py:105 | `OSError` | left | answer: no value under the old name, so nothing to move |
| autostart.py:135 | `OSError` | left | flow: no Run value, so nothing to bring up to date |
| autostart.py:156 | `OSError` | left | flow: no Run value to delete, so it's off already |
| backup.py:128 | `BaseException` | left | re-raised, after removing the half-written backup |
| backup.py:142 | `(OSError, zipfile.BadZipFile)` | left | reaches the person: raised as BackupError "isn't a Chatmon backup" |
| backup.py:169 | `(UnicodeDecodeError, ValueError, RecursionError)` | left | reaches the person: raised as BackupError "is damaged, so nothing was read" |
| brains.py:330 | `KeyError` | left | flow: `set.pop()` on an empty set ends the loop over URLs to look at again |
| brains.py:338 | `KeyError` | left | flow: the same, for the servers whose owner is to be looked at again |
| brains.py:356 | `OSError` | left | answer: nothing listening at the host and port is what `_look` asks |
| brains.py:406 | `ValueError` | left | answer: a host that isn't an IP address isn't a loopback one |
| brains.py:714 | `ValueError` | left | answer: `check_url`'s host isn't an IP address, so only "localhost" is local |
| brains.py:764 | `(OSError, ValueError, BrainError)` | left | probing: each local server says its context window one way; the other URLs' 404s, refusals and redirects are expected |
| brains.py:782 | `urllib.error.HTTPError` | left | re-raised: the refused redirect's (or error's) reply is closed first (M6A's unclosed `HTTPError 302`), then the error goes on to `learn_window` |
| brains.py:998 | `(KeyError, IndexError, TypeError)` | left | reaches the person: raised as BrainError "the answer wasn't in the expected shape" |
| brains.py:1037 | `RecursionError` | left | re-raised: as ValueError ("nested too deep"), the answer for a reply too deep to read |
| brains.py:1048 | `BrainError` | left | re-raised as it is |
| brains.py:1050 | `(AttributeError, KeyError, TypeError, IndexError, ValueError)` | left | reaches the person: raised as BrainError "the answer wasn't in the expected shape" |
| brains.py:1117 | `(ValueError, RecursionError)` | left | answer: a provider's error reply that isn't JSON is read as plain text |
| brains.py:1222 | `(ValueError, RecursionError)` | left | answer: a Claude Code line that isn't JSON is plain text (kept in `plain`) |
| brains.py:1251 | `(ValueError, RecursionError)` | left | answer: an event-stream event whose data isn't JSON isn't an event of the answer |
| brains.py:1346 | `OSError` | logged | hidden: the temp folder couldn't be listed for left-behind question folders; none removed |
| brains.py:1354 | `OSError` | left | routine loop: an entry gone or unreadable mid-scan |
| brains.py:1388 | `ProcessLookupError` | left | flow: no such process, the answer to "is it alive?" |
| brains.py:1390 | `OSError` | left | answer: someone else's process, so it's there |
| brains.py:1419 | `RuntimeError` | left | flow: the process ended and Qt let go of it before the last-resort kill |
| brains.py:1574 | `BrainError` | left | reaches the person: emitted as `failed` ("{brain}: {error}.") |
| brains.py:1594 | `TypeError` | left | probing: `disconnect()` with nothing connected raises TypeError (PyQt6) |
| brains.py:1614 | `TypeError` | left | probing: the same, for the reply's signals |
| brains.py:1695 | `OSError` | logged | hidden: a tool's answer file couldn't be read, so its stdout is used; logs the brain's name only, never the answer |
| brains.py:1701 | `BrainError` | left | reaches the person: emitted as `failed` ("{brain} didn't answer ({reason}).") |
| brains.py:1787 | `(ValueError, BrainError)` | left | reaches the person: emitted as `failed` |
| brains.py:1846 | `ValueError` | left | answer: a reply that isn't a JSON object is parsed as `{}`, which `_parsed` turns into "the answer wasn't in the expected shape" |
| brains.py:1849 | `BrainError` | left | reaches the person: emitted as `failed` (the Asker's own `_log_failure` keeps it at info, key scrubbed) |
| brains.py:1903 | `Exception` | logged | hidden: finding the brain failed, what was known is used (logged with `exc_info` before M6B; unchanged) |
| bubbleart.py:1265 | `(OSError, ValueError)` | logged | hidden: the painted bubbles' manifest.json can't be read or isn't JSON; every style is then drawn plain |
| bubbleart.py:1282 | `(FileNotFoundError, KeyError, TypeError, ValueError)` | logged | hidden: a style's art (its pictures, or its manifest entry) can't be loaded; that style is drawn plain |
| changelog.py:67 | `OSError` | logged | hidden: changelog.md (shipped with Chatmon) couldn't be read; no release notes shown |
| chats.py:156 | `(TypeError, ValueError, OverflowError)` | left | answer: a time that isn't a number reads as 0 |
| chats.py:190 | `(TypeError, ValueError, OverflowError, AttributeError)` | left | answer: data that isn't a chat is None |
| chats.py:248 | `FileNotFoundError` | left | flow: no file for that chat (one never saved, or a backup's chat not here yet) is the answer. Split out of the handler below so only real failures are logged |
| chats.py:250 | `(OSError, ValueError, RecursionError)` | logged | hidden: a chat file that can't be read or is damaged is taken as no chat (logs the chat's id, never its contents) |
| chats.py:258 | `OSError` | logged | hidden: the chats folder couldn't be listed (`recent`); no chats are shown |
| chats.py:277 | `OSError` | logged | hidden: the same, for `listing` (also a file gone between the listing and its stat) |
| chats.py:300 | `(OSError, ValueError, RecursionError)` | logged | hidden: a damaged or unreadable chat file is left out of the list (logs its path) |
| chats.py:308 | `(OSError, ValueError)` | logged | hidden: a chat you deleted couldn't be removed |
| chats.py:322 | `OSError` | logged | hidden: clearing the chats stopped part way; the count so far is returned |
| cli.py:96 | `FileNotFoundError` | left | flow: no state file yet (Chatmon hasn't run), so nothing chosen in Settings. Split out of the handler below |
| cli.py:98 | `(OSError, ValueError, AttributeError)` | logged | hidden (now logged): the state file can't be read, isn't JSON, or isn't a table; the language falls back to the settings file's or the system's. Logs the error only, never the file's contents |
| cli.py:106 | `FileNotFoundError` | left | flow: no settings file yet (Chatmon writes it the first time it runs), so the system's language. Split out of the handler below |
| cli.py:108 | `(OSError, ValueError)` | logged | hidden (now logged): config.toml can't be read or isn't TOML; the system's language. Logs the error only, never a value (the file can hold an API key) |
| cli.py:157 | `(AttributeError, OSError)` | logged | hidden (now logged): Windows' AllowSetForegroundWindow couldn't be called; the ask box still opens, maybe not in front |
| cli.py:198 | `ValueError` | left | answer: whether the hook's payload is JSON (parsing) |
| cli.py:212 | `(OSError, ValueError)` | logged | hidden (now logged): reading the hook's payload from stdin failed (closed or broken stdin); notify carries on with the arguments' payload. Logs the error only, never the payload; debug never reaches stderr, so notify still never prints |
| cli.py:296 | `(agents.AgentError, OSError)` | left | reaches the person: "{agent}: {error}" printed to stderr, and exit 1 |
| clickthrough.py:204 | `OSError` | logged | hidden: no X input shape (libX11 or libXext missing, no display, or no SHAPE extension); Qt's window mask takes over |
| events.py:123 | `OSError` | left | answer: request's None (not running, or no answer in time) |
| events.py:149 | `OSError` | left | flow: the ok is waited for only so the message isn't lost; a slow companion has it anyway (SENT) |
| events.py:152 | `OSError` | left | answer: ABSENT, nothing listening there |
| events.py:177 | `_QUEUE_FULL` | left | flow: a full queue of connections, tried again until the deadline, then re-raised |
| events.py:182 | `BaseException` | left | re-raised: the socket is closed first |
| events.py:211 | `(ValueError, RecursionError)` | left | answer: a line that isn't JSON is dropped |
| heads_up.py:53 | `Exception` | logged | hidden: psutil couldn't read the battery (logged in the ruff commit, kept) |
| heads_up.py:68 | `ImportError` | left | probing: no QtDBus (optional module) |
| heads_up.py:104 | `(OSError, ValueError)` | left | routine loop: one /sys battery that can't be read is skipped |
| heads_up.py:111 | `(OSError, ValueError)` | left | answer: which of energy_* or charge_* a battery has is told by which file reads |
| heads_up.py:138 | `OSError` | left | routine loop: a folder whose disk can't be read is skipped |
| heads_up.py:249 | `ImportError` | left | probing: no QtDBus, so no PackageKit |
| hotkey.py:498 | `ValueError` | left | reaches the person: the sentence is returned |
| hotkey.py:506 | `(AttributeError, OSError)` | left | reaches the person: the error's text is returned |
| i18n.py:178 | `(OSError, UnicodeDecodeError, CatalogError)` | logged | hidden: a translation that can't be read counts as not there; the next language (or English) is used |
| i18n.py:330 | `ValueError` | left | answer: a string that isn't brace-format has no placeholders to compare |
| i18n.py:400 | `(ValueError, SyntaxError, RecursionError)` | left | re-raised as CatalogError (a Plural-Forms formula gettext refuses) |
| keychain.py:89 | `(KeychainError, OSError)` | logged | hidden: whether a key is saved couldn't be asked; the menu takes it as none |
| keychain.py:101 | `(KeychainError, OSError)` | logged | hidden: the key couldn't be read (keychain unreachable or locked); None is used. The brain's name and the error's sentence only: KeychainError never holds a key |
| keychain.py:116 | `(KeychainError, OSError)` | left | reaches the person: returned as why it wasn't saved |
| keychain.py:128 | `(KeychainError, OSError)` | left | reaches the person: returned as why it wasn't removed |
| keychain.py:417 | `KeychainError` | logged | hidden: closing the Secret Service session failed |
| keychain.py:486 | `KeychainError` | logged | hidden: the keyring's own window (unlock, confirm) couldn't be shown; the caller still says to answer it |
| layer.py:170 | `(OSError, wayland.WaylandError)` | logged | hidden: asking the compositor what it offers failed (`offered()`); Qt then runs through XWayland with the stage as an X window |
| layer.py:237 | `OSError` | left | flow: writing our clipboard text to another app's pipe; EPIPE is how a reader that stops early (has what it wanted) ends it |
| layer.py:263 | `BlockingIOError` | left | flow: a non-blocking paste pipe with nothing in it yet |
| layer.py:265 | `OSError` | logged | hidden: reading a paste or a drop from another app's pipe failed; taken as its end, with what came so far (the error only, never the data) |
| layer.py:1056 | `ValueError` | logged | reaches the person: libxkbcommon can't read the compositor's keymap; was `print(f"chatmon: {exc}", file=sys.stderr)`, now `logger.warning("%s", exc)` |
| libdbus.py:310 | `Exception` | left | re-raised: the message is freed first |
| log.py:65 | `OSError` | left | re-raised |
| log.py:99 | `OSError` | left | reaches the caller: setup() returns None, and Chatmon runs on without a log file (there's nowhere to log it) |
| macnative.py:84 | `(AttributeError, OSError)` | logged | hidden (now logged): the Objective-C runtime or AppKit wouldn't load; every call says no |
| macnative.py:109 | `(ctypes.ArgumentError, OSError)` | logged | hidden (now logged): setCollectionBehavior: failed; returns False and Qt's way stays |
| macnative.py:213 | `(AttributeError, OSError, ValueError)` | logged | hidden (now logged): CoreGraphics' window list wouldn't load; returns None |
| macnative.py:237 | `(ctypes.ArgumentError, OSError)` | logged | hidden (now logged): reading the window list failed; says no full-screen app |
| macnative.py:268 | `OSError` | logged | hidden (now logged): ServiceManagement wouldn't load; no login item |
| macnative.py:413 | `(AttributeError, OSError)` | logged | hidden (now logged): the native menus' Objective-C class couldn't be made; Qt's menus instead |
| macnative.py:581 | `(AttributeError, OSError)` | logged | hidden (now logged): the workspace observers' class couldn't be made; nothing heard |
| macnative.py:611 | `(OSError, ValueError)` | logged | hidden (now logged): the notification names couldn't be found; the watcher doesn't listen |
| offline.py:108 | `(SyntaxError, ValueError, RecursionError, MemoryError)` | left | answer: what's typed isn't a sum |
| offline.py:116 | `_NotMath` | left | answer: not arithmetic |
| offline.py:118 | `ZeroDivisionError` | left | reaches the person: ValueError "can't divide by zero" |
| offline.py:121 | `(ValueError, TypeError)` | left | reaches the person: ValueError "that can't be worked out" |
| offline.py:272 | `ValueError` | left | answer: no such date (validating input) |
| offline.py:284 | `ValueError` | left | answer: no such date (validating input) |
| offline.py:487 | `FileNotFoundError` | left | flow: no phrase file for that language, so the next candidate or English (split out of the handler below) |
| offline.py:489 | `(OSError, ValueError)` | logged | hidden: a phrase file that's there but can't be read or isn't a phrase file; English instead |
| offline.py:628 | `OverflowError` | left | reaches the person: "That's too big a number for me." |
| offline.py:630 | `ValueError` | left | reaches the person: "Hmm: {problem}." |
| paths.py:68 | `OSError` | logged | reaches the person: was print(); "couldn't move {old} to {new}: {exc}" |
| paths.py:76 | `OSError` | logged | hidden: the mark that tells the app about the rename isn't left |
| paths.py:102 | `OSError` | logged | hidden: the folder can't be renamed whole, so it's moved file by file (a fallback) |
| paths.py:105 | `OSError` | logged | reaches the person: was print(); "couldn't move {old} to {new} yet: {exc}" |
| paths.py:121 | `OSError` | left | routine loop: on another volume every folder's rename fails alike, so it's merged; the whole folder's failed rename is logged at 102 |
| paths.py:132 | `OSError` | left | routine loop: on another volume every file's rename fails alike, so it's copied; logged once at 102 |
| paths.py:135 | `OSError` | logged | reaches the person: was print(); "couldn't move {item} yet: {exc}" |
| paths.py:139 | `OSError` | logged | hidden: the old folder isn't removed (something's still in it, perhaps a clash skipped without a word) |
| paths.py:148 | `FileNotFoundError` | left | answer: no mark, so not the first run since the rename |
| paths.py:150 | `OSError` | logged | hidden: the mark can't be removed, and it says True anyway |
| paths.py:205 | `(OSError, ValueError, TypeError)` | logged | hidden: macOS's own temporary folder can't be had, so the usual (too long) socket path |
| paths.py:210 | `OSError` | logged | hidden: the socket's private folder can't be made or made private |
| paths.py:284 | `(OSError, subprocess.SubprocessError)` | logged | hidden: the login shell's environment can't be read, so only the usual folders go on PATH; the error, never the shell's output |
| paths.py:289 | `OSError` | left | flow: killpg on a process group that's gone already |
| paths.py:342 | `OSError` | left | flow: no such registry key, so none of that PATH |
| penguin.py:240 | `TypeError` | left | probing: PyQt6's `disconnect()` raises TypeError when nothing is connected (unhosting the ask box) |
| penguin.py:400 | `TypeError` | left | probing: `createStandardContextMenu(pos)` where the widget's takes no position (QLineEdit's); asked again without |
| penguin.py:418 | `TypeError` | left | probing: `triggered.disconnect()` with nothing connected, before rewiring a context-menu action |
| penguin.py:805 | `(AttributeError, RuntimeError)` | left | routine loop: the frame clock reads the screen's refresh rate every tick; a screen being unplugged fails for a frame or two until `_screen_removed` moves the stage, and the default rate is right meanwhile (a log line per frame is what M6B rules out) |
| portowner.py:35 | `(OSError, ValueError)` | logged | hidden: None ("can't say") for a port's listeners, so Automatic won't trust a local server |
| portowner.py:49 | `OSError` | left | flow: no /proc/net/tcp6 (IPv6 off); the file that isn't there is the answer |
| portowner.py:71 | `(OSError, subprocess.SubprocessError)` | logged | hidden: lsof can't be run or doesn't answer in time, so None |
| presence.py:58 | `(AttributeError, OSError)` | logged | hidden (now logged): GetLastInputInfo failed; idle time None |
| presence.py:75 | `(AttributeError, OSError)` | logged | hidden (now logged): SHQueryUserNotificationState failed; not quiet |
| presence.py:114 | `(AttributeError, OSError)` | logged | hidden (now logged): the full-screen check failed; not covered |
| presence.py:134 | `(AttributeError, OSError)` | logged | hidden (now logged): SystemParametersInfo failed; setting None |
| presence.py:151 | `(AttributeError, OSError)` | logged | hidden (now logged): the high contrast setting couldn't be read; None |
| presence.py:165 | `(AttributeError, OSError)` | logged | hidden (now logged): CGEventSourceSecondsSinceLastEventType failed; idle time None |
| presence.py:197 | `(AttributeError, OSError, ValueError)` | logged | hidden (now logged): an NSWorkspace display option couldn't be read; None |
| presence.py:210 | `ImportError` | left | probing: no QtDBus (split from the handler below) |
| presence.py:223 | `(RuntimeError, TypeError)` | logged | hidden (now logged): a D-Bus call failed; None. Logs interface and method, never arguments |
| presence.py:234 | `ImportError` | left | probing: no QtDBus |
| presence.py:281 | `(AttributeError, OSError)` | logged | hidden (now logged): libX11 or libXss wouldn't load on an X11 session; X readings say they can't |
| presence.py:384 | `TypeError` | left | probing: disconnect() with nothing connected (convention 4's own example) |
| presence.py:431 | `(AttributeError, ImportError, RuntimeError, TypeError)` | left | probing: Qt before 6.10 has no accessibility(); PyQt6 6.11 has the signal as a method |
| presence.py:450 | `ImportError` | left | probing: no QtDBus, so no Linux listeners |
| presence.py:488 | `(ImportError, OSError, RuntimeError)` | logged | hidden (now logged): winfocus.Focus couldn't start; Focus counts as off |
| presence.py:599 | `(AttributeError, ImportError, RuntimeError)` | left | probing: Qt before 6.10 has no contrast preference |
| releasecheck.py:140 | `Refused` | left | reaches the person: `verify-update` prints why to stderr for the installer to show (stays print, convention 6) |
| releasecheck.py:143 | `OSError` | left | reaches the person: printed the same way |
| reminders.py:363 | `ValueError` | left | answer: February 30, or the 29th in a year without one |
| reminders.py:448 | `(OSError, OverflowError, ValueError)` | left | answer: further off than the clock can show, said as "a long way off" |
| reminders.py:517 | `(AttributeError, KeyError, TypeError, ValueError)` | logged | hidden: a saved reminder that can't be read is skipped; the exception's type only, never the reminder's words |
| report.py:42 | `OSError` | left | answer: no os-release file means no distribution name |
| report.py:62 | `ImportError` | left | probing: no QtGui |
| settings.py:294 | `BaseException` | left | re-raised: write_private closes the descriptor and removes the half-written temporary file first |
| settings.py:303 | `OSError` | logged | hidden (now logged): POSIX, the folder can't be opened to sync the rename; the file is written, the rename may not be on the disk yet. Logs the folder and the error |
| settings.py:308 | `OSError` | logged | hidden (now logged): POSIX, syncing the folder fails (some filesystems refuse fsync on a folder); carries on. Logs the folder and the error |
| settings.py:326 | `FileNotFoundError` | left | flow: no file is a first run (or one you deleted), never a reason to bring the backup back |
| settings.py:328 | `OSError` | logged | hidden (now logged): the file is there but can't be read; read_kept sets it aside and tells the person it was damaged, not why. Logs the path and the error, never the contents |
| settings.py:337 | `OSError` | logged | hidden (now logged): the good file's backup (`<name>.bak`) can't be compared or written; no backup this time, the file itself is fine. Logs the file and the error |
| settings.py:344 | `OSError` | logged | hidden (now logged): after a damaged file, the backup can't be read (or there is none); started afresh, and the person is told that, not why the backup couldn't be used. One handler: in this rare recovery path "no backup" is the line a bug report needs |
| settings.py:365 | `(UnicodeDecodeError, ValueError, RecursionError)` | left | answer: whether the bytes are JSON (parsing); None sends read_kept to the backup, and the person hears the file was damaged |
| settings.py:378 | `OSError` | left | reaches the person: read_kept's sentence says "I couldn't even move it aside" |
| settings.py:504 | `ValueError` | left | answer: whether a setting's text is a number (parsing) |
| settings.py:520 | `(OSError, UnicodeDecodeError, tomllib.TOMLDecodeError)` | left | reaches the person: "config.toml: <error>" returned as why the file couldn't be read (the error, never a value) |
| shortcutportal.py:79 | `(OSError, libdbus.Failure)` | left | reaches the person: every request then fails with "couldn't reach your desktop's session bus" |
| shortcutportal.py:91 | `queue.Empty` | left | flow: no work waiting |
| shortcutportal.py:106 | `(libdbus.Failure, TypeError, ValueError, KeyError, IndexError, AttributeError)` | left | reaches the person: "Your desktop couldn't set the shortcut." |
| shortcutportal.py:114 | `(ConnectionError, libdbus.Failure)` | left | reaches the person: "couldn't reach your desktop's session bus" |
| shortcutportal.py:146 | `libdbus.Failure` | left | reaches the person: no GlobalShortcuts portal (NO_PORTAL) |
| shortcutportal.py:206 | `libdbus.Failure` | left | answer: the session is already gone |
| sound.py:60 | `(wave.Error, EOFError)` | left | answer: bytes that aren't a WAV it can scale are played as they are |
| sound.py:117 | `ImportError` | left | probing: QtMultimedia not installed |
| sound.py:161 | `OSError` | logged | hidden (now logged): a cue's file couldn't be read; the next player is tried. Logs the path (a file of Chatmon's own) |
| sound.py:179 | `RuntimeError` | logged | hidden (now logged): PlaySound failed; counted in `failed` as before |
| sound.py:244 | `OSError` | logged | hidden (now logged): a Linux player wouldn't start; the next player is tried |
| sound.py:254 | `subprocess.TimeoutExpired` | left | flow: a player still running at quit is killed |
| sound.py:283 | `(AttributeError, OSError)` | logged | hidden (now logged): the system's own player couldn't be made; Qt's alone |
| sysnotify.py:26 | `ImportError` | left | probing: no QtDBus, so the slot is a plain method |
| sysnotify.py:83 | `ImportError` | left | probing: no QtDBus (split from the handler below) |
| sysnotify.py:90 | `(RuntimeError, TypeError, AttributeError)` | logged | hidden (now logged): sending the notification failed; False. Logs the exception, never the title or body |
| sysnotify.py:108 | `ImportError` | left | probing: no QtDBus, so no bus |
| updates.py:79 | `(PackageNotFoundError, ValueError, OSError)` | left | answer: not installed as a distribution, or no readable direct_url.json, means not an editable install |
| updates.py:102 | `(OSError, subprocess.SubprocessError)` | logged | hidden: the package manager's query couldn't run or timed out; the next one is asked |
| updates.py:122 | `OSError` | left | answer: a folder that isn't there (or can't be looked at) isn't the .pkg's root-owned app |
| updates.py:183 | `(ImportError, OSError, AttributeError, ValueError)` | left | reaches the person: returned as the signer ("Unknown", the error), which `verify` puts in its sentence |
| updates.py:242 | `OSError` | left | reaches the person: "it couldn't be copied to be installed ({error})" |
| updates.py:344 | `(ImportError, AttributeError, RuntimeError)` | left | probing: QNetworkInformation or its backend may not exist in this Qt |
| updates.py:437 | `(ValueError, RecursionError)` | left | answer: GitHub's reply isn't JSON; said as "GitHub's answer about the latest release wasn't readable" |
| updates.py:488 | `OSError` | left | reaches the person: "couldn't save the download ({error})" |
| updates.py:507 | `OSError` | logged | hidden: writing the download failed; the person hears only that it didn't finish (the abort's words), so the cause is logged |
| updates.py:538 | `OSError` | left | reaches the person: "couldn't keep the download ({error})" |
| wayland.py:164 | `OSError` | logged | hidden: connecting to the compositor's socket (WAYLAND_DISPLAY) failed; no overlay, the stage is an X window |
| wayland.py:230 | `(BlockingIOError, InterruptedError)` | left | flow: the socket can't take more now; flush() says so and the write notifier finishes later |
| wayland.py:232 | `OSError` | left | reaches the person: recorded as the connection's error ("sending: ..."), which layer.py's warning "lost the Wayland connection (...); quitting." gives |
| wayland.py:247 | `(BlockingIOError, InterruptedError)` | left | flow: nothing more to read now |
| wayland.py:249 | `OSError` | left | reaches the person: recorded as the connection's error ("reading: ..."), given by the same warning |
| wincaret.py:48 | `(AttributeError, OSError)` | logged | hidden (now logged): whether Magnifier is open couldn't be told; no caret |
| windrop.py:122 | `OSError` | logged | hidden (now logged): GetData failed for a format; None. Logs the format's number, never the data |
| windrop.py:145 | `OSError` | left | probing: some streams can't seek, and are read from where they are (the comment says so) |
| windrop.py:223 | `OSError` | logged | hidden (now logged): OleGetClipboard failed; Qt reads the clipboard instead. Never the clipboard's contents |
| windrop.py:305 | `Exception` | logged | hidden: a drag coming in failed (logged in the ruff commit, kept) |
| windrop.py:314 | `Exception` | logged | hidden: a drag moving over failed (logged in the ruff commit, kept) |
| windrop.py:333 | `Exception` | logged | hidden: a drop failed (logged in the ruff commit, kept) |
| winfocus.py:77 | `OSError` | left | answer: the shell didn't answer this time; `active` is None ("can't be told") |
| winfocus.py:80 | `(OSError, AttributeError, ValueError)` | logged | hidden (now logged): the Focus thread ends; `active` stays None |
| winrt.py:142 | `(AttributeError, OSError)` | logged | hidden (now logged): ole32 wouldn't load; COM can't be joined |
| winrt.py:233 | `Exception` | logged | hidden: a delegate's handler failed inside Windows' thread (logged in the ruff commit, kept) |
| wintoast.py:160 | `(AttributeError, OSError)` | logged | hidden (now logged): the process's app ID couldn't be read; None |
| wintoast.py:192 | `FileNotFoundError` | left | answer: nothing to remove |
| wintoast.py:255 | `OSError` | logged | hidden (now logged): NotificationSetting couldn't be read; the toast is tried anyway |
| wintoast.py:296 | `OSError` | logged | hidden (now logged): Action Center's toasts couldn't be listed; the tags so far |
| wintoast.py:373 | `OSError` | logged | hidden (now logged): showing a toast failed; the balloon instead (`why_not` is never shown). Logs the HRESULT, never the toast's XML or words |
| wintoast.py:444 | `OSError` | logged | hidden (now logged): hiding a toast failed; False |
| wintoast.py:456 | `OSError` | logged | hidden (now logged): clearing Action Center failed |
| wintoast.py:470 | `OSError` | left | routine loop: removing each handler from a toast Windows may have let go of |
| winuia.py:206 | `(AttributeError, OSError)` | logged | hidden (now logged): the announcer couldn't be made (a Windows before 1709, or a failure); the notification instead. Once per run |
| winuia.py:233 | `(AttributeError, OSError)` | logged | hidden (now logged): which app is in front couldn't be told; counts as not Chatmon |
| xkb.py:73 | `OSError` | left | probing: libxkbcommon, an optional library, isn't there; `library()` answers None and the overlay warns "libxkbcommon not found; can't type in the ask box." |
| xkb.py:114 | `AttributeError` | left | probing: a libxkbcommon older than 0.4 lacks the Latin-lookup calls; shortcuts work as before, on Latin layouts only |
