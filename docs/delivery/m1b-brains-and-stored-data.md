# M1B: brains, chats and stored data

Work unit M1B of the [roadmap](ROADMAP.md), items M1B-01 to M1B-17 of the [assessment](ASSESSMENT.md#m1b-brains-chats-and-stored-data-brainspy-chatspy-memorypy-settingspy-new-keychainpy-new-backuppy).
Branch `wave1/m1b`, from `improve/assessment-fixes` at `5346385`. Reports are in [reports/m1b/](reports/m1b/).

## Rationale

The assessment is the brief. Order: security (M1B-01..05, 08), durability (06, 07), error messages and calls that
never block (09..11), then features (12..17). Everything stays inside the files M1B owns (`brains.py`, `chats.py`,
`memory.py`, `settings.py`, new `keychain.py`, new `backup.py`) plus one new module, `portowner.py`, and tests. What the
app has to call is written down under **Integration notes** for M7.

### Reuse decisions

- `settings.private()` grows into one writer for every file Chatmon keeps (`write_private`): created 0600 with
  `os.open`, flushed and synced, then swapped in. `chats.py`, `memory.py` and `State` all use it instead of three copies
  of write-then-chmod.
- `brains.reachable()` / `look_again()` already answer the menu without waiting. The non-blocking finder (M1B-11) and
  the socket-owner check (M1B-03) extend that cache rather than adding a second one.
- `Asker` stays the one object that asks a brain. Streaming, the error messages, the non-blocking cancel and the brain
  test all live in it, so the app's signals (`answered`, `failed`) keep their meaning and `partial` is added.
- The SSE parsing is new: nothing in the code reads event streams yet.
- Tests follow the project's style: real `QNetworkAccessManager` against a local `http.server` replaying event streams,
  real processes for command brains (a Python script standing in for `claude`), the real Windows Credential Manager,
  and a pretend Secret Service on a private D-Bus (like `tests/fake_portal.py`) for Linux.

### Decisions taken while planning

- **M1B-02.** `claude --help` (Claude Code 2.1.288, checked 2026-11-14) lists `--strict-mcp-config` and
  `--permission-mode` with the choices `acceptEdits, auto, bypassPermissions, manual, dontAsk, plan`. `default` is still
  accepted (an unlisted alias), so the assessment's `--permission-mode default` would work today but could stop
  working without notice. The brain uses the listed `dontAsk`: anything not already approved is denied, with nobody
  asked. With `--tools ""` and `--strict-mcp-config` there's nothing to approve anyway. Streaming needs
  `--output-format stream-json --verbose --include-partial-messages`; all three are in the same help. Checked without
  sending a question: an empty stdin stops at "Input must be provided" after the options are parsed, and an invalid
  mode stops at "argument 'bogus' is invalid".
- **M1B-03.** "Belongs to the user": every listening socket on the port is owned by this account (Linux
  `/proc/net/tcp{,6}` uid; Windows `GetExtendedTcpTable` owning process, then that process's token user compared with
  ours; macOS `lsof`, which without root only sees our own processes). A brain picked by name (menu, Settings,
  `brain = "ollama"`) is the user's own choice and isn't checked; only Automatic is. A server confirmed once is
  remembered by M7 in state (`brains.confirm_server`).
- **M1B-04.** Answers from other brains aren't dropped from the history but replaced by a placeholder, so the number
  of turns (which the chat's summary counts) stays the same. A summary made from every brain's answers isn't given to
  a brain that can read files.
- **M1B-07.** The `.bak` is written when a file is read and found good, so it's the last copy known to be good; saves
  never touch it, and there's no moment without a `state.json`.
- **M1B-12.** `timeout_seconds` becomes how long a brain may go without sending anything: a long answer that keeps
  arriving isn't cut off. Command-line brains other than Claude Code print only at the end and aren't streamed.
- **M1B-13.** Keys are stored under the brain's name. Linux uses the Secret Service's `plain` session: the key goes over
  your own session bus, which only you can reach; the encrypted session needs Diffie-Hellman and AES, which the
  standard library doesn't have. Windows keeps keys with `CRED_PERSIST_LOCAL_MACHINE` (not roaming).
- **M1B-16.** The backup holds Settings changes (an allowlist of state keys), memory, notes, reminders and, if asked,
  chats. It never holds `config.toml`, which can carry `api_key` values inline, nor anything from the keychain.
- **M1B-17.** On Windows the chats folder moves to `%LOCALAPPDATA%` (non-roaming), moving existing chats once, because
  a roaming profile copies `%APPDATA%` to the domain's server and attached text is kept in the chat files.

### Decisions taken while delivering

- **Cancelling on Windows (M1B-10).** `taskkill /T` is gone. It follows the parent each process names, and Windows
  hands a finished process's number to the next one, so on a busy machine it ended programs that only shared a dead
  parent's number: twice it ended the test run itself (exit 127, no traceback). `_end_tree` walks the tree from a
  snapshot, takes a process only if it was made after its parent, and ends each through a handle opened on it, on a
  thread. A cancelled `QProcess` is handed to Qt (`setParent(None)`, `sip.transferto`) to delete once it has ended:
  deleted with its `Asker` while Qt still thought it was running, Qt killed and waited inside the destructor and the
  app aborted (0xC0000409, reproduced 7 times in 10 before, 0 in 12 after). `test_an_asker_let_go_of_straight_after_
  cancelling_takes_nothing_down` runs that scenario four times in a child process.
- **The menu never reads a key (M1B-13).** `keychain.has()` finds whether a key is saved without reading it, so the
  macOS Keychain's "Chatmon wants to use…" question can only come with a question actually asked. `Brain.available()`
  and `why_not()` use `has_key()`; `key()` reads, once a run.
- **Finder (M1B-11)** looks up to three rounds off the screen's thread: a server found running is then asked whose it
  is.
- **Brain settings (M1B-06).** `load_brains(ai, problems)` leaves out a value of the wrong kind (a `command` given as
  one string used to become a command line made of its letters) and says so, instead of crashing at start.
- **Chats in tests (M1B-17).** The Windows chats folder is `%LOCALAPPDATA%` only when that's inside `%USERPROFILE%`,
  otherwise the profile's own `AppData\Local`: a test that moves the profile (as `tests/test_app_smoke.py` does, without
  setting `LOCALAPPDATA`) never writes into the real user's chats.
- **One placeholder sentence** stands in for another brain's answer: "(Another AI answered this; its answer isn't
  passed on here.)"

### Findings not changed

None of the 17 findings turned out wrong. Two are only partly closable inside M1B's files, and are delivered as APIs
with the app's part in **Integration notes**: M1B-04 (the app must pass the guard) and M1B-07's "the user is told"
(the app must show `State.problem` / `Memory.problem`).

## Readiness review

[reports/m1b/readiness.md](reports/m1b/readiness.md).

## Verification

Commands, counts and logs are in [reports/m1b/](reports/m1b/); the ledger below binds each receipt to the files it
covers.

- Whole suite on Windows, `python -m pytest -q -p no:cacheprovider -rfs`: 589 passed, 67 skipped
  (`pytest-windows.txt`; the baseline was 514 passed, 59 skipped). `ruff check .`: clean (`ruff.txt`).
- M1B's test files on Windows: 142 passed, 8 skipped (`pytest-m1b-windows.txt`); on Linux (WSL Arch, Python 3.14.9,
  PyQt6 6.11.0, `dbus-run-session`): 143 passed, 7 skipped (`pytest-linux.txt`). Every skip names its platform.
- Red drills: 33 on Windows (`drill-spec.json`, `drills.log`, summary `drills.json`) and 6 on Linux
  (`drill-spec-linux.json`, `drills-linux.log`), all green, red for the named test, restored and green. The Linux ones
  run in a standalone copy in WSL because this worktree's `.git` names a Windows path.
- Two drills first survived and were test gaps, now closed: the locked Secret Service had no key in it, and the
  let-go crash test ran its scenario once against a crash that comes about seven times in ten.
- macOS (Keychain, `lsof`), the GitHub Linux runner (`dbus-run-session`) and the Windows runner (Credential Manager in
  its session) are pending CI (checkpoint).
- While other workers' suites ran, `test_app_smoke.py::test_a_hook_reaches_it` and
  `test_events.py::test_send_without_a_running_companion` (not M1B's) failed because another suite held this user's
  Chatmon pipe; they passed alone (`pytest-pipe-rerun.txt`) and in the final run. Once, under that load, the replay
  helper's 10 s silence limit ran out before a pretend Claude Code had started; time isn't what those tests check, so
  the helper allows 30 s (the app's default is 180).

## Integration notes

APIs as delivered, for M7 (and the owners named).

1. **Streaming (M7-01).** `Asker.partial(str)` gives each new piece of an answer as it's written (not the text so far);
   `answered(str)` the whole of it; `failed(str)` a sentence. Wire `partial` to the ask box's `append_partial(text)`.
   `Asker.ask(..., timeout_s)` is now how long a brain may go without sending anything. Streaming is on for every API
   brain unless `stream = false`; servers that answer with plain JSON still work.
2. **Errors (M7-02).** `failed` already reads "Anthropic API: invalid x-api-key (HTTP 401). Check its key in
   ANTHROPIC_API_KEY or the one saved in Settings." Nothing to wire; Try again / Ask another brain can follow it.
3. **Brain test (M7-03).** `brain.test(parent=None, timeout_s=60) -> BrainTest`, started at once;
   `BrainTest.finished(ok: bool, text: str, seconds: float)`, `BrainTest.cancel()`.
4. **Keys (M7-03).** `keychain.set(name, key) -> str | None` (None: saved; else why not), `keychain.delete(name) ->
   str | None`, `keychain.get(name) -> str | None`, `keychain.has(name) -> bool`, `keychain.where() -> str` (to say
   where keys go). `name` is the brain's name (`"anthropic-api"`). `Brain.key()` uses the settings file's `api_key`,
   then the environment variable, then the keychain; `Brain.has_key()` answers without reading. Never put a key in
   state or `config.toml`.
5. **Finding the brain (M1B-11).** `brains.Finder(parent)`; `find(brains, configured, picked, then, prefer=None) ->
   Brain | None` returns what's known at once and calls `then(brain)` on the screen's thread with the settled answer;
   `finder.last`. Replace `self._brain()` (which waits) in `submit` with it.
6. **Local servers (M1B-03).** Automatic now skips a model server that isn't yours. `brains.confirm_server(url)` lets
   Automatic use one anyway; keep `brains.confirmed_servers()` in state under `"trusted_servers"` (already in
   `backup.SETTINGS_KEYS`) and hand each back with `confirm_server` at start. When `brains.reachable(url)` is true but
   `brains.trusted(url)` false, offer "Use the model server at localhost:11434?". A brain picked by name is used as
   before.
7. **No other brains' answers for brains that read files (M1B-04).** In `app._send`, with `guard = brain.reads_files()`:
   `pairs = chat.history(brain.label, name=brain.name, own_only=guard)`;
   `neutral = chat.history(brain.label if guard else "", name=brain.name if guard else "", own_only=guard)`;
   `summary, summarized = chat.summary_for(brain.name, own_only=guard)`, passed to `context.plan` in place of
   `chat.summary, chat.summarized`; in `_compacted`, `chat.set_summary(text, covers, by=brain.name if guard else "")`.
8. **Brain per chat (M1B-15, M7-09).** Record `by=brain.name` on both `chats.Message`s in `_answered`; `Chat.brain` then
   follows the last answer. Choose with `prefer=self.chat.brain` (`brains.choose` or `Finder.find`). Ask another
   brain: `i, q = chat.last_question()`; history `chat.history(other.label, name=other.name,
   own_only=other.reads_files(), before=i)`; send `q.text` (give it `q.sent`, the attached text, only if you choose to
   and never to a brain that reads files); then add the pair with `by=other.name`.
9. **Config problems (M1B-06).** `load_config` returns per-key sentences in `config_error`
   ("config.toml: size should be a number, so it's 120 for now; …"). The start-up bubble says "Using the defaults for
   now", which is now true only for those keys: reword it when the file parsed. Coerce the merged overrides too:
   `config, problems = settings.coerce(merge(config, overrides))`, and pass a list to
   `brains.load_brains(config["ai"], problems)` and add what it says.
10. **Damaged files (M1B-07).** Show `self.state.problem` and `self.memory.problem` (when not None) in a bubble at
    start.
11. **Backup (M1B-16, M7-09).** Export: `self.save()`, then `backup.export(path, self.state, self.memory,
    self.chat_book if with_chats else None) -> Contents` (`contents.summary()` says what went in; `backup.default_name()`
    suggests a file name). Import: `contents = backup.read(path)` (raises `BackupError` with a sentence; nothing
    changed), confirm with `contents.summary()`, then `backup.bring_back(contents, self.state, self.memory,
    self.chat_book) -> str`, then read everything again: `self.config, self.config_error = self._load_config()`,
    `self.reminders = reminders.ReminderBook.from_list(self.state.get("reminders", []))`, apply the settings as
    `_reload` does, and refresh the menus.
12. **Command brains' environment (M1B-01).** Nothing to wire. A user's own command brain names its sign-in variables in
    `env = [...]` (documented in the `config.toml` template).
13. **Stale question folders (M1B-05).** Nothing to wire: the first `Asker` made removes them.
14. **Tests (M0, M6A).** `tests/test_app_smoke.py`'s `companion` fixture could set `LOCALAPPDATA` beside `APPDATA`
    (the chats folder already stays in the test's profile without it). `tests/conftest.py` could make every test use
    `keychain.use(keychain.InMemory())`, so no test reads the real keychain (today the app smoke tests read it,
    read-only). The Linux keychain tests need `dbus-run-session` (Ubuntu's `dbus` package) on the runner, as
    `test_portal_bus.py` does; without it they skip.
15. **Shared code (M1A, M6B).** `portowner._runs_as_me` repeats `winpipe._peer_is_me`'s token check, kept apart while
    M1A changes `winpipe.py`; M6B may fold them into one `winpipe.pid_is_me(pid)`.

## Changelog notes

- Answers appear as they're written, for the Anthropic, OpenAI and Gemini APIs, every OpenAI-compatible provider, and
  Claude Code.
- When a brain fails, you see what the provider said, the HTTP status, and what to do: check the key, wait for a rate
  limit, or try later. No connection says you look offline, or that a model server isn't running.
- API keys can be saved in your system's keychain (Windows Credential Manager, macOS Keychain, GNOME Keyring, KWallet
  or KeePassXC) instead of an environment variable. Keys never appear in error messages.
- Test a brain: it's asked "Say OK" and you see how long it took, or the error.
- Each chat remembers which brain it was having; carrying a chat on asks that brain again. You can ask another brain
  the same question.
- Back up and move: export your settings, memory, notes, reminders and (if you like) chats to one zip, and bring them
  back on another computer. Keys are never in a backup, and a backup is checked before anything is changed.
- Command-line brains get only the environment variables they need, not your other keys. Claude Code runs with no MCP
  servers and never asks for permission. Automatic uses only a model server you run yourself, or one you've confirmed.
  A brain that can read your files never sees other brains' answers.
- Settings that are wrong in `config.toml` are named, one by one, and the rest still apply; Chatmon no longer fails to
  start over one. A damaged state or memory file is kept aside and the last good copy used.
- Files Chatmon keeps are private from the moment they're made, and reach the disk before they replace the old ones.
- Cancelling an answer never freezes the screen, and on Windows it no longer risks ending unrelated programs.
- On Windows, chats are kept in your local app-data folder, never the roaming one; existing chats move there once.
- `timeout_seconds` is now how long a brain may go without a word, so long answers aren't cut off.

## README notes

- **Privacy, attached text** (with M1A-11): text you attach is kept with its chat so you can carry on after a restart;
  it's sent again only to the brain you first gave it to, stored only on this computer (on Windows in
  `%LOCALAPPDATA%\chatmon\chats`, never the roaming profile), nothing is written with **Keep chat history** off, and
  **Clear chat history** removes it.
- **Keys:** from an environment variable or the system keychain (Settings, AI). Never written to Chatmon's files,
  never in a backup, never in an error message.
- **Your own command brain:** list the variables it signs in with in `env = [...]`; nothing else of your environment
  is passed to it.
- **Automatic and model servers:** only a server running under your own account is picked automatically (shared
  computers); pick one by name, or confirm it once, to use another.
- **Backups:** what's in one (Settings changes, memory, notes, reminders, chats if chosen) and what never is (keys,
  `config.toml`).
- **config.toml:** a wrong value is named and falls back on its own; `timeout_seconds` is the time without a word;
  `stream = false` for a server that can't stream.
- **Files:** Chatmon's folders are yours alone (0700, files 0600); a damaged file is kept as `<name>.bad-<time>` and
  the last good copy (`<name>.bak`) is used.

## Reconciliation, wave 4 (2026-11-14)

Wave 4 read the CI runs this plan's checkpoint was waiting for, and re-ran every check whose receipt had gone stale. The
evidence is for **fb19cb9** (`improve/assessment-fixes`), bound to the repository's own bytes: LF, as git stores them
(ROADMAP.md, *Canonical bytes*). Two other workers were changing code at the same time (wayland: the overlay and
`ci.yml`; followups: packaging, the requirements and the mypy settings). Their merges will make some of these receipts
stale again.

**What CI answered** (run 43677128712 on fb19cb9, every job green; each leg's result for this plan's tests is in
[reports/m1b/ci/observed.txt](reports/m1b/ci/observed.txt)):

- **CI-MACOS.** `test_macos_keychain_keeps_replaces_and_forgets_a_key` and
  `test_a_socket_of_yours_is_yours_and_a_closed_port_nobodys` passed on all three macOS legs.
- **CI-LINUX.** The three Secret Service tests passed on all three Ubuntu legs, not skipped, because `ci.yml` installs
  Ubuntu's `dbus`. So did the Linux port-owner tests and the file and folder modes.
- **CI-WINDOWS.** Both real Credential Manager tests passed on all three Windows legs. None skipped with error 1312.
- **M7-WIRING.** M7 wired every API in the integration notes. They are M7's verified criteria (M7-01, M7-02, M7-03,
  M7-09 and INT-M1B in [m7-integration.md](m7-integration.md)).

**What was re-run.** The whole suite on Windows ([wave4/suite-windows.log](reports/wave4/suite-windows.log): 1241
passed, 148 skipped). Then the plan's 28 Windows drills that still apply and its 6 Linux drills (in WSL), every one green,
red and green again. Five Windows drills mutated text that later merges rewrote. They are listed in
[wave4/drills-left-out.txt](reports/m1b/wave4/drills-left-out.txt). Two criteria had no other drill: AC-M1B-05 (the
stale-folder tidy now runs on its own thread) and AC-M1B-12 (the stream's pieces are emitted in `_reply_read`). They have
new ones, W4-M1B-05-stale-folders and W4-M1B-12-partial, both green, red and green. The requirements were reviewed
again against the amended rules ([wave4/readiness.md](reports/m1b/wave4/readiness.md)).

**Receipts.** Every earlier passing receipt is now marked stale, as history, with its hashes untouched. The W4-
receipts replace them. Nothing remains open in M1B on fb19cb9.

```quality-ledger
{
  "schema_version": 1,
  "work": {
    "id": "M1B",
    "title": "Brains, chats and stored data",
    "scope_revision": 1,
    "brief": "docs/delivery/ASSESSMENT.md",
    "brief_reason": null,
    "rules": [
      {
        "path": "docs/delivery/ROADMAP.md",
        "revision": "fb19cb9+wave4"
      },
      {
        "path": "pyproject.toml",
        "revision": "fb19cb9"
      }
    ],
    "inputs": [
      "tests/conftest.py",
      "tests/drills/run.py",
      "docs/delivery/reports/wave4/cilog.py",
      "docs/delivery/reports/wave4/wsl_drills.py"
    ],
    "environment": {
      "platform": "windows",
      "tools": {
        "python": "3.14.10",
        "pytest": "9.2.0",
        "ruff": "0.17.4",
        "pyqt6": "6.11.0"
      }
    }
  },
  "requirements": [
    {
      "id": "M1B-01",
      "statement": "A command-line brain's environment is an allowlist: PATH, home, app-data and temp folders, SystemRoot, locale, proxy variables, CHATMON_INTERNAL, plus that brain's own auth variables.",
      "priority": "critical",
      "acceptance": [
        "AC-M1B-01"
      ],
      "superseded_by": null
    },
    {
      "id": "M1B-02",
      "statement": "Claude Code runs with --strict-mcp-config and a listed --permission-mode that never asks, checked against the installed CLI's --help.",
      "priority": "critical",
      "acceptance": [
        "AC-M1B-02"
      ],
      "superseded_by": null
    },
    {
      "id": "M1B-03",
      "statement": "Automatic picks a local model server only if its listening socket belongs to this user, or the user confirmed it once.",
      "priority": "critical",
      "acceptance": [
        "AC-M1B-03"
      ],
      "superseded_by": null
    },
    {
      "id": "M1B-04",
      "statement": "Brains that can read files (command brains not tools_off) are not sent earlier answers from other brains.",
      "priority": "critical",
      "acceptance": [
        "AC-M1B-04"
      ],
      "superseded_by": null
    },
    {
      "id": "M1B-05",
      "statement": "Stale chatmon-ask-* folders left in the temp folder by a killed Chatmon are removed at startup.",
      "priority": "normal",
      "acceptance": [
        "AC-M1B-05"
      ],
      "superseded_by": null
    },
    {
      "id": "M1B-06",
      "statement": "Each config.toml key is coerced to its default's type and a sane range, falling back per key, and bad keys are reported through config_error.",
      "priority": "critical",
      "acceptance": [
        "AC-M1B-06"
      ],
      "superseded_by": null
    },
    {
      "id": "M1B-07",
      "statement": "Saves flush before the swap; a damaged state or memory file is renamed *.bad-<time>, the last good .bak is used, and the user is told.",
      "priority": "critical",
      "acceptance": [
        "AC-M1B-07"
      ],
      "superseded_by": null
    },
    {
      "id": "M1B-08",
      "statement": "Files are created 0600 with os.open, and the state and config folders are 0700.",
      "priority": "critical",
      "acceptance": [
        "AC-M1B-08"
      ],
      "superseded_by": null
    },
    {
      "id": "M1B-09",
      "statement": "An HTTP status of 400 or above shows the provider's error, message or detail plus the status and a hint; host not found says offline.",
      "priority": "normal",
      "acceptance": [
        "AC-M1B-09"
      ],
      "superseded_by": null
    },
    {
      "id": "M1B-10",
      "statement": "Cancelling a command-line answer never blocks the screen's thread.",
      "priority": "normal",
      "acceptance": [
        "AC-M1B-10"
      ],
      "superseded_by": null
    },
    {
      "id": "M1B-11",
      "statement": "There is a non-blocking brain lookup API with a cached result.",
      "priority": "normal",
      "acceptance": [
        "AC-M1B-11"
      ],
      "superseded_by": null
    },
    {
      "id": "M1B-12",
      "statement": "Anthropic Messages, OpenAI Responses, Chat Completions (Gemini's included) and Claude Code stream; partial answers are emitted as they arrive; cancelling stops the stream.",
      "priority": "normal",
      "acceptance": [
        "AC-M1B-12"
      ],
      "superseded_by": null
    },
    {
      "id": "M1B-13",
      "statement": "keychain.py stores and reads keys in the OS store without new dependencies; brains use a stored key when the environment variable is absent; keys are never logged.",
      "priority": "normal",
      "acceptance": [
        "AC-M1B-13"
      ],
      "superseded_by": null
    },
    {
      "id": "M1B-14",
      "statement": "A brain test asks 'Say OK' and returns the time taken or the clearer error.",
      "priority": "normal",
      "acceptance": [
        "AC-M1B-14"
      ],
      "superseded_by": null
    },
    {
      "id": "M1B-15",
      "statement": "A chat records its brain, carrying it on uses that brain, and there is an API to ask another brain the same question.",
      "priority": "normal",
      "acceptance": [
        "AC-M1B-15"
      ],
      "superseded_by": null
    },
    {
      "id": "M1B-16",
      "statement": "backup.py exports Settings changes, memory, notes, reminders and optionally chats to one zip and imports it with validation; keys are never exported.",
      "priority": "normal",
      "acceptance": [
        "AC-M1B-16"
      ],
      "superseded_by": null
    },
    {
      "id": "M1B-17",
      "statement": "Attached text saved with a chat is re-sent only to the brain it was first given to, nothing is written with Keep chat history off, Clear chat history removes it, and it stays on this computer (non-roaming on Windows).",
      "priority": "normal",
      "acceptance": [
        "AC-M1B-17"
      ],
      "superseded_by": null
    }
  ],
  "acceptance": [
    {
      "id": "AC-M1B-01",
      "requirement": "M1B-01",
      "given": "A canary variable and a brain auth variable in Chatmon's environment",
      "when": "a command brain runs and reports its own environment",
      "then": "the canary is absent; PATH, the temp folder, CHATMON_INTERNAL=1 and the brain's declared auth variable are present",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M1B-02",
      "requirement": "M1B-02",
      "given": "The Claude Code preset",
      "when": "its command line is built",
      "then": "it has --tools '', --strict-mcp-config, --permission-mode dontAsk, --no-session-persistence and the stream-json flags, all named in claude 2.1.288 --help",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M1B-03",
      "requirement": "M1B-03",
      "given": "A loopback server owned by this user and a listening port owned by another account",
      "when": "Automatic chooses a brain",
      "then": "only the owned server is picked; another account's port is picked only after confirm_server, and a brain picked by name is used either way",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M1B-04",
      "requirement": "M1B-04",
      "given": "A chat with answers from brain A and B",
      "when": "the history is built for B as a brain that can read files",
      "then": "A's answers are replaced by a placeholder, the turn count is unchanged, and a summary not made for B is withheld",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M1B-05",
      "requirement": "M1B-05",
      "given": "A chatmon-ask-<pid> folder of a process that has ended and one of a live process",
      "when": "an Asker is made (startup)",
      "then": "the dead process's folder is removed and the live one's kept",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M1B-06",
      "requirement": "M1B-06",
      "given": "config.toml with size='big', breaks.every_minutes='60', updates_every_hours=10**9 and a non-table brain",
      "when": "it is loaded",
      "then": "size falls back to 120, every_minutes becomes 60, the hours clamp to 168, the brain is dropped, and config_error names each key",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M1B-07",
      "requirement": "M1B-07",
      "given": "A damaged state.json (or memory.json) with a good .bak",
      "when": "it is loaded and then saved",
      "then": "the damaged file is kept as *.bad-<time>, the .bak's data is used, problem says so, and every save syncs before os.replace",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M1B-08",
      "requirement": "M1B-08",
      "given": "A umask of 022 (POSIX)",
      "when": "settings, state, memory and chats are written",
      "then": "each file is 0600 from its creation (also the temporary one) and the state and config folders are 0700",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M1B-09",
      "requirement": "M1B-09",
      "given": "A local server answering 401, 403, 429, 500 and 404 with error bodies, and an unknown host",
      "when": "a question is asked",
      "then": "failed carries the provider's message, 'HTTP <status>' and the matching hint, or says it looks offline",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M1B-10",
      "requirement": "M1B-10",
      "given": "A command brain that is still running (a .cmd file and its child on Windows)",
      "when": "cancel() is called",
      "then": "it returns at once (well under 0.5 s) and the process tree ends soon after",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M1B-11",
      "requirement": "M1B-11",
      "given": "Brains whose availability needs probing",
      "when": "Finder.find is called",
      "then": "it returns without probing on the caller's thread, delivers the brain through its callback, and reuses the cached result while fresh",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M1B-12",
      "requirement": "M1B-12",
      "given": "A local server replaying Anthropic, Responses and Chat Completions event streams, and a pretend claude printing stream-json",
      "when": "a question is asked",
      "then": "partial emits each piece of text in order, answered emits the whole, and cancel mid-stream stops it with nothing emitted after",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M1B-13",
      "requirement": "M1B-13",
      "given": "A unique test name in the OS store (the real Credential Manager on Windows; a pretend Secret Service on Linux; the login keychain on macOS)",
      "when": "a key is set, read, replaced and deleted",
      "then": "each step round-trips, the entry is always removed, a brain without its variable uses the stored key, and neither repr nor errors show the key",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M1B-14",
      "requirement": "M1B-14",
      "given": "A local server that answers OK, and one that answers 401",
      "when": "a brain test runs",
      "then": "it reports success with the seconds taken, or the clearer HTTP error",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M1B-15",
      "requirement": "M1B-15",
      "given": "A chat answered by a brain",
      "when": "it is saved, loaded and carried on, and the last question is asked of another brain",
      "then": "the chat's brain survives the round trip, choose prefers it, and last_question gives the question with the history before it",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M1B-16",
      "requirement": "M1B-16",
      "given": "Settings, memory, notes, reminders and chats on this computer, and keys in config and the keychain",
      "when": "a backup is exported and imported elsewhere",
      "then": "everything listed comes back, no key appears in the zip, and bad zips (traversal, too big, wrong version, bad JSON, unknown files) are refused without changing anything",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M1B-17",
      "requirement": "M1B-17",
      "given": "A chat with attached text",
      "when": "it is saved, carried on with another brain, saved with Keep off, and cleared",
      "then": "the text goes only to the brain first given it (by name), nothing is written with Keep off, Clear removes the file, and on Windows the folder is under LOCALAPPDATA with old chats moved",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    }
  ],
  "tasks": [
    {
      "id": "T-M1B-A",
      "purpose": "Command brains: environment allowlist, Claude Code flags, stale temp folders removed",
      "acceptance": [
        "AC-M1B-01",
        "AC-M1B-02",
        "AC-M1B-05"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/brains.py",
          "action": "modify"
        },
        {
          "path": "tests/test_brains.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-M1B-01-behavior",
        "EV-M1B-01-red",
        "EV-M1B-02-behavior",
        "EV-M1B-02-red",
        "EV-M1B-05-behavior",
        "EV-M1B-05-red",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-RED-M1B-01-allowlist",
        "W4-RED-M1B-02-strict-mcp",
        "W4-RED-M1B-05-stale-folders"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M1B-B",
      "purpose": "Automatic trusts only local servers whose socket is ours, or confirmed",
      "acceptance": [
        "AC-M1B-03"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/portowner.py",
          "action": "create"
        },
        {
          "path": "chatmon/brains.py",
          "action": "modify"
        },
        {
          "path": "tests/test_portowner.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-M1B-03-behavior",
        "EV-M1B-03-behavior-linux",
        "EV-M1B-03-red",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-BEH-CI-LINUX",
        "W4-BEH-CI-MACOS",
        "W4-RED-M1B-03-owner-check"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M1B-C",
      "purpose": "One private, synced, atomic writer; config values checked; damaged files kept and the backup used",
      "acceptance": [
        "AC-M1B-06",
        "AC-M1B-07",
        "AC-M1B-08"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/settings.py",
          "action": "modify"
        },
        {
          "path": "chatmon/memory.py",
          "action": "modify"
        },
        {
          "path": "chatmon/chats.py",
          "action": "modify"
        },
        {
          "path": "tests/test_settings.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-M1B-06-behavior",
        "EV-M1B-06-red",
        "EV-M1B-07-behavior",
        "EV-M1B-07-red",
        "EV-M1B-08-behavior",
        "EV-M1B-08-behavior-linux",
        "EV-M1B-08-red",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-BEH-CI-LINUX",
        "W4-BEH-CI-MACOS",
        "W4-RED-M1B-06-range",
        "W4-RED-M1B-07-kept-aside",
        "W4-RED-M1B-08-file-mode"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M1B-D",
      "purpose": "Chats: no cross-brain answers for brains that read files, brain per chat, attached text kept locally and only for its brain",
      "acceptance": [
        "AC-M1B-04",
        "AC-M1B-15",
        "AC-M1B-17"
      ],
      "depends_on": [
        "T-M1B-C"
      ],
      "changes": [
        {
          "path": "chatmon/chats.py",
          "action": "modify"
        },
        {
          "path": "chatmon/brains.py",
          "action": "modify"
        },
        {
          "path": "tests/test_chats.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-M1B-04-behavior",
        "EV-M1B-04-red",
        "EV-M1B-15-behavior",
        "EV-M1B-15-red",
        "EV-M1B-17-behavior",
        "EV-M1B-17-red",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-RED-M1B-04-placeholder",
        "W4-RED-M1B-15-chat-brain",
        "W4-RED-M1B-17-only-its-brain"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M1B-E",
      "purpose": "Readable HTTP errors",
      "acceptance": [
        "AC-M1B-09"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/brains.py",
          "action": "modify"
        },
        {
          "path": "tests/test_brains.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-M1B-09-behavior",
        "EV-M1B-09-red",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-RED-M1B-09-status"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M1B-F",
      "purpose": "Cancel never blocks; a non-blocking, cached brain lookup",
      "acceptance": [
        "AC-M1B-10",
        "AC-M1B-11"
      ],
      "depends_on": [
        "T-M1B-B"
      ],
      "changes": [
        {
          "path": "chatmon/brains.py",
          "action": "modify"
        },
        {
          "path": "tests/test_brains.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-M1B-10-behavior",
        "EV-M1B-10-red",
        "EV-M1B-11-behavior",
        "EV-M1B-11-red",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-RED-M1B-10-no-wait",
        "W4-RED-M1B-11-finder"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M1B-G",
      "purpose": "Streaming answers for the HTTP APIs and Claude Code",
      "acceptance": [
        "AC-M1B-12"
      ],
      "depends_on": [
        "T-M1B-A",
        "T-M1B-E",
        "T-M1B-F"
      ],
      "changes": [
        {
          "path": "chatmon/brains.py",
          "action": "modify"
        },
        {
          "path": "tests/test_streaming.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-M1B-12-behavior",
        "EV-M1B-12-red",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-RED-M1B-12-partial"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M1B-H",
      "purpose": "Keys in the OS keychain",
      "acceptance": [
        "AC-M1B-13"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/keychain.py",
          "action": "create"
        },
        {
          "path": "chatmon/brains.py",
          "action": "modify"
        },
        {
          "path": "tests/test_keychain.py",
          "action": "create"
        },
        {
          "path": "tests/fake_secrets.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-M1B-13-behavior",
        "EV-M1B-13-behavior-linux",
        "EV-M1B-13-red",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-BEH-CI-LINUX",
        "W4-BEH-CI-MACOS",
        "W4-BEH-CI-WINDOWS",
        "W4-RED-M1B-13-saved-key"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M1B-I",
      "purpose": "A brain test",
      "acceptance": [
        "AC-M1B-14"
      ],
      "depends_on": [
        "T-M1B-E"
      ],
      "changes": [
        {
          "path": "chatmon/brains.py",
          "action": "modify"
        },
        {
          "path": "tests/test_streaming.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-M1B-14-behavior",
        "EV-M1B-14-red",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-RED-M1B-14-seconds"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M1B-J",
      "purpose": "Backup and move",
      "acceptance": [
        "AC-M1B-16"
      ],
      "depends_on": [
        "T-M1B-C"
      ],
      "changes": [
        {
          "path": "chatmon/backup.py",
          "action": "create"
        },
        {
          "path": "tests/test_backup.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-M1B-16-behavior",
        "EV-M1B-16-behavior-linux",
        "EV-M1B-16-red",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-BEH-CI-LINUX",
        "W4-BEH-CI-MACOS",
        "W4-RED-M1B-16-no-secrets"
      ],
      "blocker": null,
      "superseded_by": null
    }
  ],
  "evidence": [
    {
      "id": "EV-M1B-readiness-1",
      "acceptance": [
        "AC-M1B-01",
        "AC-M1B-02",
        "AC-M1B-03",
        "AC-M1B-04",
        "AC-M1B-05",
        "AC-M1B-06",
        "AC-M1B-07",
        "AC-M1B-08",
        "AC-M1B-09",
        "AC-M1B-10",
        "AC-M1B-11",
        "AC-M1B-12",
        "AC-M1B-13",
        "AC-M1B-14",
        "AC-M1B-15",
        "AC-M1B-16",
        "AC-M1B-17"
      ],
      "kind": "readiness",
      "status": "stale",
      "command": [],
      "method": "Read the assessment's M1B section, the roadmap and the ledger against the code at 5346385 and claude --help 2.1.288; findings, gaps and decisions written to the readiness report.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m1b/readiness.md",
        "sha256": "121492776a404d54c69d154413b12a30ecbbfe90d1c81be669b244fa034649f8"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        }
      ],
      "scope_sha256": "ec3ef0f96f7c88cc33199ec165dddec42f13bf24fd3d69c6e391ba42004c1731",
      "red": null,
      "reason": "The plan's narrative was completed after delivery (decisions, verification, integration notes), which changes the scope digest; requirements and acceptance are unchanged. Next action: none, superseded by EV-M1B-readiness-2."
    },
    {
      "id": "EV-M1B-readiness-2",
      "acceptance": [
        "AC-M1B-01",
        "AC-M1B-02",
        "AC-M1B-03",
        "AC-M1B-04",
        "AC-M1B-05",
        "AC-M1B-06",
        "AC-M1B-07",
        "AC-M1B-08",
        "AC-M1B-09",
        "AC-M1B-10",
        "AC-M1B-11",
        "AC-M1B-12",
        "AC-M1B-13",
        "AC-M1B-14",
        "AC-M1B-15",
        "AC-M1B-16",
        "AC-M1B-17"
      ],
      "kind": "readiness",
      "status": "stale",
      "command": [],
      "method": "Re-read the readiness review against the completed plan: the 17 requirements, their acceptance criteria and task coverage are unchanged; the narrative now records the delivered decisions and the app-side parts left as integration notes.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m1b/readiness.md",
        "sha256": "121492776a404d54c69d154413b12a30ecbbfe90d1c81be669b244fa034649f8"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        }
      ],
      "scope_sha256": "8ec85593933f0b09c8c403b398b47069f2f0aef991bce4afd402c0bd96e3004f",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-01-behavior",
      "acceptance": [
        "AC-M1B-01"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_backup.py",
        "tests/test_chats.py",
        "tests/test_settings.py",
        "tests/test_brains.py",
        "tests/test_streaming.py",
        "tests/test_keychain.py",
        "tests/test_portowner.py",
        "tests/test_context.py"
      ],
      "method": "M1B's test files run on Windows 11 under QT_QPA_PLATFORM=offscreen, with real Qt objects, a local replay server, real processes and the real Credential Manager; 142 passed, 8 skipped (platform reasons listed in the artifact). The tests for AC-M1B-01 are among them.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/pytest-m1b-windows.txt",
        "sha256": "fa82b58ba58c5133dd0b112ad0c39eb1a1a0a8d00504d6038cec3eb42e1865b4"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "d388e0b560b0fda778c180ad86373eeaa0a7e481f9940514c854e050058980cf"
        }
      ],
      "scope_sha256": "a893fa05d6c21322cdb98ecddf136e1d24ca3e93c8a94b6e71ad22beecdd4224",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-01-red",
      "acceptance": [
        "AC-M1B-01"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m1b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m1b/drills.log"
      ],
      "method": "Red drill M1B-01-allowlist (Windows 11, in a temporary copy of the worktree made by the harness): green on the original, chatmon/brains.py mutated once, the named tests failed with pytest's exit 1 printing the expected test, original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/drills.log",
        "sha256": "b9f8ebe5b6cb15e052432227ef378a612d459b200f363fbf2a3d8d223e092443"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "d388e0b560b0fda778c180ad86373eeaa0a7e481f9940514c854e050058980cf"
        }
      ],
      "scope_sha256": "a893fa05d6c21322cdb98ecddf136e1d24ca3e93c8a94b6e71ad22beecdd4224",
      "red": {
        "mutation": "In chatmon/brains.py, replace '    out = {k: v for k, v in environ.items() if k.upper() in exact or (starts and k.upper().startswith(starts))}' with '    out = dict(environ)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_allowlist_takes_names_in_any_case_and_endings_after_a_star",
        "observed_diagnostic": "_____ test_the_allowlist_takes_names_in_any_case_and_endings_after_a_star _____",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "e357d1fc52f9818030cd983ac99e7dfd1309d1cf7a11d091046ce6780746d0e4"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-02-behavior",
      "acceptance": [
        "AC-M1B-02"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_backup.py",
        "tests/test_chats.py",
        "tests/test_settings.py",
        "tests/test_brains.py",
        "tests/test_streaming.py",
        "tests/test_keychain.py",
        "tests/test_portowner.py",
        "tests/test_context.py"
      ],
      "method": "M1B's test files run on Windows 11 under QT_QPA_PLATFORM=offscreen, with real Qt objects, a local replay server, real processes and the real Credential Manager; 142 passed, 8 skipped (platform reasons listed in the artifact). The tests for AC-M1B-02 are among them.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/pytest-m1b-windows.txt",
        "sha256": "fa82b58ba58c5133dd0b112ad0c39eb1a1a0a8d00504d6038cec3eb42e1865b4"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "d388e0b560b0fda778c180ad86373eeaa0a7e481f9940514c854e050058980cf"
        }
      ],
      "scope_sha256": "a893fa05d6c21322cdb98ecddf136e1d24ca3e93c8a94b6e71ad22beecdd4224",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-02-red",
      "acceptance": [
        "AC-M1B-02"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m1b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m1b/drills.log"
      ],
      "method": "Red drill M1B-02-strict-mcp (Windows 11, in a temporary copy of the worktree made by the harness): green on the original, chatmon/brains.py mutated once, the named tests failed with pytest's exit 1 printing the expected test, original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/drills.log",
        "sha256": "b9f8ebe5b6cb15e052432227ef378a612d459b200f363fbf2a3d8d223e092443"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "d388e0b560b0fda778c180ad86373eeaa0a7e481f9940514c854e050058980cf"
        }
      ],
      "scope_sha256": "a893fa05d6c21322cdb98ecddf136e1d24ca3e93c8a94b6e71ad22beecdd4224",
      "red": {
        "mutation": "In chatmon/brains.py, replace '\"--tools\", \"\", \"--strict-mcp-config\", \"--permission-mode\", \"dontAsk\",' with '\"--tools\", \"\", \"--permission-mode\", \"dontAsk\",'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_claude_code_is_started_without_tools_mcp_servers_or_anyone_asked",
        "observed_diagnostic": "____ test_claude_code_is_started_without_tools_mcp_servers_or_anyone_asked ____",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "b85da580a79e0d052421080e97ec02771cff147c24c5063c9ad3db837a0e92db"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-03-behavior",
      "acceptance": [
        "AC-M1B-03"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_backup.py",
        "tests/test_chats.py",
        "tests/test_settings.py",
        "tests/test_brains.py",
        "tests/test_streaming.py",
        "tests/test_keychain.py",
        "tests/test_portowner.py",
        "tests/test_context.py"
      ],
      "method": "M1B's test files run on Windows 11 under QT_QPA_PLATFORM=offscreen, with real Qt objects, a local replay server, real processes and the real Credential Manager; 142 passed, 8 skipped (platform reasons listed in the artifact). The tests for AC-M1B-03 are among them.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/pytest-m1b-windows.txt",
        "sha256": "fa82b58ba58c5133dd0b112ad0c39eb1a1a0a8d00504d6038cec3eb42e1865b4"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f144a4878c07ce2b3375d71ec36c59e7c2b330e071ce0814b11716ce985d084f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_portowner.py",
          "sha256": "0dac6b0ce7b977c5facb5f7b4cee185c73442799a90be4208628e5a5c9b65f70"
        }
      ],
      "scope_sha256": "bf9598243c219459b8f1fce2f36d4073646fd55e1485b371edbd8855f162d8ed",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-03-behavior-linux",
      "acceptance": [
        "AC-M1B-03"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "/var/tmp/m1b-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_backup.py",
        "tests/test_chats.py",
        "tests/test_settings.py",
        "tests/test_brains.py",
        "tests/test_streaming.py",
        "tests/test_keychain.py",
        "tests/test_portowner.py",
        "tests/test_context.py"
      ],
      "method": "The same test files on Linux (WSL Arch, kernel 6.18, Python 3.14.9, PyQt6 6.11.0, dbus-run-session for the pretend Secret Service); 143 passed, 7 skipped. Covers AC-M1B-03's Linux paths.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/pytest-linux.txt",
        "sha256": "855f1c38c2dbb05f986e22595fb32fe378b7b663ad71fede554a52caaafb8d5e"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f144a4878c07ce2b3375d71ec36c59e7c2b330e071ce0814b11716ce985d084f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_portowner.py",
          "sha256": "0dac6b0ce7b977c5facb5f7b4cee185c73442799a90be4208628e5a5c9b65f70"
        }
      ],
      "scope_sha256": "bf9598243c219459b8f1fce2f36d4073646fd55e1485b371edbd8855f162d8ed",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-03-red",
      "acceptance": [
        "AC-M1B-03"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m1b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m1b/drills.log"
      ],
      "method": "Red drill M1B-03-owner-check (Windows 11, in a temporary copy of the worktree made by the harness): green on the original, chatmon/brains.py mutated once, the named tests failed with pytest's exit 1 printing the expected test, original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/drills.log",
        "sha256": "b9f8ebe5b6cb15e052432227ef378a612d459b200f363fbf2a3d8d223e092443"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f144a4878c07ce2b3375d71ec36c59e7c2b330e071ce0814b11716ce985d084f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_portowner.py",
          "sha256": "0dac6b0ce7b977c5facb5f7b4cee185c73442799a90be4208628e5a5c9b65f70"
        }
      ],
      "scope_sha256": "bf9598243c219459b8f1fce2f36d4073646fd55e1485b371edbd8855f162d8ed",
      "red": {
        "mutation": "In chatmon/brains.py, replace '        if b.automatic() and b.available(wait) and (not b.local or trusted(expand(b.url), wait)):' with '        if b.automatic() and b.available(wait):'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_automatic_uses_only_a_model_server_of_yours_or_one_you_confirmed",
        "observed_diagnostic": "____ test_automatic_uses_only_a_model_server_of_yours_or_one_you_confirmed ____",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "3256ab9804802586e0fb597edaf843f15536b8cb66eccc6c7378daee6e17086c"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-04-behavior",
      "acceptance": [
        "AC-M1B-04"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_backup.py",
        "tests/test_chats.py",
        "tests/test_settings.py",
        "tests/test_brains.py",
        "tests/test_streaming.py",
        "tests/test_keychain.py",
        "tests/test_portowner.py",
        "tests/test_context.py"
      ],
      "method": "M1B's test files run on Windows 11 under QT_QPA_PLATFORM=offscreen, with real Qt objects, a local replay server, real processes and the real Credential Manager; 142 passed, 8 skipped (platform reasons listed in the artifact). The tests for AC-M1B-04 are among them.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/pytest-m1b-windows.txt",
        "sha256": "fa82b58ba58c5133dd0b112ad0c39eb1a1a0a8d00504d6038cec3eb42e1865b4"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "030235c7a0355e75be5c58d738ffd5d7710b9912bf8e0bf5c43104e09d4b1430"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "707a8deabab87af6f9463bd2b1139fde8f91cef18341252d4c23dc728470dbef"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "29fb53787edc38856d7908b9b4cac24c255030f4c9c83a9d7ec91f5c1986ec4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "e79110e36d8beeb15b2bdf0f97058a2227c082197c9bbdfcd8ce4e120801fd46"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "91c590f2b26ad1dde2373d6f6619fff6198a38f0ccb480d287b82b22776cee31"
        }
      ],
      "scope_sha256": "c80c18bd0515d0f8db890e50df4b4373fc0a301c71a1aaeab7b0664491c72c19",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-04-red",
      "acceptance": [
        "AC-M1B-04"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m1b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m1b/drills.log"
      ],
      "method": "Red drill M1B-04-placeholder (Windows 11, in a temporary copy of the worktree made by the harness): green on the original, chatmon/chats.py mutated once, the named tests failed with pytest's exit 1 printing the expected test, original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/drills.log",
        "sha256": "b9f8ebe5b6cb15e052432227ef378a612d459b200f363fbf2a3d8d223e092443"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "030235c7a0355e75be5c58d738ffd5d7710b9912bf8e0bf5c43104e09d4b1430"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "707a8deabab87af6f9463bd2b1139fde8f91cef18341252d4c23dc728470dbef"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "29fb53787edc38856d7908b9b4cac24c255030f4c9c83a9d7ec91f5c1986ec4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "e79110e36d8beeb15b2bdf0f97058a2227c082197c9bbdfcd8ce4e120801fd46"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "91c590f2b26ad1dde2373d6f6619fff6198a38f0ccb480d287b82b22776cee31"
        }
      ],
      "scope_sha256": "c80c18bd0515d0f8db890e50df4b4373fc0a301c71a1aaeab7b0664491c72c19",
      "red": {
        "mutation": "In chatmon/chats.py, replace '                out.append((question, m.text if not own_only or _same(m, brain, name) else OTHER_ANSWER))' with '                out.append((question, m.text))'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_brain_that_reads_files_never_gets_another_brains_answers",
        "observed_diagnostic": "_______ test_a_brain_that_reads_files_never_gets_another_brains_answers _______",
        "before": [
          {
            "path": "chatmon/chats.py",
            "sha256": "030235c7a0355e75be5c58d738ffd5d7710b9912bf8e0bf5c43104e09d4b1430"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/chats.py",
            "sha256": "b0f4ec8aa15e6aa411fcfc554ce1416cae0d8cc67fb6cb173e1ed27fb198d419"
          }
        ],
        "after": [
          {
            "path": "chatmon/chats.py",
            "sha256": "030235c7a0355e75be5c58d738ffd5d7710b9912bf8e0bf5c43104e09d4b1430"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-05-behavior",
      "acceptance": [
        "AC-M1B-05"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_backup.py",
        "tests/test_chats.py",
        "tests/test_settings.py",
        "tests/test_brains.py",
        "tests/test_streaming.py",
        "tests/test_keychain.py",
        "tests/test_portowner.py",
        "tests/test_context.py"
      ],
      "method": "M1B's test files run on Windows 11 under QT_QPA_PLATFORM=offscreen, with real Qt objects, a local replay server, real processes and the real Credential Manager; 142 passed, 8 skipped (platform reasons listed in the artifact). The tests for AC-M1B-05 are among them.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/pytest-m1b-windows.txt",
        "sha256": "fa82b58ba58c5133dd0b112ad0c39eb1a1a0a8d00504d6038cec3eb42e1865b4"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "d388e0b560b0fda778c180ad86373eeaa0a7e481f9940514c854e050058980cf"
        }
      ],
      "scope_sha256": "a893fa05d6c21322cdb98ecddf136e1d24ca3e93c8a94b6e71ad22beecdd4224",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-05-red",
      "acceptance": [
        "AC-M1B-05"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m1b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m1b/drills.log"
      ],
      "method": "Red drill M1B-05-stale-folders (Windows 11, in a temporary copy of the worktree made by the harness): green on the original, chatmon/brains.py mutated once, the named tests failed with pytest's exit 1 printing the expected test, original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/drills.log",
        "sha256": "b9f8ebe5b6cb15e052432227ef378a612d459b200f363fbf2a3d8d223e092443"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "d388e0b560b0fda778c180ad86373eeaa0a7e481f9940514c854e050058980cf"
        }
      ],
      "scope_sha256": "a893fa05d6c21322cdb98ecddf136e1d24ca3e93c8a94b6e71ad22beecdd4224",
      "red": {
        "mutation": "In chatmon/brains.py, replace '            remove_stale_folders()\\n' with '            pass\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_folders_a_stopped_chatmon_left_are_removed_and_running_ones_kept",
        "observed_diagnostic": "____ test_folders_a_stopped_chatmon_left_are_removed_and_running_ones_kept ____",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "47a5862dd8a613ef146239cc398bb30c2ebcd271f69e257fd1083ad08682e494"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-06-behavior",
      "acceptance": [
        "AC-M1B-06"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_backup.py",
        "tests/test_chats.py",
        "tests/test_settings.py",
        "tests/test_brains.py",
        "tests/test_streaming.py",
        "tests/test_keychain.py",
        "tests/test_portowner.py",
        "tests/test_context.py"
      ],
      "method": "M1B's test files run on Windows 11 under QT_QPA_PLATFORM=offscreen, with real Qt objects, a local replay server, real processes and the real Credential Manager; 142 passed, 8 skipped (platform reasons listed in the artifact). The tests for AC-M1B-06 are among them.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/pytest-m1b-windows.txt",
        "sha256": "fa82b58ba58c5133dd0b112ad0c39eb1a1a0a8d00504d6038cec3eb42e1865b4"
      },
      "inputs": [
        {
          "path": "chatmon/chats.py",
          "sha256": "030235c7a0355e75be5c58d738ffd5d7710b9912bf8e0bf5c43104e09d4b1430"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "707a8deabab87af6f9463bd2b1139fde8f91cef18341252d4c23dc728470dbef"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "29fb53787edc38856d7908b9b4cac24c255030f4c9c83a9d7ec91f5c1986ec4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "91c590f2b26ad1dde2373d6f6619fff6198a38f0ccb480d287b82b22776cee31"
        }
      ],
      "scope_sha256": "9cfbe6bdfaff9482db211071d8029457bf22d7dcee2d87a054aa987b4cacd8a9",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-06-red",
      "acceptance": [
        "AC-M1B-06"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m1b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m1b/drills.log"
      ],
      "method": "Red drill M1B-06-range (Windows 11, in a temporary copy of the worktree made by the harness): green on the original, chatmon/settings.py mutated once, the named tests failed with pytest's exit 1 printing the expected test, original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/drills.log",
        "sha256": "b9f8ebe5b6cb15e052432227ef378a612d459b200f363fbf2a3d8d223e092443"
      },
      "inputs": [
        {
          "path": "chatmon/chats.py",
          "sha256": "030235c7a0355e75be5c58d738ffd5d7710b9912bf8e0bf5c43104e09d4b1430"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "707a8deabab87af6f9463bd2b1139fde8f91cef18341252d4c23dc728470dbef"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "29fb53787edc38856d7908b9b4cac24c255030f4c9c83a9d7ec91f5c1986ec4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "91c590f2b26ad1dde2373d6f6619fff6198a38f0ccb480d287b82b22776cee31"
        }
      ],
      "scope_sha256": "9cfbe6bdfaff9482db211071d8029457bf22d7dcee2d87a054aa987b4cacd8a9",
      "red": {
        "mutation": "In chatmon/settings.py, replace '        if not low <= number <= high:' with '        if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_bad_value_costs_only_its_own_setting",
        "observed_diagnostic": "_________________ test_a_bad_value_costs_only_its_own_setting _________________",
        "before": [
          {
            "path": "chatmon/settings.py",
            "sha256": "29fb53787edc38856d7908b9b4cac24c255030f4c9c83a9d7ec91f5c1986ec4c"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/settings.py",
            "sha256": "e87345c9112421753ccd449956bc0bf7de706ed5c7c1b858bb75253e0cd5149d"
          }
        ],
        "after": [
          {
            "path": "chatmon/settings.py",
            "sha256": "29fb53787edc38856d7908b9b4cac24c255030f4c9c83a9d7ec91f5c1986ec4c"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-07-behavior",
      "acceptance": [
        "AC-M1B-07"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_backup.py",
        "tests/test_chats.py",
        "tests/test_settings.py",
        "tests/test_brains.py",
        "tests/test_streaming.py",
        "tests/test_keychain.py",
        "tests/test_portowner.py",
        "tests/test_context.py"
      ],
      "method": "M1B's test files run on Windows 11 under QT_QPA_PLATFORM=offscreen, with real Qt objects, a local replay server, real processes and the real Credential Manager; 142 passed, 8 skipped (platform reasons listed in the artifact). The tests for AC-M1B-07 are among them.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/pytest-m1b-windows.txt",
        "sha256": "fa82b58ba58c5133dd0b112ad0c39eb1a1a0a8d00504d6038cec3eb42e1865b4"
      },
      "inputs": [
        {
          "path": "chatmon/chats.py",
          "sha256": "030235c7a0355e75be5c58d738ffd5d7710b9912bf8e0bf5c43104e09d4b1430"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "707a8deabab87af6f9463bd2b1139fde8f91cef18341252d4c23dc728470dbef"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "29fb53787edc38856d7908b9b4cac24c255030f4c9c83a9d7ec91f5c1986ec4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "91c590f2b26ad1dde2373d6f6619fff6198a38f0ccb480d287b82b22776cee31"
        }
      ],
      "scope_sha256": "9cfbe6bdfaff9482db211071d8029457bf22d7dcee2d87a054aa987b4cacd8a9",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-07-red",
      "acceptance": [
        "AC-M1B-07"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m1b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m1b/drills.log"
      ],
      "method": "Red drill M1B-07-kept-aside (Windows 11, in a temporary copy of the worktree made by the harness): green on the original, chatmon/settings.py mutated once, the named tests failed with pytest's exit 1 printing the expected test, original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/drills.log",
        "sha256": "b9f8ebe5b6cb15e052432227ef378a612d459b200f363fbf2a3d8d223e092443"
      },
      "inputs": [
        {
          "path": "chatmon/chats.py",
          "sha256": "030235c7a0355e75be5c58d738ffd5d7710b9912bf8e0bf5c43104e09d4b1430"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "707a8deabab87af6f9463bd2b1139fde8f91cef18341252d4c23dc728470dbef"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "29fb53787edc38856d7908b9b4cac24c255030f4c9c83a9d7ec91f5c1986ec4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "91c590f2b26ad1dde2373d6f6619fff6198a38f0ccb480d287b82b22776cee31"
        }
      ],
      "scope_sha256": "9cfbe6bdfaff9482db211071d8029457bf22d7dcee2d87a054aa987b4cacd8a9",
      "red": {
        "mutation": "In chatmon/settings.py, replace '    kept = _set_aside(path)' with '    kept = None'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_damaged_state_file_is_kept_aside_and_the_last_good_copy_used",
        "observed_diagnostic": "_____ test_a_damaged_state_file_is_kept_aside_and_the_last_good_copy_used _____",
        "before": [
          {
            "path": "chatmon/settings.py",
            "sha256": "29fb53787edc38856d7908b9b4cac24c255030f4c9c83a9d7ec91f5c1986ec4c"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/settings.py",
            "sha256": "94c77b296416f4f08e024633fd1cb86d25c363ab37832e8e14e7f346db243ea0"
          }
        ],
        "after": [
          {
            "path": "chatmon/settings.py",
            "sha256": "29fb53787edc38856d7908b9b4cac24c255030f4c9c83a9d7ec91f5c1986ec4c"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-08-behavior",
      "acceptance": [
        "AC-M1B-08"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_backup.py",
        "tests/test_chats.py",
        "tests/test_settings.py",
        "tests/test_brains.py",
        "tests/test_streaming.py",
        "tests/test_keychain.py",
        "tests/test_portowner.py",
        "tests/test_context.py"
      ],
      "method": "M1B's test files run on Windows 11 under QT_QPA_PLATFORM=offscreen, with real Qt objects, a local replay server, real processes and the real Credential Manager; 142 passed, 8 skipped (platform reasons listed in the artifact). The tests for AC-M1B-08 are among them.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/pytest-m1b-windows.txt",
        "sha256": "fa82b58ba58c5133dd0b112ad0c39eb1a1a0a8d00504d6038cec3eb42e1865b4"
      },
      "inputs": [
        {
          "path": "chatmon/chats.py",
          "sha256": "030235c7a0355e75be5c58d738ffd5d7710b9912bf8e0bf5c43104e09d4b1430"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "707a8deabab87af6f9463bd2b1139fde8f91cef18341252d4c23dc728470dbef"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "29fb53787edc38856d7908b9b4cac24c255030f4c9c83a9d7ec91f5c1986ec4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "91c590f2b26ad1dde2373d6f6619fff6198a38f0ccb480d287b82b22776cee31"
        }
      ],
      "scope_sha256": "9cfbe6bdfaff9482db211071d8029457bf22d7dcee2d87a054aa987b4cacd8a9",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-08-behavior-linux",
      "acceptance": [
        "AC-M1B-08"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "/var/tmp/m1b-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_backup.py",
        "tests/test_chats.py",
        "tests/test_settings.py",
        "tests/test_brains.py",
        "tests/test_streaming.py",
        "tests/test_keychain.py",
        "tests/test_portowner.py",
        "tests/test_context.py"
      ],
      "method": "The same test files on Linux (WSL Arch, kernel 6.18, Python 3.14.9, PyQt6 6.11.0, dbus-run-session for the pretend Secret Service); 143 passed, 7 skipped. Covers AC-M1B-08's Linux paths.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/pytest-linux.txt",
        "sha256": "855f1c38c2dbb05f986e22595fb32fe378b7b663ad71fede554a52caaafb8d5e"
      },
      "inputs": [
        {
          "path": "chatmon/chats.py",
          "sha256": "030235c7a0355e75be5c58d738ffd5d7710b9912bf8e0bf5c43104e09d4b1430"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "707a8deabab87af6f9463bd2b1139fde8f91cef18341252d4c23dc728470dbef"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "29fb53787edc38856d7908b9b4cac24c255030f4c9c83a9d7ec91f5c1986ec4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "91c590f2b26ad1dde2373d6f6619fff6198a38f0ccb480d287b82b22776cee31"
        }
      ],
      "scope_sha256": "9cfbe6bdfaff9482db211071d8029457bf22d7dcee2d87a054aa987b4cacd8a9",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-08-red",
      "acceptance": [
        "AC-M1B-08"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "/var/tmp/m1b-venv/bin/python",
        "tests/drills/run.py",
        "docs/delivery/reports/m1b/drill-spec-linux.json",
        "--log",
        "/var/tmp/m1b-drill-out/drills-linux.log",
        "--python",
        "/var/tmp/m1b-venv/bin/python"
      ],
      "method": "Red drill M1B-08-file-mode (WSL Arch Linux, in a standalone git copy of the working tree's bytes (this worktree's .git names a Windows path); the log was copied back): green on the original, chatmon/settings.py mutated once, the named tests failed with pytest's exit 1 printing the expected test, original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/drills-linux.log",
        "sha256": "1c26dd1b9ab58f9e76850ecfa656c3000acbe63f3b7c3cef74a83908e4c1f6bf"
      },
      "inputs": [
        {
          "path": "chatmon/chats.py",
          "sha256": "030235c7a0355e75be5c58d738ffd5d7710b9912bf8e0bf5c43104e09d4b1430"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "707a8deabab87af6f9463bd2b1139fde8f91cef18341252d4c23dc728470dbef"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "29fb53787edc38856d7908b9b4cac24c255030f4c9c83a9d7ec91f5c1986ec4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "91c590f2b26ad1dde2373d6f6619fff6198a38f0ccb480d287b82b22776cee31"
        }
      ],
      "scope_sha256": "9cfbe6bdfaff9482db211071d8029457bf22d7dcee2d87a054aa987b4cacd8a9",
      "red": {
        "mutation": "In chatmon/settings.py, replace 'os.fchmod(fd, 0o600)' with 'os.fchmod(fd, 0o644)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_files_are_made_private_from_the_start_and_folders_too",
        "observed_diagnostic": "__________ test_files_are_made_private_from_the_start_and_folders_too __________",
        "before": [
          {
            "path": "chatmon/settings.py",
            "sha256": "29fb53787edc38856d7908b9b4cac24c255030f4c9c83a9d7ec91f5c1986ec4c"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/settings.py",
            "sha256": "9a7b7dc7ba2f18f7bd2e40464e2e0a885eab7d585578698dd8dd151eb444ed5c"
          }
        ],
        "after": [
          {
            "path": "chatmon/settings.py",
            "sha256": "29fb53787edc38856d7908b9b4cac24c255030f4c9c83a9d7ec91f5c1986ec4c"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-09-behavior",
      "acceptance": [
        "AC-M1B-09"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_backup.py",
        "tests/test_chats.py",
        "tests/test_settings.py",
        "tests/test_brains.py",
        "tests/test_streaming.py",
        "tests/test_keychain.py",
        "tests/test_portowner.py",
        "tests/test_context.py"
      ],
      "method": "M1B's test files run on Windows 11 under QT_QPA_PLATFORM=offscreen, with real Qt objects, a local replay server, real processes and the real Credential Manager; 142 passed, 8 skipped (platform reasons listed in the artifact). The tests for AC-M1B-09 are among them.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/pytest-m1b-windows.txt",
        "sha256": "fa82b58ba58c5133dd0b112ad0c39eb1a1a0a8d00504d6038cec3eb42e1865b4"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "d388e0b560b0fda778c180ad86373eeaa0a7e481f9940514c854e050058980cf"
        }
      ],
      "scope_sha256": "52698eeb02a8182cbf263a24936f1c554dc720299bb79f18c2f07309aa2356bc",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-09-red",
      "acceptance": [
        "AC-M1B-09"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m1b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m1b/drills.log"
      ],
      "method": "Red drill M1B-09-status (Windows 11, in a temporary copy of the worktree made by the harness): green on the original, chatmon/brains.py mutated once, the named tests failed with pytest's exit 1 printing the expected test, original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/drills.log",
        "sha256": "b9f8ebe5b6cb15e052432227ef378a612d459b200f363fbf2a3d8d223e092443"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "d388e0b560b0fda778c180ad86373eeaa0a7e481f9940514c854e050058980cf"
        }
      ],
      "scope_sha256": "52698eeb02a8182cbf263a24936f1c554dc720299bb79f18c2f07309aa2356bc",
      "red": {
        "mutation": "In chatmon/brains.py, replace 'if isinstance(status, int) and status >= 400:' with 'if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_an_http_error_says_what_the_provider_said_the_status_and_what_to_do",
        "observed_diagnostic": "FAILED tests/test_streaming.py::test_an_http_error_says_what_the_provider_said_the_status_and_what_to_do[401-body0-invalid x-api-key-Check its key in ANTHROPIC_API_KEY]",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "4d051ff1b9989fb6d219065495727d568bc15eba4c341e8c0101eee5c9b8c1e4"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-10-behavior",
      "acceptance": [
        "AC-M1B-10"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_backup.py",
        "tests/test_chats.py",
        "tests/test_settings.py",
        "tests/test_brains.py",
        "tests/test_streaming.py",
        "tests/test_keychain.py",
        "tests/test_portowner.py",
        "tests/test_context.py"
      ],
      "method": "M1B's test files run on Windows 11 under QT_QPA_PLATFORM=offscreen, with real Qt objects, a local replay server, real processes and the real Credential Manager; 142 passed, 8 skipped (platform reasons listed in the artifact). The tests for AC-M1B-10 are among them.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/pytest-m1b-windows.txt",
        "sha256": "fa82b58ba58c5133dd0b112ad0c39eb1a1a0a8d00504d6038cec3eb42e1865b4"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f144a4878c07ce2b3375d71ec36c59e7c2b330e071ce0814b11716ce985d084f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "d388e0b560b0fda778c180ad86373eeaa0a7e481f9940514c854e050058980cf"
        },
        {
          "path": "tests/test_portowner.py",
          "sha256": "0dac6b0ce7b977c5facb5f7b4cee185c73442799a90be4208628e5a5c9b65f70"
        }
      ],
      "scope_sha256": "54a65666e2c4b28ca451db1a6ced4a7b5262f7ebbecddec01a8a22f071fe1cf6",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-10-red",
      "acceptance": [
        "AC-M1B-10"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m1b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m1b/drills.log"
      ],
      "method": "Red drill M1B-10-no-wait (Windows 11, in a temporary copy of the worktree made by the harness): green on the original, chatmon/brains.py mutated once, the named tests failed with pytest's exit 1 printing the expected test, original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/drills.log",
        "sha256": "b9f8ebe5b6cb15e052432227ef378a612d459b200f363fbf2a3d8d223e092443"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f144a4878c07ce2b3375d71ec36c59e7c2b330e071ce0814b11716ce985d084f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "d388e0b560b0fda778c180ad86373eeaa0a7e481f9940514c854e050058980cf"
        },
        {
          "path": "tests/test_portowner.py",
          "sha256": "0dac6b0ce7b977c5facb5f7b4cee185c73442799a90be4208628e5a5c9b65f70"
        }
      ],
      "scope_sha256": "54a65666e2c4b28ca451db1a6ced4a7b5262f7ebbecddec01a8a22f071fe1cf6",
      "red": {
        "mutation": "In chatmon/brains.py, replace '    threading.Thread(target=end, daemon=True).start()' with '    end()'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_cancelling_on_windows_stops_the_tool_behind_a_cmd_file_without_waiting",
        "observed_diagnostic": "_ test_cancelling_on_windows_stops_the_tool_behind_a_cmd_file_without_waiting _",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "bbe57dcd3391ab76007cb5069eba1585fc6d99688da793aef99e53e6ea3023a8"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-11-behavior",
      "acceptance": [
        "AC-M1B-11"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_backup.py",
        "tests/test_chats.py",
        "tests/test_settings.py",
        "tests/test_brains.py",
        "tests/test_streaming.py",
        "tests/test_keychain.py",
        "tests/test_portowner.py",
        "tests/test_context.py"
      ],
      "method": "M1B's test files run on Windows 11 under QT_QPA_PLATFORM=offscreen, with real Qt objects, a local replay server, real processes and the real Credential Manager; 142 passed, 8 skipped (platform reasons listed in the artifact). The tests for AC-M1B-11 are among them.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/pytest-m1b-windows.txt",
        "sha256": "fa82b58ba58c5133dd0b112ad0c39eb1a1a0a8d00504d6038cec3eb42e1865b4"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f144a4878c07ce2b3375d71ec36c59e7c2b330e071ce0814b11716ce985d084f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "d388e0b560b0fda778c180ad86373eeaa0a7e481f9940514c854e050058980cf"
        },
        {
          "path": "tests/test_portowner.py",
          "sha256": "0dac6b0ce7b977c5facb5f7b4cee185c73442799a90be4208628e5a5c9b65f70"
        }
      ],
      "scope_sha256": "54a65666e2c4b28ca451db1a6ced4a7b5262f7ebbecddec01a8a22f071fe1cf6",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-11-red",
      "acceptance": [
        "AC-M1B-11"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m1b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m1b/drills.log"
      ],
      "method": "Red drill M1B-11-finder (Windows 11, in a temporary copy of the worktree made by the harness): green on the original, chatmon/brains.py mutated once, the named tests failed with pytest's exit 1 printing the expected test, original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/drills.log",
        "sha256": "b9f8ebe5b6cb15e052432227ef378a612d459b200f363fbf2a3d8d223e092443"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f144a4878c07ce2b3375d71ec36c59e7c2b330e071ce0814b11716ce985d084f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "d388e0b560b0fda778c180ad86373eeaa0a7e481f9940514c854e050058980cf"
        },
        {
          "path": "tests/test_portowner.py",
          "sha256": "0dac6b0ce7b977c5facb5f7b4cee185c73442799a90be4208628e5a5c9b65f70"
        }
      ],
      "scope_sha256": "54a65666e2c4b28ca451db1a6ced4a7b5262f7ebbecddec01a8a22f071fe1cf6",
      "red": {
        "mutation": "In chatmon/brains.py, replace '        quick = choose(brains, configured, picked, wait=False, prefer=prefer)' with '        quick = choose(brains, configured, picked, wait=True, prefer=prefer)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_finding_the_brain_never_probes_on_the_screens_thread_and_remembers",
        "observed_diagnostic": "___ test_finding_the_brain_never_probes_on_the_screens_thread_and_remembers ___",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "1d33af50321f759c5a6b882e86b009a6597a30452430aec4f2101f7ab0ea50a7"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-12-behavior",
      "acceptance": [
        "AC-M1B-12"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_backup.py",
        "tests/test_chats.py",
        "tests/test_settings.py",
        "tests/test_brains.py",
        "tests/test_streaming.py",
        "tests/test_keychain.py",
        "tests/test_portowner.py",
        "tests/test_context.py"
      ],
      "method": "M1B's test files run on Windows 11 under QT_QPA_PLATFORM=offscreen, with real Qt objects, a local replay server, real processes and the real Credential Manager; 142 passed, 8 skipped (platform reasons listed in the artifact). The tests for AC-M1B-12 are among them.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/pytest-m1b-windows.txt",
        "sha256": "fa82b58ba58c5133dd0b112ad0c39eb1a1a0a8d00504d6038cec3eb42e1865b4"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f144a4878c07ce2b3375d71ec36c59e7c2b330e071ce0814b11716ce985d084f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "d388e0b560b0fda778c180ad86373eeaa0a7e481f9940514c854e050058980cf"
        },
        {
          "path": "tests/test_portowner.py",
          "sha256": "0dac6b0ce7b977c5facb5f7b4cee185c73442799a90be4208628e5a5c9b65f70"
        },
        {
          "path": "tests/test_streaming.py",
          "sha256": "de7c8d05cf58c33dc5a7cb878f4af3c461c2bda8ddb767ffb1c3ac71e9852ddb"
        }
      ],
      "scope_sha256": "b5c16dc02a4c62a37ff1d4205f6657213f382fa91e5346c237092774defa574a",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-12-red",
      "acceptance": [
        "AC-M1B-12"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m1b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m1b/drills.log"
      ],
      "method": "Red drill M1B-12-partial (Windows 11, in a temporary copy of the worktree made by the harness): green on the original, chatmon/brains.py mutated once, the named tests failed with pytest's exit 1 printing the expected test, original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/drills.log",
        "sha256": "b9f8ebe5b6cb15e052432227ef378a612d459b200f363fbf2a3d8d223e092443"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f144a4878c07ce2b3375d71ec36c59e7c2b330e071ce0814b11716ce985d084f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "d388e0b560b0fda778c180ad86373eeaa0a7e481f9940514c854e050058980cf"
        },
        {
          "path": "tests/test_portowner.py",
          "sha256": "0dac6b0ce7b977c5facb5f7b4cee185c73442799a90be4208628e5a5c9b65f70"
        },
        {
          "path": "tests/test_streaming.py",
          "sha256": "de7c8d05cf58c33dc5a7cb878f4af3c461c2bda8ddb767ffb1c3ac71e9852ddb"
        }
      ],
      "scope_sha256": "b5c16dc02a4c62a37ff1d4205f6657213f382fa91e5346c237092774defa574a",
      "red": {
        "mutation": "In chatmon/brains.py, replace '            for piece in self._stream.feed(chunk):\\n                self.partial.emit(piece)\\n            return' with '            self._stream.feed(chunk)\\n            return'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_anthropic_api_streams_each_piece_as_its_written",
        "observed_diagnostic": "__________ test_the_anthropic_api_streams_each_piece_as_its_written ___________",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "da5cf51468837a921401ec3946b367921654446e619b1ad1e30dbac60d1e4095"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-13-behavior",
      "acceptance": [
        "AC-M1B-13"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_backup.py",
        "tests/test_chats.py",
        "tests/test_settings.py",
        "tests/test_brains.py",
        "tests/test_streaming.py",
        "tests/test_keychain.py",
        "tests/test_portowner.py",
        "tests/test_context.py"
      ],
      "method": "M1B's test files run on Windows 11 under QT_QPA_PLATFORM=offscreen, with real Qt objects, a local replay server, real processes and the real Credential Manager; 142 passed, 8 skipped (platform reasons listed in the artifact). The tests for AC-M1B-13 are among them.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/pytest-m1b-windows.txt",
        "sha256": "fa82b58ba58c5133dd0b112ad0c39eb1a1a0a8d00504d6038cec3eb42e1865b4"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "df3b74f6c60207744a119442999483cc5799017ee8fb8cabaf1582c036554370"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "1534023cb83d4811b23227f49c940991a7f22a60e2cae9c5297725265e8f1096"
        },
        {
          "path": "tests/test_keychain.py",
          "sha256": "0a3fdb9afe3a9dabc4783884c81efcc00fbd240530b2a10c2e8d8fd770322609"
        }
      ],
      "scope_sha256": "db437c72ecc67d21a33e7fd0f5ce031bb355668f16265a656c73e9d1716f3719",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-13-behavior-linux",
      "acceptance": [
        "AC-M1B-13"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "/var/tmp/m1b-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_backup.py",
        "tests/test_chats.py",
        "tests/test_settings.py",
        "tests/test_brains.py",
        "tests/test_streaming.py",
        "tests/test_keychain.py",
        "tests/test_portowner.py",
        "tests/test_context.py"
      ],
      "method": "The same test files on Linux (WSL Arch, kernel 6.18, Python 3.14.9, PyQt6 6.11.0, dbus-run-session for the pretend Secret Service); 143 passed, 7 skipped. Covers AC-M1B-13's Linux paths.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/pytest-linux.txt",
        "sha256": "855f1c38c2dbb05f986e22595fb32fe378b7b663ad71fede554a52caaafb8d5e"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "df3b74f6c60207744a119442999483cc5799017ee8fb8cabaf1582c036554370"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "1534023cb83d4811b23227f49c940991a7f22a60e2cae9c5297725265e8f1096"
        },
        {
          "path": "tests/test_keychain.py",
          "sha256": "0a3fdb9afe3a9dabc4783884c81efcc00fbd240530b2a10c2e8d8fd770322609"
        }
      ],
      "scope_sha256": "db437c72ecc67d21a33e7fd0f5ce031bb355668f16265a656c73e9d1716f3719",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-13-red",
      "acceptance": [
        "AC-M1B-13"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m1b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m1b/drills.log"
      ],
      "method": "Red drill M1B-13-saved-key (Windows 11, in a temporary copy of the worktree made by the harness): green on the original, chatmon/brains.py mutated once, the named tests failed with pytest's exit 1 printing the expected test, original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/drills.log",
        "sha256": "b9f8ebe5b6cb15e052432227ef378a612d459b200f363fbf2a3d8d223e092443"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "df3b74f6c60207744a119442999483cc5799017ee8fb8cabaf1582c036554370"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "1534023cb83d4811b23227f49c940991a7f22a60e2cae9c5297725265e8f1096"
        },
        {
          "path": "tests/test_keychain.py",
          "sha256": "0a3fdb9afe3a9dabc4783884c81efcc00fbd240530b2a10c2e8d8fd770322609"
        }
      ],
      "scope_sha256": "db437c72ecc67d21a33e7fd0f5ce031bb355668f16265a656c73e9d1716f3719",
      "red": {
        "mutation": "In chatmon/brains.py, replace '        return keychain.get(self.name) or \"\"' with '        return \"\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_brain_uses_its_saved_key_when_its_variable_isnt_set",
        "observed_diagnostic": "_________ test_a_brain_uses_its_saved_key_when_its_variable_isnt_set __________",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "1ccbc4fd3e2c1cd3524c23069478a06253891f401165209c71c962b196a4474e"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-14-behavior",
      "acceptance": [
        "AC-M1B-14"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_backup.py",
        "tests/test_chats.py",
        "tests/test_settings.py",
        "tests/test_brains.py",
        "tests/test_streaming.py",
        "tests/test_keychain.py",
        "tests/test_portowner.py",
        "tests/test_context.py"
      ],
      "method": "M1B's test files run on Windows 11 under QT_QPA_PLATFORM=offscreen, with real Qt objects, a local replay server, real processes and the real Credential Manager; 142 passed, 8 skipped (platform reasons listed in the artifact). The tests for AC-M1B-14 are among them.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/pytest-m1b-windows.txt",
        "sha256": "fa82b58ba58c5133dd0b112ad0c39eb1a1a0a8d00504d6038cec3eb42e1865b4"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "d388e0b560b0fda778c180ad86373eeaa0a7e481f9940514c854e050058980cf"
        },
        {
          "path": "tests/test_streaming.py",
          "sha256": "de7c8d05cf58c33dc5a7cb878f4af3c461c2bda8ddb767ffb1c3ac71e9852ddb"
        }
      ],
      "scope_sha256": "50d67dd1ba1d0256574a38002d4aa8d173e628a749ae648863b1e028128c7eae",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-14-red",
      "acceptance": [
        "AC-M1B-14"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m1b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m1b/drills.log"
      ],
      "method": "Red drill M1B-14-seconds (Windows 11, in a temporary copy of the worktree made by the harness): green on the original, chatmon/brains.py mutated once, the named tests failed with pytest's exit 1 printing the expected test, original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/drills.log",
        "sha256": "b9f8ebe5b6cb15e052432227ef378a612d459b200f363fbf2a3d8d223e092443"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "d388e0b560b0fda778c180ad86373eeaa0a7e481f9940514c854e050058980cf"
        },
        {
          "path": "tests/test_streaming.py",
          "sha256": "de7c8d05cf58c33dc5a7cb878f4af3c461c2bda8ddb767ffb1c3ac71e9852ddb"
        }
      ],
      "scope_sha256": "50d67dd1ba1d0256574a38002d4aa8d173e628a749ae648863b1e028128c7eae",
      "red": {
        "mutation": "In chatmon/brains.py, replace '        self.finished.emit(ok, text, round(time.monotonic() - self._started, 2))' with '        self.finished.emit(ok, text, 0.0)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_brain_test_says_how_long_the_answer_took_or_whats_wrong",
        "observed_diagnostic": "_______ test_a_brain_test_says_how_long_the_answer_took_or_whats_wrong ________",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "726a10b88319b157a0340113bca73f0980c2f33033ae7360aaa6baf9bcf4e18c"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-15-behavior",
      "acceptance": [
        "AC-M1B-15"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_backup.py",
        "tests/test_chats.py",
        "tests/test_settings.py",
        "tests/test_brains.py",
        "tests/test_streaming.py",
        "tests/test_keychain.py",
        "tests/test_portowner.py",
        "tests/test_context.py"
      ],
      "method": "M1B's test files run on Windows 11 under QT_QPA_PLATFORM=offscreen, with real Qt objects, a local replay server, real processes and the real Credential Manager; 142 passed, 8 skipped (platform reasons listed in the artifact). The tests for AC-M1B-15 are among them.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/pytest-m1b-windows.txt",
        "sha256": "fa82b58ba58c5133dd0b112ad0c39eb1a1a0a8d00504d6038cec3eb42e1865b4"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "030235c7a0355e75be5c58d738ffd5d7710b9912bf8e0bf5c43104e09d4b1430"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "707a8deabab87af6f9463bd2b1139fde8f91cef18341252d4c23dc728470dbef"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "29fb53787edc38856d7908b9b4cac24c255030f4c9c83a9d7ec91f5c1986ec4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "e79110e36d8beeb15b2bdf0f97058a2227c082197c9bbdfcd8ce4e120801fd46"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "91c590f2b26ad1dde2373d6f6619fff6198a38f0ccb480d287b82b22776cee31"
        }
      ],
      "scope_sha256": "c80c18bd0515d0f8db890e50df4b4373fc0a301c71a1aaeab7b0664491c72c19",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-15-red",
      "acceptance": [
        "AC-M1B-15"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m1b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m1b/drills.log"
      ],
      "method": "Red drill M1B-15-chat-brain (Windows 11, in a temporary copy of the worktree made by the harness): green on the original, chatmon/chats.py mutated once, the named tests failed with pytest's exit 1 printing the expected test, original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/drills.log",
        "sha256": "b9f8ebe5b6cb15e052432227ef378a612d459b200f363fbf2a3d8d223e092443"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "030235c7a0355e75be5c58d738ffd5d7710b9912bf8e0bf5c43104e09d4b1430"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "707a8deabab87af6f9463bd2b1139fde8f91cef18341252d4c23dc728470dbef"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "29fb53787edc38856d7908b9b4cac24c255030f4c9c83a9d7ec91f5c1986ec4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "e79110e36d8beeb15b2bdf0f97058a2227c082197c9bbdfcd8ce4e120801fd46"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "91c590f2b26ad1dde2373d6f6619fff6198a38f0ccb480d287b82b22776cee31"
        }
      ],
      "scope_sha256": "c80c18bd0515d0f8db890e50df4b4373fc0a301c71a1aaeab7b0664491c72c19",
      "red": {
        "mutation": "In chatmon/chats.py, replace '            self.brain = message.by' with '            pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_chat_remembers_its_brain_and_the_question_to_ask_another",
        "observed_diagnostic": "_______ test_a_chat_remembers_its_brain_and_the_question_to_ask_another _______",
        "before": [
          {
            "path": "chatmon/chats.py",
            "sha256": "030235c7a0355e75be5c58d738ffd5d7710b9912bf8e0bf5c43104e09d4b1430"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/chats.py",
            "sha256": "e72e14cae95bb4bd5c0fd7f668dc227acb194c07221e2e10188ed17beddcc926"
          }
        ],
        "after": [
          {
            "path": "chatmon/chats.py",
            "sha256": "030235c7a0355e75be5c58d738ffd5d7710b9912bf8e0bf5c43104e09d4b1430"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-16-behavior",
      "acceptance": [
        "AC-M1B-16"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_backup.py",
        "tests/test_chats.py",
        "tests/test_settings.py",
        "tests/test_brains.py",
        "tests/test_streaming.py",
        "tests/test_keychain.py",
        "tests/test_portowner.py",
        "tests/test_context.py"
      ],
      "method": "M1B's test files run on Windows 11 under QT_QPA_PLATFORM=offscreen, with real Qt objects, a local replay server, real processes and the real Credential Manager; 142 passed, 8 skipped (platform reasons listed in the artifact). The tests for AC-M1B-16 are among them.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/pytest-m1b-windows.txt",
        "sha256": "fa82b58ba58c5133dd0b112ad0c39eb1a1a0a8d00504d6038cec3eb42e1865b4"
      },
      "inputs": [
        {
          "path": "chatmon/backup.py",
          "sha256": "4343c42222f5172eebf82f58405117ad63f58c59cc8cca376fb2218763428650"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "030235c7a0355e75be5c58d738ffd5d7710b9912bf8e0bf5c43104e09d4b1430"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "707a8deabab87af6f9463bd2b1139fde8f91cef18341252d4c23dc728470dbef"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "29fb53787edc38856d7908b9b4cac24c255030f4c9c83a9d7ec91f5c1986ec4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "1964c1190fffdd6cfcb2f0c79b5fa7879f950661b951881e597c4b6c45b8ae04"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "91c590f2b26ad1dde2373d6f6619fff6198a38f0ccb480d287b82b22776cee31"
        }
      ],
      "scope_sha256": "4a658b61f2b306455be15f9e0d155f4683aed1fdcda51e9b5d1b017c4686ab89",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-16-behavior-linux",
      "acceptance": [
        "AC-M1B-16"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "/var/tmp/m1b-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_backup.py",
        "tests/test_chats.py",
        "tests/test_settings.py",
        "tests/test_brains.py",
        "tests/test_streaming.py",
        "tests/test_keychain.py",
        "tests/test_portowner.py",
        "tests/test_context.py"
      ],
      "method": "The same test files on Linux (WSL Arch, kernel 6.18, Python 3.14.9, PyQt6 6.11.0, dbus-run-session for the pretend Secret Service); 143 passed, 7 skipped. Covers AC-M1B-16's Linux paths.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/pytest-linux.txt",
        "sha256": "855f1c38c2dbb05f986e22595fb32fe378b7b663ad71fede554a52caaafb8d5e"
      },
      "inputs": [
        {
          "path": "chatmon/backup.py",
          "sha256": "4343c42222f5172eebf82f58405117ad63f58c59cc8cca376fb2218763428650"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "030235c7a0355e75be5c58d738ffd5d7710b9912bf8e0bf5c43104e09d4b1430"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "707a8deabab87af6f9463bd2b1139fde8f91cef18341252d4c23dc728470dbef"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "29fb53787edc38856d7908b9b4cac24c255030f4c9c83a9d7ec91f5c1986ec4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "1964c1190fffdd6cfcb2f0c79b5fa7879f950661b951881e597c4b6c45b8ae04"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "91c590f2b26ad1dde2373d6f6619fff6198a38f0ccb480d287b82b22776cee31"
        }
      ],
      "scope_sha256": "4a658b61f2b306455be15f9e0d155f4683aed1fdcda51e9b5d1b017c4686ab89",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-16-red",
      "acceptance": [
        "AC-M1B-16"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m1b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m1b/drills.log"
      ],
      "method": "Red drill M1B-16-no-secrets (Windows 11, in a temporary copy of the worktree made by the harness): green on the original, chatmon/backup.py mutated once, the named tests failed with pytest's exit 1 printing the expected test, original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/drills.log",
        "sha256": "b9f8ebe5b6cb15e052432227ef378a612d459b200f363fbf2a3d8d223e092443"
      },
      "inputs": [
        {
          "path": "chatmon/backup.py",
          "sha256": "4343c42222f5172eebf82f58405117ad63f58c59cc8cca376fb2218763428650"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "030235c7a0355e75be5c58d738ffd5d7710b9912bf8e0bf5c43104e09d4b1430"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "707a8deabab87af6f9463bd2b1139fde8f91cef18341252d4c23dc728470dbef"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "29fb53787edc38856d7908b9b4cac24c255030f4c9c83a9d7ec91f5c1986ec4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "1964c1190fffdd6cfcb2f0c79b5fa7879f950661b951881e597c4b6c45b8ae04"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "91c590f2b26ad1dde2373d6f6619fff6198a38f0ccb480d287b82b22776cee31"
        }
      ],
      "scope_sha256": "4a658b61f2b306455be15f9e0d155f4683aed1fdcda51e9b5d1b017c4686ab89",
      "red": {
        "mutation": "In chatmon/backup.py, replace '        return {k: _no_secrets(v) for k, v in value.items() if not (isinstance(k, str) and _SECRET.search(k))}' with '        return {k: _no_secrets(v) for k, v in value.items()}'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_no_key_ever_goes_into_a_backup",
        "observed_diagnostic": "_____________________ test_no_key_ever_goes_into_a_backup _____________________",
        "before": [
          {
            "path": "chatmon/backup.py",
            "sha256": "4343c42222f5172eebf82f58405117ad63f58c59cc8cca376fb2218763428650"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/backup.py",
            "sha256": "c23ebf4fbb812e6841e7df1b5a5ca404f620af35527e8e190c45709f141c046b"
          }
        ],
        "after": [
          {
            "path": "chatmon/backup.py",
            "sha256": "4343c42222f5172eebf82f58405117ad63f58c59cc8cca376fb2218763428650"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-17-behavior",
      "acceptance": [
        "AC-M1B-17"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_backup.py",
        "tests/test_chats.py",
        "tests/test_settings.py",
        "tests/test_brains.py",
        "tests/test_streaming.py",
        "tests/test_keychain.py",
        "tests/test_portowner.py",
        "tests/test_context.py"
      ],
      "method": "M1B's test files run on Windows 11 under QT_QPA_PLATFORM=offscreen, with real Qt objects, a local replay server, real processes and the real Credential Manager; 142 passed, 8 skipped (platform reasons listed in the artifact). The tests for AC-M1B-17 are among them.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/pytest-m1b-windows.txt",
        "sha256": "fa82b58ba58c5133dd0b112ad0c39eb1a1a0a8d00504d6038cec3eb42e1865b4"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "030235c7a0355e75be5c58d738ffd5d7710b9912bf8e0bf5c43104e09d4b1430"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "707a8deabab87af6f9463bd2b1139fde8f91cef18341252d4c23dc728470dbef"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "29fb53787edc38856d7908b9b4cac24c255030f4c9c83a9d7ec91f5c1986ec4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "e79110e36d8beeb15b2bdf0f97058a2227c082197c9bbdfcd8ce4e120801fd46"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "91c590f2b26ad1dde2373d6f6619fff6198a38f0ccb480d287b82b22776cee31"
        }
      ],
      "scope_sha256": "c80c18bd0515d0f8db890e50df4b4373fc0a301c71a1aaeab7b0664491c72c19",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "EV-M1B-17-red",
      "acceptance": [
        "AC-M1B-17"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m1b/drill-spec.json",
        "--log",
        "docs/delivery/reports/m1b/drills.log"
      ],
      "method": "Red drill M1B-17-only-its-brain (Windows 11, in a temporary copy of the worktree made by the harness): green on the original, chatmon/chats.py mutated once, the named tests failed with pytest's exit 1 printing the expected test, original bytes restored (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/drills.log",
        "sha256": "b9f8ebe5b6cb15e052432227ef378a612d459b200f363fbf2a3d8d223e092443"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "a90b18e30e7977190cd4ac1e633c78cab3161c70d136d463eeea16542195f7dc"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "030235c7a0355e75be5c58d738ffd5d7710b9912bf8e0bf5c43104e09d4b1430"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "707a8deabab87af6f9463bd2b1139fde8f91cef18341252d4c23dc728470dbef"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "29fb53787edc38856d7908b9b4cac24c255030f4c9c83a9d7ec91f5c1986ec4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "e79110e36d8beeb15b2bdf0f97058a2227c082197c9bbdfcd8ce4e120801fd46"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "91c590f2b26ad1dde2373d6f6619fff6198a38f0ccb480d287b82b22776cee31"
        }
      ],
      "scope_sha256": "c80c18bd0515d0f8db890e50df4b4373fc0a301c71a1aaeab7b0664491c72c19",
      "red": {
        "mutation": "In chatmon/chats.py, replace '                if m.sent and _same(m, brain, name):' with '                if m.sent:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_attached_text_goes_again_only_to_the_brain_of_that_name",
        "observed_diagnostic": "________ test_attached_text_goes_again_only_to_the_brain_of_that_name _________",
        "before": [
          {
            "path": "chatmon/chats.py",
            "sha256": "030235c7a0355e75be5c58d738ffd5d7710b9912bf8e0bf5c43104e09d4b1430"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/chats.py",
            "sha256": "d681837bf3a21a3e90840aa3485d0b8b4f5fb4470882eb9de3ed7ac5ce3341d6"
          }
        ],
        "after": [
          {
            "path": "chatmon/chats.py",
            "sha256": "030235c7a0355e75be5c58d738ffd5d7710b9912bf8e0bf5c43104e09d4b1430"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-READY",
      "acceptance": [
        "AC-M1B-01",
        "AC-M1B-02",
        "AC-M1B-03",
        "AC-M1B-04",
        "AC-M1B-05",
        "AC-M1B-06",
        "AC-M1B-07",
        "AC-M1B-08",
        "AC-M1B-09",
        "AC-M1B-10",
        "AC-M1B-11",
        "AC-M1B-12",
        "AC-M1B-13",
        "AC-M1B-14",
        "AC-M1B-15",
        "AC-M1B-16",
        "AC-M1B-17"
      ],
      "kind": "readiness",
      "status": "pass",
      "command": [],
      "method": "Requirements review again at fb19cb9 (readiness.md): M1B-01 to M1B-17 re-read against ASSESSMENT.md, the amended ROADMAP.md and pyproject.toml as they are now and the code that carries them; no conflict or gap; M7's wiring of the APIs (the M7-WIRING operation) checked against M7's verified criteria.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m1b/wave4/readiness.md",
        "sha256": "e62123c3fa198edc3b61e1a5f1822bc7b83c657f903d91b5cebb10dc61402b0e"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        }
      ],
      "scope_sha256": "b24e2dc2976a4418bf9560d0c3c4534f374818258ced714d89f55e08a5078a05",
      "red": null,
      "reason": null
    },
    {
      "id": "W4-BEH-WINDOWS",
      "acceptance": [
        "AC-M1B-01",
        "AC-M1B-02",
        "AC-M1B-03",
        "AC-M1B-04",
        "AC-M1B-05",
        "AC-M1B-06",
        "AC-M1B-07",
        "AC-M1B-08",
        "AC-M1B-09",
        "AC-M1B-10",
        "AC-M1B-11",
        "AC-M1B-12",
        "AC-M1B-13",
        "AC-M1B-14",
        "AC-M1B-15",
        "AC-M1B-16",
        "AC-M1B-17"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider"
      ],
      "method": "The whole suite on fb19cb9's source on this Windows 11 workstation (offscreen Qt, the shared venv), which runs every test these criteria's earlier receipts named: 1241 passed, 148 skipped (other platforms' tests, each skip with its reason), exit 0; per-test results are mapped from the log by docs/delivery/reports/wave4/cilog.py. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/wave4/suite-windows.log",
        "sha256": "2d041d737c4983f9a73256c95d51463d4792262b3a54516e77e796950e87713b"
      },
      "inputs": [
        {
          "path": "chatmon/backup.py",
          "sha256": "d3bd1cd5888a3154ece55bbe2576c92f009dbd129119f8229d2401f343b0e3ac"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "f3b2bdce2d193aa9b795215993b34576ce303e31c790182a6bdf89f274e0ce8d"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "4a477a372dae3f820a19a62a8874d931e7e4d127c10fdf76caa1cfc6b7ce16a2"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "b181faa58af667a9a37405c7db6b6073f65e793198dc5fafd255f20b852f5f5c"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "8088e2ee077fdae2399de93dccfc21919ba4269dab1f9eec963b06e9b2a74425"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "b1acf8c868d28a5af93e40c580c1b948866f0a93c3f4f59f684d889c555a8c57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "34cb09f237c59ca943aea71db0d14daf10de1e07eefa1f255cd9f79ea1da5da4"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "c4d630d291cbc80f16712e2d37ae88f850dc690270bfad375bdd42cf55cda379"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "fff50c7d100160385ef3fda84de0bfb05d0aed0eaa01f2fd82df66782c14858e"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "46a0a4a5bda6fa6ba7cda972e97ef3167ae57b712ea3333f93822388f5be6dee"
        },
        {
          "path": "tests/test_keychain.py",
          "sha256": "0a3fdb9afe3a9dabc4783884c81efcc00fbd240530b2a10c2e8d8fd770322609"
        },
        {
          "path": "tests/test_portowner.py",
          "sha256": "0dac6b0ce7b977c5facb5f7b4cee185c73442799a90be4208628e5a5c9b65f70"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "affe95b6d0bab7956280a75aaf0528e05caedf030fefeefef9fd6ae0b7cdd112"
        },
        {
          "path": "tests/test_streaming.py",
          "sha256": "de7c8d05cf58c33dc5a7cb878f4af3c461c2bda8ddb767ffb1c3ac71e9852ddb"
        }
      ],
      "scope_sha256": "b24e2dc2976a4418bf9560d0c3c4534f374818258ced714d89f55e08a5078a05",
      "red": null,
      "reason": null
    },
    {
      "id": "W4-BEH-CI-LINUX",
      "acceptance": [
        "AC-M1B-03",
        "AC-M1B-08",
        "AC-M1B-13",
        "AC-M1B-16"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "gh",
        "run",
        "view",
        "43677128712",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132699632422",
        "--log"
      ],
      "method": "CI run 43677128712 on fb19cb9, job test (ubuntu-24.04, 3.15). The Secret Service tests passed there, not skipped: tests/test_keychain.py::test_the_secret_service_keeps_replaces_and_forgets_a_key_in_its_own_types, test_a_locked_keyring_is_never_prompted_to_fill_in_the_menu_only_to_save and test_no_keyring_at_all_is_said_and_never_waited_for, on a private session bus from Ubuntu's dbus package, which ci.yml installs. Also passed: the Linux port-owner tests (tests/test_portowner.py::test_on_linux_your_socket_and_someone_elses_on_one_port_isnt_yours and test_on_linux_a_port_another_account_listens_on_isnt_yours), tests/test_settings.py's file and folder modes, and tests/test_backup.py's private zip. The same passed on ubuntu 3.11 and ubuntu-24.04-arm 3.14, and all but the other-account port test passed in the three distro containers. This resolves the CI-LINUX pending operation. Read from the job's log (fetched here with the command above, exit 0) by docs/delivery/reports/wave4/cilog.py, which maps pytest's progress characters onto fb19cb9's collection and checks the run's own counts and skip lines; every leg's result for these tests is in ci/observed.txt. The CI run's own platform and versions are in the log; this receipt's environment is the plan's profile, the workstation that fetched and read it (ROADMAP: evidence from elsewhere). Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/ci/ci-132699632422-test-ubuntu-24.04-3.15.log",
        "sha256": "c8df7ed105a19cceca9f88adc79c3c24358bbdf3b6097f6c4f55b5d5e72de729"
      },
      "inputs": [
        {
          "path": "chatmon/backup.py",
          "sha256": "d3bd1cd5888a3154ece55bbe2576c92f009dbd129119f8229d2401f343b0e3ac"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "f3b2bdce2d193aa9b795215993b34576ce303e31c790182a6bdf89f274e0ce8d"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "4a477a372dae3f820a19a62a8874d931e7e4d127c10fdf76caa1cfc6b7ce16a2"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "b181faa58af667a9a37405c7db6b6073f65e793198dc5fafd255f20b852f5f5c"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "8088e2ee077fdae2399de93dccfc21919ba4269dab1f9eec963b06e9b2a74425"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "b1acf8c868d28a5af93e40c580c1b948866f0a93c3f4f59f684d889c555a8c57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "34cb09f237c59ca943aea71db0d14daf10de1e07eefa1f255cd9f79ea1da5da4"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "c4d630d291cbc80f16712e2d37ae88f850dc690270bfad375bdd42cf55cda379"
        },
        {
          "path": "tests/test_keychain.py",
          "sha256": "0a3fdb9afe3a9dabc4783884c81efcc00fbd240530b2a10c2e8d8fd770322609"
        },
        {
          "path": "tests/test_portowner.py",
          "sha256": "0dac6b0ce7b977c5facb5f7b4cee185c73442799a90be4208628e5a5c9b65f70"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "affe95b6d0bab7956280a75aaf0528e05caedf030fefeefef9fd6ae0b7cdd112"
        }
      ],
      "scope_sha256": "616c66c6517150dafaa0f8721628b3a41b894bb337bee211cbd5b785b09e7472",
      "red": null,
      "reason": null
    },
    {
      "id": "W4-BEH-CI-MACOS",
      "acceptance": [
        "AC-M1B-03",
        "AC-M1B-08",
        "AC-M1B-13",
        "AC-M1B-16"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "gh",
        "run",
        "view",
        "43677128712",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132699632411",
        "--log"
      ],
      "method": "CI run 43677128712 on fb19cb9, job test (macos-latest, 3.14). Passed: tests/test_keychain.py::test_macos_keychain_keeps_replaces_and_forgets_a_key (the Keychain through Security.framework), tests/test_portowner.py::test_a_socket_of_yours_is_yours_and_a_closed_port_nobodys (the lsof port-owner check), tests/test_settings.py's file and folder modes, and tests/test_backup.py's private zip. The same passed on the 3.11 and 3.15 legs. This resolves the CI-MACOS pending operation. Read from the job's log (fetched here with the command above, exit 0) by docs/delivery/reports/wave4/cilog.py, which maps pytest's progress characters onto fb19cb9's collection and checks the run's own counts and skip lines; every leg's result for these tests is in ci/observed.txt. The CI run's own platform and versions are in the log; this receipt's environment is the plan's profile, the workstation that fetched and read it (ROADMAP: evidence from elsewhere). Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/ci/ci-132699632411-test-macos-latest-3.14.log",
        "sha256": "920bde71199ea9324e478253bf5cbbbe73ac6294ce31018d2e94db1ba7e91c04"
      },
      "inputs": [
        {
          "path": "chatmon/backup.py",
          "sha256": "d3bd1cd5888a3154ece55bbe2576c92f009dbd129119f8229d2401f343b0e3ac"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "f3b2bdce2d193aa9b795215993b34576ce303e31c790182a6bdf89f274e0ce8d"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "4a477a372dae3f820a19a62a8874d931e7e4d127c10fdf76caa1cfc6b7ce16a2"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "b181faa58af667a9a37405c7db6b6073f65e793198dc5fafd255f20b852f5f5c"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "8088e2ee077fdae2399de93dccfc21919ba4269dab1f9eec963b06e9b2a74425"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "b1acf8c868d28a5af93e40c580c1b948866f0a93c3f4f59f684d889c555a8c57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "34cb09f237c59ca943aea71db0d14daf10de1e07eefa1f255cd9f79ea1da5da4"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "c4d630d291cbc80f16712e2d37ae88f850dc690270bfad375bdd42cf55cda379"
        },
        {
          "path": "tests/test_keychain.py",
          "sha256": "0a3fdb9afe3a9dabc4783884c81efcc00fbd240530b2a10c2e8d8fd770322609"
        },
        {
          "path": "tests/test_portowner.py",
          "sha256": "0dac6b0ce7b977c5facb5f7b4cee185c73442799a90be4208628e5a5c9b65f70"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "affe95b6d0bab7956280a75aaf0528e05caedf030fefeefef9fd6ae0b7cdd112"
        }
      ],
      "scope_sha256": "616c66c6517150dafaa0f8721628b3a41b894bb337bee211cbd5b785b09e7472",
      "red": null,
      "reason": null
    },
    {
      "id": "W4-BEH-CI-WINDOWS",
      "acceptance": [
        "AC-M1B-13"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "gh",
        "run",
        "view",
        "43677128712",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132699632366",
        "--log"
      ],
      "method": "CI run 43677128712 on fb19cb9, job test (windows-latest, 3.14). The real Credential Manager tests passed there and did not skip with error 1312: tests/test_keychain.py::test_windows_credential_manager_keeps_replaces_and_forgets_a_key and test_windows_keeps_a_key_on_this_computer_and_files_it_under_chatmon. They also passed on the 3.11 and 3.15 legs. This resolves the CI-WINDOWS pending operation. Read from the job's log (fetched here with the command above, exit 0) by docs/delivery/reports/wave4/cilog.py, which maps pytest's progress characters onto fb19cb9's collection and checks the run's own counts and skip lines; every leg's result for these tests is in ci/observed.txt. The CI run's own platform and versions are in the log; this receipt's environment is the plan's profile, the workstation that fetched and read it (ROADMAP: evidence from elsewhere). Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/ci/ci-132699632366-test-windows-latest-3.14.log",
        "sha256": "f8f5894f64fbd90ecfd7a5fa8bd6299d4734605169d4b0d27af824d6b070b91c"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "4a477a372dae3f820a19a62a8874d931e7e4d127c10fdf76caa1cfc6b7ce16a2"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "34cb09f237c59ca943aea71db0d14daf10de1e07eefa1f255cd9f79ea1da5da4"
        },
        {
          "path": "tests/test_keychain.py",
          "sha256": "0a3fdb9afe3a9dabc4783884c81efcc00fbd240530b2a10c2e8d8fd770322609"
        }
      ],
      "scope_sha256": "bce103635ee2495c88e7e994f817ab3b4edc091815abfd4daac4164494af01e4",
      "red": null,
      "reason": null
    },
    {
      "id": "W4-RED-M1B-01-allowlist",
      "acceptance": [
        "AC-M1B-01"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_brains.py::test_the_allowlist_takes_names_in_any_case_and_endings_after_a_star",
        "tests/test_brains.py::test_a_command_brain_gets_only_what_it_needs_of_the_environment"
      ],
      "method": "Red drill M1B-01-allowlist through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/wave4/drills.log",
        "sha256": "ac3a1fea58936ecf82bacd96537f79434e1c8f031e534a1cbaabab418b998425"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "fff50c7d100160385ef3fda84de0bfb05d0aed0eaa01f2fd82df66782c14858e"
        }
      ],
      "scope_sha256": "a7aac1fe38b742ce35183be85cd464780d64c9c85375c9b9d16fd2f049c393e9",
      "red": {
        "mutation": "M1B-01-allowlist: in chatmon/brains.py, '    out = {k: v for k, v in environ.items() if k.upper() in exact or (starts and k.upper().startswith(starts))}' became '    out = dict(environ)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_allowlist_takes_names_in_any_case_and_endings_after_a_star",
        "observed_diagnostic": "_____ test_the_allowlist_takes_names_in_any_case_and_endings_after_a_star _____",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "466eabe1691faf35a6fa77c052daf222150b188048a52d7b426816fd95ee90be"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4-RED-M1B-02-strict-mcp",
      "acceptance": [
        "AC-M1B-02"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_brains.py::test_claude_code_is_started_without_tools_mcp_servers_or_anyone_asked",
        "tests/test_streaming.py::test_claude_code_streams_its_answer"
      ],
      "method": "Red drill M1B-02-strict-mcp through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/wave4/drills.log",
        "sha256": "ac3a1fea58936ecf82bacd96537f79434e1c8f031e534a1cbaabab418b998425"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "fff50c7d100160385ef3fda84de0bfb05d0aed0eaa01f2fd82df66782c14858e"
        }
      ],
      "scope_sha256": "a7aac1fe38b742ce35183be85cd464780d64c9c85375c9b9d16fd2f049c393e9",
      "red": {
        "mutation": "M1B-02-strict-mcp: in chatmon/brains.py, '\"--tools\", \"\", \"--strict-mcp-config\", \"--permission-mode\", \"dontAsk\",' became '\"--tools\", \"\", \"--permission-mode\", \"dontAsk\",'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_claude_code_is_started_without_tools_mcp_servers_or_anyone_asked",
        "observed_diagnostic": "____ test_claude_code_is_started_without_tools_mcp_servers_or_anyone_asked ____",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "0b169819a584c42a785bf788e46d10e190adb6d593b20f834d815ce3725cd961"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4-RED-M1B-03-owner-check",
      "acceptance": [
        "AC-M1B-03"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_brains.py::test_automatic_uses_only_a_model_server_of_yours_or_one_you_confirmed"
      ],
      "method": "Red drill M1B-03-owner-check through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/wave4/drills.log",
        "sha256": "ac3a1fea58936ecf82bacd96537f79434e1c8f031e534a1cbaabab418b998425"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "8088e2ee077fdae2399de93dccfc21919ba4269dab1f9eec963b06e9b2a74425"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_portowner.py",
          "sha256": "0dac6b0ce7b977c5facb5f7b4cee185c73442799a90be4208628e5a5c9b65f70"
        }
      ],
      "scope_sha256": "e9e0d8846e2ce6869fcd65c2e1367fd8ee3dfaeaaa98151c8812dc65c7502145",
      "red": {
        "mutation": "M1B-03-owner-check: in chatmon/brains.py, '        if b.automatic() and b.available(wait) and (not b.local or trusted(expand(b.url), wait)):' became '        if b.automatic() and b.available(wait):'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_automatic_uses_only_a_model_server_of_yours_or_one_you_confirmed",
        "observed_diagnostic": "____ test_automatic_uses_only_a_model_server_of_yours_or_one_you_confirmed ____",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "9b88111eb2daec6f679589270faa05e465d7661e9cb750f1611253ef6e55c14d"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4-RED-M1B-04-placeholder",
      "acceptance": [
        "AC-M1B-04"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_chats.py::test_a_brain_that_reads_files_never_gets_another_brains_answers"
      ],
      "method": "Red drill M1B-04-placeholder through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/wave4/drills.log",
        "sha256": "ac3a1fea58936ecf82bacd96537f79434e1c8f031e534a1cbaabab418b998425"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "f3b2bdce2d193aa9b795215993b34576ce303e31c790182a6bdf89f274e0ce8d"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "b181faa58af667a9a37405c7db6b6073f65e793198dc5fafd255f20b852f5f5c"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "b1acf8c868d28a5af93e40c580c1b948866f0a93c3f4f59f684d889c555a8c57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "46a0a4a5bda6fa6ba7cda972e97ef3167ae57b712ea3333f93822388f5be6dee"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "affe95b6d0bab7956280a75aaf0528e05caedf030fefeefef9fd6ae0b7cdd112"
        }
      ],
      "scope_sha256": "ef52703f3a72ae243619230323453eb3b43fd6b17c82cae3a11f48096422d68b",
      "red": {
        "mutation": "M1B-04-placeholder: in chatmon/chats.py, '                out.append((question, m.text if not own_only or _same(m, brain, name) else OTHER_ANSWER))' became '                out.append((question, m.text))'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_brain_that_reads_files_never_gets_another_brains_answers",
        "observed_diagnostic": "_______ test_a_brain_that_reads_files_never_gets_another_brains_answers _______",
        "before": [
          {
            "path": "chatmon/chats.py",
            "sha256": "f3b2bdce2d193aa9b795215993b34576ce303e31c790182a6bdf89f274e0ce8d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/chats.py",
            "sha256": "05c955a792786bf12e533e5e2b655ee75230bfcd285a34c79a42889c8d6198d8"
          }
        ],
        "after": [
          {
            "path": "chatmon/chats.py",
            "sha256": "f3b2bdce2d193aa9b795215993b34576ce303e31c790182a6bdf89f274e0ce8d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4-RED-M1B-06-range",
      "acceptance": [
        "AC-M1B-06"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_settings.py::test_a_bad_value_costs_only_its_own_setting",
        "tests/test_settings.py::test_every_setting_the_app_reads_as_a_number_is_one_after_loading"
      ],
      "method": "Red drill M1B-06-range through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/wave4/drills.log",
        "sha256": "ac3a1fea58936ecf82bacd96537f79434e1c8f031e534a1cbaabab418b998425"
      },
      "inputs": [
        {
          "path": "chatmon/chats.py",
          "sha256": "f3b2bdce2d193aa9b795215993b34576ce303e31c790182a6bdf89f274e0ce8d"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "b181faa58af667a9a37405c7db6b6073f65e793198dc5fafd255f20b852f5f5c"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "b1acf8c868d28a5af93e40c580c1b948866f0a93c3f4f59f684d889c555a8c57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "affe95b6d0bab7956280a75aaf0528e05caedf030fefeefef9fd6ae0b7cdd112"
        }
      ],
      "scope_sha256": "310a1ac589e64c6c79b83c04da433adf357585468ae508646cf4dba9487e14fa",
      "red": {
        "mutation": "M1B-06-range: in chatmon/settings.py, '        if not low <= number <= high:' became '        if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_bad_value_costs_only_its_own_setting",
        "observed_diagnostic": "_________________ test_a_bad_value_costs_only_its_own_setting _________________",
        "before": [
          {
            "path": "chatmon/settings.py",
            "sha256": "b1acf8c868d28a5af93e40c580c1b948866f0a93c3f4f59f684d889c555a8c57"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/settings.py",
            "sha256": "1a38cca6682daf977cbb68375b4a322f992f27ccdae6115749f1af001679019a"
          }
        ],
        "after": [
          {
            "path": "chatmon/settings.py",
            "sha256": "b1acf8c868d28a5af93e40c580c1b948866f0a93c3f4f59f684d889c555a8c57"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4-RED-M1B-07-kept-aside",
      "acceptance": [
        "AC-M1B-07"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_settings.py::test_a_damaged_state_file_is_kept_aside_and_the_last_good_copy_used",
        "tests/test_settings.py::test_a_damaged_memory_file_is_never_written_over"
      ],
      "method": "Red drill M1B-07-kept-aside through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/wave4/drills.log",
        "sha256": "ac3a1fea58936ecf82bacd96537f79434e1c8f031e534a1cbaabab418b998425"
      },
      "inputs": [
        {
          "path": "chatmon/chats.py",
          "sha256": "f3b2bdce2d193aa9b795215993b34576ce303e31c790182a6bdf89f274e0ce8d"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "b181faa58af667a9a37405c7db6b6073f65e793198dc5fafd255f20b852f5f5c"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "b1acf8c868d28a5af93e40c580c1b948866f0a93c3f4f59f684d889c555a8c57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "affe95b6d0bab7956280a75aaf0528e05caedf030fefeefef9fd6ae0b7cdd112"
        }
      ],
      "scope_sha256": "310a1ac589e64c6c79b83c04da433adf357585468ae508646cf4dba9487e14fa",
      "red": {
        "mutation": "M1B-07-kept-aside: in chatmon/settings.py, '    kept = _set_aside(path)' became '    kept = None'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_damaged_state_file_is_kept_aside_and_the_last_good_copy_used",
        "observed_diagnostic": "_____ test_a_damaged_state_file_is_kept_aside_and_the_last_good_copy_used _____",
        "before": [
          {
            "path": "chatmon/settings.py",
            "sha256": "b1acf8c868d28a5af93e40c580c1b948866f0a93c3f4f59f684d889c555a8c57"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/settings.py",
            "sha256": "56dbed61269412e388143b9bf970304cc89309922a9d652fed8e216041f90773"
          }
        ],
        "after": [
          {
            "path": "chatmon/settings.py",
            "sha256": "b1acf8c868d28a5af93e40c580c1b948866f0a93c3f4f59f684d889c555a8c57"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4-RED-M1B-08-file-mode",
      "acceptance": [
        "AC-M1B-08"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "/var/tmp/plans-venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_settings.py::test_files_are_made_private_from_the_start_and_folders_too"
      ],
      "method": "Red drill M1B-08-file-mode in WSL (Arch Linux) through docs/delivery/reports/wave4/wsl_drills.py, which hands each drill to tests/drills/run.py's own drill step, under xvfb-run -a with /var/tmp/plans-venv/bin/python, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/wave4/drills-linux.log",
        "sha256": "d635db22f65c93c6252018f94d4ebb0c855c97696422014efb02380c6a1f7a2d"
      },
      "inputs": [
        {
          "path": "chatmon/chats.py",
          "sha256": "f3b2bdce2d193aa9b795215993b34576ce303e31c790182a6bdf89f274e0ce8d"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "b181faa58af667a9a37405c7db6b6073f65e793198dc5fafd255f20b852f5f5c"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "b1acf8c868d28a5af93e40c580c1b948866f0a93c3f4f59f684d889c555a8c57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "affe95b6d0bab7956280a75aaf0528e05caedf030fefeefef9fd6ae0b7cdd112"
        }
      ],
      "scope_sha256": "310a1ac589e64c6c79b83c04da433adf357585468ae508646cf4dba9487e14fa",
      "red": {
        "mutation": "M1B-08-file-mode: in chatmon/settings.py, 'os.fchmod(fd, 0o600)' became 'os.fchmod(fd, 0o644)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_files_are_made_private_from_the_start_and_folders_too",
        "observed_diagnostic": "__________ test_files_are_made_private_from_the_start_and_folders_too __________",
        "before": [
          {
            "path": "chatmon/settings.py",
            "sha256": "b1acf8c868d28a5af93e40c580c1b948866f0a93c3f4f59f684d889c555a8c57"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/settings.py",
            "sha256": "37a48e16e31b7342b3351aed28c491ad8cc8bc6a8dd0e7c2bdef98613a63095d"
          }
        ],
        "after": [
          {
            "path": "chatmon/settings.py",
            "sha256": "b1acf8c868d28a5af93e40c580c1b948866f0a93c3f4f59f684d889c555a8c57"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4-RED-M1B-09-status",
      "acceptance": [
        "AC-M1B-09"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_streaming.py::test_an_http_error_says_what_the_provider_said_the_status_and_what_to_do"
      ],
      "method": "Red drill M1B-09-status through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/wave4/drills.log",
        "sha256": "ac3a1fea58936ecf82bacd96537f79434e1c8f031e534a1cbaabab418b998425"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "fff50c7d100160385ef3fda84de0bfb05d0aed0eaa01f2fd82df66782c14858e"
        }
      ],
      "scope_sha256": "ea140c3de5455e4f0225d8a3f01b877df05e61216868787cc5c05b8842e72c80",
      "red": {
        "mutation": "M1B-09-status: in chatmon/brains.py, 'if isinstance(status, int) and status >= 400:' became 'if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_an_http_error_says_what_the_provider_said_the_status_and_what_to_do",
        "observed_diagnostic": "_ test_an_http_error_says_what_the_provider_said_the_status_and_what_to_do[401-body0-invalid x-api-key-Check its key in ANTHROPIC_API_KEY] _",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "da7a6f7898c90463d733620612e83eb9599fc6d42d10f8e6f5e68ba2000e1669"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4-RED-M1B-10-no-wait",
      "acceptance": [
        "AC-M1B-10"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_brains.py::test_cancelling_on_windows_stops_the_tool_behind_a_cmd_file_without_waiting"
      ],
      "method": "Red drill M1B-10-no-wait through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/wave4/drills.log",
        "sha256": "ac3a1fea58936ecf82bacd96537f79434e1c8f031e534a1cbaabab418b998425"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "8088e2ee077fdae2399de93dccfc21919ba4269dab1f9eec963b06e9b2a74425"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "fff50c7d100160385ef3fda84de0bfb05d0aed0eaa01f2fd82df66782c14858e"
        },
        {
          "path": "tests/test_portowner.py",
          "sha256": "0dac6b0ce7b977c5facb5f7b4cee185c73442799a90be4208628e5a5c9b65f70"
        }
      ],
      "scope_sha256": "9a85477fc8370b888434ef03418c0d3c462277a8683b325f87b9e74c4e546571",
      "red": {
        "mutation": "M1B-10-no-wait: in chatmon/brains.py, '    threading.Thread(target=end, daemon=True).start()' became '    end()'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_cancelling_on_windows_stops_the_tool_behind_a_cmd_file_without_waiting",
        "observed_diagnostic": "_ test_cancelling_on_windows_stops_the_tool_behind_a_cmd_file_without_waiting _",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "0d6f541c58ea853ea8d7b335bf8202069dd0d5494d5f77d9e36d3698f2212cc8"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4-RED-M1B-11-finder",
      "acceptance": [
        "AC-M1B-11"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_brains.py::test_finding_the_brain_never_probes_on_the_screens_thread_and_remembers"
      ],
      "method": "Red drill M1B-11-finder through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/wave4/drills.log",
        "sha256": "ac3a1fea58936ecf82bacd96537f79434e1c8f031e534a1cbaabab418b998425"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "8088e2ee077fdae2399de93dccfc21919ba4269dab1f9eec963b06e9b2a74425"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "fff50c7d100160385ef3fda84de0bfb05d0aed0eaa01f2fd82df66782c14858e"
        },
        {
          "path": "tests/test_portowner.py",
          "sha256": "0dac6b0ce7b977c5facb5f7b4cee185c73442799a90be4208628e5a5c9b65f70"
        }
      ],
      "scope_sha256": "9a85477fc8370b888434ef03418c0d3c462277a8683b325f87b9e74c4e546571",
      "red": {
        "mutation": "M1B-11-finder: in chatmon/brains.py, '        quick = choose(brains, configured, picked, wait=False, prefer=prefer)' became '        quick = choose(brains, configured, picked, wait=True, prefer=prefer)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_finding_the_brain_never_probes_on_the_screens_thread_and_remembers",
        "observed_diagnostic": "___ test_finding_the_brain_never_probes_on_the_screens_thread_and_remembers ___",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "97198f81a6ee5c322e4594db995e9e70fde8619d2f3ceed9746e409b66ef91a8"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4-RED-M1B-13-saved-key",
      "acceptance": [
        "AC-M1B-13"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_keychain.py::test_a_brain_uses_its_saved_key_when_its_variable_isnt_set"
      ],
      "method": "Red drill M1B-13-saved-key through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/wave4/drills.log",
        "sha256": "ac3a1fea58936ecf82bacd96537f79434e1c8f031e534a1cbaabab418b998425"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "4a477a372dae3f820a19a62a8874d931e7e4d127c10fdf76caa1cfc6b7ce16a2"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "34cb09f237c59ca943aea71db0d14daf10de1e07eefa1f255cd9f79ea1da5da4"
        },
        {
          "path": "tests/test_keychain.py",
          "sha256": "0a3fdb9afe3a9dabc4783884c81efcc00fbd240530b2a10c2e8d8fd770322609"
        }
      ],
      "scope_sha256": "bce103635ee2495c88e7e994f817ab3b4edc091815abfd4daac4164494af01e4",
      "red": {
        "mutation": "M1B-13-saved-key: in chatmon/brains.py, '        return keychain.get(self.name) or \"\"' became '        return \"\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_brain_uses_its_saved_key_when_its_variable_isnt_set",
        "observed_diagnostic": "_________ test_a_brain_uses_its_saved_key_when_its_variable_isnt_set __________",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "35a4460a88bdc405096a9878642d7ba6ce763e26e1b83bab2cb088cee659d3c0"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4-RED-M1B-14-seconds",
      "acceptance": [
        "AC-M1B-14"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_streaming.py::test_a_brain_test_says_how_long_the_answer_took_or_whats_wrong"
      ],
      "method": "Red drill M1B-14-seconds through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/wave4/drills.log",
        "sha256": "ac3a1fea58936ecf82bacd96537f79434e1c8f031e534a1cbaabab418b998425"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "fff50c7d100160385ef3fda84de0bfb05d0aed0eaa01f2fd82df66782c14858e"
        },
        {
          "path": "tests/test_streaming.py",
          "sha256": "de7c8d05cf58c33dc5a7cb878f4af3c461c2bda8ddb767ffb1c3ac71e9852ddb"
        }
      ],
      "scope_sha256": "bf8a478e01bbb12ec421e0c1ee848932d21a9acc2892dac8875dd3d99808cfaf",
      "red": {
        "mutation": "M1B-14-seconds: in chatmon/brains.py, '        self.finished.emit(ok, text, round(time.monotonic() - self._started, 2))' became '        self.finished.emit(ok, text, 0.0)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_brain_test_says_how_long_the_answer_took_or_whats_wrong",
        "observed_diagnostic": "_______ test_a_brain_test_says_how_long_the_answer_took_or_whats_wrong ________",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "a3ef748d3615e54c0dfc0994a19517e103fc60140d9ee3c335eb885b04e408ae"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4-RED-M1B-15-chat-brain",
      "acceptance": [
        "AC-M1B-15"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_chats.py::test_a_chat_remembers_its_brain_and_the_question_to_ask_another"
      ],
      "method": "Red drill M1B-15-chat-brain through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/wave4/drills.log",
        "sha256": "ac3a1fea58936ecf82bacd96537f79434e1c8f031e534a1cbaabab418b998425"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "f3b2bdce2d193aa9b795215993b34576ce303e31c790182a6bdf89f274e0ce8d"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "b181faa58af667a9a37405c7db6b6073f65e793198dc5fafd255f20b852f5f5c"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "b1acf8c868d28a5af93e40c580c1b948866f0a93c3f4f59f684d889c555a8c57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "46a0a4a5bda6fa6ba7cda972e97ef3167ae57b712ea3333f93822388f5be6dee"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "affe95b6d0bab7956280a75aaf0528e05caedf030fefeefef9fd6ae0b7cdd112"
        }
      ],
      "scope_sha256": "ef52703f3a72ae243619230323453eb3b43fd6b17c82cae3a11f48096422d68b",
      "red": {
        "mutation": "M1B-15-chat-brain: in chatmon/chats.py, '            self.brain = message.by' became '            pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_chat_remembers_its_brain_and_the_question_to_ask_another",
        "observed_diagnostic": "_______ test_a_chat_remembers_its_brain_and_the_question_to_ask_another _______",
        "before": [
          {
            "path": "chatmon/chats.py",
            "sha256": "f3b2bdce2d193aa9b795215993b34576ce303e31c790182a6bdf89f274e0ce8d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/chats.py",
            "sha256": "895fedf9386d0cd7c54900f9a1534b4bf78f75ddbfc20c714cb9c71b9c7ed0c2"
          }
        ],
        "after": [
          {
            "path": "chatmon/chats.py",
            "sha256": "f3b2bdce2d193aa9b795215993b34576ce303e31c790182a6bdf89f274e0ce8d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4-RED-M1B-16-no-secrets",
      "acceptance": [
        "AC-M1B-16"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_backup.py::test_no_key_ever_goes_into_a_backup",
        "tests/test_backup.py::test_a_key_slipped_into_a_backup_by_hand_is_never_brought_back"
      ],
      "method": "Red drill M1B-16-no-secrets through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/wave4/drills.log",
        "sha256": "ac3a1fea58936ecf82bacd96537f79434e1c8f031e534a1cbaabab418b998425"
      },
      "inputs": [
        {
          "path": "chatmon/backup.py",
          "sha256": "d3bd1cd5888a3154ece55bbe2576c92f009dbd129119f8229d2401f343b0e3ac"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "f3b2bdce2d193aa9b795215993b34576ce303e31c790182a6bdf89f274e0ce8d"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "b181faa58af667a9a37405c7db6b6073f65e793198dc5fafd255f20b852f5f5c"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "b1acf8c868d28a5af93e40c580c1b948866f0a93c3f4f59f684d889c555a8c57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "c4d630d291cbc80f16712e2d37ae88f850dc690270bfad375bdd42cf55cda379"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "affe95b6d0bab7956280a75aaf0528e05caedf030fefeefef9fd6ae0b7cdd112"
        }
      ],
      "scope_sha256": "14b9dd0e0132f9867738c90cdb7201b042b28759dc45834d1a34ba8602db29fb",
      "red": {
        "mutation": "M1B-16-no-secrets: in chatmon/backup.py, '        return {k: _no_secrets(v) for k, v in value.items() if not (isinstance(k, str) and _SECRET.search(k))}' became '        return {k: _no_secrets(v) for k, v in value.items()}'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_no_key_ever_goes_into_a_backup",
        "observed_diagnostic": "_____________________ test_no_key_ever_goes_into_a_backup _____________________",
        "before": [
          {
            "path": "chatmon/backup.py",
            "sha256": "d3bd1cd5888a3154ece55bbe2576c92f009dbd129119f8229d2401f343b0e3ac"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/backup.py",
            "sha256": "4353fd2f014e818bf19f09689ceed3cb6aec0d2182155f6b92a4e3ef9c4ca425"
          }
        ],
        "after": [
          {
            "path": "chatmon/backup.py",
            "sha256": "d3bd1cd5888a3154ece55bbe2576c92f009dbd129119f8229d2401f343b0e3ac"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4-RED-M1B-17-only-its-brain",
      "acceptance": [
        "AC-M1B-17"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_chats.py::test_attached_text_goes_again_only_to_the_brain_of_that_name",
        "tests/test_chats.py::test_attached_text_goes_again_only_to_the_brain_it_went_to"
      ],
      "method": "Red drill M1B-17-only-its-brain through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/wave4/drills.log",
        "sha256": "ac3a1fea58936ecf82bacd96537f79434e1c8f031e534a1cbaabab418b998425"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "f3b2bdce2d193aa9b795215993b34576ce303e31c790182a6bdf89f274e0ce8d"
        },
        {
          "path": "chatmon/memory.py",
          "sha256": "b181faa58af667a9a37405c7db6b6073f65e793198dc5fafd255f20b852f5f5c"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "b1acf8c868d28a5af93e40c580c1b948866f0a93c3f4f59f684d889c555a8c57"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "46a0a4a5bda6fa6ba7cda972e97ef3167ae57b712ea3333f93822388f5be6dee"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "affe95b6d0bab7956280a75aaf0528e05caedf030fefeefef9fd6ae0b7cdd112"
        }
      ],
      "scope_sha256": "ef52703f3a72ae243619230323453eb3b43fd6b17c82cae3a11f48096422d68b",
      "red": {
        "mutation": "M1B-17-only-its-brain: in chatmon/chats.py, '                if m.sent and _same(m, brain, name):' became '                if m.sent:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_attached_text_goes_again_only_to_the_brain_of_that_name",
        "observed_diagnostic": "________ test_attached_text_goes_again_only_to_the_brain_of_that_name _________",
        "before": [
          {
            "path": "chatmon/chats.py",
            "sha256": "f3b2bdce2d193aa9b795215993b34576ce303e31c790182a6bdf89f274e0ce8d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/chats.py",
            "sha256": "00e4d1cfc642b9da417f65282ed49c976cf2e34b35bc1a29d3144f65da9afd63"
          }
        ],
        "after": [
          {
            "path": "chatmon/chats.py",
            "sha256": "f3b2bdce2d193aa9b795215993b34576ce303e31c790182a6bdf89f274e0ce8d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4-RED-M1B-05-stale-folders",
      "acceptance": [
        "AC-M1B-05"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_brains.py::test_folders_a_stopped_chatmon_left_are_removed_and_running_ones_kept"
      ],
      "method": "Red drill W4-M1B-05-stale-folders through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/wave4/drills-new.log",
        "sha256": "e7d00a027deba6de0f3436f45bf04bca523561bbb44d907e81f929298f9897a9"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "fff50c7d100160385ef3fda84de0bfb05d0aed0eaa01f2fd82df66782c14858e"
        }
      ],
      "scope_sha256": "a7aac1fe38b742ce35183be85cd464780d64c9c85375c9b9d16fd2f049c393e9",
      "red": {
        "mutation": "W4-M1B-05-stale-folders: in chatmon/brains.py, '_tidying = threading.Thread(target=remove_stale_folders, name=\"chatmon-tidy\", daemon=True)' became '_tidying = threading.Thread(target=lambda: 0, name=\"chatmon-tidy\", daemon=True)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_folders_a_stopped_chatmon_left_are_removed_and_running_ones_kept",
        "observed_diagnostic": "____ test_folders_a_stopped_chatmon_left_are_removed_and_running_ones_kept ____",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "56bf2512b02017323703db27086e9f915424348c36eee0dddd7ef30ac3e63ac7"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4-RED-M1B-12-partial",
      "acceptance": [
        "AC-M1B-12"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_streaming.py::test_the_anthropic_api_streams_each_piece_as_its_written",
        "tests/test_streaming.py::test_the_openai_responses_api_streams"
      ],
      "method": "Red drill W4-M1B-12-partial through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "ruff": "0.17.4",
          "pyqt6": "6.11.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m1b/wave4/drills-new.log",
        "sha256": "e7d00a027deba6de0f3436f45bf04bca523561bbb44d907e81f929298f9897a9"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "8088e2ee077fdae2399de93dccfc21919ba4269dab1f9eec963b06e9b2a74425"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "docs/delivery/reports/wave4/wsl_drills.py",
          "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "fff50c7d100160385ef3fda84de0bfb05d0aed0eaa01f2fd82df66782c14858e"
        },
        {
          "path": "tests/test_portowner.py",
          "sha256": "0dac6b0ce7b977c5facb5f7b4cee185c73442799a90be4208628e5a5c9b65f70"
        },
        {
          "path": "tests/test_streaming.py",
          "sha256": "de7c8d05cf58c33dc5a7cb878f4af3c461c2bda8ddb767ffb1c3ac71e9852ddb"
        }
      ],
      "scope_sha256": "a0c96282895470aae931cbb320447e7afffdb9943c494755d2f4b862dfd64b51",
      "red": {
        "mutation": "W4-M1B-12-partial: in chatmon/brains.py, '            for piece in stream.feed(chunk):\\n                self.partial.emit(piece)\\n            return' became '            stream.feed(chunk)\\n            return'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_anthropic_api_streams_each_piece_as_its_written",
        "observed_diagnostic": "__________ test_the_anthropic_api_streams_each_piece_as_its_written ___________",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "6ae03621f760d0587de6a0b61c669ee340cbc4a3d3398c7810cdb309905be6bf"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
          }
        ]
      },
      "reason": null
    }
  ],
  "checkpoint": {
    "scope_sha256": "b24e2dc2976a4418bf9560d0c3c4534f374818258ced714d89f55e08a5078a05",
    "inputs": [
      {
        "path": "chatmon/backup.py",
        "sha256": "d3bd1cd5888a3154ece55bbe2576c92f009dbd129119f8229d2401f343b0e3ac"
      },
      {
        "path": "chatmon/brains.py",
        "sha256": "562ce2962dea886224b127b59285226238f351895f461fb1330daa07442a0c38"
      },
      {
        "path": "chatmon/chats.py",
        "sha256": "f3b2bdce2d193aa9b795215993b34576ce303e31c790182a6bdf89f274e0ce8d"
      },
      {
        "path": "chatmon/keychain.py",
        "sha256": "4a477a372dae3f820a19a62a8874d931e7e4d127c10fdf76caa1cfc6b7ce16a2"
      },
      {
        "path": "chatmon/memory.py",
        "sha256": "b181faa58af667a9a37405c7db6b6073f65e793198dc5fafd255f20b852f5f5c"
      },
      {
        "path": "chatmon/portowner.py",
        "sha256": "8088e2ee077fdae2399de93dccfc21919ba4269dab1f9eec963b06e9b2a74425"
      },
      {
        "path": "chatmon/settings.py",
        "sha256": "b1acf8c868d28a5af93e40c580c1b948866f0a93c3f4f59f684d889c555a8c57"
      },
      {
        "path": "docs/delivery/ASSESSMENT.md",
        "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
      },
      {
        "path": "docs/delivery/ROADMAP.md",
        "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
      },
      {
        "path": "docs/delivery/reports/wave4/cilog.py",
        "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
      },
      {
        "path": "docs/delivery/reports/wave4/wsl_drills.py",
        "sha256": "a2aca37f8755a050308ad61cfddb22745a397de4726ff8adff42adf9a4d0f7e3"
      },
      {
        "path": "pyproject.toml",
        "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
      },
      {
        "path": "tests/conftest.py",
        "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
      },
      {
        "path": "tests/drills/run.py",
        "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
      },
      {
        "path": "tests/fake_secrets.py",
        "sha256": "34cb09f237c59ca943aea71db0d14daf10de1e07eefa1f255cd9f79ea1da5da4"
      },
      {
        "path": "tests/test_backup.py",
        "sha256": "c4d630d291cbc80f16712e2d37ae88f850dc690270bfad375bdd42cf55cda379"
      },
      {
        "path": "tests/test_brains.py",
        "sha256": "fff50c7d100160385ef3fda84de0bfb05d0aed0eaa01f2fd82df66782c14858e"
      },
      {
        "path": "tests/test_chats.py",
        "sha256": "46a0a4a5bda6fa6ba7cda972e97ef3167ae57b712ea3333f93822388f5be6dee"
      },
      {
        "path": "tests/test_keychain.py",
        "sha256": "0a3fdb9afe3a9dabc4783884c81efcc00fbd240530b2a10c2e8d8fd770322609"
      },
      {
        "path": "tests/test_portowner.py",
        "sha256": "0dac6b0ce7b977c5facb5f7b4cee185c73442799a90be4208628e5a5c9b65f70"
      },
      {
        "path": "tests/test_settings.py",
        "sha256": "affe95b6d0bab7956280a75aaf0528e05caedf030fefeefef9fd6ae0b7cdd112"
      },
      {
        "path": "tests/test_streaming.py",
        "sha256": "de7c8d05cf58c33dc5a7cb878f4af3c461c2bda8ddb767ffb1c3ac71e9852ddb"
      }
    ],
    "environment": {
      "platform": "windows",
      "tools": {
        "python": "3.14.10",
        "pytest": "9.2.0",
        "ruff": "0.17.4",
        "pyqt6": "6.11.0"
      }
    },
    "verified_tasks": [
      "T-M1B-A",
      "T-M1B-B",
      "T-M1B-C",
      "T-M1B-D",
      "T-M1B-E",
      "T-M1B-F",
      "T-M1B-G",
      "T-M1B-H",
      "T-M1B-I",
      "T-M1B-J"
    ],
    "pending_operations": [],
    "next_action": "None in M1B on fb19cb9. The other workers' merges change files these receipts are bound to: re-run the suite and this plan's drill specs in wave4/ on the merged tree.",
    "source_revision": "fb19cb934fa03b7e3bc6e3ba192a366f1a3093d0"
  }
}
```
