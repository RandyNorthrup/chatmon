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

## Readiness review

[reports/m1b/readiness.md](reports/m1b/readiness.md).

## Integration notes

Filled in from what was actually delivered; see the end of this plan.

## Changelog notes

See the end of this plan.

## README notes

See the end of this plan.

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
        "revision": "5346385"
      },
      {
        "path": "pyproject.toml",
        "revision": "5346385"
      }
    ],
    "inputs": [
      "tests/conftest.py",
      "tests/drills/run.py"
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "pass",
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
      "reason": null
    }
  ],
  "checkpoint": null
}
```
