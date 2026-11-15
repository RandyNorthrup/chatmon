# M6B: Static analysis and logging

Milestone M6B of the [improvement roadmap](ROADMAP.md), assessment items M6B-01 to M6B-03, plus the unclosed
resources [M6A's integration note 4](m6a-ci-tooling.md#integration-notes) left for M6B. Branch `wave3/m6b`, from
`improve/assessment-fixes` at `dd2e375` (waves 1 and 2 and M8's phase A merged), brought up to `fd0fe70` (the
coordinator's CI fix: UI Automation stays on Windows, Qt 6.4 guards) by the authorized merge `04690ba`, then to `ff78572` (M8's phase B, and the README and changelog for 0.10.0) by `e2ecbf2`. Commits: `64bff38` (ruff), `0f58e71` (the log), `cdfeeca` (types, loggers and leaks), `33d0da8` (the leak in test_wayland), `0116403` (this plan), `e2ecbf2` (the merge, with updates.py's conflict resolved) and `e2541ef` (the plan again) for phase A, merged into the feature branch at `210c6e0`; then, from `78853bf` (M8 closed), `1f82a77` (phase B) and this plan. The ledger
at the end owns every requirement, task, state and receipt. Reports, logs and the drill spec are in
[reports/m6b/](reports/m6b/).

## Rationale

### Scope

M6B ran in two phases, because M8 was translating the strings of the app's eight hub files meanwhile:

- **Phase A:** every module except `chatmon/app.py`, `settingswin.py`, `cli.py`, `menus.py`, `messages.py`,
  `asking.py`, `commands.py` and `settings.py`, and their tests; the ruff and mypy configuration; the new
  `chatmon/log.py`.
- **Phase B (after M8 merged):** those eight files: their ruff findings and per-file exemptions, their mypy
  exemptions, app.py's switch from its hand-made log to `log.setup()`, and their `print()` diagnostics and
  swallowed errors; then dropping `default::ResourceWarning`.
- **Leftovers in the same files (M6B-LEFT),** added by the coordinator with phase B: the *status* command waited for
  the brain on its worker; Settings didn't show the hotkey's Wayland wording, which hotkey.py kept private; sound's
  players weren't let go of at quit; and a reminder test's bubble came late once on CI's macOS.

Non-goals: `ruff format` (the code keeps its own layout), new runtime dependencies, translating log lines (M8's rule:
logs and stderr diagnostics are English), and changing what any user-facing output says, apart from Open the log's
sentence (no longer true once the log is always kept) and the hotkey line Settings gained (leftover 2).

The coordinator added two rules during this wave, both taken up here: every module imports on every OS (a test
imports each one, in CI on all three), and a Qt API newer than 6.4 is used only where it exists (Ubuntu 24.04's
PyQt6 runs on Qt 6.4; the distribution CI job is what catches a slip, and the review below looks for one in every
line changed here).

### Design

**Ruff (M6B-01).** `pyproject.toml` selects F, E9, B, UP, C4, PIE, PERF, RUF, S, DTZ, BLE and C90 (McCabe, 15).
RUF001-003 are off everywhere: ×, ÷, π and typographic quotes are written on purpose. A finding is fixed when the fix
is honest, otherwise suppressed on its own line with the reason after the code (`# noqa: S603 - a fixed
package-manager query`). Scoped per-file ignores, each with its reason in `pyproject.toml`:

| Where | Ignored | Why |
|---|---|---|
| `tests/**` | S101, S603, S607, S108, S311, S314, S105/S106, DTZ001/005/006 | pytest's asserts; the tests' own fixed commands; mkdtemp'd short socket folders; test data's randomness; XML Chatmon wrote; made-up tokens (added with M8's merge, whose test passes `copy_token="t"`); local wall time, as in the code |
| `docs/delivery/reports/m2,m3,m4b,m6a,m7/**` | the new families | recorded scripts whose bytes their ledgers bind by SHA-256 |

Functions over 15 are split into named helpers when there is an honest seam (the stage's frame tick, the overlay's
keyboard events, the stage menu's keys, the string extractor's scan); a scoped `noqa: C901` with a reason otherwise.

**mypy (M6B-02).** Each module comes off the exemption list once `mypy --platform linux`, `win32` and `darwin` all
pass it. Errors are fixed in the code: narrowing with an `if ... is None` guard or a local variable rather than a
cast, and never an `assert` (ruff's S101 holds production code to that); `typing.cast` only where an API is typed
more loosely than it behaves, with the reason; `# type: ignore[code]` only for a stub's mistake, with the reason.
Platform-only ctypes names are reached the way `winrt.py` does (`getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)`)
or under a `sys.platform` check mypy understands, so the module still imports everywhere.

**Logging (M6B-03).** `chatmon/log.py`:

| Call | What it does |
|---|---|
| `log.setup()` | Once, as Chatmon starts: Chatmon's loggers (`chatmon.*`) go to `chatmon.log` in the state folder, made 0600 on POSIX and never opened through a symbolic link, starting over past 1 MB with the last kept as `chatmon.log.old` (the same name and limit as app.py's hand-made log); warnings and worse to stderr too, when there is one, as `chatmon: <message>`. Level INFO, or DEBUG when `CHATMON_DEBUG` is set to anything (the overlay's switch's meaning). Returns the log's path, or None when the state folder can't be written. |
| `log.reset()` | Takes away and closes what `setup()` added (tests). |
| `log.blank_keys(text)` | Blanks anything shaped like a provider's key (`sk-…`, `AIza…`, `xai-…`, `gsk_…`, a Bearer token). Both handlers format through it, tracebacks included. |

app.py calls `setup()` first thing in `run()`, in place of its own log (which it kept only without a console, by
pointing stdout and stderr at the file), and logs an exception that escapes a slot at error level, traceback and
all, before offering to report it.

Conventions for every module:

1. `logger = logging.getLogger(__name__)` after the imports. Arguments are passed to the call (`"couldn't read
   %s: %s", path, exc`), never formatted into the message first.
2. **debug:** an error Chatmon carries on past. **info:** something worth having in a bug report (a question that
   failed). **warning:** a problem the person should hear of, which used to be `print(..., file=sys.stderr)`.
   **error:** uncaught exceptions (app.py, phase B).
3. A handler *hides* an error when something expected to work fails and the code carries on without telling anyone:
   `pass`, `continue`, a default returned or a fallback taken. It logs at debug what failed and the exception
   (`exc_info=True` where the traceback is the useful part, as in a blind `except Exception`).
4. Left as they are, each recorded in [handlers.md](reports/m6b/handlers.md) with which kind it is: the exception is
   the answer (parsing or validating input, probing whether bytes are text); flow control (`BlockingIOError` on a
   non-blocking socket, `queue.Empty`, `ProcessLookupError` asking whether a process lives, a file that isn't
   there being the answer); probing an API that differs between Qt or OS versions (a `TypeError` from
   `disconnect()`, an optional module's `ImportError`); the error reaches the person (it's in the message returned,
   emitted or raised); and loops where any item may fail routinely (a process gone mid-scan).
5. Never logged: keys or tokens, chat text (questions, answers, transcripts), prompts, attachments and their
   contents, the clipboard, or what's typed in the ask box. Logged: what failed, paths, error strings, status
   codes, counts and lengths, the names of brains and agents.
6. `print()` diagnostics become `logger.warning` with the same words, without the `chatmon:` prefix, which the
   console handler adds back. Output meant for the person at a terminal stays `print`: `cli.py` (phase B) and the
   `verify-update` helper in `releasecheck.py`, which root runs and whose words the installer shows.

**Unclosed resources.** M6A's list ([note 4](m6a-ci-tooling.md#integration-notes)) is closed at its sources, and
whatever remains is listed under Integration notes for phase B, which can then drop `default::ResourceWarning` from
`pyproject.toml`.

### Reuse

- `brains._scrub` already kept the brain's own key out of error messages; the Asker's failure log goes through it.
- app.py's `_open_private` (0600, `O_NOFOLLOW`, `fchmod` on an older file) is the model for the log's opener, and
  its `LOG_LIMIT` and `.old` name are kept.
- `tests/drills/run.py` runs the test drills; `replay_server.py` is the pretend provider for the brain-error test;
  the M4B import test's fresh-interpreter approach is reused for every module.
- `docs/delivery/reports/m7/receipt.py`'s way of binding receipts to the validator's snapshot is reused.

New code with its own responsibility: `chatmon/log.py` (the one place logging is set up), `tests/test_log.py`,
`tests/test_imports.py`, and the gate drills (`reports/m6b/gate_drills.py`), which prove ruff's new families and
mypy fail on a violation (the drill harness only runs pytest).

### Not real, deferred, or moved

- **E402 and E731 are not added.** The 58 old `# noqa: E402` comments were unused even with E402 on (ruff allows
  imports after `os.environ` and `sys.path` changes), so they were removed as RUF100 asks
  ([readiness.md](reports/m6b/readiness.md), D2).
- **PyQt6 6.12's stubs.** sysnotify.py and report.py pass with them (the brief). The rest of the package has
  about a hundred errors that appear only with 6.12's stubs, the same on all three platforms, almost all one stub
  bug (`pyqtSignal(...)`: "Missing named argument 'arguments'", in every QObject with signals) and Self-typed
  parents; CI's mypy runs the locked 6.11, which passes ([linux-types-logs.log](reports/m6b/linux-types-logs.log)
  has the phase-A run). They are for whoever moves the lock to 6.12 (integration note 3).
- **`bubble.py`'s 16 `annotation-unchecked` notes.** Notes, not errors (mypy passes): annotated lines inside the
  untyped `SpeechBubble.__init__` and `AskBox.__init__`. Typing those two surfaces some 45 errors in Qt calls; left
  for a later pass.
- **macOS's App Nap** (leftover 4) can't be reproduced on this computer: CI's macOS legs show whether the reminder
  test, and `test_macnative.py`'s App Nap test, hold (D22).

## Results

Run on Windows 11 with Python 3.14.10, PyQt6 6.11.0 (Qt 6.11.2), pytest 9.2.0, ruff 0.17.4 and mypy 2.4.1
([context.log](reports/m6b/context.log)), and on Linux in WSL Arch (Python 3.14.9, PyQt6 6.12.1 on Qt 6.12.0,
offscreen).

| Check | Command | Result |
|---|---|---|
| Whole suite, Windows | `python -m pytest -q -p no:cacheprovider` | 1241 passed, 148 skipped, every warning an error (ResourceWarning too) ([suite-final.log](reports/m6b/suite-final.log)); the first phase-B run found the one test still using app.py's old log (test_windows.py), since moved to log.py ([suite-phaseb-first.log](reports/m6b/suite-phaseb-first.log)); phase A ended at 1233 passed ([suite-before-m8b.log](reports/m6b/suite-before-m8b.log) has the run before M8's phase B); dd2e375 had 1209 passed, 145 skipped and 21 ResourceWarnings ([suite-ruff.log](reports/m6b/suite-ruff.log)) |
| Whole suite, Linux (WSL) | the same, in a byte-for-byte copy of the worktree | 1269 passed, 120 skipped, every warning an error, on phase B's source ([linux-suite.log](reports/m6b/linux-suite.log)); an observation, not a receipt (its environment isn't the plan's) |
| ruff | `python -m ruff check .` | clean, with no per-file exemption left for the hub files ([ruff.log](reports/m6b/ruff.log), with the count of per-line suppressions by code) |
| mypy | `python -m mypy --platform linux` (and `win32`, `darwin`) | no issues in 69 files on each, with no override at all ([mypy-linux.log](reports/m6b/mypy-linux.log), [mypy-win32.log](reports/m6b/mypy-win32.log), [mypy-darwin.log](reports/m6b/mypy-darwin.log)) |
| String template | `python packaging/extract_strings.py --check` | current, regenerated for phase B's two new sentences ([template.log](reports/m6b/template.log)) |
| Red drills, Windows | `python tests/drills/run.py docs/delivery/reports/m6b/drill-spec.json --log docs/delivery/reports/m6b/drills.log`, and `drill-spec-b.json` into `drills-b.log` | 21 of 21 and 9 of 9 green, red for the intended reason (the logs show each assertion), green again with the file's bytes restored ([drills.log](reports/m6b/drills.log), [drills-b.log](reports/m6b/drills-b.log)) |
| Red drills, Linux | the same harness in WSL on `drill-spec-linux.json` | 5 of 5: the overlay's key events, winpipe importing Windows on Linux, the log's 0600 and `O_NOFOLLOW`, typed text in the overlay's debug log ([drills-linux.log](reports/m6b/drills-linux.log)); an observation |
| Gate drills | `python docs/delivery/reports/m6b/gate_drills.py` | 16 of 16: one violation per new ruff family and S101 in chatmon/, a finding in app.py and in an app test, and a type error in brains.py, winpipe.py, app.py and menus.py, each failing its gate naming the rule, then clean again ([gate-drills.log](reports/m6b/gate-drills.log)) |

**Counts.**

| Item | Phase A | Phase B |
|---|---|---|
| M6B-01 | Findings in phase-A code, tests, packaging/ and art/ on dd2e375 (S101 aside), fixed / suppressed on their line: UP 20 / 0; C4 1 / 0; PIE 3 / 0; PERF 6 / 0; RUF 136 / 3 (82 unused `noqa` comments removed; RUF046 twice for numpy's round, RUF012 once for comtypes); S 4 / 21 (S603 12, S607 4, S311 3, S310 1, S108 1: fixed argv, art and animation randomness, a check_url-guarded urlopen, a mkdtemp'd socket folder); DTZ 0 / 5 (local wall time); BLE 6 / 2 (the six in chatmon now log; two in tests hand the exception on); C90 4 / 1 (four functions split; one art tool). Per-file ignores in tests/: S101 3,187, S 68, DTZ 91. | 35 in the eight files and four of their tests (after M8's merge): fixed 21 (RUF100 6, RUF015 3, BLE001 2 by logging, RUF005 2, PERF401 2, RUF059 2, C901 1 by splitting `_apply_settings`, RUF012 1, UP037 1, and the startup line's DTZ005, gone with app.py's own log), suppressed 14 (DTZ: local wall time) |
| M6B-02 | 41 modules off the exemption list (48 → 7; asking.py already passed). ~375 errors fixed. | The last 7 off it, and the override block gone: 104 (linux), 114 (win32), 104 (darwin) errors fixed |
| M6B-03 | 8 of the 12 phase-A `print()` calls converted (autostart 1, paths 3, layer 4 including its debug printer); releasecheck's 4 stay (terminal output). 91 of 226 except handlers log. | app.py's 7 diagnostics converted (6 warnings, the startup line info); its two "already running" lines and cli.py's 22 stay (terminal output). 17 of the eight files' 39 handlers log. In all, 108 of chatmon's 265 handlers log; 157 are left with their kind ([handlers.md](reports/m6b/handlers.md)). |
| M6B-RW | All 21 ResourceWarnings closed at their source. | `default::ResourceWarning` dropped: every warning fails the test it's raised in. |

**A crash once.** The first full run of the phase-A types-and-logging tree hit a Windows access violation inside Qt
while `test_app_m7.py`'s fixture built a companion (in app.py's `setWindowIcon`, with brain-probing threads
connecting); the rerun of the identical tree passed, as has every run since
([suite-types-logs-crash.log](reports/m6b/suite-types-logs-crash.log), [suite-types-logs.log](reports/m6b/suite-types-logs.log)).
Nothing in M6B's diff touches that path; it's recorded in case it recurs (integration note 2).

**The ledger.** Readiness, closure and resume validation pass ([validate-readiness.log](reports/m6b/validate-readiness.log),
[validate-closure.log](reports/m6b/validate-closure.log), [validate-resume.log](reports/m6b/validate-resume.log)). The
receipts are built by [bind.py](reports/m6b/bind.py) from the logs above; the handler inventory was joined from the
source and the notes made as each module was converted.

## Integration notes

1. **CI (coordinator), not run from here.** The Linux xvfb legs and the distribution containers (Qt 6.4 on Ubuntu
   24.04) on every changed module, and macOS, where M6B's changes were type-checked (`--platform darwin`) but never
   run: in particular `test_macnative.py::test_app_nap_is_held_off_so_timers_keep_their_time` and whether the
   reminder test (leftover 4) stays steady there. `tests/test_imports.py` checks every module imports on each OS.
2. **A one-off crash** (Results): if a Windows access violation in `test_app_m7.py`'s companion fixture shows up
   again, it's worth a look independent of M6B.
3. **When the lock moves to PyQt6 6.12** (Dependabot): mypy will report the 6.12-only errors listed above. The
   `pyqtSignal` one is a stub bug; one `# type: ignore[call-arg]` per signal, or a stub override, is the likely fix.
4. **The dev extra pins ruff 0.17.3** (`pyproject.toml`, `requirements-dev.txt`); this work ran 0.17.4, the shared
   venv's. CI's lint job runs 0.17.3 on the same rules; a difference between the two would show there.
5. **The string template** (`chatmon/locale/chatmon.pot`) gained two sentences ("Your desktop has it as: {keys}",
   and Open the log's new "I keep one in my state folder, and couldn't write it there.") and lost the old one.
6. **APIs.** `chatmon/log.py`: `setup() -> Path | None`, `reset()`, `log_file()`, `debugging()`,
   `blank_keys(text)`, `LIMIT`, `DEBUG_ENV`; app.py calls `setup()` as it starts. `hotkey.register(sequence,
   callback, failed=None, bound=None)`: `bound(description)` hears how the shortcut is pressed. `sound.close()`.
   `macnative.keep_time(reason) -> bool`. Every module logs through `logging.getLogger(__name__)`.

## Changelog notes

- **Chatmon keeps a log.** What goes wrong is written to `chatmon.log` in Chatmon's state folder, readable only by
  you on Linux and macOS, and kept small: past 1 MB it starts over, with the last one kept as `chatmon.log.old`.
  Started from a terminal, problems still show there too. **Open the log** in the menu shows it.
- **`CHATMON_DEBUG=1` keeps the details** in the log: every error Chatmon carried on past, and the overlay's
  keyboard and focus changes.
- **No key, chat or typed text ever goes into the log.** A provider that repeats your key in an error has it
  blanked out; the overlay's debugging no longer records what you type in the ask box.
- **On Wayland, Settings › Accessibility says how your desktop set the hotkey**, in its own words, where it chose
  other keys than the ones you picked.
- **Reminders and bubbles keep their time on macOS** while Chatmon's windows are out of sight (behind a full-screen
  app, hidden, on another Space): App Nap no longer holds them back.
- **Fixes:** Chatmon's Windows-only parts no longer stop it from starting on Linux or macOS when they're imported
  there; *status* no longer waits on looking for a brain; a sound still playing as Chatmon quits finishes, and no
  player is left behind.

## README notes

- **Privacy and security:** "Chatmon keeps a log of what went wrong (`chatmon.log` in its state folder: on Linux
  `~/.local/state/chatmon/`, on Windows `%LOCALAPPDATA%\chatmon\state\`, on macOS
  `~/Library/Application Support/chatmon/state/`), readable only by you. It never holds your keys, your chats or
  what you type." (Check the macOS and Windows folders against `paths.state_dir()` when writing it.)
- **Troubleshooting:** "Something went wrong? **Open the log** in the menu (Help & updates) shows what happened.
  Start Chatmon with `CHATMON_DEBUG=1` to keep the details too."
- **The hotkey** (Settings › Accessibility): "On Wayland your desktop has the last word on the keys, and Settings
  shows the keys it chose."
- **Running the tests / contributing:** ruff checks modern syntax, comprehensions, security, naive datetimes, blind
  excepts and complexity (15); mypy checks every module on Linux, Windows and macOS; and any warning, an unclosed
  file or socket included, fails the test it's raised in.

```quality-ledger
{
  "schema_version": 1,
  "work": {
    "id": "M6B",
    "title": "Static analysis and logging",
    "scope_revision": 2,
    "brief": "docs/delivery/ASSESSMENT.md",
    "brief_reason": null,
    "rules": [
      {
        "path": "docs/delivery/ROADMAP.md",
        "revision": "78853bf"
      },
      {
        "path": "pyproject.toml",
        "revision": "wave3/m6b"
      }
    ],
    "inputs": [
      "docs/delivery/m6a-ci-tooling.md",
      "docs/delivery/m8-translation.md",
      "tests/conftest.py",
      "tests/drills/run.py"
    ],
    "environment": {
      "platform": "windows",
      "tools": {
        "python": "3.14.10",
        "pytest": "9.2.0",
        "PyQt6": "6.11.0",
        "Qt": "6.11.2",
        "ruff": "0.17.4",
        "mypy": "2.4.1"
      }
    }
  },
  "requirements": [
    {
      "id": "M6B-01",
      "statement": "ruff adds UP, C4, PIE, PERF, RUF (ignoring RUF001-003), S (S101 ignored in tests), DTZ, BLE and C90 with max-complexity 15, and every finding is fixed or suppressed on its line with a reason",
      "priority": "normal",
      "acceptance": [
        "M6B-01.A1",
        "M6B-01.A2",
        "M6B-01.A3"
      ],
      "superseded_by": null
    },
    {
      "id": "M6B-02",
      "statement": "mypy's exemptions are removed module by module until every module passes on Linux, Windows and macOS, and every module imports on every OS",
      "priority": "normal",
      "acceptance": [
        "M6B-02.A1",
        "M6B-02.A2",
        "M6B-02.A3"
      ],
      "superseded_by": null
    },
    {
      "id": "M6B-03",
      "statement": "logging writes through a RotatingFileHandler in the state folder, CHATMON_DEBUG sets the level, swallowed errors are logged at debug level, and keys and chat text are never logged",
      "priority": "critical",
      "acceptance": [
        "M6B-03.A1",
        "M6B-03.A2",
        "M6B-03.A3",
        "M6B-03.A4",
        "M6B-03.A5",
        "M6B-03.A6"
      ],
      "superseded_by": null
    },
    {
      "id": "M6B-RW",
      "statement": "The unclosed sockets, files and processes M6A listed are closed where they are made, so the ResourceWarning exemption can be dropped",
      "priority": "low",
      "acceptance": [
        "M6B-RW.A1"
      ],
      "superseded_by": null
    },
    {
      "id": "M6B-LEFT",
      "priority": "normal",
      "superseded_by": null,
      "statement": "The leftovers in the hub files: status asks the brain finder, Settings shows the hotkey's Wayland wording, quitting lets go of the sound players, and the macOS reminder test doesn't race a timer",
      "acceptance": [
        "M6B-LEFT.A1",
        "M6B-LEFT.A2",
        "M6B-LEFT.A3",
        "M6B-LEFT.A4"
      ]
    }
  ],
  "acceptance": [
    {
      "id": "M6B-01.A1",
      "requirement": "M6B-01",
      "given": "pyproject.toml's ruff settings and the whole repository",
      "when": "ruff check . runs",
      "then": "It selects the eleven families with max-complexity 15 and passes; a representative violation of each new family (UP, C4, PIE, PERF, RUF, S, DTZ, BLE, C90) in a phase-A module makes it fail naming that rule; RUF001-003 are ignored and S101 only in tests",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6B-01.A2",
      "requirement": "M6B-01",
      "given": "The fixes and the four functions split into helpers",
      "when": "The whole suite runs and the string template is extracted",
      "then": "Every test passes with its expected English untouched, the template is unchanged, and breaking a split-out helper (the stage's bubble placement, the menu's moving keys, the overlay's key events, the extractor's marked-call check) fails the tests that cover it",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6B-01.A3",
      "requirement": "M6B-01",
      "given": "The eight files M8 is translating",
      "when": "Phase B runs after M8 merges",
      "then": "Their per-file exemptions are gone and ruff passes with every finding in them fixed or suppressed with a reason",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6B-02.A1",
      "requirement": "M6B-02",
      "given": "pyproject.toml's mypy settings, with PyQt6 6.11's stubs (what ships) and 6.12's (Arch's)",
      "when": "mypy --platform linux, win32 and darwin run",
      "then": "Each passes, the exemption list holds only the eight M8 files, and a type error put in a newly gated module makes mypy fail naming it",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6B-02.A2",
      "requirement": "M6B-02",
      "given": "Every chatmon module but __main__",
      "when": "A fresh interpreter imports them all on the OS the suite runs on",
      "then": "Each imports, and a module that reaches another OS's library on import fails the test naming it",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6B-02.A3",
      "requirement": "M6B-02",
      "given": "The eight files M8 is translating",
      "when": "Phase B runs after M8 merges",
      "then": "They come off the exemption list, and mypy passes on all three platforms with no override left",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6B-03.A1",
      "requirement": "M6B-03",
      "given": "A state folder, with and without CHATMON_DEBUG, with and without a console",
      "when": "log.setup() runs and Chatmon's loggers say something at each level",
      "then": "chatmon.log in the state folder holds info and worse (debug too with CHATMON_DEBUG), never another library's lines; warnings reach stderr as 'chatmon: ...' when there is one; setting up twice writes each line once; an unwritable state folder leaves Chatmon running with no log",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6B-03.A2",
      "requirement": "M6B-03",
      "given": "A log written past 1 MB, an older log made at the umask, and a symbolic link in the log's place",
      "when": "Lines are logged",
      "then": "The full log is kept as chatmon.log.old (never .log.1) and a new one started; on POSIX the log is 0600 and the link is never followed",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6B-03.A3",
      "requirement": "M6B-03",
      "given": "A provider that repeats the brain's key in its refusal, and key-shaped text in a message or traceback",
      "when": "The question fails and the failure is logged",
      "then": "The log says which brain failed and the provider's words, with the key blanked, both by the brain's own scrubbing (a key of no known shape) and by the log's blanking (a known shape); the overlay's focus debugging never logs typed text",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6B-03.A4",
      "requirement": "M6B-03",
      "given": "Phase-A modules that printed diagnostics to stderr, and the overlay's own debug printer",
      "when": "Those problems happen",
      "then": "They are logged (warnings, with the same words; the overlay's at debug), and terminal output meant for the person stays print",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6B-03.A5",
      "requirement": "M6B-03",
      "given": "A failure an except block in a phase-A module used to hide",
      "when": "It happens",
      "then": "Chatmon carries on exactly as before and a debug line names what failed; every handler in the phase-A modules is logged or listed in handlers.md with why it is left",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6B-03.A6",
      "requirement": "M6B-03",
      "given": "The eight files M8 is translating, and app.py's hand-made log",
      "when": "Phase B runs after M8 merges",
      "then": "app.py calls log.setup() instead of redirecting stderr to its own file, uncaught exceptions are logged at error level, and the eight files' print diagnostics and hidden errors follow the conventions",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6B-RW.A1",
      "requirement": "M6B-RW",
      "given": "The unclosed sockets, files and processes M6A listed in phase-A code and tests",
      "when": "The suite runs with ResourceWarning as an error",
      "then": "None of them is reported; any left (in M8's files) is listed with where it is made",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6B-LEFT.A1",
      "requirement": "M6B-LEFT",
      "given": "A companion whose brain may need looking for",
      "when": "The status command runs",
      "then": "It names the brain a question would go to, from brains.Finder, and nothing calls brains.choose with wait=True",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6B-LEFT.A2",
      "requirement": "M6B-LEFT",
      "given": "A desktop that has the hotkey as other keys, said in its own words (Wayland's portal)",
      "when": "It says so, before or while Settings is open",
      "then": "hotkey.register's bound callback hears it, and Settings › Accessibility shows 'Your desktop has it as: …'; nothing extra when it's just the keys picked",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6B-LEFT.A3",
      "requirement": "M6B-LEFT",
      "given": "A Linux player still sounding",
      "when": "Chatmon quits",
      "then": "quit() calls sound.close(), which waits for the sound and reaps the player, leaving none running, and finds the players again for a later sound",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6B-LEFT.A4",
      "requirement": "M6B-LEFT",
      "given": "A script's reminder whose time can't be told, sent while another bubble is up",
      "when": "The reminder test runs",
      "then": "With the bubble on screen closed first, 'Reminder not set' shows at once, no timer raced; on macOS Chatmon asks not to be App Napped (test_macnative.py, run by CI's macOS legs)",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    }
  ],
  "tasks": [
    {
      "id": "T1-ruff",
      "purpose": "Add the rule families, fix or suppress every finding in phase-A files, split the four too-complex functions",
      "acceptance": [
        "M6B-01.A1",
        "M6B-01.A2"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "art/tools/blink-inbetween.py",
          "action": "modify"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "action": "modify"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "action": "modify"
        },
        {
          "path": "art/tools/creature-cut.py",
          "action": "modify"
        },
        {
          "path": "art/tools/creature-preview.py",
          "action": "modify"
        },
        {
          "path": "art/tools/creature-qc.py",
          "action": "modify"
        },
        {
          "path": "art/tools/loop-qc.py",
          "action": "modify"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "action": "modify"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "action": "modify"
        },
        {
          "path": "art/tools/readme_media.py",
          "action": "modify"
        },
        {
          "path": "art/tools/sound-cues.py",
          "action": "modify"
        },
        {
          "path": "art/tools/spritefix.py",
          "action": "modify"
        },
        {
          "path": "chatmon/a11y.py",
          "action": "modify"
        },
        {
          "path": "chatmon/agents.py",
          "action": "modify"
        },
        {
          "path": "chatmon/behavior.py",
          "action": "modify"
        },
        {
          "path": "chatmon/brains.py",
          "action": "modify"
        },
        {
          "path": "chatmon/bubble.py",
          "action": "modify"
        },
        {
          "path": "chatmon/chats.py",
          "action": "modify"
        },
        {
          "path": "chatmon/heads_up.py",
          "action": "modify"
        },
        {
          "path": "chatmon/hotkey.py",
          "action": "modify"
        },
        {
          "path": "chatmon/layer.py",
          "action": "modify"
        },
        {
          "path": "chatmon/linuxsession.py",
          "action": "modify"
        },
        {
          "path": "chatmon/macnative.py",
          "action": "modify"
        },
        {
          "path": "chatmon/paths.py",
          "action": "modify"
        },
        {
          "path": "chatmon/penguin.py",
          "action": "modify"
        },
        {
          "path": "chatmon/portal.py",
          "action": "modify"
        },
        {
          "path": "chatmon/portowner.py",
          "action": "modify"
        },
        {
          "path": "chatmon/reminders.py",
          "action": "modify"
        },
        {
          "path": "chatmon/richtext.py",
          "action": "modify"
        },
        {
          "path": "chatmon/sound.py",
          "action": "modify"
        },
        {
          "path": "chatmon/stagemenu.py",
          "action": "modify"
        },
        {
          "path": "chatmon/sysnotify.py",
          "action": "modify"
        },
        {
          "path": "chatmon/updates.py",
          "action": "modify"
        },
        {
          "path": "chatmon/wayland.py",
          "action": "modify"
        },
        {
          "path": "chatmon/windrop.py",
          "action": "modify"
        },
        {
          "path": "chatmon/winfiles.py",
          "action": "modify"
        },
        {
          "path": "chatmon/winlock.py",
          "action": "modify"
        },
        {
          "path": "chatmon/winrt.py",
          "action": "modify"
        },
        {
          "path": "packaging/build.py",
          "action": "modify"
        },
        {
          "path": "packaging/extract_strings.py",
          "action": "modify"
        },
        {
          "path": "packaging/macos/entry.py",
          "action": "modify"
        },
        {
          "path": "pyproject.toml",
          "action": "modify"
        },
        {
          "path": "tests/drills/run.py",
          "action": "modify"
        },
        {
          "path": "tests/ed25519_sign.py",
          "action": "modify"
        },
        {
          "path": "tests/fake_secrets.py",
          "action": "modify"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "action": "modify"
        },
        {
          "path": "tests/test_backup.py",
          "action": "modify"
        },
        {
          "path": "tests/test_behavior.py",
          "action": "modify"
        },
        {
          "path": "tests/test_brains.py",
          "action": "modify"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "action": "modify"
        },
        {
          "path": "tests/test_chats.py",
          "action": "modify"
        },
        {
          "path": "tests/test_companions.py",
          "action": "modify"
        },
        {
          "path": "tests/test_context.py",
          "action": "modify"
        },
        {
          "path": "tests/test_contrast.py",
          "action": "modify"
        },
        {
          "path": "tests/test_events.py",
          "action": "modify"
        },
        {
          "path": "tests/test_heads_up.py",
          "action": "modify"
        },
        {
          "path": "tests/test_install_update.py",
          "action": "modify"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "action": "modify"
        },
        {
          "path": "tests/test_parser_properties.py",
          "action": "modify"
        },
        {
          "path": "tests/test_platform_events.py",
          "action": "modify"
        },
        {
          "path": "tests/test_presence.py",
          "action": "modify"
        },
        {
          "path": "tests/test_releasecheck.py",
          "action": "modify"
        },
        {
          "path": "tests/test_reminders.py",
          "action": "modify"
        },
        {
          "path": "tests/test_rich_text.py",
          "action": "modify"
        },
        {
          "path": "tests/test_sprites.py",
          "action": "modify"
        },
        {
          "path": "tests/test_stage_features.py",
          "action": "modify"
        },
        {
          "path": "tests/test_stage_timer.py",
          "action": "modify"
        },
        {
          "path": "tests/test_stagemenu.py",
          "action": "modify"
        },
        {
          "path": "tests/test_updates.py",
          "action": "modify"
        },
        {
          "path": "tests/test_wayland.py",
          "action": "modify"
        },
        {
          "path": "tests/test_xkb.py",
          "action": "modify"
        },
        {
          "path": "tests/uia_client.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-red-M6B-01-bubble-not-clear-of-the-box",
        "E-red-M6B-01-extractor-misses-import-time",
        "E-red-M6B-01-menu-end-key-goes-home",
        "E-red-gate-ruff-BLE",
        "E-red-gate-ruff-C4",
        "E-red-gate-ruff-C90",
        "E-red-gate-ruff-DTZ",
        "E-red-gate-ruff-PERF",
        "E-red-gate-ruff-PIE",
        "E-red-gate-ruff-RUF",
        "E-red-gate-ruff-S",
        "E-red-gate-ruff-S101-in-chatmon",
        "E-red-gate-ruff-UP",
        "E-ruff",
        "E-suite",
        "E-template"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T2-log",
      "purpose": "chatmon/log.py and its tests; the Asker logs failures with the key scrubbed",
      "acceptance": [
        "M6B-03.A1",
        "M6B-03.A2",
        "M6B-03.A3"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/log.py",
          "action": "create"
        },
        {
          "path": "tests/test_log.py",
          "action": "create"
        },
        {
          "path": "chatmon/brains.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-red-M6B-03-brain-failure-not-logged",
        "E-red-M6B-03-brain-key-not-scrubbed",
        "E-red-M6B-03-console-not-blanked",
        "E-red-M6B-03-debug-env-ignored",
        "E-red-M6B-03-keys-not-blanked",
        "E-red-M6B-03-limit-ten-times",
        "E-red-M6B-03-no-stderr",
        "E-red-M6B-03-rotated-as-dot-1",
        "E-red-M6B-03-setup-twice-doubles",
        "E-suite"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T3-loggers",
      "purpose": "Loggers in the phase-A modules: print diagnostics, the overlay's debug printer (no typed text), hidden errors at debug; handlers.md",
      "acceptance": [
        "M6B-03.A3",
        "M6B-03.A4",
        "M6B-03.A5"
      ],
      "depends_on": [
        "T2-log"
      ],
      "changes": [
        {
          "path": "chatmon/a11y.py",
          "action": "modify"
        },
        {
          "path": "chatmon/agents.py",
          "action": "modify"
        },
        {
          "path": "chatmon/attachments.py",
          "action": "modify"
        },
        {
          "path": "chatmon/autostart.py",
          "action": "modify"
        },
        {
          "path": "chatmon/brains.py",
          "action": "modify"
        },
        {
          "path": "chatmon/bubbleart.py",
          "action": "modify"
        },
        {
          "path": "chatmon/changelog.py",
          "action": "modify"
        },
        {
          "path": "chatmon/chats.py",
          "action": "modify"
        },
        {
          "path": "chatmon/clickthrough.py",
          "action": "modify"
        },
        {
          "path": "chatmon/i18n.py",
          "action": "modify"
        },
        {
          "path": "chatmon/keychain.py",
          "action": "modify"
        },
        {
          "path": "chatmon/layer.py",
          "action": "modify"
        },
        {
          "path": "chatmon/macnative.py",
          "action": "modify"
        },
        {
          "path": "chatmon/offline.py",
          "action": "modify"
        },
        {
          "path": "chatmon/paths.py",
          "action": "modify"
        },
        {
          "path": "chatmon/portowner.py",
          "action": "modify"
        },
        {
          "path": "chatmon/presence.py",
          "action": "modify"
        },
        {
          "path": "chatmon/reminders.py",
          "action": "modify"
        },
        {
          "path": "chatmon/sound.py",
          "action": "modify"
        },
        {
          "path": "chatmon/sysnotify.py",
          "action": "modify"
        },
        {
          "path": "chatmon/updates.py",
          "action": "modify"
        },
        {
          "path": "chatmon/wayland.py",
          "action": "modify"
        },
        {
          "path": "chatmon/wincaret.py",
          "action": "modify"
        },
        {
          "path": "chatmon/windrop.py",
          "action": "modify"
        },
        {
          "path": "chatmon/winfocus.py",
          "action": "modify"
        },
        {
          "path": "chatmon/winrt.py",
          "action": "modify"
        },
        {
          "path": "chatmon/wintoast.py",
          "action": "modify"
        },
        {
          "path": "chatmon/winuia.py",
          "action": "modify"
        },
        {
          "path": "tests/test_agents.py",
          "action": "modify"
        },
        {
          "path": "tests/test_autostart.py",
          "action": "modify"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "action": "modify"
        },
        {
          "path": "tests/test_chats.py",
          "action": "modify"
        },
        {
          "path": "tests/test_clickthrough.py",
          "action": "modify"
        },
        {
          "path": "tests/test_offline.py",
          "action": "modify"
        },
        {
          "path": "tests/test_presence.py",
          "action": "modify"
        },
        {
          "path": "tests/test_reminders.py",
          "action": "modify"
        },
        {
          "path": "tests/test_sound.py",
          "action": "modify"
        },
        {
          "path": "tests/test_updates.py",
          "action": "modify"
        },
        {
          "path": "tests/test_wayland.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-red-M6B-03-autostart-warning-printed",
        "E-red-M6B-03-brain-failure-not-logged",
        "E-red-M6B-03-brain-key-not-scrubbed",
        "E-red-M6B-03-chat-failure-hidden",
        "E-red-M6B-03-console-not-blanked",
        "E-red-M6B-03-keys-not-blanked",
        "E-red-M6B-03-package-manager-failure-hidden",
        "E-red-M6B-03-phrases-failure-hidden",
        "E-red-M6B-03-player-failure-hidden",
        "E-red-M6B-03-reminder-words-logged",
        "E-suite"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T4-mypy",
      "purpose": "Type errors fixed module by module, the exemption list down to seven of M8's files, every module importing on every OS, and a test of that",
      "acceptance": [
        "M6B-02.A1",
        "M6B-02.A2"
      ],
      "depends_on": [
        "T1-ruff"
      ],
      "changes": [
        {
          "path": "chatmon/a11y.py",
          "action": "modify"
        },
        {
          "path": "chatmon/agents.py",
          "action": "modify"
        },
        {
          "path": "chatmon/attachments.py",
          "action": "modify"
        },
        {
          "path": "chatmon/autostart.py",
          "action": "modify"
        },
        {
          "path": "chatmon/backup.py",
          "action": "modify"
        },
        {
          "path": "chatmon/brains.py",
          "action": "modify"
        },
        {
          "path": "chatmon/bubble.py",
          "action": "modify"
        },
        {
          "path": "chatmon/bubbleart.py",
          "action": "modify"
        },
        {
          "path": "chatmon/changelog.py",
          "action": "modify"
        },
        {
          "path": "chatmon/chats.py",
          "action": "modify"
        },
        {
          "path": "chatmon/clickthrough.py",
          "action": "modify"
        },
        {
          "path": "chatmon/context.py",
          "action": "modify"
        },
        {
          "path": "chatmon/ed25519.py",
          "action": "modify"
        },
        {
          "path": "chatmon/events.py",
          "action": "modify"
        },
        {
          "path": "chatmon/heads_up.py",
          "action": "modify"
        },
        {
          "path": "chatmon/hotkey.py",
          "action": "modify"
        },
        {
          "path": "chatmon/i18n.py",
          "action": "modify"
        },
        {
          "path": "chatmon/keychain.py",
          "action": "modify"
        },
        {
          "path": "chatmon/layer.py",
          "action": "modify"
        },
        {
          "path": "chatmon/libdbus.py",
          "action": "modify"
        },
        {
          "path": "chatmon/linuxsession.py",
          "action": "modify"
        },
        {
          "path": "chatmon/macnative.py",
          "action": "modify"
        },
        {
          "path": "chatmon/offline.py",
          "action": "modify"
        },
        {
          "path": "chatmon/packagekit.py",
          "action": "modify"
        },
        {
          "path": "chatmon/paths.py",
          "action": "modify"
        },
        {
          "path": "chatmon/penguin.py",
          "action": "modify"
        },
        {
          "path": "chatmon/portal.py",
          "action": "modify"
        },
        {
          "path": "chatmon/portowner.py",
          "action": "modify"
        },
        {
          "path": "chatmon/presence.py",
          "action": "modify"
        },
        {
          "path": "chatmon/reminders.py",
          "action": "modify"
        },
        {
          "path": "chatmon/report.py",
          "action": "modify"
        },
        {
          "path": "chatmon/richtext.py",
          "action": "modify"
        },
        {
          "path": "chatmon/sound.py",
          "action": "modify"
        },
        {
          "path": "chatmon/sprites.py",
          "action": "modify"
        },
        {
          "path": "chatmon/stagemenu.py",
          "action": "modify"
        },
        {
          "path": "chatmon/sysnotify.py",
          "action": "modify"
        },
        {
          "path": "chatmon/updates.py",
          "action": "modify"
        },
        {
          "path": "chatmon/wayland.py",
          "action": "modify"
        },
        {
          "path": "chatmon/wincaret.py",
          "action": "modify"
        },
        {
          "path": "chatmon/windrop.py",
          "action": "modify"
        },
        {
          "path": "chatmon/winfocus.py",
          "action": "modify"
        },
        {
          "path": "chatmon/winlock.py",
          "action": "modify"
        },
        {
          "path": "chatmon/winpipe.py",
          "action": "modify"
        },
        {
          "path": "chatmon/winrt.py",
          "action": "modify"
        },
        {
          "path": "chatmon/wintoast.py",
          "action": "modify"
        },
        {
          "path": "chatmon/wintrust.py",
          "action": "modify"
        },
        {
          "path": "chatmon/winuia.py",
          "action": "modify"
        },
        {
          "path": "chatmon/xkb.py",
          "action": "modify"
        },
        {
          "path": "pyproject.toml",
          "action": "modify"
        },
        {
          "path": "tests/test_imports.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-mypy-darwin",
        "E-mypy-linux",
        "E-mypy-win32",
        "E-red-M6B-02-a-module-loads-macos-on-import",
        "E-red-gate-mypy-brains",
        "E-red-gate-mypy-winpipe",
        "E-suite"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T5-leaks",
      "purpose": "Close the unclosed sockets, files and processes M6A listed",
      "acceptance": [
        "M6B-RW.A1"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/brains.py",
          "action": "modify"
        },
        {
          "path": "chatmon/paths.py",
          "action": "modify"
        },
        {
          "path": "tests/test_brains.py",
          "action": "modify"
        },
        {
          "path": "tests/test_events.py",
          "action": "modify"
        },
        {
          "path": "tests/test_updates.py",
          "action": "modify"
        },
        {
          "path": "tests/test_wayland.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-red-M6B-B-leak-fails-without-a-flag",
        "E-red-M6B-RW-http-error-left-open",
        "E-red-M6B-RW-release-server-left-open",
        "E-suite"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T6-phase-b",
      "purpose": "Phase B: the eight hub files' ruff findings and exemptions, their mypy exemptions, app.py's switch to log.setup(), their prints and hidden errors, and default::ResourceWarning dropped",
      "acceptance": [
        "M6B-01.A3",
        "M6B-02.A3",
        "M6B-03.A6"
      ],
      "depends_on": [
        "T1-ruff",
        "T2-log",
        "T3-loggers",
        "T4-mypy"
      ],
      "changes": [
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "chatmon/asking.py",
          "action": "modify"
        },
        {
          "path": "chatmon/cli.py",
          "action": "modify"
        },
        {
          "path": "chatmon/commands.py",
          "action": "modify"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "action": "modify"
        },
        {
          "path": "chatmon/menus.py",
          "action": "modify"
        },
        {
          "path": "chatmon/messages.py",
          "action": "modify"
        },
        {
          "path": "chatmon/settings.py",
          "action": "modify"
        },
        {
          "path": "chatmon/settingswin.py",
          "action": "modify"
        },
        {
          "path": "pyproject.toml",
          "action": "modify"
        },
        {
          "path": "tests/app_harness.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_reminders.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_smoke.py",
          "action": "modify"
        },
        {
          "path": "tests/test_i18n.py",
          "action": "modify"
        },
        {
          "path": "tests/test_settings.py",
          "action": "modify"
        },
        {
          "path": "tests/test_windows.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-mypy-darwin",
        "E-mypy-linux",
        "E-mypy-win32",
        "E-red-M6B-B-escaped-exception-not-in-the-log",
        "E-red-M6B-B-unreadable-settings-hidden",
        "E-red-gate-mypy-app",
        "E-red-gate-mypy-menus",
        "E-red-gate-ruff-app",
        "E-red-gate-ruff-app-test",
        "E-ruff",
        "E-suite"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T7-leftovers",
      "purpose": "The leftovers in the hub files: status through the brain finder, the hotkey's wording in Settings, sound.close() at quit, App Nap held off and the reminder test made steady",
      "acceptance": [
        "M6B-LEFT.A1",
        "M6B-LEFT.A2",
        "M6B-LEFT.A3",
        "M6B-LEFT.A4"
      ],
      "depends_on": [
        "T6-phase-b"
      ],
      "changes": [
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "chatmon/hotkey.py",
          "action": "modify"
        },
        {
          "path": "chatmon/macnative.py",
          "action": "modify"
        },
        {
          "path": "chatmon/settingswin.py",
          "action": "modify"
        },
        {
          "path": "chatmon/sound.py",
          "action": "modify"
        },
        {
          "path": "tests/app_harness.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_m7.py",
          "action": "modify"
        },
        {
          "path": "tests/test_app_reminders.py",
          "action": "modify"
        },
        {
          "path": "tests/test_hotkey.py",
          "action": "modify"
        },
        {
          "path": "tests/test_macnative.py",
          "action": "modify"
        },
        {
          "path": "tests/test_sound.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-red-M6B-B-desktops-words-not-shown",
        "E-red-M6B-B-hotkey-bound-kept-private",
        "E-red-M6B-B-player-not-closed",
        "E-red-M6B-B-players-left-at-quit",
        "E-red-M6B-B-status-waits-for-the-brain",
        "E-red-M6B-B-unclear-script-reminder-unsaid",
        "E-suite"
      ],
      "blocker": null,
      "superseded_by": null
    }
  ],
  "evidence": [
    {
      "id": "E-readiness",
      "acceptance": [
        "M6B-01.A1",
        "M6B-01.A2",
        "M6B-01.A3",
        "M6B-02.A1",
        "M6B-02.A2",
        "M6B-02.A3",
        "M6B-03.A1",
        "M6B-03.A2",
        "M6B-03.A3",
        "M6B-03.A4",
        "M6B-03.A5",
        "M6B-03.A6",
        "M6B-RW.A1",
        "M6B-LEFT.A1",
        "M6B-LEFT.A2",
        "M6B-LEFT.A3",
        "M6B-LEFT.A4"
      ],
      "kind": "readiness",
      "status": "pass",
      "command": [],
      "method": "Requirements review of M6B-01..03 and M6A's note 4 against the assessment, the roadmap's rules, the wave-3 brief and the coordinator's two added rules: the findings re-checked on dd2e375, decisions D1-D17, failure behaviour, terms and coverage; then phase B's and the leftovers' (M6B-LEFT), re-checked on 210c6e0, decisions D18-D23 (readiness.md).",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m6b/readiness.md",
        "sha256": "aa570d55e17777364ad0952c3ec20aa72124039f045cb38d990e0847d4fb408f"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        }
      ],
      "scope_sha256": "1555e7799fa08ace926224db522f1cd82524930e398dc1945ed8a7e428ba3f3d",
      "red": null,
      "reason": null
    },
    {
      "id": "E-suite",
      "acceptance": [
        "M6B-01.A2",
        "M6B-02.A2",
        "M6B-03.A1",
        "M6B-03.A2",
        "M6B-03.A3",
        "M6B-03.A4",
        "M6B-03.A5",
        "M6B-03.A6",
        "M6B-LEFT.A1",
        "M6B-LEFT.A2",
        "M6B-LEFT.A3",
        "M6B-LEFT.A4",
        "M6B-RW.A1"
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
      "method": "The whole suite on the final source (exported from the index into a scratch folder, real Qt objects offscreen), every warning an error, ResourceWarning too: 1241 passed, 148 skipped; it runs test_log.py, test_imports.py and every test the drills name.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/suite-final.log",
        "sha256": "c51274a0e7e3019fffa021aa26cfa7e4e0c19b5dd18589e7e3b20c41c26f5def"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "7e16f6b335ab56d8cb0746655cc997d6746b3d1bd24330b69e6e50dd3bbb23dd"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "786f8e2aa8d1e853ee92be33dfda0e6008439151e7beaa7052dcaf98ccbdde2d"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "1974f004b3074ea41ab30b1f0fa0b9f8ad212d9ca127d22bd7839bf3f538edae"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "552dea1c3cde46bcba3f360a5cef3e1844ea7af57fdab54bec1a397312f409f0"
        },
        {
          "path": "chatmon/context.py",
          "sha256": "53bf39016325ee5a8458dcb1d540b05a8a29cfd85934d6aa06cefa01f7200dcb"
        },
        {
          "path": "chatmon/ed25519.py",
          "sha256": "cee9d926326e398c783dc261214f15fe8b5dfc99719559a7739e094c266b9cc4"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "671b6a38b502e8d0a1d5882579d5906ebfb3fc005341fb26bb8967f84fe8bd26"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "be76509122882a3805c8340eb74547e0106c5d00d337dc50376597e5a8239cd8"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "1e7e5be17c68fa9e879b99b0e24113559d1856781b810f3fc540b22d7cd32885"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "30dc957489a349a915484f480a5b4621eaf3fe945e62ca76ebcafa3763384a34"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "41d0eea4d55dbf783696e07d499d93ffff1eee968501cb7e9f0393f23a00e97c"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "be49db85d004a8ee166ce412394c122c47bf2880e52c8f0a8dcf57e0cf4c7abe"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/report.py",
          "sha256": "8887d1f776e10f109c8edd7bca7ee0252e2569cf299c10ea959c11a550ac71a8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "132ec69ef2b5ec2a5d88a84e5510acd6ae9fd2670215ba08b2afe7b9e93911d2"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "ca1c253330fd2d606bb9f5429f107300a41e4b16b1d72c80d00ef760660f65a3"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "c8b5c367084d25187c68eba4fbdb05774ce6c2c977c29811001523c40e789dc4"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "844992d0ec60b49646d47d3c80a3ddb015046585a513d3d1baa7a96591fdd055"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "04abb06254ad357f0f943989fb89d3f903d72189cb4c60bb47d1d87caf73a3f9"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "chatmon/xkb.py",
          "sha256": "10a00e4c71d2b1771b2850ae5f6570b95af04433b2a6dbe4be38a7c6c86aea4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "cfe165292e0e040194480a37f954995803def534d8c07e54fdba3254386ccff6"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "57243e1b45e87b98c53e6a5999fc6457ab83cdfe4e97f43814b2a11fce5f38d7"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "ff636d3239ffef20685de7e86c6ce1a18e2753d6d7f77027349a9ff0b9c08edd"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "c313741b7009b7a1a7c7b13e4f160662aaead0c4f225d48e91b529bdf60d15a3"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "03666f40b0987e337270d8d69b303648d37ae5cf8bc3f5ccde9e3dddd91d2167"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "193614b91c1729ef801478fd6747a867920c60930a918ef2f80359736b3a9347"
        },
        {
          "path": "tests/test_imports.py",
          "sha256": "bb03d577b13589450c80feafc976ef5da20d3e86f64c69ffb4b42f2922db5033"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_macnative.py",
          "sha256": "2da102be56c933c363d0e78794907716fbabdf94f5985fd2fc2762b1f5d1f651"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "c73db48214065cfde5d4c08fa0c42054b8b7688abcaa81730c32a6f55a59746d"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_windows.py",
          "sha256": "0a605c59891ec08734d8bf5b8767d775acf4b469999e51ede48630d39f633c33"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "1555e7799fa08ace926224db522f1cd82524930e398dc1945ed8a7e428ba3f3d",
      "red": null,
      "reason": null
    },
    {
      "id": "E-template",
      "acceptance": [
        "M6B-01.A2"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "packaging/extract_strings.py",
        "--check"
      ],
      "method": "The string extractor's check on the final source: the template is what the code says (phase B's two new sentences in it).",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/template.log",
        "sha256": "19c5bf7869f37452574f14ff206d4e9bb30d7c46818a848f21caf4f9f88e1f37"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "b9566fff6d92a9ae0f274cc1a6842f22e274dbc5fae1fcb1b23e70c7b21b278d",
      "red": null,
      "reason": null
    },
    {
      "id": "E-ruff",
      "acceptance": [
        "M6B-01.A1",
        "M6B-01.A3"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "ruff",
        "check",
        "."
      ],
      "method": "ruff with pyproject.toml's eleven families and max-complexity 15 over the whole repository, the hub files without any exemption: clean; the log also counts the per-line suppressions by code.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/ruff.log",
        "sha256": "6a9f2f0c06e9d2fed1b4399c2431cc10a29d2cf4337ab1be1289a9db2cb8eb9a"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "7e16f6b335ab56d8cb0746655cc997d6746b3d1bd24330b69e6e50dd3bbb23dd"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "786f8e2aa8d1e853ee92be33dfda0e6008439151e7beaa7052dcaf98ccbdde2d"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "1974f004b3074ea41ab30b1f0fa0b9f8ad212d9ca127d22bd7839bf3f538edae"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "552dea1c3cde46bcba3f360a5cef3e1844ea7af57fdab54bec1a397312f409f0"
        },
        {
          "path": "chatmon/context.py",
          "sha256": "53bf39016325ee5a8458dcb1d540b05a8a29cfd85934d6aa06cefa01f7200dcb"
        },
        {
          "path": "chatmon/ed25519.py",
          "sha256": "cee9d926326e398c783dc261214f15fe8b5dfc99719559a7739e094c266b9cc4"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "671b6a38b502e8d0a1d5882579d5906ebfb3fc005341fb26bb8967f84fe8bd26"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "be76509122882a3805c8340eb74547e0106c5d00d337dc50376597e5a8239cd8"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "1e7e5be17c68fa9e879b99b0e24113559d1856781b810f3fc540b22d7cd32885"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "30dc957489a349a915484f480a5b4621eaf3fe945e62ca76ebcafa3763384a34"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "41d0eea4d55dbf783696e07d499d93ffff1eee968501cb7e9f0393f23a00e97c"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "be49db85d004a8ee166ce412394c122c47bf2880e52c8f0a8dcf57e0cf4c7abe"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/report.py",
          "sha256": "8887d1f776e10f109c8edd7bca7ee0252e2569cf299c10ea959c11a550ac71a8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "132ec69ef2b5ec2a5d88a84e5510acd6ae9fd2670215ba08b2afe7b9e93911d2"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "ca1c253330fd2d606bb9f5429f107300a41e4b16b1d72c80d00ef760660f65a3"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "c8b5c367084d25187c68eba4fbdb05774ce6c2c977c29811001523c40e789dc4"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "844992d0ec60b49646d47d3c80a3ddb015046585a513d3d1baa7a96591fdd055"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "04abb06254ad357f0f943989fb89d3f903d72189cb4c60bb47d1d87caf73a3f9"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "chatmon/xkb.py",
          "sha256": "10a00e4c71d2b1771b2850ae5f6570b95af04433b2a6dbe4be38a7c6c86aea4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "cfe165292e0e040194480a37f954995803def534d8c07e54fdba3254386ccff6"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "ff636d3239ffef20685de7e86c6ce1a18e2753d6d7f77027349a9ff0b9c08edd"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "c313741b7009b7a1a7c7b13e4f160662aaead0c4f225d48e91b529bdf60d15a3"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "193614b91c1729ef801478fd6747a867920c60930a918ef2f80359736b3a9347"
        },
        {
          "path": "tests/test_imports.py",
          "sha256": "bb03d577b13589450c80feafc976ef5da20d3e86f64c69ffb4b42f2922db5033"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "c73db48214065cfde5d4c08fa0c42054b8b7688abcaa81730c32a6f55a59746d"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_windows.py",
          "sha256": "0a605c59891ec08734d8bf5b8767d775acf4b469999e51ede48630d39f633c33"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "791e260975da81a54071cdbddcedfeb76da3c20fee1bc5ae9853adeaebc34b7b",
      "red": null,
      "reason": null
    },
    {
      "id": "E-mypy-linux",
      "acceptance": [
        "M6B-02.A1",
        "M6B-02.A3"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "mypy",
        "--platform",
        "linux"
      ],
      "method": "mypy for linux on the final source with pyproject.toml's settings and no exemption at all: no issues in 69 files.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/mypy-linux.log",
        "sha256": "9f84be0fdf78a60d1204a8e2ef941fdfba8a5733ae93f039c43c9d6c3f4ae269"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "7e16f6b335ab56d8cb0746655cc997d6746b3d1bd24330b69e6e50dd3bbb23dd"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "786f8e2aa8d1e853ee92be33dfda0e6008439151e7beaa7052dcaf98ccbdde2d"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "1974f004b3074ea41ab30b1f0fa0b9f8ad212d9ca127d22bd7839bf3f538edae"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "552dea1c3cde46bcba3f360a5cef3e1844ea7af57fdab54bec1a397312f409f0"
        },
        {
          "path": "chatmon/context.py",
          "sha256": "53bf39016325ee5a8458dcb1d540b05a8a29cfd85934d6aa06cefa01f7200dcb"
        },
        {
          "path": "chatmon/ed25519.py",
          "sha256": "cee9d926326e398c783dc261214f15fe8b5dfc99719559a7739e094c266b9cc4"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "671b6a38b502e8d0a1d5882579d5906ebfb3fc005341fb26bb8967f84fe8bd26"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "be76509122882a3805c8340eb74547e0106c5d00d337dc50376597e5a8239cd8"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "1e7e5be17c68fa9e879b99b0e24113559d1856781b810f3fc540b22d7cd32885"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "30dc957489a349a915484f480a5b4621eaf3fe945e62ca76ebcafa3763384a34"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "41d0eea4d55dbf783696e07d499d93ffff1eee968501cb7e9f0393f23a00e97c"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "be49db85d004a8ee166ce412394c122c47bf2880e52c8f0a8dcf57e0cf4c7abe"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/report.py",
          "sha256": "8887d1f776e10f109c8edd7bca7ee0252e2569cf299c10ea959c11a550ac71a8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "132ec69ef2b5ec2a5d88a84e5510acd6ae9fd2670215ba08b2afe7b9e93911d2"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "ca1c253330fd2d606bb9f5429f107300a41e4b16b1d72c80d00ef760660f65a3"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "c8b5c367084d25187c68eba4fbdb05774ce6c2c977c29811001523c40e789dc4"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "844992d0ec60b49646d47d3c80a3ddb015046585a513d3d1baa7a96591fdd055"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "04abb06254ad357f0f943989fb89d3f903d72189cb4c60bb47d1d87caf73a3f9"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "chatmon/xkb.py",
          "sha256": "10a00e4c71d2b1771b2850ae5f6570b95af04433b2a6dbe4be38a7c6c86aea4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "cfe165292e0e040194480a37f954995803def534d8c07e54fdba3254386ccff6"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "ff636d3239ffef20685de7e86c6ce1a18e2753d6d7f77027349a9ff0b9c08edd"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "c313741b7009b7a1a7c7b13e4f160662aaead0c4f225d48e91b529bdf60d15a3"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "193614b91c1729ef801478fd6747a867920c60930a918ef2f80359736b3a9347"
        },
        {
          "path": "tests/test_imports.py",
          "sha256": "bb03d577b13589450c80feafc976ef5da20d3e86f64c69ffb4b42f2922db5033"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "c73db48214065cfde5d4c08fa0c42054b8b7688abcaa81730c32a6f55a59746d"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_windows.py",
          "sha256": "0a605c59891ec08734d8bf5b8767d775acf4b469999e51ede48630d39f633c33"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "791e260975da81a54071cdbddcedfeb76da3c20fee1bc5ae9853adeaebc34b7b",
      "red": null,
      "reason": null
    },
    {
      "id": "E-mypy-win32",
      "acceptance": [
        "M6B-02.A1",
        "M6B-02.A3"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "mypy",
        "--platform",
        "win32"
      ],
      "method": "mypy for win32 on the final source with pyproject.toml's settings and no exemption at all: no issues in 69 files.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/mypy-win32.log",
        "sha256": "6725346e7e718672bdbfe20e19d65da5ab4a76dc6251bc46e844b527baab356e"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "7e16f6b335ab56d8cb0746655cc997d6746b3d1bd24330b69e6e50dd3bbb23dd"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "786f8e2aa8d1e853ee92be33dfda0e6008439151e7beaa7052dcaf98ccbdde2d"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "1974f004b3074ea41ab30b1f0fa0b9f8ad212d9ca127d22bd7839bf3f538edae"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "552dea1c3cde46bcba3f360a5cef3e1844ea7af57fdab54bec1a397312f409f0"
        },
        {
          "path": "chatmon/context.py",
          "sha256": "53bf39016325ee5a8458dcb1d540b05a8a29cfd85934d6aa06cefa01f7200dcb"
        },
        {
          "path": "chatmon/ed25519.py",
          "sha256": "cee9d926326e398c783dc261214f15fe8b5dfc99719559a7739e094c266b9cc4"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "671b6a38b502e8d0a1d5882579d5906ebfb3fc005341fb26bb8967f84fe8bd26"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "be76509122882a3805c8340eb74547e0106c5d00d337dc50376597e5a8239cd8"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "1e7e5be17c68fa9e879b99b0e24113559d1856781b810f3fc540b22d7cd32885"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "30dc957489a349a915484f480a5b4621eaf3fe945e62ca76ebcafa3763384a34"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "41d0eea4d55dbf783696e07d499d93ffff1eee968501cb7e9f0393f23a00e97c"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "be49db85d004a8ee166ce412394c122c47bf2880e52c8f0a8dcf57e0cf4c7abe"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/report.py",
          "sha256": "8887d1f776e10f109c8edd7bca7ee0252e2569cf299c10ea959c11a550ac71a8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "132ec69ef2b5ec2a5d88a84e5510acd6ae9fd2670215ba08b2afe7b9e93911d2"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "ca1c253330fd2d606bb9f5429f107300a41e4b16b1d72c80d00ef760660f65a3"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "c8b5c367084d25187c68eba4fbdb05774ce6c2c977c29811001523c40e789dc4"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "844992d0ec60b49646d47d3c80a3ddb015046585a513d3d1baa7a96591fdd055"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "04abb06254ad357f0f943989fb89d3f903d72189cb4c60bb47d1d87caf73a3f9"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "chatmon/xkb.py",
          "sha256": "10a00e4c71d2b1771b2850ae5f6570b95af04433b2a6dbe4be38a7c6c86aea4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "cfe165292e0e040194480a37f954995803def534d8c07e54fdba3254386ccff6"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "ff636d3239ffef20685de7e86c6ce1a18e2753d6d7f77027349a9ff0b9c08edd"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "c313741b7009b7a1a7c7b13e4f160662aaead0c4f225d48e91b529bdf60d15a3"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "193614b91c1729ef801478fd6747a867920c60930a918ef2f80359736b3a9347"
        },
        {
          "path": "tests/test_imports.py",
          "sha256": "bb03d577b13589450c80feafc976ef5da20d3e86f64c69ffb4b42f2922db5033"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "c73db48214065cfde5d4c08fa0c42054b8b7688abcaa81730c32a6f55a59746d"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_windows.py",
          "sha256": "0a605c59891ec08734d8bf5b8767d775acf4b469999e51ede48630d39f633c33"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "791e260975da81a54071cdbddcedfeb76da3c20fee1bc5ae9853adeaebc34b7b",
      "red": null,
      "reason": null
    },
    {
      "id": "E-mypy-darwin",
      "acceptance": [
        "M6B-02.A1",
        "M6B-02.A3"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "mypy",
        "--platform",
        "darwin"
      ],
      "method": "mypy for darwin on the final source with pyproject.toml's settings and no exemption at all: no issues in 69 files.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/mypy-darwin.log",
        "sha256": "af309d5c0841d64d77560cc6056b750325c998edb7acfa70bb534e28ce0e1651"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "7e16f6b335ab56d8cb0746655cc997d6746b3d1bd24330b69e6e50dd3bbb23dd"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "786f8e2aa8d1e853ee92be33dfda0e6008439151e7beaa7052dcaf98ccbdde2d"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "1974f004b3074ea41ab30b1f0fa0b9f8ad212d9ca127d22bd7839bf3f538edae"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "552dea1c3cde46bcba3f360a5cef3e1844ea7af57fdab54bec1a397312f409f0"
        },
        {
          "path": "chatmon/context.py",
          "sha256": "53bf39016325ee5a8458dcb1d540b05a8a29cfd85934d6aa06cefa01f7200dcb"
        },
        {
          "path": "chatmon/ed25519.py",
          "sha256": "cee9d926326e398c783dc261214f15fe8b5dfc99719559a7739e094c266b9cc4"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "671b6a38b502e8d0a1d5882579d5906ebfb3fc005341fb26bb8967f84fe8bd26"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "be76509122882a3805c8340eb74547e0106c5d00d337dc50376597e5a8239cd8"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "1e7e5be17c68fa9e879b99b0e24113559d1856781b810f3fc540b22d7cd32885"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "30dc957489a349a915484f480a5b4621eaf3fe945e62ca76ebcafa3763384a34"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "41d0eea4d55dbf783696e07d499d93ffff1eee968501cb7e9f0393f23a00e97c"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "be49db85d004a8ee166ce412394c122c47bf2880e52c8f0a8dcf57e0cf4c7abe"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/report.py",
          "sha256": "8887d1f776e10f109c8edd7bca7ee0252e2569cf299c10ea959c11a550ac71a8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "132ec69ef2b5ec2a5d88a84e5510acd6ae9fd2670215ba08b2afe7b9e93911d2"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "ca1c253330fd2d606bb9f5429f107300a41e4b16b1d72c80d00ef760660f65a3"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "c8b5c367084d25187c68eba4fbdb05774ce6c2c977c29811001523c40e789dc4"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "844992d0ec60b49646d47d3c80a3ddb015046585a513d3d1baa7a96591fdd055"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "04abb06254ad357f0f943989fb89d3f903d72189cb4c60bb47d1d87caf73a3f9"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "chatmon/xkb.py",
          "sha256": "10a00e4c71d2b1771b2850ae5f6570b95af04433b2a6dbe4be38a7c6c86aea4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "cfe165292e0e040194480a37f954995803def534d8c07e54fdba3254386ccff6"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "ff636d3239ffef20685de7e86c6ce1a18e2753d6d7f77027349a9ff0b9c08edd"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "c313741b7009b7a1a7c7b13e4f160662aaead0c4f225d48e91b529bdf60d15a3"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "193614b91c1729ef801478fd6747a867920c60930a918ef2f80359736b3a9347"
        },
        {
          "path": "tests/test_imports.py",
          "sha256": "bb03d577b13589450c80feafc976ef5da20d3e86f64c69ffb4b42f2922db5033"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "c73db48214065cfde5d4c08fa0c42054b8b7688abcaa81730c32a6f55a59746d"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_windows.py",
          "sha256": "0a605c59891ec08734d8bf5b8767d775acf4b469999e51ede48630d39f633c33"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "791e260975da81a54071cdbddcedfeb76da3c20fee1bc5ae9853adeaebc34b7b",
      "red": null,
      "reason": null
    },
    {
      "id": "E-red-M6B-01-bubble-not-clear-of-the-box",
      "acceptance": [
        "M6B-01.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_overlay_stage.py::test_a_message_goes_above_the_open_box"
      ],
      "method": "Red drill M6B-01-bubble-not-clear-of-the-box through tests/drills/run.py in a temporary copy: green, chatmon/penguin.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills.log",
        "sha256": "d7bb64c714466377c7e159321d922703544484034ffb4e27dff7ee729cf387ed"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "b9566fff6d92a9ae0f274cc1a6842f22e274dbc5fae1fcb1b23e70c7b21b278d",
      "red": {
        "mutation": "M6B-01-bubble-not-clear-of-the-box: in chatmon/penguin.py, '            top = min(top, self._clear_of.geometry().top() - origin.y())\\r\\n' became '            top = top\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_message_goes_above_the_open_box",
        "observed_diagnostic": "___________________ test_a_message_goes_above_the_open_box ____________________",
        "before": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "cd79fb18f89a1b23bd2a8777b6056e12717310e2e926c647316dd534544410c9"
          }
        ],
        "after": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-01-menu-end-key-goes-home",
      "acceptance": [
        "M6B-01.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_stagemenu.py::test_the_keyboard_moves_opens_picks_and_closes"
      ],
      "method": "Red drill M6B-01-menu-end-key-goes-home through tests/drills/run.py in a temporary copy: green, chatmon/stagemenu.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills.log",
        "sha256": "d7bb64c714466377c7e159321d922703544484034ffb4e27dff7ee729cf387ed"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "b9566fff6d92a9ae0f274cc1a6842f22e274dbc5fae1fcb1b23e70c7b21b278d",
      "red": {
        "mutation": "M6B-01-menu-end-key-goes-home: in chatmon/stagemenu.py, 'self._activate(panel, pickable[0 if key == Qt.Key.Key_Home else -1])' became 'self._activate(panel, pickable[0])'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_keyboard_moves_opens_picks_and_closes",
        "observed_diagnostic": "_______________ test_the_keyboard_moves_opens_picks_and_closes ________________",
        "before": [
          {
            "path": "chatmon/stagemenu.py",
            "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/stagemenu.py",
            "sha256": "e61684c2a914dfd78c6d54a297101e36f54d182d3d8cc3f25232dd1140e68084"
          }
        ],
        "after": [
          {
            "path": "chatmon/stagemenu.py",
            "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-01-extractor-misses-import-time",
      "acceptance": [
        "M6B-01.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_i18n.py::test_the_extractor_refuses_a_string_that_couldnt_be_translated"
      ],
      "method": "Red drill M6B-01-extractor-misses-import-time through tests/drills/run.py in a temporary copy: green, packaging/extract_strings.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills.log",
        "sha256": "d7bb64c714466377c7e159321d922703544484034ffb4e27dff7ee729cf387ed"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "b9566fff6d92a9ae0f274cc1a6842f22e274dbc5fae1fcb1b23e70c7b21b278d",
      "red": {
        "mutation": "M6B-01-extractor-misses-import-time: in packaging/extract_strings.py, '    if marker in TRANSLATED_NOW and at_import:\\r\\n' became '    if False:\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_extractor_refuses_a_string_that_couldnt_be_translated",
        "observed_diagnostic": "_ test_the_extractor_refuses_a_string_that_couldnt_be_translated[GREETING = _(\"Hi\")\\n-imported] _",
        "before": [
          {
            "path": "packaging/extract_strings.py",
            "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
          }
        ],
        "mutated": [
          {
            "path": "packaging/extract_strings.py",
            "sha256": "559c35008cda39ebb0b862fa3db6e47edceefd95ee3986c660797ea0b3792af1"
          }
        ],
        "after": [
          {
            "path": "packaging/extract_strings.py",
            "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-02-a-module-loads-macos-on-import",
      "acceptance": [
        "M6B-02.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_imports.py"
      ],
      "method": "Red drill M6B-02-a-module-loads-macos-on-import through tests/drills/run.py in a temporary copy: green, chatmon/macnative.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills.log",
        "sha256": "d7bb64c714466377c7e159321d922703544484034ffb4e27dff7ee729cf387ed"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "786f8e2aa8d1e853ee92be33dfda0e6008439151e7beaa7052dcaf98ccbdde2d"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/context.py",
          "sha256": "53bf39016325ee5a8458dcb1d540b05a8a29cfd85934d6aa06cefa01f7200dcb"
        },
        {
          "path": "chatmon/ed25519.py",
          "sha256": "cee9d926326e398c783dc261214f15fe8b5dfc99719559a7739e094c266b9cc4"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "671b6a38b502e8d0a1d5882579d5906ebfb3fc005341fb26bb8967f84fe8bd26"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "be76509122882a3805c8340eb74547e0106c5d00d337dc50376597e5a8239cd8"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "be49db85d004a8ee166ce412394c122c47bf2880e52c8f0a8dcf57e0cf4c7abe"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/report.py",
          "sha256": "8887d1f776e10f109c8edd7bca7ee0252e2569cf299c10ea959c11a550ac71a8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "c8b5c367084d25187c68eba4fbdb05774ce6c2c977c29811001523c40e789dc4"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "844992d0ec60b49646d47d3c80a3ddb015046585a513d3d1baa7a96591fdd055"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "04abb06254ad357f0f943989fb89d3f903d72189cb4c60bb47d1d87caf73a3f9"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "chatmon/xkb.py",
          "sha256": "10a00e4c71d2b1771b2850ae5f6570b95af04433b2a6dbe4be38a7c6c86aea4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_imports.py",
          "sha256": "bb03d577b13589450c80feafc976ef5da20d3e86f64c69ffb4b42f2922db5033"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "aa9c6d74d9193298753f401b13339d6a21b3bd46111464211f8bb0d50aa964a8",
      "red": {
        "mutation": "M6B-02-a-module-loads-macos-on-import: in chatmon/macnative.py, 'logger = logging.getLogger(__name__)\\r\\n' became 'logger = logging.getLogger(__name__)\\r\\n_objc = ctypes.cdll.LoadLibrary(\"/usr/lib/libobjc.A.dylib\")\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "chatmon.macnative doesn't import on win32",
        "observed_diagnostic": "E       AssertionError: chatmon.macnative doesn't import on win32:",
        "before": [
          {
            "path": "chatmon/macnative.py",
            "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/macnative.py",
            "sha256": "4f68f5d651f5a651379c9ab46e91b34d29fd8ff01e08f41e36bac20c98eee4d1"
          }
        ],
        "after": [
          {
            "path": "chatmon/macnative.py",
            "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-03-debug-env-ignored",
      "acceptance": [
        "M6B-03.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_log.py::test_chatmon_debug_keeps_the_details_too"
      ],
      "method": "Red drill M6B-03-debug-env-ignored through tests/drills/run.py in a temporary copy: green, chatmon/log.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills.log",
        "sha256": "d7bb64c714466377c7e159321d922703544484034ffb4e27dff7ee729cf387ed"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        }
      ],
      "scope_sha256": "d35083be967856d71fa64de19d516bdd9a890f01c6e57609a72e1b1cd180c6c4",
      "red": {
        "mutation": "M6B-03-debug-env-ignored: in chatmon/log.py, '    level = logging.DEBUG if debugging() else logging.INFO\\n' became '    level = logging.INFO\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_chatmon_debug_keeps_the_details_too",
        "observed_diagnostic": "__________________ test_chatmon_debug_keeps_the_details_too ___________________",
        "before": [
          {
            "path": "chatmon/log.py",
            "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/log.py",
            "sha256": "e36447c4c7e274d1c1c84fa2e78b3782db4393898b93a3388150d3d85420a25b"
          }
        ],
        "after": [
          {
            "path": "chatmon/log.py",
            "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-03-no-stderr",
      "acceptance": [
        "M6B-03.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_log.py::test_problems_reach_stderr_as_well_and_details_and_news_dont"
      ],
      "method": "Red drill M6B-03-no-stderr through tests/drills/run.py in a temporary copy: green, chatmon/log.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills.log",
        "sha256": "d7bb64c714466377c7e159321d922703544484034ffb4e27dff7ee729cf387ed"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        }
      ],
      "scope_sha256": "d35083be967856d71fa64de19d516bdd9a890f01c6e57609a72e1b1cd180c6c4",
      "red": {
        "mutation": "M6B-03-no-stderr: in chatmon/log.py, '    if sys.stderr is not None:\\n' became '    if False:\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_problems_reach_stderr_as_well_and_details_and_news_dont",
        "observed_diagnostic": "________ test_problems_reach_stderr_as_well_and_details_and_news_dont _________",
        "before": [
          {
            "path": "chatmon/log.py",
            "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/log.py",
            "sha256": "762273bae88fad83f7bdb9c823582a1f7b1b10bfb3245b99d70e342d2e29103a"
          }
        ],
        "after": [
          {
            "path": "chatmon/log.py",
            "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-03-setup-twice-doubles",
      "acceptance": [
        "M6B-03.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_log.py::test_setting_up_twice_keeps_one_of_each"
      ],
      "method": "Red drill M6B-03-setup-twice-doubles through tests/drills/run.py in a temporary copy: green, chatmon/log.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills.log",
        "sha256": "d7bb64c714466377c7e159321d922703544484034ffb4e27dff7ee729cf387ed"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        }
      ],
      "scope_sha256": "d35083be967856d71fa64de19d516bdd9a890f01c6e57609a72e1b1cd180c6c4",
      "red": {
        "mutation": "M6B-03-setup-twice-doubles: in chatmon/log.py, '    reset()\\n    level = ' became '    level = '",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_setting_up_twice_keeps_one_of_each",
        "observed_diagnostic": "___________________ test_setting_up_twice_keeps_one_of_each ___________________",
        "before": [
          {
            "path": "chatmon/log.py",
            "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/log.py",
            "sha256": "556c2be548cf050405d8e4dd1244ee6afa54aa9608213c6bdcf021f402b30f4b"
          }
        ],
        "after": [
          {
            "path": "chatmon/log.py",
            "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-03-rotated-as-dot-1",
      "acceptance": [
        "M6B-03.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_log.py::test_a_full_log_starts_over_and_the_last_one_is_kept_as_old"
      ],
      "method": "Red drill M6B-03-rotated-as-dot-1 through tests/drills/run.py in a temporary copy: green, chatmon/log.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills.log",
        "sha256": "d7bb64c714466377c7e159321d922703544484034ffb4e27dff7ee729cf387ed"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        }
      ],
      "scope_sha256": "d35083be967856d71fa64de19d516bdd9a890f01c6e57609a72e1b1cd180c6c4",
      "red": {
        "mutation": "M6B-03-rotated-as-dot-1: in chatmon/log.py, '    return default.removesuffix(\".1\") + \".old\"\\n' became '    return default\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_full_log_starts_over_and_the_last_one_is_kept_as_old",
        "observed_diagnostic": "_________ test_a_full_log_starts_over_and_the_last_one_is_kept_as_old _________",
        "before": [
          {
            "path": "chatmon/log.py",
            "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/log.py",
            "sha256": "3c73a342d73100491091505d702d84367c3714c17904754de96e61fbeba7df31"
          }
        ],
        "after": [
          {
            "path": "chatmon/log.py",
            "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-03-limit-ten-times",
      "acceptance": [
        "M6B-03.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_log.py::test_a_full_log_starts_over_and_the_last_one_is_kept_as_old"
      ],
      "method": "Red drill M6B-03-limit-ten-times through tests/drills/run.py in a temporary copy: green, chatmon/log.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills.log",
        "sha256": "d7bb64c714466377c7e159321d922703544484034ffb4e27dff7ee729cf387ed"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        }
      ],
      "scope_sha256": "d35083be967856d71fa64de19d516bdd9a890f01c6e57609a72e1b1cd180c6c4",
      "red": {
        "mutation": "M6B-03-limit-ten-times: in chatmon/log.py, 'maxBytes=LIMIT,' became 'maxBytes=LIMIT * 10,'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_full_log_starts_over_and_the_last_one_is_kept_as_old",
        "observed_diagnostic": "_________ test_a_full_log_starts_over_and_the_last_one_is_kept_as_old _________",
        "before": [
          {
            "path": "chatmon/log.py",
            "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/log.py",
            "sha256": "8f5ccedcc65dad1c65f439121450c0eef45a535161d15e7a119aa3e659979da1"
          }
        ],
        "after": [
          {
            "path": "chatmon/log.py",
            "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-03-keys-not-blanked",
      "acceptance": [
        "M6B-03.A3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_log.py::test_anything_shaped_like_a_key_is_blanked_as_it_is_written"
      ],
      "method": "Red drill M6B-03-keys-not-blanked through tests/drills/run.py in a temporary copy: green, chatmon/log.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills.log",
        "sha256": "d7bb64c714466377c7e159321d922703544484034ffb4e27dff7ee729cf387ed"
      },
      "inputs": [
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        }
      ],
      "scope_sha256": "a69c67927029e50e3973257e7fb2b8a153863230020fad3f1c5399647321b6d3",
      "red": {
        "mutation": "M6B-03-keys-not-blanked: in chatmon/log.py, '    return _KEYS.sub(BLANKED, text)\\n' became '    return text\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_anything_shaped_like_a_key_is_blanked_as_it_is_written",
        "observed_diagnostic": "_________ test_anything_shaped_like_a_key_is_blanked_as_it_is_written _________",
        "before": [
          {
            "path": "chatmon/log.py",
            "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/log.py",
            "sha256": "2e2b4667413f122cd91df69b548a73ace83de53df757ac82949396a1104d6c3f"
          }
        ],
        "after": [
          {
            "path": "chatmon/log.py",
            "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-03-console-not-blanked",
      "acceptance": [
        "M6B-03.A3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_log.py::test_anything_shaped_like_a_key_is_blanked_as_it_is_written"
      ],
      "method": "Red drill M6B-03-console-not-blanked through tests/drills/run.py in a temporary copy: green, chatmon/log.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills.log",
        "sha256": "d7bb64c714466377c7e159321d922703544484034ffb4e27dff7ee729cf387ed"
      },
      "inputs": [
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        }
      ],
      "scope_sha256": "a69c67927029e50e3973257e7fb2b8a153863230020fad3f1c5399647321b6d3",
      "red": {
        "mutation": "M6B-03-console-not-blanked: in chatmon/log.py, '        console.setFormatter(_Blanking(CONSOLE_FORMAT))\\n' became '        console.setFormatter(logging.Formatter(CONSOLE_FORMAT))\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_anything_shaped_like_a_key_is_blanked_as_it_is_written",
        "observed_diagnostic": "_________ test_anything_shaped_like_a_key_is_blanked_as_it_is_written _________",
        "before": [
          {
            "path": "chatmon/log.py",
            "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/log.py",
            "sha256": "91a88abc91cf8c466d3937866502b78f362085cf57608a7d1dd17ffaaf031a7d"
          }
        ],
        "after": [
          {
            "path": "chatmon/log.py",
            "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-03-brain-key-not-scrubbed",
      "acceptance": [
        "M6B-03.A3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_log.py::test_a_logged_brain_error_never_carries_the_key"
      ],
      "method": "Red drill M6B-03-brain-key-not-scrubbed through tests/drills/run.py in a temporary copy: green, chatmon/brains.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills.log",
        "sha256": "d7bb64c714466377c7e159321d922703544484034ffb4e27dff7ee729cf387ed"
      },
      "inputs": [
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        }
      ],
      "scope_sha256": "a69c67927029e50e3973257e7fb2b8a153863230020fad3f1c5399647321b6d3",
      "red": {
        "mutation": "M6B-03-brain-key-not-scrubbed: in chatmon/brains.py, '    return text.replace(key, \"…\") if len(key) >= 8 else text\\r\\n' became '    return text\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_logged_brain_error_never_carries_the_key",
        "observed_diagnostic": "_______________ test_a_logged_brain_error_never_carries_the_key _______________",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "a0facaf3e6612a7d19cc61b54581e183e876b73b604d868196c08fc1841643a5"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-03-brain-failure-not-logged",
      "acceptance": [
        "M6B-03.A3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_log.py::test_a_logged_brain_error_never_carries_the_key"
      ],
      "method": "Red drill M6B-03-brain-failure-not-logged through tests/drills/run.py in a temporary copy: green, chatmon/brains.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills.log",
        "sha256": "d7bb64c714466377c7e159321d922703544484034ffb4e27dff7ee729cf387ed"
      },
      "inputs": [
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        }
      ],
      "scope_sha256": "a69c67927029e50e3973257e7fb2b8a153863230020fad3f1c5399647321b6d3",
      "red": {
        "mutation": "M6B-03-brain-failure-not-logged: in chatmon/brains.py, '        self.failed.connect(self._log_failure)\\r\\n' became ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_logged_brain_error_never_carries_the_key",
        "observed_diagnostic": "_______________ test_a_logged_brain_error_never_carries_the_key _______________",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "d6055df6ac7b35c863ac1359208188f717d02d25027595ff5c5fb12ca34a3daf"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-03-autostart-warning-printed",
      "acceptance": [
        "M6B-03.A4"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_autostart.py::test_a_login_item_macos_turns_down_falls_back_to_a_launch_agent"
      ],
      "method": "Red drill M6B-03-autostart-warning-printed through tests/drills/run.py in a temporary copy: green, chatmon/autostart.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills.log",
        "sha256": "d7bb64c714466377c7e159321d922703544484034ffb4e27dff7ee729cf387ed"
      },
      "inputs": [
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        }
      ],
      "scope_sha256": "a69c67927029e50e3973257e7fb2b8a153863230020fad3f1c5399647321b6d3",
      "red": {
        "mutation": "M6B-03-autostart-warning-printed: in chatmon/autostart.py, '        logger.warning(\"couldn\\'t add Chatmon to Login Items (%s), so a LaunchAgent starts it\", problem)\\r\\n' became '        print(f\"couldn\\'t add Chatmon to Login Items ({problem}), so a LaunchAgent starts it\", file=sys.stderr)\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_login_item_macos_turns_down_falls_back_to_a_launch_agent",
        "observed_diagnostic": "_______ test_a_login_item_macos_turns_down_falls_back_to_a_launch_agent _______",
        "before": [
          {
            "path": "chatmon/autostart.py",
            "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/autostart.py",
            "sha256": "dbe7fe1f7aecb0898d1c561a78c9f84a5d4cfb34aebaffc56e86030a91cbfcb4"
          }
        ],
        "after": [
          {
            "path": "chatmon/autostart.py",
            "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-03-chat-failure-hidden",
      "acceptance": [
        "M6B-03.A5"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_chats.py::test_a_damaged_chat_file_is_logged_and_left_out_and_one_not_kept_is_not"
      ],
      "method": "Red drill M6B-03-chat-failure-hidden through tests/drills/run.py in a temporary copy: green, chatmon/chats.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills.log",
        "sha256": "d7bb64c714466377c7e159321d922703544484034ffb4e27dff7ee729cf387ed"
      },
      "inputs": [
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        }
      ],
      "scope_sha256": "a69c67927029e50e3973257e7fb2b8a153863230020fad3f1c5399647321b6d3",
      "red": {
        "mutation": "M6B-03-chat-failure-hidden: in chatmon/chats.py, '            logger.debug(\"couldn\\'t read chat %s: %s\", chat_id, exc)\\r\\n' became '            pass\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_damaged_chat_file_is_logged_and_left_out_and_one_not_kept_is_not",
        "observed_diagnostic": "___ test_a_damaged_chat_file_is_logged_and_left_out_and_one_not_kept_is_not ___",
        "before": [
          {
            "path": "chatmon/chats.py",
            "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/chats.py",
            "sha256": "481922eee2e2c269d0ec47c69e933c1e46d0116493ec7b3904c815c59bf922ae"
          }
        ],
        "after": [
          {
            "path": "chatmon/chats.py",
            "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-03-package-manager-failure-hidden",
      "acceptance": [
        "M6B-03.A5"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_updates.py::test_a_package_manager_that_wont_run_is_logged_and_the_next_one_asked"
      ],
      "method": "Red drill M6B-03-package-manager-failure-hidden through tests/drills/run.py in a temporary copy: green, chatmon/updates.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills.log",
        "sha256": "d7bb64c714466377c7e159321d922703544484034ffb4e27dff7ee729cf387ed"
      },
      "inputs": [
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        }
      ],
      "scope_sha256": "a69c67927029e50e3973257e7fb2b8a153863230020fad3f1c5399647321b6d3",
      "red": {
        "mutation": "M6B-03-package-manager-failure-hidden: in chatmon/updates.py, '                    logger.debug(\"couldn\\'t ask %s whether it installed Chatmon: %s\", query[0], exc)\\r\\n' became '                    pass\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_package_manager_that_wont_run_is_logged_and_the_next_one_asked",
        "observed_diagnostic": "____ test_a_package_manager_that_wont_run_is_logged_and_the_next_one_asked ____",
        "before": [
          {
            "path": "chatmon/updates.py",
            "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/updates.py",
            "sha256": "fe0826c0f7679589cad9418ee0ff7d0439bca89f6610cef2b2524ab49fefe0a4"
          }
        ],
        "after": [
          {
            "path": "chatmon/updates.py",
            "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-03-phrases-failure-hidden",
      "acceptance": [
        "M6B-03.A5"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_offline.py::test_a_broken_translation_is_logged_and_a_missing_one_isnt"
      ],
      "method": "Red drill M6B-03-phrases-failure-hidden through tests/drills/run.py in a temporary copy: green, chatmon/offline.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills.log",
        "sha256": "d7bb64c714466377c7e159321d922703544484034ffb4e27dff7ee729cf387ed"
      },
      "inputs": [
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        }
      ],
      "scope_sha256": "a69c67927029e50e3973257e7fb2b8a153863230020fad3f1c5399647321b6d3",
      "red": {
        "mutation": "M6B-03-phrases-failure-hidden: in chatmon/offline.py, '            logger.debug(\"couldn\\'t read the phrases in %s: %s\", folder / f\"{candidate}.json\", exc)\\r\\n' became '            pass\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_broken_translation_is_logged_and_a_missing_one_isnt",
        "observed_diagnostic": "_________ test_a_broken_translation_is_logged_and_a_missing_one_isnt __________",
        "before": [
          {
            "path": "chatmon/offline.py",
            "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/offline.py",
            "sha256": "c0873417fa821a0f3a8c9553362c541454869e491715f0d304a455b639198bf8"
          }
        ],
        "after": [
          {
            "path": "chatmon/offline.py",
            "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-03-reminder-words-logged",
      "acceptance": [
        "M6B-03.A5"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_reminders.py::test_a_saved_reminder_that_cant_be_read_is_logged_without_its_words"
      ],
      "method": "Red drill M6B-03-reminder-words-logged through tests/drills/run.py in a temporary copy: green, chatmon/reminders.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills.log",
        "sha256": "d7bb64c714466377c7e159321d922703544484034ffb4e27dff7ee729cf387ed"
      },
      "inputs": [
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        }
      ],
      "scope_sha256": "a69c67927029e50e3973257e7fb2b8a153863230020fad3f1c5399647321b6d3",
      "red": {
        "mutation": "M6B-03-reminder-words-logged: in chatmon/reminders.py, '                logger.debug(\"skipped a saved reminder that can\\'t be read (%s)\", type(exc).__name__)\\r\\n' became '                logger.debug(\"skipped a saved reminder that can\\'t be read (%s): %s\", type(exc).__name__, entry)\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_saved_reminder_that_cant_be_read_is_logged_without_its_words",
        "observed_diagnostic": "_____ test_a_saved_reminder_that_cant_be_read_is_logged_without_its_words _____",
        "before": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "02b33ffc0086dafead445d9263fcf88409fb0f429ea045ae2692bf9892608e7e"
          }
        ],
        "after": [
          {
            "path": "chatmon/reminders.py",
            "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-03-player-failure-hidden",
      "acceptance": [
        "M6B-03.A5"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_sound.py::test_a_player_that_wont_start_goes_to_the_log_and_the_next_one_plays"
      ],
      "method": "Red drill M6B-03-player-failure-hidden through tests/drills/run.py in a temporary copy: green, chatmon/sound.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills.log",
        "sha256": "d7bb64c714466377c7e159321d922703544484034ffb4e27dff7ee729cf387ed"
      },
      "inputs": [
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        }
      ],
      "scope_sha256": "a69c67927029e50e3973257e7fb2b8a153863230020fad3f1c5399647321b6d3",
      "red": {
        "mutation": "M6B-03-player-failure-hidden: in chatmon/sound.py, '            logger.debug(\"couldn\\'t start %s: %s\", self.name, exc)\\r\\n' became '            pass\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_player_that_wont_start_goes_to_the_log_and_the_next_one_plays",
        "observed_diagnostic": "____ test_a_player_that_wont_start_goes_to_the_log_and_the_next_one_plays _____",
        "before": [
          {
            "path": "chatmon/sound.py",
            "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sound.py",
            "sha256": "d8866ffa3244bee58464ce4aeef83a07f04fef3687f66dd8e5fa349b4f090410"
          }
        ],
        "after": [
          {
            "path": "chatmon/sound.py",
            "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-RW-http-error-left-open",
      "acceptance": [
        "M6B-RW.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-W",
        "error::ResourceWarning",
        "tests/test_brains.py::test_a_local_servers_window_is_asked_for_and_a_redirect_never_followed"
      ],
      "method": "Red drill M6B-RW-http-error-left-open through tests/drills/run.py in a temporary copy: green, chatmon/brains.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills.log",
        "sha256": "d7bb64c714466377c7e159321d922703544484034ffb4e27dff7ee729cf387ed"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        }
      ],
      "scope_sha256": "6c763c74141387ea7fd6e6ae978de9a9b4f7db471f7a2a4c7bdfe4d4a456a929",
      "red": {
        "mutation": "M6B-RW-http-error-left-open: in chatmon/brains.py, '        exc.close()\\r\\n        raise\\r\\n' became '        raise\\r\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "ResourceWarning",
        "observed_diagnostic": ">           _warnings.warn(self.warn_message, ResourceWarning)",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "9e048e3e456a183d02289e261a7d38a4b6a963339c90f7c080e288acd1e1d937"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-RW-release-server-left-open",
      "acceptance": [
        "M6B-RW.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-W",
        "error::ResourceWarning",
        "tests/test_updates.py"
      ],
      "method": "Red drill M6B-RW-release-server-left-open through tests/drills/run.py in a temporary copy: green, tests/test_updates.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills.log",
        "sha256": "d7bb64c714466377c7e159321d922703544484034ffb4e27dff7ee729cf387ed"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        }
      ],
      "scope_sha256": "6c763c74141387ea7fd6e6ae978de9a9b4f7db471f7a2a4c7bdfe4d4a456a929",
      "red": {
        "mutation": "M6B-RW-release-server-left-open: in tests/test_updates.py, '    server.shutdown()\\r\\n    server.server_close()\\r\\n\\r\\n\\r\\ndef run_updater' became '    server.shutdown()\\r\\n\\r\\n\\r\\ndef run_updater'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "ResourceWarning",
        "observed_diagnostic": "E           ResourceWarning: unclosed <socket.socket fd=960, family=2, type=1, proto=0, laddr=('127.0.0.1', 56312)>",
        "before": [
          {
            "path": "tests/test_updates.py",
            "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
          }
        ],
        "mutated": [
          {
            "path": "tests/test_updates.py",
            "sha256": "0234967f0b7016e6c74e7c1343690ed471c69e99a869bce00b25fd271491de8c"
          }
        ],
        "after": [
          {
            "path": "tests/test_updates.py",
            "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-B-escaped-exception-not-in-the-log",
      "acceptance": [
        "M6B-03.A6"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_smoke.py::test_an_exception_that_escapes_a_slot_goes_into_the_log_with_its_traceback"
      ],
      "method": "Red drill M6B-B-escaped-exception-not-in-the-log through tests/drills/run.py in a temporary copy: green, chatmon/app.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills-b.log",
        "sha256": "60df2298b0bd80d3cd5f9bdefdc4304e2d1854e618d65ddc63cc509dc5193f5f"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "7e16f6b335ab56d8cb0746655cc997d6746b3d1bd24330b69e6e50dd3bbb23dd"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "786f8e2aa8d1e853ee92be33dfda0e6008439151e7beaa7052dcaf98ccbdde2d"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "1974f004b3074ea41ab30b1f0fa0b9f8ad212d9ca127d22bd7839bf3f538edae"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "552dea1c3cde46bcba3f360a5cef3e1844ea7af57fdab54bec1a397312f409f0"
        },
        {
          "path": "chatmon/context.py",
          "sha256": "53bf39016325ee5a8458dcb1d540b05a8a29cfd85934d6aa06cefa01f7200dcb"
        },
        {
          "path": "chatmon/ed25519.py",
          "sha256": "cee9d926326e398c783dc261214f15fe8b5dfc99719559a7739e094c266b9cc4"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "671b6a38b502e8d0a1d5882579d5906ebfb3fc005341fb26bb8967f84fe8bd26"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "be76509122882a3805c8340eb74547e0106c5d00d337dc50376597e5a8239cd8"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "1e7e5be17c68fa9e879b99b0e24113559d1856781b810f3fc540b22d7cd32885"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "30dc957489a349a915484f480a5b4621eaf3fe945e62ca76ebcafa3763384a34"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "41d0eea4d55dbf783696e07d499d93ffff1eee968501cb7e9f0393f23a00e97c"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "be49db85d004a8ee166ce412394c122c47bf2880e52c8f0a8dcf57e0cf4c7abe"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/report.py",
          "sha256": "8887d1f776e10f109c8edd7bca7ee0252e2569cf299c10ea959c11a550ac71a8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "132ec69ef2b5ec2a5d88a84e5510acd6ae9fd2670215ba08b2afe7b9e93911d2"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "ca1c253330fd2d606bb9f5429f107300a41e4b16b1d72c80d00ef760660f65a3"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "c8b5c367084d25187c68eba4fbdb05774ce6c2c977c29811001523c40e789dc4"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "844992d0ec60b49646d47d3c80a3ddb015046585a513d3d1baa7a96591fdd055"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "04abb06254ad357f0f943989fb89d3f903d72189cb4c60bb47d1d87caf73a3f9"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "chatmon/xkb.py",
          "sha256": "10a00e4c71d2b1771b2850ae5f6570b95af04433b2a6dbe4be38a7c6c86aea4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "cfe165292e0e040194480a37f954995803def534d8c07e54fdba3254386ccff6"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "ff636d3239ffef20685de7e86c6ce1a18e2753d6d7f77027349a9ff0b9c08edd"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "c313741b7009b7a1a7c7b13e4f160662aaead0c4f225d48e91b529bdf60d15a3"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "193614b91c1729ef801478fd6747a867920c60930a918ef2f80359736b3a9347"
        },
        {
          "path": "tests/test_imports.py",
          "sha256": "bb03d577b13589450c80feafc976ef5da20d3e86f64c69ffb4b42f2922db5033"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "c73db48214065cfde5d4c08fa0c42054b8b7688abcaa81730c32a6f55a59746d"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_windows.py",
          "sha256": "0a605c59891ec08734d8bf5b8767d775acf4b469999e51ede48630d39f633c33"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "791e260975da81a54071cdbddcedfeb76da3c20fee1bc5ae9853adeaebc34b7b",
      "red": {
        "mutation": "M6B-B-escaped-exception-not-in-the-log: in chatmon/app.py, '    logger.error(\"something went wrong\", exc_info=(kind, value, tb))' became '    logger.debug(\"something went wrong\", exc_info=(kind, value, tb))'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_an_exception_that_escapes_a_slot_goes_into_the_log_with_its_traceback",
        "observed_diagnostic": "_ test_an_exception_that_escapes_a_slot_goes_into_the_log_with_its_traceback __",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "4259e6c1ad4158507f98d8692d85c4bf73793b4a37ee81f5617501f3bea64964"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-B-status-waits-for-the-brain",
      "acceptance": [
        "M6B-LEFT.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_status_names_the_brain_from_the_finder_and_never_waits_for_one"
      ],
      "method": "Red drill M6B-B-status-waits-for-the-brain through tests/drills/run.py in a temporary copy: green, chatmon/app.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills-b.log",
        "sha256": "60df2298b0bd80d3cd5f9bdefdc4304e2d1854e618d65ddc63cc509dc5193f5f"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "7e16f6b335ab56d8cb0746655cc997d6746b3d1bd24330b69e6e50dd3bbb23dd"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "786f8e2aa8d1e853ee92be33dfda0e6008439151e7beaa7052dcaf98ccbdde2d"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "1974f004b3074ea41ab30b1f0fa0b9f8ad212d9ca127d22bd7839bf3f538edae"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "552dea1c3cde46bcba3f360a5cef3e1844ea7af57fdab54bec1a397312f409f0"
        },
        {
          "path": "chatmon/context.py",
          "sha256": "53bf39016325ee5a8458dcb1d540b05a8a29cfd85934d6aa06cefa01f7200dcb"
        },
        {
          "path": "chatmon/ed25519.py",
          "sha256": "cee9d926326e398c783dc261214f15fe8b5dfc99719559a7739e094c266b9cc4"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "671b6a38b502e8d0a1d5882579d5906ebfb3fc005341fb26bb8967f84fe8bd26"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "be76509122882a3805c8340eb74547e0106c5d00d337dc50376597e5a8239cd8"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "1e7e5be17c68fa9e879b99b0e24113559d1856781b810f3fc540b22d7cd32885"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "30dc957489a349a915484f480a5b4621eaf3fe945e62ca76ebcafa3763384a34"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "41d0eea4d55dbf783696e07d499d93ffff1eee968501cb7e9f0393f23a00e97c"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "be49db85d004a8ee166ce412394c122c47bf2880e52c8f0a8dcf57e0cf4c7abe"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/report.py",
          "sha256": "8887d1f776e10f109c8edd7bca7ee0252e2569cf299c10ea959c11a550ac71a8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "132ec69ef2b5ec2a5d88a84e5510acd6ae9fd2670215ba08b2afe7b9e93911d2"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "ca1c253330fd2d606bb9f5429f107300a41e4b16b1d72c80d00ef760660f65a3"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "c8b5c367084d25187c68eba4fbdb05774ce6c2c977c29811001523c40e789dc4"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "844992d0ec60b49646d47d3c80a3ddb015046585a513d3d1baa7a96591fdd055"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "04abb06254ad357f0f943989fb89d3f903d72189cb4c60bb47d1d87caf73a3f9"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "chatmon/xkb.py",
          "sha256": "10a00e4c71d2b1771b2850ae5f6570b95af04433b2a6dbe4be38a7c6c86aea4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "cfe165292e0e040194480a37f954995803def534d8c07e54fdba3254386ccff6"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "57243e1b45e87b98c53e6a5999fc6457ab83cdfe4e97f43814b2a11fce5f38d7"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "ff636d3239ffef20685de7e86c6ce1a18e2753d6d7f77027349a9ff0b9c08edd"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "c313741b7009b7a1a7c7b13e4f160662aaead0c4f225d48e91b529bdf60d15a3"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "03666f40b0987e337270d8d69b303648d37ae5cf8bc3f5ccde9e3dddd91d2167"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "193614b91c1729ef801478fd6747a867920c60930a918ef2f80359736b3a9347"
        },
        {
          "path": "tests/test_imports.py",
          "sha256": "bb03d577b13589450c80feafc976ef5da20d3e86f64c69ffb4b42f2922db5033"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_macnative.py",
          "sha256": "2da102be56c933c363d0e78794907716fbabdf94f5985fd2fc2762b1f5d1f651"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "c73db48214065cfde5d4c08fa0c42054b8b7688abcaa81730c32a6f55a59746d"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_windows.py",
          "sha256": "0a605c59891ec08734d8bf5b8767d775acf4b469999e51ede48630d39f633c33"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "47e1814cbb60dc0fcc3d14155f1086156737e006722bfd60c4252dac44e299fc",
      "red": {
        "mutation": "M6B-B-status-waits-for-the-brain: in chatmon/app.py, '        self.finder.find(self.brains, self.config[\"ai\"][\"brain\"], self.state.get(\"brain\"), found)' became '        found(self._brain())'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_status_names_the_brain_from_the_finder_and_never_waits_for_one",
        "observed_diagnostic": "_____ test_status_names_the_brain_from_the_finder_and_never_waits_for_one _____",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "d445c81ec7be0e20703a753d16add0423c2ad31d776dc567c0cabf6fc8daa7a8"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-B-desktops-words-not-shown",
      "acceptance": [
        "M6B-LEFT.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_settings_says_how_the_desktop_has_the_hotkey_where_it_chose_its_own_words"
      ],
      "method": "Red drill M6B-B-desktops-words-not-shown through tests/drills/run.py in a temporary copy: green, chatmon/settingswin.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills-b.log",
        "sha256": "60df2298b0bd80d3cd5f9bdefdc4304e2d1854e618d65ddc63cc509dc5193f5f"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "7e16f6b335ab56d8cb0746655cc997d6746b3d1bd24330b69e6e50dd3bbb23dd"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "786f8e2aa8d1e853ee92be33dfda0e6008439151e7beaa7052dcaf98ccbdde2d"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "1974f004b3074ea41ab30b1f0fa0b9f8ad212d9ca127d22bd7839bf3f538edae"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "552dea1c3cde46bcba3f360a5cef3e1844ea7af57fdab54bec1a397312f409f0"
        },
        {
          "path": "chatmon/context.py",
          "sha256": "53bf39016325ee5a8458dcb1d540b05a8a29cfd85934d6aa06cefa01f7200dcb"
        },
        {
          "path": "chatmon/ed25519.py",
          "sha256": "cee9d926326e398c783dc261214f15fe8b5dfc99719559a7739e094c266b9cc4"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "671b6a38b502e8d0a1d5882579d5906ebfb3fc005341fb26bb8967f84fe8bd26"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "be76509122882a3805c8340eb74547e0106c5d00d337dc50376597e5a8239cd8"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "1e7e5be17c68fa9e879b99b0e24113559d1856781b810f3fc540b22d7cd32885"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "30dc957489a349a915484f480a5b4621eaf3fe945e62ca76ebcafa3763384a34"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "41d0eea4d55dbf783696e07d499d93ffff1eee968501cb7e9f0393f23a00e97c"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "be49db85d004a8ee166ce412394c122c47bf2880e52c8f0a8dcf57e0cf4c7abe"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/report.py",
          "sha256": "8887d1f776e10f109c8edd7bca7ee0252e2569cf299c10ea959c11a550ac71a8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "132ec69ef2b5ec2a5d88a84e5510acd6ae9fd2670215ba08b2afe7b9e93911d2"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "ca1c253330fd2d606bb9f5429f107300a41e4b16b1d72c80d00ef760660f65a3"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "c8b5c367084d25187c68eba4fbdb05774ce6c2c977c29811001523c40e789dc4"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "844992d0ec60b49646d47d3c80a3ddb015046585a513d3d1baa7a96591fdd055"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "04abb06254ad357f0f943989fb89d3f903d72189cb4c60bb47d1d87caf73a3f9"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "chatmon/xkb.py",
          "sha256": "10a00e4c71d2b1771b2850ae5f6570b95af04433b2a6dbe4be38a7c6c86aea4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "cfe165292e0e040194480a37f954995803def534d8c07e54fdba3254386ccff6"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "57243e1b45e87b98c53e6a5999fc6457ab83cdfe4e97f43814b2a11fce5f38d7"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "ff636d3239ffef20685de7e86c6ce1a18e2753d6d7f77027349a9ff0b9c08edd"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "c313741b7009b7a1a7c7b13e4f160662aaead0c4f225d48e91b529bdf60d15a3"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "03666f40b0987e337270d8d69b303648d37ae5cf8bc3f5ccde9e3dddd91d2167"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "193614b91c1729ef801478fd6747a867920c60930a918ef2f80359736b3a9347"
        },
        {
          "path": "tests/test_imports.py",
          "sha256": "bb03d577b13589450c80feafc976ef5da20d3e86f64c69ffb4b42f2922db5033"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_macnative.py",
          "sha256": "2da102be56c933c363d0e78794907716fbabdf94f5985fd2fc2762b1f5d1f651"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "c73db48214065cfde5d4c08fa0c42054b8b7688abcaa81730c32a6f55a59746d"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_windows.py",
          "sha256": "0a605c59891ec08734d8bf5b8767d775acf4b469999e51ede48630d39f633c33"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "47e1814cbb60dc0fcc3d14155f1086156737e006722bfd60c4252dac44e299fc",
      "red": {
        "mutation": "M6B-B-desktops-words-not-shown: in chatmon/settingswin.py, '        self.hotkey_bound.setVisible(shown)' became '        self.hotkey_bound.setVisible(False)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_settings_says_how_the_desktop_has_the_hotkey_where_it_chose_its_own_words",
        "observed_diagnostic": "_ test_settings_says_how_the_desktop_has_the_hotkey_where_it_chose_its_own_words _",
        "before": [
          {
            "path": "chatmon/settingswin.py",
            "sha256": "ca1c253330fd2d606bb9f5429f107300a41e4b16b1d72c80d00ef760660f65a3"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/settingswin.py",
            "sha256": "2519d2f9b500bda591c9cb8bc8d3f655c55290be3215aa674e98525a4b711c17"
          }
        ],
        "after": [
          {
            "path": "chatmon/settingswin.py",
            "sha256": "ca1c253330fd2d606bb9f5429f107300a41e4b16b1d72c80d00ef760660f65a3"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-B-hotkey-bound-kept-private",
      "acceptance": [
        "M6B-LEFT.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_hotkey.py::test_the_apps_one_shortcut_says_how_the_desktop_has_it"
      ],
      "method": "Red drill M6B-B-hotkey-bound-kept-private through tests/drills/run.py in a temporary copy: green, chatmon/hotkey.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills-b.log",
        "sha256": "60df2298b0bd80d3cd5f9bdefdc4304e2d1854e618d65ddc63cc509dc5193f5f"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "7e16f6b335ab56d8cb0746655cc997d6746b3d1bd24330b69e6e50dd3bbb23dd"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "786f8e2aa8d1e853ee92be33dfda0e6008439151e7beaa7052dcaf98ccbdde2d"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "1974f004b3074ea41ab30b1f0fa0b9f8ad212d9ca127d22bd7839bf3f538edae"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "552dea1c3cde46bcba3f360a5cef3e1844ea7af57fdab54bec1a397312f409f0"
        },
        {
          "path": "chatmon/context.py",
          "sha256": "53bf39016325ee5a8458dcb1d540b05a8a29cfd85934d6aa06cefa01f7200dcb"
        },
        {
          "path": "chatmon/ed25519.py",
          "sha256": "cee9d926326e398c783dc261214f15fe8b5dfc99719559a7739e094c266b9cc4"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "671b6a38b502e8d0a1d5882579d5906ebfb3fc005341fb26bb8967f84fe8bd26"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "be76509122882a3805c8340eb74547e0106c5d00d337dc50376597e5a8239cd8"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "1e7e5be17c68fa9e879b99b0e24113559d1856781b810f3fc540b22d7cd32885"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "30dc957489a349a915484f480a5b4621eaf3fe945e62ca76ebcafa3763384a34"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "41d0eea4d55dbf783696e07d499d93ffff1eee968501cb7e9f0393f23a00e97c"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "be49db85d004a8ee166ce412394c122c47bf2880e52c8f0a8dcf57e0cf4c7abe"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/report.py",
          "sha256": "8887d1f776e10f109c8edd7bca7ee0252e2569cf299c10ea959c11a550ac71a8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "132ec69ef2b5ec2a5d88a84e5510acd6ae9fd2670215ba08b2afe7b9e93911d2"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "ca1c253330fd2d606bb9f5429f107300a41e4b16b1d72c80d00ef760660f65a3"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "c8b5c367084d25187c68eba4fbdb05774ce6c2c977c29811001523c40e789dc4"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "844992d0ec60b49646d47d3c80a3ddb015046585a513d3d1baa7a96591fdd055"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "04abb06254ad357f0f943989fb89d3f903d72189cb4c60bb47d1d87caf73a3f9"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "chatmon/xkb.py",
          "sha256": "10a00e4c71d2b1771b2850ae5f6570b95af04433b2a6dbe4be38a7c6c86aea4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "cfe165292e0e040194480a37f954995803def534d8c07e54fdba3254386ccff6"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "57243e1b45e87b98c53e6a5999fc6457ab83cdfe4e97f43814b2a11fce5f38d7"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "ff636d3239ffef20685de7e86c6ce1a18e2753d6d7f77027349a9ff0b9c08edd"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "c313741b7009b7a1a7c7b13e4f160662aaead0c4f225d48e91b529bdf60d15a3"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "03666f40b0987e337270d8d69b303648d37ae5cf8bc3f5ccde9e3dddd91d2167"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "193614b91c1729ef801478fd6747a867920c60930a918ef2f80359736b3a9347"
        },
        {
          "path": "tests/test_imports.py",
          "sha256": "bb03d577b13589450c80feafc976ef5da20d3e86f64c69ffb4b42f2922db5033"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_macnative.py",
          "sha256": "2da102be56c933c363d0e78794907716fbabdf94f5985fd2fc2762b1f5d1f651"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "c73db48214065cfde5d4c08fa0c42054b8b7688abcaa81730c32a6f55a59746d"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_windows.py",
          "sha256": "0a605c59891ec08734d8bf5b8767d775acf4b469999e51ede48630d39f633c33"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "47e1814cbb60dc0fcc3d14155f1086156737e006722bfd60c4252dac44e299fc",
      "red": {
        "mutation": "M6B-B-hotkey-bound-kept-private: in chatmon/hotkey.py, '    _hotkey.on_pressed, _hotkey.on_failed, _hotkey.on_bound = callback, failed, bound' became '    _hotkey.on_pressed, _hotkey.on_failed, _hotkey.on_bound = callback, failed, None'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_apps_one_shortcut_says_how_the_desktop_has_it",
        "observed_diagnostic": "___________ test_the_apps_one_shortcut_says_how_the_desktop_has_it ____________",
        "before": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "7eec2b6130eddd1e6de2b24ed7eb947ab1e986d2c00d57b259220265761f80a9"
          }
        ],
        "after": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-B-players-left-at-quit",
      "acceptance": [
        "M6B-LEFT.A3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_m7.py::test_quitting_lets_go_of_the_sound_players"
      ],
      "method": "Red drill M6B-B-players-left-at-quit through tests/drills/run.py in a temporary copy: green, chatmon/app.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills-b.log",
        "sha256": "60df2298b0bd80d3cd5f9bdefdc4304e2d1854e618d65ddc63cc509dc5193f5f"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "7e16f6b335ab56d8cb0746655cc997d6746b3d1bd24330b69e6e50dd3bbb23dd"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "786f8e2aa8d1e853ee92be33dfda0e6008439151e7beaa7052dcaf98ccbdde2d"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "1974f004b3074ea41ab30b1f0fa0b9f8ad212d9ca127d22bd7839bf3f538edae"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "552dea1c3cde46bcba3f360a5cef3e1844ea7af57fdab54bec1a397312f409f0"
        },
        {
          "path": "chatmon/context.py",
          "sha256": "53bf39016325ee5a8458dcb1d540b05a8a29cfd85934d6aa06cefa01f7200dcb"
        },
        {
          "path": "chatmon/ed25519.py",
          "sha256": "cee9d926326e398c783dc261214f15fe8b5dfc99719559a7739e094c266b9cc4"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "671b6a38b502e8d0a1d5882579d5906ebfb3fc005341fb26bb8967f84fe8bd26"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "be76509122882a3805c8340eb74547e0106c5d00d337dc50376597e5a8239cd8"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "1e7e5be17c68fa9e879b99b0e24113559d1856781b810f3fc540b22d7cd32885"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "30dc957489a349a915484f480a5b4621eaf3fe945e62ca76ebcafa3763384a34"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "41d0eea4d55dbf783696e07d499d93ffff1eee968501cb7e9f0393f23a00e97c"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "be49db85d004a8ee166ce412394c122c47bf2880e52c8f0a8dcf57e0cf4c7abe"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/report.py",
          "sha256": "8887d1f776e10f109c8edd7bca7ee0252e2569cf299c10ea959c11a550ac71a8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "132ec69ef2b5ec2a5d88a84e5510acd6ae9fd2670215ba08b2afe7b9e93911d2"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "ca1c253330fd2d606bb9f5429f107300a41e4b16b1d72c80d00ef760660f65a3"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "c8b5c367084d25187c68eba4fbdb05774ce6c2c977c29811001523c40e789dc4"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "844992d0ec60b49646d47d3c80a3ddb015046585a513d3d1baa7a96591fdd055"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "04abb06254ad357f0f943989fb89d3f903d72189cb4c60bb47d1d87caf73a3f9"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "chatmon/xkb.py",
          "sha256": "10a00e4c71d2b1771b2850ae5f6570b95af04433b2a6dbe4be38a7c6c86aea4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "cfe165292e0e040194480a37f954995803def534d8c07e54fdba3254386ccff6"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "57243e1b45e87b98c53e6a5999fc6457ab83cdfe4e97f43814b2a11fce5f38d7"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "ff636d3239ffef20685de7e86c6ce1a18e2753d6d7f77027349a9ff0b9c08edd"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "c313741b7009b7a1a7c7b13e4f160662aaead0c4f225d48e91b529bdf60d15a3"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "03666f40b0987e337270d8d69b303648d37ae5cf8bc3f5ccde9e3dddd91d2167"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "193614b91c1729ef801478fd6747a867920c60930a918ef2f80359736b3a9347"
        },
        {
          "path": "tests/test_imports.py",
          "sha256": "bb03d577b13589450c80feafc976ef5da20d3e86f64c69ffb4b42f2922db5033"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_macnative.py",
          "sha256": "2da102be56c933c363d0e78794907716fbabdf94f5985fd2fc2762b1f5d1f651"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "c73db48214065cfde5d4c08fa0c42054b8b7688abcaa81730c32a6f55a59746d"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_windows.py",
          "sha256": "0a605c59891ec08734d8bf5b8767d775acf4b469999e51ede48630d39f633c33"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "47e1814cbb60dc0fcc3d14155f1086156737e006722bfd60c4252dac44e299fc",
      "red": {
        "mutation": "M6B-B-players-left-at-quit: in chatmon/app.py, '        sound.close()  # a Linux player still sounding finishes and is reaped, never left behind' became '        pass  # a Linux player still sounding finishes and is reaped, never left behind'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_quitting_lets_go_of_the_sound_players",
        "observed_diagnostic": "_________________ test_quitting_lets_go_of_the_sound_players __________________",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "b5e6f4d971c7136dc15d23327712b5780e33e9a7f74e92ab97585e60b6abf9ae"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-B-player-not-closed",
      "acceptance": [
        "M6B-LEFT.A3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_sound.py::test_closing_waits_for_a_sound_still_playing_and_leaves_no_player_behind"
      ],
      "method": "Red drill M6B-B-player-not-closed through tests/drills/run.py in a temporary copy: green, chatmon/sound.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills-b.log",
        "sha256": "60df2298b0bd80d3cd5f9bdefdc4304e2d1854e618d65ddc63cc509dc5193f5f"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "7e16f6b335ab56d8cb0746655cc997d6746b3d1bd24330b69e6e50dd3bbb23dd"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "786f8e2aa8d1e853ee92be33dfda0e6008439151e7beaa7052dcaf98ccbdde2d"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "1974f004b3074ea41ab30b1f0fa0b9f8ad212d9ca127d22bd7839bf3f538edae"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "552dea1c3cde46bcba3f360a5cef3e1844ea7af57fdab54bec1a397312f409f0"
        },
        {
          "path": "chatmon/context.py",
          "sha256": "53bf39016325ee5a8458dcb1d540b05a8a29cfd85934d6aa06cefa01f7200dcb"
        },
        {
          "path": "chatmon/ed25519.py",
          "sha256": "cee9d926326e398c783dc261214f15fe8b5dfc99719559a7739e094c266b9cc4"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "671b6a38b502e8d0a1d5882579d5906ebfb3fc005341fb26bb8967f84fe8bd26"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "be76509122882a3805c8340eb74547e0106c5d00d337dc50376597e5a8239cd8"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "1e7e5be17c68fa9e879b99b0e24113559d1856781b810f3fc540b22d7cd32885"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "30dc957489a349a915484f480a5b4621eaf3fe945e62ca76ebcafa3763384a34"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "41d0eea4d55dbf783696e07d499d93ffff1eee968501cb7e9f0393f23a00e97c"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "be49db85d004a8ee166ce412394c122c47bf2880e52c8f0a8dcf57e0cf4c7abe"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/report.py",
          "sha256": "8887d1f776e10f109c8edd7bca7ee0252e2569cf299c10ea959c11a550ac71a8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "132ec69ef2b5ec2a5d88a84e5510acd6ae9fd2670215ba08b2afe7b9e93911d2"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "ca1c253330fd2d606bb9f5429f107300a41e4b16b1d72c80d00ef760660f65a3"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "c8b5c367084d25187c68eba4fbdb05774ce6c2c977c29811001523c40e789dc4"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "844992d0ec60b49646d47d3c80a3ddb015046585a513d3d1baa7a96591fdd055"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "04abb06254ad357f0f943989fb89d3f903d72189cb4c60bb47d1d87caf73a3f9"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "chatmon/xkb.py",
          "sha256": "10a00e4c71d2b1771b2850ae5f6570b95af04433b2a6dbe4be38a7c6c86aea4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "cfe165292e0e040194480a37f954995803def534d8c07e54fdba3254386ccff6"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "57243e1b45e87b98c53e6a5999fc6457ab83cdfe4e97f43814b2a11fce5f38d7"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "ff636d3239ffef20685de7e86c6ce1a18e2753d6d7f77027349a9ff0b9c08edd"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "c313741b7009b7a1a7c7b13e4f160662aaead0c4f225d48e91b529bdf60d15a3"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "03666f40b0987e337270d8d69b303648d37ae5cf8bc3f5ccde9e3dddd91d2167"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "193614b91c1729ef801478fd6747a867920c60930a918ef2f80359736b3a9347"
        },
        {
          "path": "tests/test_imports.py",
          "sha256": "bb03d577b13589450c80feafc976ef5da20d3e86f64c69ffb4b42f2922db5033"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_macnative.py",
          "sha256": "2da102be56c933c363d0e78794907716fbabdf94f5985fd2fc2762b1f5d1f651"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "c73db48214065cfde5d4c08fa0c42054b8b7688abcaa81730c32a6f55a59746d"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_windows.py",
          "sha256": "0a605c59891ec08734d8bf5b8767d775acf4b469999e51ede48630d39f633c33"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "47e1814cbb60dc0fcc3d14155f1086156737e006722bfd60c4252dac44e299fc",
      "red": {
        "mutation": "M6B-B-player-not-closed: in chatmon/sound.py, '            if close is not None:\\r\\n                close()' became '            if close is not None:\\r\\n                pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_closing_waits_for_a_sound_still_playing_and_leaves_no_player_behind",
        "observed_diagnostic": "__ test_closing_waits_for_a_sound_still_playing_and_leaves_no_player_behind ___",
        "before": [
          {
            "path": "chatmon/sound.py",
            "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sound.py",
            "sha256": "14c1399e45c217a13509185a831dca6348e56be127f14051c2825cc3affc0dc0"
          }
        ],
        "after": [
          {
            "path": "chatmon/sound.py",
            "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-B-unreadable-settings-hidden",
      "acceptance": [
        "M6B-03.A6"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_settings.py::test_a_state_file_that_cant_be_read_is_logged_and_started_afresh"
      ],
      "method": "Red drill M6B-B-unreadable-settings-hidden through tests/drills/run.py in a temporary copy: green, chatmon/settings.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills-b.log",
        "sha256": "60df2298b0bd80d3cd5f9bdefdc4304e2d1854e618d65ddc63cc509dc5193f5f"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "7e16f6b335ab56d8cb0746655cc997d6746b3d1bd24330b69e6e50dd3bbb23dd"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "786f8e2aa8d1e853ee92be33dfda0e6008439151e7beaa7052dcaf98ccbdde2d"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "1974f004b3074ea41ab30b1f0fa0b9f8ad212d9ca127d22bd7839bf3f538edae"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "552dea1c3cde46bcba3f360a5cef3e1844ea7af57fdab54bec1a397312f409f0"
        },
        {
          "path": "chatmon/context.py",
          "sha256": "53bf39016325ee5a8458dcb1d540b05a8a29cfd85934d6aa06cefa01f7200dcb"
        },
        {
          "path": "chatmon/ed25519.py",
          "sha256": "cee9d926326e398c783dc261214f15fe8b5dfc99719559a7739e094c266b9cc4"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "671b6a38b502e8d0a1d5882579d5906ebfb3fc005341fb26bb8967f84fe8bd26"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "be76509122882a3805c8340eb74547e0106c5d00d337dc50376597e5a8239cd8"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "1e7e5be17c68fa9e879b99b0e24113559d1856781b810f3fc540b22d7cd32885"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "30dc957489a349a915484f480a5b4621eaf3fe945e62ca76ebcafa3763384a34"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "41d0eea4d55dbf783696e07d499d93ffff1eee968501cb7e9f0393f23a00e97c"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "be49db85d004a8ee166ce412394c122c47bf2880e52c8f0a8dcf57e0cf4c7abe"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/report.py",
          "sha256": "8887d1f776e10f109c8edd7bca7ee0252e2569cf299c10ea959c11a550ac71a8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "132ec69ef2b5ec2a5d88a84e5510acd6ae9fd2670215ba08b2afe7b9e93911d2"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "ca1c253330fd2d606bb9f5429f107300a41e4b16b1d72c80d00ef760660f65a3"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "c8b5c367084d25187c68eba4fbdb05774ce6c2c977c29811001523c40e789dc4"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "844992d0ec60b49646d47d3c80a3ddb015046585a513d3d1baa7a96591fdd055"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "04abb06254ad357f0f943989fb89d3f903d72189cb4c60bb47d1d87caf73a3f9"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "chatmon/xkb.py",
          "sha256": "10a00e4c71d2b1771b2850ae5f6570b95af04433b2a6dbe4be38a7c6c86aea4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "cfe165292e0e040194480a37f954995803def534d8c07e54fdba3254386ccff6"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "ff636d3239ffef20685de7e86c6ce1a18e2753d6d7f77027349a9ff0b9c08edd"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "c313741b7009b7a1a7c7b13e4f160662aaead0c4f225d48e91b529bdf60d15a3"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "193614b91c1729ef801478fd6747a867920c60930a918ef2f80359736b3a9347"
        },
        {
          "path": "tests/test_imports.py",
          "sha256": "bb03d577b13589450c80feafc976ef5da20d3e86f64c69ffb4b42f2922db5033"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "c73db48214065cfde5d4c08fa0c42054b8b7688abcaa81730c32a6f55a59746d"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_windows.py",
          "sha256": "0a605c59891ec08734d8bf5b8767d775acf4b469999e51ede48630d39f633c33"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "791e260975da81a54071cdbddcedfeb76da3c20fee1bc5ae9853adeaebc34b7b",
      "red": {
        "mutation": "M6B-B-unreadable-settings-hidden: in chatmon/settings.py, '        logger.debug(\"couldn\\'t read %s: %s\", path, exc)' became '        pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_state_file_that_cant_be_read_is_logged_and_started_afresh",
        "observed_diagnostic": "______ test_a_state_file_that_cant_be_read_is_logged_and_started_afresh _______",
        "before": [
          {
            "path": "chatmon/settings.py",
            "sha256": "132ec69ef2b5ec2a5d88a84e5510acd6ae9fd2670215ba08b2afe7b9e93911d2"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/settings.py",
            "sha256": "8c32642b4979dfc19abd2f4af49b15254aa7c40e76bd6e00a524f31c822247ca"
          }
        ],
        "after": [
          {
            "path": "chatmon/settings.py",
            "sha256": "132ec69ef2b5ec2a5d88a84e5510acd6ae9fd2670215ba08b2afe7b9e93911d2"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-B-unclear-script-reminder-unsaid",
      "acceptance": [
        "M6B-LEFT.A4"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_app_reminders.py::test_adding_a_reminder_keeps_its_repeat_and_explains_an_unclear_time"
      ],
      "method": "Red drill M6B-B-unclear-script-reminder-unsaid through tests/drills/run.py in a temporary copy: green, chatmon/app.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills-b.log",
        "sha256": "60df2298b0bd80d3cd5f9bdefdc4304e2d1854e618d65ddc63cc509dc5193f5f"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "7e16f6b335ab56d8cb0746655cc997d6746b3d1bd24330b69e6e50dd3bbb23dd"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "786f8e2aa8d1e853ee92be33dfda0e6008439151e7beaa7052dcaf98ccbdde2d"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "1974f004b3074ea41ab30b1f0fa0b9f8ad212d9ca127d22bd7839bf3f538edae"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "552dea1c3cde46bcba3f360a5cef3e1844ea7af57fdab54bec1a397312f409f0"
        },
        {
          "path": "chatmon/context.py",
          "sha256": "53bf39016325ee5a8458dcb1d540b05a8a29cfd85934d6aa06cefa01f7200dcb"
        },
        {
          "path": "chatmon/ed25519.py",
          "sha256": "cee9d926326e398c783dc261214f15fe8b5dfc99719559a7739e094c266b9cc4"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "671b6a38b502e8d0a1d5882579d5906ebfb3fc005341fb26bb8967f84fe8bd26"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "be76509122882a3805c8340eb74547e0106c5d00d337dc50376597e5a8239cd8"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "1e7e5be17c68fa9e879b99b0e24113559d1856781b810f3fc540b22d7cd32885"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "30dc957489a349a915484f480a5b4621eaf3fe945e62ca76ebcafa3763384a34"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "41d0eea4d55dbf783696e07d499d93ffff1eee968501cb7e9f0393f23a00e97c"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "be49db85d004a8ee166ce412394c122c47bf2880e52c8f0a8dcf57e0cf4c7abe"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/report.py",
          "sha256": "8887d1f776e10f109c8edd7bca7ee0252e2569cf299c10ea959c11a550ac71a8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "132ec69ef2b5ec2a5d88a84e5510acd6ae9fd2670215ba08b2afe7b9e93911d2"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "ca1c253330fd2d606bb9f5429f107300a41e4b16b1d72c80d00ef760660f65a3"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "c8b5c367084d25187c68eba4fbdb05774ce6c2c977c29811001523c40e789dc4"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "844992d0ec60b49646d47d3c80a3ddb015046585a513d3d1baa7a96591fdd055"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "04abb06254ad357f0f943989fb89d3f903d72189cb4c60bb47d1d87caf73a3f9"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "chatmon/xkb.py",
          "sha256": "10a00e4c71d2b1771b2850ae5f6570b95af04433b2a6dbe4be38a7c6c86aea4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "cfe165292e0e040194480a37f954995803def534d8c07e54fdba3254386ccff6"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_app_m7.py",
          "sha256": "57243e1b45e87b98c53e6a5999fc6457ab83cdfe4e97f43814b2a11fce5f38d7"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "ff636d3239ffef20685de7e86c6ce1a18e2753d6d7f77027349a9ff0b9c08edd"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "c313741b7009b7a1a7c7b13e4f160662aaead0c4f225d48e91b529bdf60d15a3"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_hotkey.py",
          "sha256": "03666f40b0987e337270d8d69b303648d37ae5cf8bc3f5ccde9e3dddd91d2167"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "193614b91c1729ef801478fd6747a867920c60930a918ef2f80359736b3a9347"
        },
        {
          "path": "tests/test_imports.py",
          "sha256": "bb03d577b13589450c80feafc976ef5da20d3e86f64c69ffb4b42f2922db5033"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_macnative.py",
          "sha256": "2da102be56c933c363d0e78794907716fbabdf94f5985fd2fc2762b1f5d1f651"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "c73db48214065cfde5d4c08fa0c42054b8b7688abcaa81730c32a6f55a59746d"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_windows.py",
          "sha256": "0a605c59891ec08734d8bf5b8767d775acf4b469999e51ede48630d39f633c33"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "47e1814cbb60dc0fcc3d14155f1086156737e006722bfd60c4252dac44e299fc",
      "red": {
        "mutation": "M6B-B-unclear-script-reminder-unsaid: in chatmon/app.py, '                self.say(_(\"Reminder not set\"), reminders.explain(command), timeout_s=15, background=True)' became '                pass'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_adding_a_reminder_keeps_its_repeat_and_explains_an_unclear_time",
        "observed_diagnostic": "____ test_adding_a_reminder_keeps_its_repeat_and_explains_an_unclear_time _____",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "ab3cda2f91c04c4a216b684bd08d83a499391f8c7ff2337b63e6b772fbb91d15"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M6B-B-leak-fails-without-a-flag",
      "acceptance": [
        "M6B-RW.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_brains.py::test_a_local_servers_window_is_asked_for_and_a_redirect_never_followed"
      ],
      "method": "Red drill M6B-B-leak-fails-without-a-flag through tests/drills/run.py in a temporary copy: green, chatmon/brains.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/drills-b.log",
        "sha256": "60df2298b0bd80d3cd5f9bdefdc4304e2d1854e618d65ddc63cc509dc5193f5f"
      },
      "inputs": [
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        }
      ],
      "scope_sha256": "6c763c74141387ea7fd6e6ae978de9a9b4f7db471f7a2a4c7bdfe4d4a456a929",
      "red": {
        "mutation": "M6B-B-leak-fails-without-a-flag: in chatmon/brains.py, '        exc.close()\\r\\n        raise' became '        raise'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "PytestUnraisableExceptionWarning: Exception ignored while calling deallocator <function _TemporaryFileCloser.__del__",
        "observed_diagnostic": "E                   pytest.PytestUnraisableExceptionWarning: Exception ignored while calling deallocator <function _TemporaryFileCloser.__del__ at 0x000001AD9913D900>: None",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "9e048e3e456a183d02289e261a7d38a4b6a963339c90f7c080e288acd1e1d937"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-gate-ruff-UP",
      "acceptance": [
        "M6B-01.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m6b/gate_drills.py"
      ],
      "method": "Gate drill ruff-UP (gate_drills.py) in a temporary copy of chatmon/, packaging/, tests/ and pyproject.toml: the gate (python.exe -m ruff check --no-cache .) green, then failing on one violation and naming UP031, then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/gate-drills.log",
        "sha256": "66d114298ae4904d20b988745ce591adf9333067b2d8148a64abb2bd1010b895"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "b9566fff6d92a9ae0f274cc1a6842f22e274dbc5fae1fcb1b23e70c7b21b278d",
      "red": {
        "mutation": "ruff-UP: in chatmon/behavior.py, appended '_DRILL = \"%s\" % 1\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "UP031",
        "observed_diagnostic": "UP031 Use format specifiers instead of percent format",
        "before": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "265b50e5ac00b0a25d16433cfaea1327af51d5521d0d2f6ed82d42e442e5eae8"
          }
        ],
        "after": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-gate-ruff-C4",
      "acceptance": [
        "M6B-01.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m6b/gate_drills.py"
      ],
      "method": "Gate drill ruff-C4 (gate_drills.py) in a temporary copy of chatmon/, packaging/, tests/ and pyproject.toml: the gate (python.exe -m ruff check --no-cache .) green, then failing on one violation and naming C416, then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/gate-drills.log",
        "sha256": "66d114298ae4904d20b988745ce591adf9333067b2d8148a64abb2bd1010b895"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "b9566fff6d92a9ae0f274cc1a6842f22e274dbc5fae1fcb1b23e70c7b21b278d",
      "red": {
        "mutation": "ruff-C4: in chatmon/behavior.py, appended '_DRILL = [v for v in (1, 2)]\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "C416",
        "observed_diagnostic": "C416 Unnecessary list comprehension (rewrite using `list()`)",
        "before": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "cb0fc4d8b484ead636b352f490bdc838eebc81bbbad23119db49eaba5d9d0f5c"
          }
        ],
        "after": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-gate-ruff-PIE",
      "acceptance": [
        "M6B-01.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m6b/gate_drills.py"
      ],
      "method": "Gate drill ruff-PIE (gate_drills.py) in a temporary copy of chatmon/, packaging/, tests/ and pyproject.toml: the gate (python.exe -m ruff check --no-cache .) green, then failing on one violation and naming PIE808, then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/gate-drills.log",
        "sha256": "66d114298ae4904d20b988745ce591adf9333067b2d8148a64abb2bd1010b895"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "b9566fff6d92a9ae0f274cc1a6842f22e274dbc5fae1fcb1b23e70c7b21b278d",
      "red": {
        "mutation": "ruff-PIE: in chatmon/behavior.py, appended '_DRILL = list(range(0, 3))\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "PIE808",
        "observed_diagnostic": "PIE808 [*] Unnecessary `start` argument in `range`",
        "before": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "e081bba7902eb7b564f83819826e03c3b90639a6918539ab1f8bbfe35843bc3a"
          }
        ],
        "after": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-gate-ruff-PERF",
      "acceptance": [
        "M6B-01.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m6b/gate_drills.py"
      ],
      "method": "Gate drill ruff-PERF (gate_drills.py) in a temporary copy of chatmon/, packaging/, tests/ and pyproject.toml: the gate (python.exe -m ruff check --no-cache .) green, then failing on one violation and naming PERF401, then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/gate-drills.log",
        "sha256": "66d114298ae4904d20b988745ce591adf9333067b2d8148a64abb2bd1010b895"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "b9566fff6d92a9ae0f274cc1a6842f22e274dbc5fae1fcb1b23e70c7b21b278d",
      "red": {
        "mutation": "ruff-PERF: in chatmon/behavior.py, appended 'def _drill(items):\\n    out = []\\n    for i in items:\\n        out.append(i * 2)\\n    return out\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "PERF401",
        "observed_diagnostic": "PERF401 Use a list comprehension to create a transformed list",
        "before": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "15ab4148b4bbf07d4e2f80026629f5c031d8f4a0b6b6d360a923ded047ac5495"
          }
        ],
        "after": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-gate-ruff-RUF",
      "acceptance": [
        "M6B-01.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m6b/gate_drills.py"
      ],
      "method": "Gate drill ruff-RUF (gate_drills.py) in a temporary copy of chatmon/, packaging/, tests/ and pyproject.toml: the gate (python.exe -m ruff check --no-cache .) green, then failing on one violation and naming RUF015, then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/gate-drills.log",
        "sha256": "66d114298ae4904d20b988745ce591adf9333067b2d8148a64abb2bd1010b895"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "b9566fff6d92a9ae0f274cc1a6842f22e274dbc5fae1fcb1b23e70c7b21b278d",
      "red": {
        "mutation": "ruff-RUF: in chatmon/behavior.py, appended '_DRILL = list(range(3))[0]\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "RUF015",
        "observed_diagnostic": "RUF015 Prefer `next(iter(range(3)))` over single element slice",
        "before": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "c6c3b8e675c923947ba3bebc01b87196a998a2ce67ba5cd687a53edcd16b47d4"
          }
        ],
        "after": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-gate-ruff-S",
      "acceptance": [
        "M6B-01.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m6b/gate_drills.py"
      ],
      "method": "Gate drill ruff-S (gate_drills.py) in a temporary copy of chatmon/, packaging/, tests/ and pyproject.toml: the gate (python.exe -m ruff check --no-cache .) green, then failing on one violation and naming S307, then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/gate-drills.log",
        "sha256": "66d114298ae4904d20b988745ce591adf9333067b2d8148a64abb2bd1010b895"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "b9566fff6d92a9ae0f274cc1a6842f22e274dbc5fae1fcb1b23e70c7b21b278d",
      "red": {
        "mutation": "ruff-S: in chatmon/behavior.py, appended '_DRILL = eval(\"1\")\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "S307",
        "observed_diagnostic": "S307 Use of possibly insecure function; consider using `ast.literal_eval`",
        "before": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "7f493c2b23cfcc899fc3094cacf69a4b400ff2f3665dd53fc3a1bcc5d468c799"
          }
        ],
        "after": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-gate-ruff-DTZ",
      "acceptance": [
        "M6B-01.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m6b/gate_drills.py"
      ],
      "method": "Gate drill ruff-DTZ (gate_drills.py) in a temporary copy of chatmon/, packaging/, tests/ and pyproject.toml: the gate (python.exe -m ruff check --no-cache .) green, then failing on one violation and naming DTZ005, then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/gate-drills.log",
        "sha256": "66d114298ae4904d20b988745ce591adf9333067b2d8148a64abb2bd1010b895"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "b9566fff6d92a9ae0f274cc1a6842f22e274dbc5fae1fcb1b23e70c7b21b278d",
      "red": {
        "mutation": "ruff-DTZ: in chatmon/behavior.py, appended 'import datetime as _dt\\n\\n_DRILL = _dt.datetime.now()\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DTZ005",
        "observed_diagnostic": "DTZ005 `datetime.datetime.now()` called without a `tz` argument",
        "before": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "90e57c48cdacfe83cc3af5dcb89575107a77968600624214c76baf0b13c5acd6"
          }
        ],
        "after": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-gate-ruff-BLE",
      "acceptance": [
        "M6B-01.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m6b/gate_drills.py"
      ],
      "method": "Gate drill ruff-BLE (gate_drills.py) in a temporary copy of chatmon/, packaging/, tests/ and pyproject.toml: the gate (python.exe -m ruff check --no-cache .) green, then failing on one violation and naming BLE001, then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/gate-drills.log",
        "sha256": "66d114298ae4904d20b988745ce591adf9333067b2d8148a64abb2bd1010b895"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "b9566fff6d92a9ae0f274cc1a6842f22e274dbc5fae1fcb1b23e70c7b21b278d",
      "red": {
        "mutation": "ruff-BLE: in chatmon/behavior.py, appended 'try:\\n    _DRILL = 1\\nexcept Exception:\\n    _DRILL = 2\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "BLE001",
        "observed_diagnostic": "BLE001 Do not catch blind exception: `Exception`",
        "before": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "4deb8b188983207bc42371e1bffb7e5d478a664d771ee96345f24e026d06bb96"
          }
        ],
        "after": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-gate-ruff-C90",
      "acceptance": [
        "M6B-01.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m6b/gate_drills.py"
      ],
      "method": "Gate drill ruff-C90 (gate_drills.py) in a temporary copy of chatmon/, packaging/, tests/ and pyproject.toml: the gate (python.exe -m ruff check --no-cache .) green, then failing on one violation and naming C901, then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/gate-drills.log",
        "sha256": "66d114298ae4904d20b988745ce591adf9333067b2d8148a64abb2bd1010b895"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "b9566fff6d92a9ae0f274cc1a6842f22e274dbc5fae1fcb1b23e70c7b21b278d",
      "red": {
        "mutation": "ruff-C90: in chatmon/behavior.py, appended 'def _drill(x):\\n    if x == 0:\\n        return 0\\n    if x == 1:\\n        return 1\\n    if x == 2:\\n        return 2\\n    if x == 3:\\n        return 3\\n    if x == 4:\\n        return 4\\n    if x == 5:\\n        return 5\\n    if x == 6:\\n        return 6\\n    if x == 7:\\n        return 7\\n    if x == 8:\\n        return 8\\n    if x == 9:\\n        return 9\\n    if x == 10:\\n        return 10\\n    if x == 11:\\n        return 11\\n    if x == 12:\\n        return 12\\n    if x == 13:\\n        return 13\\n    if x == 14:\\n        return 14\\n    return -1\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "C901",
        "observed_diagnostic": "C901 `_drill` is too complex (16 > 15)",
        "before": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "ac5dc05f4075837b43edfa493d4a0a29cd08e415589892775782facb78790d8f"
          }
        ],
        "after": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-gate-ruff-S101-in-chatmon",
      "acceptance": [
        "M6B-01.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m6b/gate_drills.py"
      ],
      "method": "Gate drill ruff-S101-in-chatmon (gate_drills.py) in a temporary copy of chatmon/, packaging/, tests/ and pyproject.toml: the gate (python.exe -m ruff check --no-cache .) green, then failing on one violation and naming S101, then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/gate-drills.log",
        "sha256": "66d114298ae4904d20b988745ce591adf9333067b2d8148a64abb2bd1010b895"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "b9566fff6d92a9ae0f274cc1a6842f22e274dbc5fae1fcb1b23e70c7b21b278d",
      "red": {
        "mutation": "ruff-S101-in-chatmon: in chatmon/behavior.py, appended 'assert __name__\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "S101",
        "observed_diagnostic": "S101 Use of `assert` detected",
        "before": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "d09111de737f8c86957043b9201a4e272aa5a2f7483f4e4dc40751c7a9a99cd6"
          }
        ],
        "after": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-gate-ruff-app",
      "acceptance": [
        "M6B-01.A3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m6b/gate_drills.py"
      ],
      "method": "Gate drill ruff-app (gate_drills.py) in a temporary copy of chatmon/, packaging/, tests/ and pyproject.toml: the gate (python.exe -m ruff check --no-cache .) green, then failing on one violation and naming DTZ005, then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/gate-drills.log",
        "sha256": "66d114298ae4904d20b988745ce591adf9333067b2d8148a64abb2bd1010b895"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "7e16f6b335ab56d8cb0746655cc997d6746b3d1bd24330b69e6e50dd3bbb23dd"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "786f8e2aa8d1e853ee92be33dfda0e6008439151e7beaa7052dcaf98ccbdde2d"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "1974f004b3074ea41ab30b1f0fa0b9f8ad212d9ca127d22bd7839bf3f538edae"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "552dea1c3cde46bcba3f360a5cef3e1844ea7af57fdab54bec1a397312f409f0"
        },
        {
          "path": "chatmon/context.py",
          "sha256": "53bf39016325ee5a8458dcb1d540b05a8a29cfd85934d6aa06cefa01f7200dcb"
        },
        {
          "path": "chatmon/ed25519.py",
          "sha256": "cee9d926326e398c783dc261214f15fe8b5dfc99719559a7739e094c266b9cc4"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "671b6a38b502e8d0a1d5882579d5906ebfb3fc005341fb26bb8967f84fe8bd26"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "be76509122882a3805c8340eb74547e0106c5d00d337dc50376597e5a8239cd8"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "1e7e5be17c68fa9e879b99b0e24113559d1856781b810f3fc540b22d7cd32885"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "30dc957489a349a915484f480a5b4621eaf3fe945e62ca76ebcafa3763384a34"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "41d0eea4d55dbf783696e07d499d93ffff1eee968501cb7e9f0393f23a00e97c"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "be49db85d004a8ee166ce412394c122c47bf2880e52c8f0a8dcf57e0cf4c7abe"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/report.py",
          "sha256": "8887d1f776e10f109c8edd7bca7ee0252e2569cf299c10ea959c11a550ac71a8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "132ec69ef2b5ec2a5d88a84e5510acd6ae9fd2670215ba08b2afe7b9e93911d2"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "ca1c253330fd2d606bb9f5429f107300a41e4b16b1d72c80d00ef760660f65a3"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "c8b5c367084d25187c68eba4fbdb05774ce6c2c977c29811001523c40e789dc4"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "844992d0ec60b49646d47d3c80a3ddb015046585a513d3d1baa7a96591fdd055"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "04abb06254ad357f0f943989fb89d3f903d72189cb4c60bb47d1d87caf73a3f9"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "chatmon/xkb.py",
          "sha256": "10a00e4c71d2b1771b2850ae5f6570b95af04433b2a6dbe4be38a7c6c86aea4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "cfe165292e0e040194480a37f954995803def534d8c07e54fdba3254386ccff6"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "ff636d3239ffef20685de7e86c6ce1a18e2753d6d7f77027349a9ff0b9c08edd"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "c313741b7009b7a1a7c7b13e4f160662aaead0c4f225d48e91b529bdf60d15a3"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "193614b91c1729ef801478fd6747a867920c60930a918ef2f80359736b3a9347"
        },
        {
          "path": "tests/test_imports.py",
          "sha256": "bb03d577b13589450c80feafc976ef5da20d3e86f64c69ffb4b42f2922db5033"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "c73db48214065cfde5d4c08fa0c42054b8b7688abcaa81730c32a6f55a59746d"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_windows.py",
          "sha256": "0a605c59891ec08734d8bf5b8767d775acf4b469999e51ede48630d39f633c33"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "791e260975da81a54071cdbddcedfeb76da3c20fee1bc5ae9853adeaebc34b7b",
      "red": {
        "mutation": "ruff-app: in chatmon/app.py, appended 'import datetime as _dt\\n\\n_DRILL = _dt.datetime.now()\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DTZ005",
        "observed_diagnostic": "DTZ005 `datetime.datetime.now()` called without a `tz` argument",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "809df5ed7b4542a83b91a34acd9943d42a6726b6481a0b7b7ffbfb54c060234e"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-gate-ruff-app-test",
      "acceptance": [
        "M6B-01.A3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m6b/gate_drills.py"
      ],
      "method": "Gate drill ruff-app-test (gate_drills.py) in a temporary copy of chatmon/, packaging/, tests/ and pyproject.toml: the gate (python.exe -m ruff check --no-cache .) green, then failing on one violation and naming RUF015, then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/gate-drills.log",
        "sha256": "66d114298ae4904d20b988745ce591adf9333067b2d8148a64abb2bd1010b895"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "7e16f6b335ab56d8cb0746655cc997d6746b3d1bd24330b69e6e50dd3bbb23dd"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "786f8e2aa8d1e853ee92be33dfda0e6008439151e7beaa7052dcaf98ccbdde2d"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "1974f004b3074ea41ab30b1f0fa0b9f8ad212d9ca127d22bd7839bf3f538edae"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "552dea1c3cde46bcba3f360a5cef3e1844ea7af57fdab54bec1a397312f409f0"
        },
        {
          "path": "chatmon/context.py",
          "sha256": "53bf39016325ee5a8458dcb1d540b05a8a29cfd85934d6aa06cefa01f7200dcb"
        },
        {
          "path": "chatmon/ed25519.py",
          "sha256": "cee9d926326e398c783dc261214f15fe8b5dfc99719559a7739e094c266b9cc4"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "671b6a38b502e8d0a1d5882579d5906ebfb3fc005341fb26bb8967f84fe8bd26"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "be76509122882a3805c8340eb74547e0106c5d00d337dc50376597e5a8239cd8"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "1e7e5be17c68fa9e879b99b0e24113559d1856781b810f3fc540b22d7cd32885"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "30dc957489a349a915484f480a5b4621eaf3fe945e62ca76ebcafa3763384a34"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "41d0eea4d55dbf783696e07d499d93ffff1eee968501cb7e9f0393f23a00e97c"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "be49db85d004a8ee166ce412394c122c47bf2880e52c8f0a8dcf57e0cf4c7abe"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/report.py",
          "sha256": "8887d1f776e10f109c8edd7bca7ee0252e2569cf299c10ea959c11a550ac71a8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "132ec69ef2b5ec2a5d88a84e5510acd6ae9fd2670215ba08b2afe7b9e93911d2"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "ca1c253330fd2d606bb9f5429f107300a41e4b16b1d72c80d00ef760660f65a3"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "c8b5c367084d25187c68eba4fbdb05774ce6c2c977c29811001523c40e789dc4"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "844992d0ec60b49646d47d3c80a3ddb015046585a513d3d1baa7a96591fdd055"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "04abb06254ad357f0f943989fb89d3f903d72189cb4c60bb47d1d87caf73a3f9"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "chatmon/xkb.py",
          "sha256": "10a00e4c71d2b1771b2850ae5f6570b95af04433b2a6dbe4be38a7c6c86aea4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "cfe165292e0e040194480a37f954995803def534d8c07e54fdba3254386ccff6"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "ff636d3239ffef20685de7e86c6ce1a18e2753d6d7f77027349a9ff0b9c08edd"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "c313741b7009b7a1a7c7b13e4f160662aaead0c4f225d48e91b529bdf60d15a3"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "193614b91c1729ef801478fd6747a867920c60930a918ef2f80359736b3a9347"
        },
        {
          "path": "tests/test_imports.py",
          "sha256": "bb03d577b13589450c80feafc976ef5da20d3e86f64c69ffb4b42f2922db5033"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "c73db48214065cfde5d4c08fa0c42054b8b7688abcaa81730c32a6f55a59746d"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_windows.py",
          "sha256": "0a605c59891ec08734d8bf5b8767d775acf4b469999e51ede48630d39f633c33"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "791e260975da81a54071cdbddcedfeb76da3c20fee1bc5ae9853adeaebc34b7b",
      "red": {
        "mutation": "ruff-app-test: in tests/test_app_smoke.py, appended '_DRILL = list(range(3))[0]\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "RUF015",
        "observed_diagnostic": "RUF015 Prefer `next(iter(range(3)))` over single element slice",
        "before": [
          {
            "path": "tests/test_app_smoke.py",
            "sha256": "c313741b7009b7a1a7c7b13e4f160662aaead0c4f225d48e91b529bdf60d15a3"
          }
        ],
        "mutated": [
          {
            "path": "tests/test_app_smoke.py",
            "sha256": "cf47bf7eae911aa1ad569bdcead05dfee3524ddfdb06369cdb0c723d8dd3a534"
          }
        ],
        "after": [
          {
            "path": "tests/test_app_smoke.py",
            "sha256": "c313741b7009b7a1a7c7b13e4f160662aaead0c4f225d48e91b529bdf60d15a3"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-gate-mypy-brains",
      "acceptance": [
        "M6B-02.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m6b/gate_drills.py"
      ],
      "method": "Gate drill mypy-brains (gate_drills.py) in a temporary copy of chatmon/, packaging/, tests/ and pyproject.toml: the gate (python.exe -m mypy --platform linux --no-incremental) green, then failing on one violation and naming Incompatible types in assignment, then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/gate-drills.log",
        "sha256": "66d114298ae4904d20b988745ce591adf9333067b2d8148a64abb2bd1010b895"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "786f8e2aa8d1e853ee92be33dfda0e6008439151e7beaa7052dcaf98ccbdde2d"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/context.py",
          "sha256": "53bf39016325ee5a8458dcb1d540b05a8a29cfd85934d6aa06cefa01f7200dcb"
        },
        {
          "path": "chatmon/ed25519.py",
          "sha256": "cee9d926326e398c783dc261214f15fe8b5dfc99719559a7739e094c266b9cc4"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "671b6a38b502e8d0a1d5882579d5906ebfb3fc005341fb26bb8967f84fe8bd26"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "be76509122882a3805c8340eb74547e0106c5d00d337dc50376597e5a8239cd8"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "be49db85d004a8ee166ce412394c122c47bf2880e52c8f0a8dcf57e0cf4c7abe"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/report.py",
          "sha256": "8887d1f776e10f109c8edd7bca7ee0252e2569cf299c10ea959c11a550ac71a8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "c8b5c367084d25187c68eba4fbdb05774ce6c2c977c29811001523c40e789dc4"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "844992d0ec60b49646d47d3c80a3ddb015046585a513d3d1baa7a96591fdd055"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "04abb06254ad357f0f943989fb89d3f903d72189cb4c60bb47d1d87caf73a3f9"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "chatmon/xkb.py",
          "sha256": "10a00e4c71d2b1771b2850ae5f6570b95af04433b2a6dbe4be38a7c6c86aea4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_imports.py",
          "sha256": "bb03d577b13589450c80feafc976ef5da20d3e86f64c69ffb4b42f2922db5033"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "aa9c6d74d9193298753f401b13339d6a21b3bd46111464211f8bb0d50aa964a8",
      "red": {
        "mutation": "mypy-brains: in chatmon/brains.py, 'MAX_REPLY = 32 * 2**20' became 'MAX_REPLY: int = \"32 MB\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "Incompatible types in assignment",
        "observed_diagnostic": "chatmon\\brains.py:1159: error: Incompatible types in assignment (expression has type \"str\", variable has type \"int\")  [assignment]",
        "before": [
          {
            "path": "chatmon/brains.py",
            "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/brains.py",
            "sha256": "9da6e6fd4757ef19ba43d35ead73f29dc21c9db88b3ea0eca9313c5eb3664f99"
          }
        ],
        "after": [
          {
            "path": "chatmon/brains.py",
            "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-gate-mypy-winpipe",
      "acceptance": [
        "M6B-02.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m6b/gate_drills.py"
      ],
      "method": "Gate drill mypy-winpipe (gate_drills.py) in a temporary copy of chatmon/, packaging/, tests/ and pyproject.toml: the gate (python.exe -m mypy --platform linux --no-incremental) green, then failing on one violation and naming Incompatible types in assignment, then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/gate-drills.log",
        "sha256": "66d114298ae4904d20b988745ce591adf9333067b2d8148a64abb2bd1010b895"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "786f8e2aa8d1e853ee92be33dfda0e6008439151e7beaa7052dcaf98ccbdde2d"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/context.py",
          "sha256": "53bf39016325ee5a8458dcb1d540b05a8a29cfd85934d6aa06cefa01f7200dcb"
        },
        {
          "path": "chatmon/ed25519.py",
          "sha256": "cee9d926326e398c783dc261214f15fe8b5dfc99719559a7739e094c266b9cc4"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "671b6a38b502e8d0a1d5882579d5906ebfb3fc005341fb26bb8967f84fe8bd26"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "be76509122882a3805c8340eb74547e0106c5d00d337dc50376597e5a8239cd8"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "be49db85d004a8ee166ce412394c122c47bf2880e52c8f0a8dcf57e0cf4c7abe"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/report.py",
          "sha256": "8887d1f776e10f109c8edd7bca7ee0252e2569cf299c10ea959c11a550ac71a8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "c8b5c367084d25187c68eba4fbdb05774ce6c2c977c29811001523c40e789dc4"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "844992d0ec60b49646d47d3c80a3ddb015046585a513d3d1baa7a96591fdd055"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "04abb06254ad357f0f943989fb89d3f903d72189cb4c60bb47d1d87caf73a3f9"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "chatmon/xkb.py",
          "sha256": "10a00e4c71d2b1771b2850ae5f6570b95af04433b2a6dbe4be38a7c6c86aea4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_imports.py",
          "sha256": "bb03d577b13589450c80feafc976ef5da20d3e86f64c69ffb4b42f2922db5033"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "aa9c6d74d9193298753f401b13339d6a21b3bd46111464211f8bb0d50aa964a8",
      "red": {
        "mutation": "mypy-winpipe: in chatmon/winpipe.py, 'REPLY_MAX = 64 * 1024' became 'REPLY_MAX: int = \"64 KB\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "Incompatible types in assignment",
        "observed_diagnostic": "chatmon\\winpipe.py:50: error: Incompatible types in assignment (expression has type \"str\", variable has type \"int\")  [assignment]",
        "before": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "844992d0ec60b49646d47d3c80a3ddb015046585a513d3d1baa7a96591fdd055"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "8df2265c6af12285470bf7b1da9675d5d4b786909599b43967eb3671ccf7414b"
          }
        ],
        "after": [
          {
            "path": "chatmon/winpipe.py",
            "sha256": "844992d0ec60b49646d47d3c80a3ddb015046585a513d3d1baa7a96591fdd055"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-gate-mypy-app",
      "acceptance": [
        "M6B-02.A3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m6b/gate_drills.py"
      ],
      "method": "Gate drill mypy-app (gate_drills.py) in a temporary copy of chatmon/, packaging/, tests/ and pyproject.toml: the gate (python.exe -m mypy --platform linux --no-incremental) green, then failing on one violation and naming Incompatible types in assignment, then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/gate-drills.log",
        "sha256": "66d114298ae4904d20b988745ce591adf9333067b2d8148a64abb2bd1010b895"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "7e16f6b335ab56d8cb0746655cc997d6746b3d1bd24330b69e6e50dd3bbb23dd"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "786f8e2aa8d1e853ee92be33dfda0e6008439151e7beaa7052dcaf98ccbdde2d"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "1974f004b3074ea41ab30b1f0fa0b9f8ad212d9ca127d22bd7839bf3f538edae"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "552dea1c3cde46bcba3f360a5cef3e1844ea7af57fdab54bec1a397312f409f0"
        },
        {
          "path": "chatmon/context.py",
          "sha256": "53bf39016325ee5a8458dcb1d540b05a8a29cfd85934d6aa06cefa01f7200dcb"
        },
        {
          "path": "chatmon/ed25519.py",
          "sha256": "cee9d926326e398c783dc261214f15fe8b5dfc99719559a7739e094c266b9cc4"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "671b6a38b502e8d0a1d5882579d5906ebfb3fc005341fb26bb8967f84fe8bd26"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "be76509122882a3805c8340eb74547e0106c5d00d337dc50376597e5a8239cd8"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "1e7e5be17c68fa9e879b99b0e24113559d1856781b810f3fc540b22d7cd32885"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "30dc957489a349a915484f480a5b4621eaf3fe945e62ca76ebcafa3763384a34"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "41d0eea4d55dbf783696e07d499d93ffff1eee968501cb7e9f0393f23a00e97c"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "be49db85d004a8ee166ce412394c122c47bf2880e52c8f0a8dcf57e0cf4c7abe"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/report.py",
          "sha256": "8887d1f776e10f109c8edd7bca7ee0252e2569cf299c10ea959c11a550ac71a8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "132ec69ef2b5ec2a5d88a84e5510acd6ae9fd2670215ba08b2afe7b9e93911d2"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "ca1c253330fd2d606bb9f5429f107300a41e4b16b1d72c80d00ef760660f65a3"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "c8b5c367084d25187c68eba4fbdb05774ce6c2c977c29811001523c40e789dc4"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "844992d0ec60b49646d47d3c80a3ddb015046585a513d3d1baa7a96591fdd055"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "04abb06254ad357f0f943989fb89d3f903d72189cb4c60bb47d1d87caf73a3f9"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "chatmon/xkb.py",
          "sha256": "10a00e4c71d2b1771b2850ae5f6570b95af04433b2a6dbe4be38a7c6c86aea4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "cfe165292e0e040194480a37f954995803def534d8c07e54fdba3254386ccff6"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "ff636d3239ffef20685de7e86c6ce1a18e2753d6d7f77027349a9ff0b9c08edd"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "c313741b7009b7a1a7c7b13e4f160662aaead0c4f225d48e91b529bdf60d15a3"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "193614b91c1729ef801478fd6747a867920c60930a918ef2f80359736b3a9347"
        },
        {
          "path": "tests/test_imports.py",
          "sha256": "bb03d577b13589450c80feafc976ef5da20d3e86f64c69ffb4b42f2922db5033"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "c73db48214065cfde5d4c08fa0c42054b8b7688abcaa81730c32a6f55a59746d"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_windows.py",
          "sha256": "0a605c59891ec08734d8bf5b8767d775acf4b469999e51ede48630d39f633c33"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "791e260975da81a54071cdbddcedfeb76da3c20fee1bc5ae9853adeaebc34b7b",
      "red": {
        "mutation": "mypy-app: in chatmon/app.py, 'MAX_CONNECTIONS = 64' became 'MAX_CONNECTIONS: int = \"64\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "Incompatible types in assignment",
        "observed_diagnostic": "chatmon\\app.py:44: error: Incompatible types in assignment (expression has type \"str\", variable has type \"int\")  [assignment]",
        "before": [
          {
            "path": "chatmon/app.py",
            "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/app.py",
            "sha256": "a746c1dd11e6a32130c3c8e48fe25f366294381efc96f70ff5e95d1acf85da36"
          }
        ],
        "after": [
          {
            "path": "chatmon/app.py",
            "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-gate-mypy-menus",
      "acceptance": [
        "M6B-02.A3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m6b/gate_drills.py"
      ],
      "method": "Gate drill mypy-menus (gate_drills.py) in a temporary copy of chatmon/, packaging/, tests/ and pyproject.toml: the gate (python.exe -m mypy --platform linux --no-incremental) green, then failing on one violation and naming Incompatible types in assignment, then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6b/gate-drills.log",
        "sha256": "66d114298ae4904d20b988745ce591adf9333067b2d8148a64abb2bd1010b895"
      },
      "inputs": [
        {
          "path": "art/tools/blink-inbetween.py",
          "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
        },
        {
          "path": "art/tools/bubble-cut.py",
          "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
        },
        {
          "path": "art/tools/bubble-preview.py",
          "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
        },
        {
          "path": "art/tools/creature-cut.py",
          "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
        },
        {
          "path": "art/tools/creature-preview.py",
          "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
        },
        {
          "path": "art/tools/creature-qc.py",
          "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
        },
        {
          "path": "art/tools/loop-qc.py",
          "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
        },
        {
          "path": "art/tools/penguin-slice.py",
          "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
        },
        {
          "path": "art/tools/penguin-touchup.py",
          "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
        },
        {
          "path": "art/tools/readme_media.py",
          "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
        },
        {
          "path": "art/tools/sound-cues.py",
          "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
        },
        {
          "path": "art/tools/spritefix.py",
          "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
        },
        {
          "path": "chatmon/agents.py",
          "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
        },
        {
          "path": "chatmon/asking.py",
          "sha256": "7e16f6b335ab56d8cb0746655cc997d6746b3d1bd24330b69e6e50dd3bbb23dd"
        },
        {
          "path": "chatmon/attachments.py",
          "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
        },
        {
          "path": "chatmon/autostart.py",
          "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
        },
        {
          "path": "chatmon/backup.py",
          "sha256": "786f8e2aa8d1e853ee92be33dfda0e6008439151e7beaa7052dcaf98ccbdde2d"
        },
        {
          "path": "chatmon/behavior.py",
          "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
        },
        {
          "path": "chatmon/bubbleart.py",
          "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
        },
        {
          "path": "chatmon/chats.py",
          "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
        },
        {
          "path": "chatmon/cli.py",
          "sha256": "1974f004b3074ea41ab30b1f0fa0b9f8ad212d9ca127d22bd7839bf3f538edae"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
        },
        {
          "path": "chatmon/commands.py",
          "sha256": "552dea1c3cde46bcba3f360a5cef3e1844ea7af57fdab54bec1a397312f409f0"
        },
        {
          "path": "chatmon/context.py",
          "sha256": "53bf39016325ee5a8458dcb1d540b05a8a29cfd85934d6aa06cefa01f7200dcb"
        },
        {
          "path": "chatmon/ed25519.py",
          "sha256": "cee9d926326e398c783dc261214f15fe8b5dfc99719559a7739e094c266b9cc4"
        },
        {
          "path": "chatmon/events.py",
          "sha256": "671b6a38b502e8d0a1d5882579d5906ebfb3fc005341fb26bb8967f84fe8bd26"
        },
        {
          "path": "chatmon/heads_up.py",
          "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
        },
        {
          "path": "chatmon/libdbus.py",
          "sha256": "be76509122882a3805c8340eb74547e0106c5d00d337dc50376597e5a8239cd8"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
        },
        {
          "path": "chatmon/locale/chatmon.pot",
          "sha256": "1e7e5be17c68fa9e879b99b0e24113559d1856781b810f3fc540b22d7cd32885"
        },
        {
          "path": "chatmon/log.py",
          "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "30dc957489a349a915484f480a5b4621eaf3fe945e62ca76ebcafa3763384a34"
        },
        {
          "path": "chatmon/messages.py",
          "sha256": "41d0eea4d55dbf783696e07d499d93ffff1eee968501cb7e9f0393f23a00e97c"
        },
        {
          "path": "chatmon/offline.py",
          "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "be49db85d004a8ee166ce412394c122c47bf2880e52c8f0a8dcf57e0cf4c7abe"
        },
        {
          "path": "chatmon/paths.py",
          "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
        },
        {
          "path": "chatmon/portowner.py",
          "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
        },
        {
          "path": "chatmon/reminders.py",
          "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
        },
        {
          "path": "chatmon/report.py",
          "sha256": "8887d1f776e10f109c8edd7bca7ee0252e2569cf299c10ea959c11a550ac71a8"
        },
        {
          "path": "chatmon/richtext.py",
          "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
        },
        {
          "path": "chatmon/settings.py",
          "sha256": "132ec69ef2b5ec2a5d88a84e5510acd6ae9fd2670215ba08b2afe7b9e93911d2"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "ca1c253330fd2d606bb9f5429f107300a41e4b16b1d72c80d00ef760660f65a3"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "c8b5c367084d25187c68eba4fbdb05774ce6c2c977c29811001523c40e789dc4"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
        },
        {
          "path": "chatmon/sysnotify.py",
          "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
        },
        {
          "path": "chatmon/wayland.py",
          "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
        },
        {
          "path": "chatmon/wincaret.py",
          "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
        },
        {
          "path": "chatmon/windrop.py",
          "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
        },
        {
          "path": "chatmon/winfiles.py",
          "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
        },
        {
          "path": "chatmon/winfocus.py",
          "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
        },
        {
          "path": "chatmon/winlock.py",
          "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
        },
        {
          "path": "chatmon/winpipe.py",
          "sha256": "844992d0ec60b49646d47d3c80a3ddb015046585a513d3d1baa7a96591fdd055"
        },
        {
          "path": "chatmon/winrt.py",
          "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
        },
        {
          "path": "chatmon/wintrust.py",
          "sha256": "04abb06254ad357f0f943989fb89d3f903d72189cb4c60bb47d1d87caf73a3f9"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
        },
        {
          "path": "chatmon/xkb.py",
          "sha256": "10a00e4c71d2b1771b2850ae5f6570b95af04433b2a6dbe4be38a7c6c86aea4c"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
        },
        {
          "path": "packaging/extract_strings.py",
          "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
        },
        {
          "path": "packaging/macos/entry.py",
          "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/app_harness.py",
          "sha256": "cfe165292e0e040194480a37f954995803def534d8c07e54fdba3254386ccff6"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/ed25519_sign.py",
          "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
        },
        {
          "path": "tests/fake_secrets.py",
          "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
        },
        {
          "path": "tests/fake_shortcuts_portal.py",
          "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
        },
        {
          "path": "tests/test_agents.py",
          "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
        },
        {
          "path": "tests/test_app_reminders.py",
          "sha256": "ff636d3239ffef20685de7e86c6ce1a18e2753d6d7f77027349a9ff0b9c08edd"
        },
        {
          "path": "tests/test_app_smoke.py",
          "sha256": "c313741b7009b7a1a7c7b13e4f160662aaead0c4f225d48e91b529bdf60d15a3"
        },
        {
          "path": "tests/test_autostart.py",
          "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
        },
        {
          "path": "tests/test_backup.py",
          "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
        },
        {
          "path": "tests/test_brains.py",
          "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
        },
        {
          "path": "tests/test_bubble_styles.py",
          "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
        },
        {
          "path": "tests/test_chats.py",
          "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
        },
        {
          "path": "tests/test_companions.py",
          "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
        },
        {
          "path": "tests/test_context.py",
          "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
        },
        {
          "path": "tests/test_contrast.py",
          "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
        },
        {
          "path": "tests/test_events.py",
          "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
        },
        {
          "path": "tests/test_heads_up.py",
          "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "193614b91c1729ef801478fd6747a867920c60930a918ef2f80359736b3a9347"
        },
        {
          "path": "tests/test_imports.py",
          "sha256": "bb03d577b13589450c80feafc976ef5da20d3e86f64c69ffb4b42f2922db5033"
        },
        {
          "path": "tests/test_install_update.py",
          "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
        },
        {
          "path": "tests/test_log.py",
          "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
        },
        {
          "path": "tests/test_offline.py",
          "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
        },
        {
          "path": "tests/test_parser_properties.py",
          "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_presence.py",
          "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
        },
        {
          "path": "tests/test_releasecheck.py",
          "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
        },
        {
          "path": "tests/test_reminders.py",
          "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
        },
        {
          "path": "tests/test_rich_text.py",
          "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
        },
        {
          "path": "tests/test_settings.py",
          "sha256": "c73db48214065cfde5d4c08fa0c42054b8b7688abcaa81730c32a6f55a59746d"
        },
        {
          "path": "tests/test_sound.py",
          "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
        },
        {
          "path": "tests/test_updates.py",
          "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
        },
        {
          "path": "tests/test_windows.py",
          "sha256": "0a605c59891ec08734d8bf5b8767d775acf4b469999e51ede48630d39f633c33"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "791e260975da81a54071cdbddcedfeb76da3c20fee1bc5ae9853adeaebc34b7b",
      "red": {
        "mutation": "mypy-menus: in chatmon/menus.py, 'RECENT_CHATS = 8' became 'RECENT_CHATS: int = \"8\"'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "Incompatible types in assignment",
        "observed_diagnostic": "chatmon\\menus.py:43: error: Incompatible types in assignment (expression has type \"str\", variable has type \"int\")  [assignment]",
        "before": [
          {
            "path": "chatmon/menus.py",
            "sha256": "30dc957489a349a915484f480a5b4621eaf3fe945e62ca76ebcafa3763384a34"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/menus.py",
            "sha256": "afff691cba0beb3020df8f70588930ef940accac06facbe82fbf795a897ff3ac"
          }
        ],
        "after": [
          {
            "path": "chatmon/menus.py",
            "sha256": "30dc957489a349a915484f480a5b4621eaf3fe945e62ca76ebcafa3763384a34"
          }
        ]
      },
      "reason": null
    }
  ],
  "checkpoint": {
    "scope_sha256": "1555e7799fa08ace926224db522f1cd82524930e398dc1945ed8a7e428ba3f3d",
    "inputs": [
      {
        "path": "art/tools/blink-inbetween.py",
        "sha256": "24e7080a4fb36e3400cf6c91d385e057a933e75377dcffc9daecb18e41712b37"
      },
      {
        "path": "art/tools/bubble-cut.py",
        "sha256": "39d92f5c12dadbeba07517e4ee29c9d499ac7e889cb90b1c5653178ccdc6569c"
      },
      {
        "path": "art/tools/bubble-preview.py",
        "sha256": "11c3b94edb588b826f31137dca94c59aa95594a90b17be744f72303620f6d8f0"
      },
      {
        "path": "art/tools/creature-cut.py",
        "sha256": "d6ba5e9a8572e1696a05159b6afef5d1fc44c11cf68e79947cab555b44572bbf"
      },
      {
        "path": "art/tools/creature-preview.py",
        "sha256": "db2cccedc857ec7c2dfc5e760f523ac5af25619b4e5fe5e252ea513886395763"
      },
      {
        "path": "art/tools/creature-qc.py",
        "sha256": "524571f615bfdcaa7bf2ee4f805980185146525f394ecdcf357aa3639033f13f"
      },
      {
        "path": "art/tools/loop-qc.py",
        "sha256": "1c7cf7d5b9afd970b83b1a53f2d858a5044de92b67389dd0b0c2024da2476af3"
      },
      {
        "path": "art/tools/penguin-slice.py",
        "sha256": "b8dcc3e604b0555cd8d371e098a191cb6bad6d93c259357b197eb70f9f0ad2ba"
      },
      {
        "path": "art/tools/penguin-touchup.py",
        "sha256": "f69851a2e6c46afa4c6ff1ffb877c324343423592a8de07e1003d3139fde7b1e"
      },
      {
        "path": "art/tools/readme_media.py",
        "sha256": "fa096b6ad4a6275d15f60b8426033e17a24ee08071b2a24a3c3e8f9f6e6ebf05"
      },
      {
        "path": "art/tools/sound-cues.py",
        "sha256": "cf41434e733ab15146af849f6d1f7f2f595e0311672558515e46403d38b2dd9f"
      },
      {
        "path": "art/tools/spritefix.py",
        "sha256": "e84b8ac8b7226f559a0be3be7ac7a3f2a25d4c1e93baec9b645df35727fb4d4b"
      },
      {
        "path": "chatmon/a11y.py",
        "sha256": "f5470b248a86ec4a7569b42c3e7425bec76de65f1072f70bb5b7161758b71e12"
      },
      {
        "path": "chatmon/agents.py",
        "sha256": "c3ec9612341fbc5eb9ee1cf15dfebf0c4f9cff6134b9a8a6d520b8d852e97612"
      },
      {
        "path": "chatmon/app.py",
        "sha256": "8982f886175e09f8893a5e37f34c8d78ae1c1c9b83c6fe3f4475853900868355"
      },
      {
        "path": "chatmon/asking.py",
        "sha256": "7e16f6b335ab56d8cb0746655cc997d6746b3d1bd24330b69e6e50dd3bbb23dd"
      },
      {
        "path": "chatmon/attachments.py",
        "sha256": "55e74ae62ead9fb9f976b5730ea2de01ff4d254415cfcd40fc583f4e781d4ac7"
      },
      {
        "path": "chatmon/autostart.py",
        "sha256": "4e868a4bf0f848abff242ee99c2ab487a80e4e2e1962d5c19e0d37f23d42adfe"
      },
      {
        "path": "chatmon/backup.py",
        "sha256": "786f8e2aa8d1e853ee92be33dfda0e6008439151e7beaa7052dcaf98ccbdde2d"
      },
      {
        "path": "chatmon/behavior.py",
        "sha256": "c61055d7793d06f973273c2bb55367ec3a1a2dec27188015598cf2da14b02fe0"
      },
      {
        "path": "chatmon/brains.py",
        "sha256": "7bb0fb06c1c85207c7cdaf12eeabd437664527db8fde717a155328cfa70e356c"
      },
      {
        "path": "chatmon/bubble.py",
        "sha256": "c82d962604d14bc4544652a7aae1f7f4e35bd8bb9b5281bb7657f3d8b7e476b9"
      },
      {
        "path": "chatmon/bubbleart.py",
        "sha256": "79cadd43f3c47468792a48c03027610e0f99b8a614d6cf600a313c8fb486a9db"
      },
      {
        "path": "chatmon/changelog.py",
        "sha256": "50db0f23ea376a0f45d859b618c3928e261162f8bd2b620dd010a81131ab5fe1"
      },
      {
        "path": "chatmon/chats.py",
        "sha256": "0bb9dc11929a5958e024e2d5fac604cc8fe4c91d0b9983ad03a5d3ba080e45d1"
      },
      {
        "path": "chatmon/cli.py",
        "sha256": "1974f004b3074ea41ab30b1f0fa0b9f8ad212d9ca127d22bd7839bf3f538edae"
      },
      {
        "path": "chatmon/clickthrough.py",
        "sha256": "35d054017a137d8c4bff0146dc51ca54fe3b639271ab1dab130f9ac28cf063b0"
      },
      {
        "path": "chatmon/commands.py",
        "sha256": "552dea1c3cde46bcba3f360a5cef3e1844ea7af57fdab54bec1a397312f409f0"
      },
      {
        "path": "chatmon/context.py",
        "sha256": "53bf39016325ee5a8458dcb1d540b05a8a29cfd85934d6aa06cefa01f7200dcb"
      },
      {
        "path": "chatmon/ed25519.py",
        "sha256": "cee9d926326e398c783dc261214f15fe8b5dfc99719559a7739e094c266b9cc4"
      },
      {
        "path": "chatmon/events.py",
        "sha256": "671b6a38b502e8d0a1d5882579d5906ebfb3fc005341fb26bb8967f84fe8bd26"
      },
      {
        "path": "chatmon/heads_up.py",
        "sha256": "1129de1f9965555fed70bb8fe33307c7a75d1b6f668c4abf51226c89d398e99f"
      },
      {
        "path": "chatmon/hotkey.py",
        "sha256": "b3e835248a3c4f41998d15cc9636bc48d88e04cd091be61f8c17b2ea9e4925a9"
      },
      {
        "path": "chatmon/i18n.py",
        "sha256": "752edf74f6b9b56ff42cf6a5bb37b3527fcbed0f6d90c0d175cb0f1693065667"
      },
      {
        "path": "chatmon/keychain.py",
        "sha256": "935720c05c1c6029ce4462f8b65b9e1910f21ae55a6fcf141805252fd0cd2cca"
      },
      {
        "path": "chatmon/layer.py",
        "sha256": "8225bf635b5a29f291d218cb47dd87d727dbd252180120666fe26d2f6113cfcc"
      },
      {
        "path": "chatmon/libdbus.py",
        "sha256": "be76509122882a3805c8340eb74547e0106c5d00d337dc50376597e5a8239cd8"
      },
      {
        "path": "chatmon/linuxsession.py",
        "sha256": "19cae3f0456caf4a0b24a49f45300cbcee7f51a1d37e4b31aeb03052dc3adf60"
      },
      {
        "path": "chatmon/locale/chatmon.pot",
        "sha256": "1e7e5be17c68fa9e879b99b0e24113559d1856781b810f3fc540b22d7cd32885"
      },
      {
        "path": "chatmon/log.py",
        "sha256": "9036df5d396745a4eb3ac3ca3dd89c75dc2d981cf86c1d6ff52bff7aa6a9f54c"
      },
      {
        "path": "chatmon/macnative.py",
        "sha256": "16e517f52d77c50f8646c06bb1d65d90832616f8205f25834b9710e207c8e661"
      },
      {
        "path": "chatmon/menus.py",
        "sha256": "30dc957489a349a915484f480a5b4621eaf3fe945e62ca76ebcafa3763384a34"
      },
      {
        "path": "chatmon/messages.py",
        "sha256": "41d0eea4d55dbf783696e07d499d93ffff1eee968501cb7e9f0393f23a00e97c"
      },
      {
        "path": "chatmon/offline.py",
        "sha256": "79b537a454950b6dc678d985e8987cee0d9221e1a46b7d9f65b4245bcb37a515"
      },
      {
        "path": "chatmon/packagekit.py",
        "sha256": "be49db85d004a8ee166ce412394c122c47bf2880e52c8f0a8dcf57e0cf4c7abe"
      },
      {
        "path": "chatmon/paths.py",
        "sha256": "5202c06ca5be1c034e44f4a6390c4341c096a5346eaebf37f33b6f1591a14d60"
      },
      {
        "path": "chatmon/penguin.py",
        "sha256": "9493204ae70d1f65776e9f47f1356a7bed004d7bbe993ab93d32e2c9ffcc2f7f"
      },
      {
        "path": "chatmon/portal.py",
        "sha256": "b32ce5b6d1a7692edd97056f7e741010b0d6f913720e5a24059250a13d60b46e"
      },
      {
        "path": "chatmon/portowner.py",
        "sha256": "f98b48bd0445c3edde0eee77eca058f74ce2fad782aedfbc7d5ff596585a11ee"
      },
      {
        "path": "chatmon/presence.py",
        "sha256": "693d137057360269a54eed648b11aed5dc29164e464abec7baa60dde333e1cc8"
      },
      {
        "path": "chatmon/reminders.py",
        "sha256": "d23b616def00e4ccf52d83b2458ca3ea30bcbadeed549860408e1650a453be3a"
      },
      {
        "path": "chatmon/report.py",
        "sha256": "8887d1f776e10f109c8edd7bca7ee0252e2569cf299c10ea959c11a550ac71a8"
      },
      {
        "path": "chatmon/richtext.py",
        "sha256": "1721a173876e15b97f8feeecdec02d3a4f62d5056bb92ba9f64b2dc721525564"
      },
      {
        "path": "chatmon/settings.py",
        "sha256": "132ec69ef2b5ec2a5d88a84e5510acd6ae9fd2670215ba08b2afe7b9e93911d2"
      },
      {
        "path": "chatmon/settingswin.py",
        "sha256": "ca1c253330fd2d606bb9f5429f107300a41e4b16b1d72c80d00ef760660f65a3"
      },
      {
        "path": "chatmon/sound.py",
        "sha256": "3305a54fd329318da21f447a75552adeda28cd374c6824e00a050c8cdcc01762"
      },
      {
        "path": "chatmon/sprites.py",
        "sha256": "c8b5c367084d25187c68eba4fbdb05774ce6c2c977c29811001523c40e789dc4"
      },
      {
        "path": "chatmon/stagemenu.py",
        "sha256": "d424c68e78666eda69b02e08b62a0bd41349de8f0271a7ad576e445e91181785"
      },
      {
        "path": "chatmon/sysnotify.py",
        "sha256": "4375ff68ebe1a8e34722d25af043f9e480ad60335faf75ae6876acd06705b500"
      },
      {
        "path": "chatmon/updates.py",
        "sha256": "3b616d4b7526efbf0b9db04e113f744c5c3dd507e133dea7d29a756536c73c15"
      },
      {
        "path": "chatmon/wayland.py",
        "sha256": "26dbd06283820d2bbb880f199a9bf5a8de150d94b49aed9c02d47743b95601dc"
      },
      {
        "path": "chatmon/wincaret.py",
        "sha256": "4a4aaf06269fb483215210379c67ef1ba058e90f2daa57c78c1ceb262b54f63f"
      },
      {
        "path": "chatmon/windrop.py",
        "sha256": "184ae7aa65a29051fa9141308518ae4ed5305086749950792a0383ac0754edd4"
      },
      {
        "path": "chatmon/winfiles.py",
        "sha256": "aac1114fa6558fcb052c630e27e3673371410d7b9d7fbcd879c8b6763cd5d2a9"
      },
      {
        "path": "chatmon/winfocus.py",
        "sha256": "8b3dd22183b6936272a133dc5a1ece575857488399ffa89f1a14d6aa13ab2083"
      },
      {
        "path": "chatmon/winlock.py",
        "sha256": "a7bde057a091b90ab2b503b69751a37ddd44a4bd880b11e6e9373ad2ce9260e1"
      },
      {
        "path": "chatmon/winpipe.py",
        "sha256": "844992d0ec60b49646d47d3c80a3ddb015046585a513d3d1baa7a96591fdd055"
      },
      {
        "path": "chatmon/winrt.py",
        "sha256": "1a47ac2e8c3e49354c5480bbd72d2b545559357b145d4e4a58cddc020e00738b"
      },
      {
        "path": "chatmon/wintoast.py",
        "sha256": "ccaa31909300829b40bb9f497062b367754341b79b049f7f6b0604de4aee173f"
      },
      {
        "path": "chatmon/wintrust.py",
        "sha256": "04abb06254ad357f0f943989fb89d3f903d72189cb4c60bb47d1d87caf73a3f9"
      },
      {
        "path": "chatmon/winuia.py",
        "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
      },
      {
        "path": "chatmon/xkb.py",
        "sha256": "10a00e4c71d2b1771b2850ae5f6570b95af04433b2a6dbe4be38a7c6c86aea4c"
      },
      {
        "path": "docs/delivery/ASSESSMENT.md",
        "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
      },
      {
        "path": "docs/delivery/ROADMAP.md",
        "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
      },
      {
        "path": "docs/delivery/m6a-ci-tooling.md",
        "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
      },
      {
        "path": "docs/delivery/m8-translation.md",
        "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
      },
      {
        "path": "packaging/build.py",
        "sha256": "cec159d31989b12b832ba7eb89f1da68ee21e09f187de7d5599df792345130fd"
      },
      {
        "path": "packaging/extract_strings.py",
        "sha256": "d4d7d309c837687655263e9fd2d44dd6aa7b7d84b30364e023cceadbe94a10a5"
      },
      {
        "path": "packaging/macos/entry.py",
        "sha256": "d7d935c0eadeee0d006d9ceabf6891f7c3e53b585dc775e219a696a61327031d"
      },
      {
        "path": "pyproject.toml",
        "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
      },
      {
        "path": "tests/app_harness.py",
        "sha256": "cfe165292e0e040194480a37f954995803def534d8c07e54fdba3254386ccff6"
      },
      {
        "path": "tests/conftest.py",
        "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
      },
      {
        "path": "tests/drills/run.py",
        "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
      },
      {
        "path": "tests/ed25519_sign.py",
        "sha256": "18ea2e1291eafd03f372833b9c79d2c0d399ece82b3a8319e99ad39ca1a2abe9"
      },
      {
        "path": "tests/fake_secrets.py",
        "sha256": "adbcf00e7256e6e0b182e7875bc51bb3038a70e98d672208cd444d57946ba0ef"
      },
      {
        "path": "tests/fake_shortcuts_portal.py",
        "sha256": "293a31a106aa9cc62845f5bf0e8ed84bf1a38240d5dd81991467e3aa13b473e2"
      },
      {
        "path": "tests/test_agents.py",
        "sha256": "50c31ac8d10cebd5c780b7c171f2a43fc7298a2695bf769e29dc8eba56eac2ea"
      },
      {
        "path": "tests/test_app_m7.py",
        "sha256": "57243e1b45e87b98c53e6a5999fc6457ab83cdfe4e97f43814b2a11fce5f38d7"
      },
      {
        "path": "tests/test_app_reminders.py",
        "sha256": "ff636d3239ffef20685de7e86c6ce1a18e2753d6d7f77027349a9ff0b9c08edd"
      },
      {
        "path": "tests/test_app_smoke.py",
        "sha256": "c313741b7009b7a1a7c7b13e4f160662aaead0c4f225d48e91b529bdf60d15a3"
      },
      {
        "path": "tests/test_autostart.py",
        "sha256": "0cbbea39ce2441b4f53ec7267b6f73ff7e27c4f6fcd9fd407759c967fdf1127d"
      },
      {
        "path": "tests/test_backup.py",
        "sha256": "63a6e05f89c8d7bcdbfb247adba3d01ffa23e2c1f245e38a59839860680360a0"
      },
      {
        "path": "tests/test_behavior.py",
        "sha256": "dc64c9641707eed3fa2371f64342df3259980f36c1ad9468e87a96a7cabc09e4"
      },
      {
        "path": "tests/test_brains.py",
        "sha256": "8bf0a812d402c2596d23393d6f03cee19943a824bf165e260d6e8356cbf8c463"
      },
      {
        "path": "tests/test_bubble_styles.py",
        "sha256": "aa1b7a7592378884af14a30e7c29aada1eaa943cc6849a7d146ce351fad9c6ca"
      },
      {
        "path": "tests/test_chats.py",
        "sha256": "0c145349ddce8f6a458915828a75949911a2caa3cf4383ac2174a8eb4ea13953"
      },
      {
        "path": "tests/test_clickthrough.py",
        "sha256": "4d0b3e933354b91d5931c8f491e93c6d071382cd218c72739abe35f4c570ba51"
      },
      {
        "path": "tests/test_companions.py",
        "sha256": "d579523565960699bd9e78f5e7c276b178e78b5355d21f7d71b8964476b9abb3"
      },
      {
        "path": "tests/test_context.py",
        "sha256": "fe6a88e437e5f53ab989e655bdbef0fe09efa9aa15e9e0e15b298baf68531db1"
      },
      {
        "path": "tests/test_contrast.py",
        "sha256": "b7b5d7ab8bf28fdd1509b2f5be8c7f07daf0c57715640892af6108c5bcd23194"
      },
      {
        "path": "tests/test_events.py",
        "sha256": "994d66781b3f83141d4a6c3bdc0addfb0d0dc97081cb93eba94709bb760f9dc6"
      },
      {
        "path": "tests/test_heads_up.py",
        "sha256": "425357105681ec65683bf24285fb34177271a021929fa353444488b8a6e618bb"
      },
      {
        "path": "tests/test_hotkey.py",
        "sha256": "03666f40b0987e337270d8d69b303648d37ae5cf8bc3f5ccde9e3dddd91d2167"
      },
      {
        "path": "tests/test_i18n.py",
        "sha256": "193614b91c1729ef801478fd6747a867920c60930a918ef2f80359736b3a9347"
      },
      {
        "path": "tests/test_imports.py",
        "sha256": "bb03d577b13589450c80feafc976ef5da20d3e86f64c69ffb4b42f2922db5033"
      },
      {
        "path": "tests/test_install_update.py",
        "sha256": "98ee98a80cbf40ccf8c422ded3a4ad75f39ac3fc75190575c015313104ac4fe5"
      },
      {
        "path": "tests/test_log.py",
        "sha256": "57ce8df1feb1e79349d651e7ff7a4d907cca308da9d45b8ff0f748758316bc3c"
      },
      {
        "path": "tests/test_macnative.py",
        "sha256": "2da102be56c933c363d0e78794907716fbabdf94f5985fd2fc2762b1f5d1f651"
      },
      {
        "path": "tests/test_offline.py",
        "sha256": "77186516d8a8bf46e69168f6e04c0d8e5ff5c86b5330739efff80a044493fab7"
      },
      {
        "path": "tests/test_overlay_stage.py",
        "sha256": "81a46788dc70849454a2657fea7c4939c63cd0546b808567c8a5deee4c474be2"
      },
      {
        "path": "tests/test_parser_properties.py",
        "sha256": "0db3b0daee44ceba6a15cc20bb3266c44f3dd1f2c47c4d2c41eb467fd1bb39ef"
      },
      {
        "path": "tests/test_platform_events.py",
        "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
      },
      {
        "path": "tests/test_presence.py",
        "sha256": "a207d0c20e1de66f84585f67efb0058c6c5ca6ad5f544034d9c3996d992205a7"
      },
      {
        "path": "tests/test_releasecheck.py",
        "sha256": "a479d0f061c3ea74e9271e9521548311ddab89a7c8fcca0f08a94e96d2a27999"
      },
      {
        "path": "tests/test_reminders.py",
        "sha256": "527211438b58307dba518ca65769128cc1136ecd51a27287ab96131f39357e80"
      },
      {
        "path": "tests/test_rich_text.py",
        "sha256": "14e2cf79db133b8cf608c87258d5977d0facc925bb97c3830ccf9252385819cd"
      },
      {
        "path": "tests/test_settings.py",
        "sha256": "c73db48214065cfde5d4c08fa0c42054b8b7688abcaa81730c32a6f55a59746d"
      },
      {
        "path": "tests/test_sound.py",
        "sha256": "4c6df9e11a1769767208a7da5b203e3d4d25c2032c0de26c3a720bb58409bcbe"
      },
      {
        "path": "tests/test_sprites.py",
        "sha256": "24f144a2e149944eef57574145cfd6ed00fda5a63b5e81f6dd4c7dbe93ff7843"
      },
      {
        "path": "tests/test_stage_features.py",
        "sha256": "2cfcfdf1ecd528fa9d6c1ff88e63df63232ad1e90d3879db4dd48a5ab144cbee"
      },
      {
        "path": "tests/test_stage_timer.py",
        "sha256": "ecfe748e25cc7953e8b8f5141570992d0dede789841527ca75a109a8d17b17c0"
      },
      {
        "path": "tests/test_stagemenu.py",
        "sha256": "55356be0ebdfdbf2d898fc5da67c9ca962b8d0755e311868dcf215b8b275e356"
      },
      {
        "path": "tests/test_updates.py",
        "sha256": "190cf8e64240bd536ec025a88317ae6efe7857c23498d1915642ce3b60c6dc2b"
      },
      {
        "path": "tests/test_wayland.py",
        "sha256": "b96fd98ee481e8bab776493c465bb1ac0b4483fcd98aa52ecbc7ec0898052e8a"
      },
      {
        "path": "tests/test_windows.py",
        "sha256": "0a605c59891ec08734d8bf5b8767d775acf4b469999e51ede48630d39f633c33"
      },
      {
        "path": "tests/test_xkb.py",
        "sha256": "c06c9790c22b1a4cba6cb3015cf151d037e33b7daa3c6cdcc432ab837a04118d"
      },
      {
        "path": "tests/uia_client.py",
        "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
      }
    ],
    "environment": {
      "platform": "windows",
      "tools": {
        "PyQt6": "6.11.0",
        "Qt": "6.11.2",
        "mypy": "2.4.1",
        "pytest": "9.2.0",
        "python": "3.14.10",
        "ruff": "0.17.4"
      }
    },
    "verified_tasks": [
      "T1-ruff",
      "T2-log",
      "T3-loggers",
      "T4-mypy",
      "T5-leaks",
      "T6-phase-b",
      "T7-leftovers"
    ],
    "pending_operations": [],
    "next_action": "None in M6B: the coordinator's CI run of the feature branch (Linux xvfb, the Qt 6.4 containers, macOS) is what's left to see (integration note 1).",
    "source_revision": "1f82a772938fbe6c019aec48a30a04564e4f3fa4"
  }
}
```
