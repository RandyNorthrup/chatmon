# M1B readiness review, 2026-11-14

Reviewed: the M1B section of [ASSESSMENT.md](../../ASSESSMENT.md), the [roadmap](../../ROADMAP.md) (owner decisions,
file ownership, the M1B/M7 contract, rules for workers) and the plan's ledger, against the code at `5346385`
(`brains.py`, `chats.py`, `memory.py`, `settings.py`, and their callers in `app.py`, `context.py`, `settingswin.py`,
`tests/`). This is a review of the requirements, not proof that any code works.

## Findings re-checked in the code

| ID | Re-check | Result |
|---|---|---|
| M1B-01 | `Asker._run`: `QProcessEnvironment.systemEnvironment()` plus two inserts | Real |
| M1B-02 | Preset `claude`: `-p --tools "" --no-session-persistence` only; `claude --help` (2.1.288) | Real. `--permission-mode default` is accepted but unlisted; `dontAsk` chosen (plan, Decisions) |
| M1B-03 | `choose()` auto path: `available()` → `reachable()` only, no owner check | Real |
| M1B-04 | `app._send`: `chat.history(brain.label)` gives every brain's answers to any brain; summary likewise | Real. The fix needs `app.py` to pass the guard: data API here, wiring in Integration notes |
| M1B-05 | `tempfile.mkdtemp(prefix="chatmon-ask-")`, removed only by `_drop_output_file` | Real |
| M1B-06 | `load_config` returns `merge(DEFAULTS, user)` unchecked; `int("big")` in `app.py:156`; `_every` overflows past 596 h | Real ✓ (coordinator) |
| M1B-07 | `State.load` swallows `ValueError` and starts `{}`; no fsync in any save | Real |
| M1B-08 | `write_text` then `chmod`; `mkdir` without mode for state/config | Real |
| M1B-09 | `_reply_finished` never reads the status; a 401 body is parsed as an answer | Real |
| M1B-10 | `_kill_tree` runs `taskkill` with `timeout=5`, then `waitForFinished(1000)`, on the screen's thread | Real |
| M1B-11 | `choose(wait=True)` probes each local URL with a 0.15 s connect on the caller's thread | Real |
| M1B-12 | No `stream` anywhere | Real (feature) |
| M1B-13 | `Brain.key()` reads `api_key` or the environment only | Real (feature) |
| M1B-14..17 | Not present | Features |

## Clarity, conflicts and gaps

- **Contract wording.** The roadmap's M1B/M7 contract names `Asker.partial(str)`, `keychain.get/set/delete` and a
  brain `test()`. `partial` carries each new piece of text (the ask box's `append_partial(text)` appends), not the text
  so far. Recorded in Integration notes.
- **Things only the app can do.** "The user is told" (M1B-07), giving the guard to `chat.history` (M1B-04), showing a
  confirmed server (M1B-03), and wiring Test, keys, backup and brain per chat into Settings and the menus belong to
  `app.py`/`settingswin.py`, which M1B may not edit. Each criterion is tested at the API M1B owns; the app's part is
  an Integration note for M7, not counted as delivered here.
- **Missing failure behavior, now specified.** Keychain unavailable or locked: `get` returns None, `set`/`delete`
  return an error sentence. Backup import of a bad zip: refused whole, nothing changed. Config value out of range:
  clamped, and reported; of the wrong type: the default, and reported. A brain stream that ends without a final
  event: the text received so far is the answer if there is any, else an error.
- **Terminology.** "Brain name" is the key in `[ai.brains]` (stable); "label" is what's shown. Chats today match the
  brain by label; M1B-15/17 record the name too and prefer it, so two brains sharing a label stay apart.
- **Scope.** Distribution, the Settings window and `app.py` are out of scope (other milestones). No new runtime
  dependency: ctypes, QtDBus, `zipfile`, `json`.
- **Platform coverage.** Windows paths run here. Linux paths (`/proc/net/tcp`, Secret Service, POSIX modes) run in a
  throwaway WSL Arch venv (PyQt6 6.11, `dbus-run-session`) as well as in CI. macOS paths (Keychain through
  Security.framework, `lsof`) run only in CI: a pending operation in the checkpoint.

## Coverage

Every requirement M1B-01..17 has one acceptance criterion with behavior and red checks, and each criterion has an
owning task (ledger). Dependencies: T-M1B-D and T-M1B-J need the writer from T-M1B-C; T-M1B-G needs the error mapping
(E), the environment (A) and the cancel path (F); T-M1B-I needs E. No cycles.

Verdict: ready, with the app-side parts recorded as Integration notes rather than claimed.
