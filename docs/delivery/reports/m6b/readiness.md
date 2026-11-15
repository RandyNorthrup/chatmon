# M6B readiness review

A review of the requirements M6B-01 to M6B-03 ([ASSESSMENT.md](../../ASSESSMENT.md#m6b-static-analysis-and-logging-every-module-after-m8)),
the unclosed resources M6A left for M6B ([m6a-ci-tooling.md, integration note 4](../../m6a-ci-tooling.md#integration-notes)),
the coordinator's wave-3 brief (phase A now, the eight files M8 is translating in phase B) and the two rules the
coordinator added during the wave (every module imports on every OS; Qt APIs newer than 6.4 are guarded). It
reviews the requirements, not the code: the receipts in the plan's ledger are what show the code works.

The findings were re-checked on `dd2e375` before anything changed, and the decisions below were taken then, in the
order the work was done (ruff first, then logging, then types). This write-up was made during the work, from the
notes and baselines kept as it went.

## The findings, re-checked on dd2e375

| Item | Assessment said | Found on dd2e375 | Verdict |
|---|---|---|---|
| M6B-01 | ruff checks only F, E9 and B | `select = ["F", "E9", "B"]`. With the new families: 3,623 findings, of which 3,187 S101 (asserts, nearly all in tests), 276 other findings in tests/, 64 in phase-A modules, 24 in M8's eight files, 44 in art/tools, 19 in docs/delivery/reports, 9 in packaging/ | Real |
| M6B-02 | most modules fail mypy | 48 of 68 modules exempt. With no exemptions: 498 errors in 46 files (linux), 463 in 41 (win32), 507 in 48 (darwin); about 125 of them in M8's eight files | Real |
| M6B-03 | 27 `print()` calls, a hand-made log, 82 of ~150 `except` blocks swallow errors | 43 `print()` calls: 31 in app.py and cli.py (phase B), 12 in phase-A modules (autostart 1, layer 4 including its debug printer, paths 3, releasecheck 4). app.py's `_log_without_a_console` writes stdout and stderr to chatmon.log only when there's no console. 258 except handlers: 219 in phase-A modules (197 that neither raise nor log), 39 in M8's files | Real; the counts grew with waves 1 and 2 |
| M6A note 4 | unclosed sockets, files and processes | 21 ResourceWarnings in the Windows run (`suite-ruff.log`): test_updates' release server, test_brains' redirect servers, an `HTTPError 302` never closed, a subprocess and a text file in the Windows tree test, and three in test_events | Real |

## Decisions

| # | Question | Decision |
|---|---|---|
| D1 | Phases | The coordinator's split: phase A is every module but `app.py`, `settingswin.py`, `cli.py`, `menus.py`, `messages.py`, `asking.py`, `commands.py` and `settings.py` (and their tests, which M8 may touch); phase B does those after M8 merges. Their per-file ignores cover every new ruff family, not only today's findings, so M8's merge can't turn ruff red before phase B. |
| D2 | RUF100 on old `# noqa: E402` comments | Ruff's E402 allows imports after `os.environ` and `sys.path` changes, so the 52 comments were unused even with E402 on. They're removed (RUF100's fix), except in `tests/app_harness.py` and `test_app_smoke.py` (phase B) and the recorded scripts below. E402 and E731 aren't added: not in the item, and enabling them would make none of the comments used. |
| D3 | Tests | S101 (asserts), S603/S607 (fixed commands), S108 (mkdtemp'd short socket folders, compared paths), S311 (test data's randomness), S314 (XML Chatmon wrote) and DTZ001/005/006 (local wall time, as the code under test uses) are per-file ignores for `tests/**`, each with its reason; everything else in tests is fixed. |
| D4 | `docs/delivery/reports/**` | Past milestones' scripts there are receipt artifacts whose bytes their ledgers bind; editing them would break those receipts. The folders with Python files (m2, m3, m4b, m6a, m7) ignore the new families; M6B's own scripts are linted. |
| D5 | DTZ in chatmon | Reminders, chats and times are the computer's local wall time by design (M5's contract): each naive `fromtimestamp`/`now` is suppressed on its line with that reason, not made aware. |
| D6 | Complexity over 15 | Four functions had an honest seam and were split (the stage's frame tick at 25, the overlay's keyboard events, the stage menu's keys, the string extractor's scan); one art tool keeps a scoped `noqa: C901`. |
| D7 | The log file | `setup()` always keeps chatmon.log once called, also when there's a console (the item: logging writes through a RotatingFileHandler), and warnings go to stderr too when there is one. Same file, same 1 MB limit and same `.old` name as app.py's log, same 0600 and `O_NOFOLLOW`. Rotation happens as a line is written rather than only at start; the result is the same bound. |
| D8 | `CHATMON_DEBUG` | Keeps the overlay switch's meaning: set to anything (even "0") turns debug on. Changing that would change behaviour. |
| D9 | Keys in logs | Two layers: code never logs keys, chat text, prompts, attachments, the clipboard or typed text (convention 5); and the log's formatter blanks provider-shaped keys and Bearer tokens, tracebacks included, should one slip into an error message. The required test drives a real failed question against a pretend provider that repeats a key of no known shape, so the brain's own scrubbing is what's tested. |
| D10 | The logger's name | `logger`: ruff's BLE001 accepts a blind except that logs with `exc_info=True` only through a name it recognises (`logger`, `log`, `_logger`; not `_log`). |
| D11 | Which handlers log | Convention 3 and 4 in the plan: an error Chatmon carries on past is logged at debug; the exception being the answer, flow control, API probing, an error that reaches the person, and routine per-item failures are left, each listed with its kind in handlers.md. "Swallowed" in the item is read this way, rather than "every except without a raise", which would log every failed `int()` of typed text. |
| D12 | Which prints stay | Terminal output meant for the person: `releasecheck.py`'s `verify-update` messages (root runs it; the installer shows its words) and, in phase B, `cli.py`. The rest become warnings with the same words. |
| D13 | Overlay debug output | Today's `CHATMON_DEBUG` overlay lines include the ask box's surrounding text and raw text-input events (commit and preedit strings): typed text. They are changed to lengths and offsets; a deliberate change, in debug-only output, for the privacy rule. |
| D14 | PyQt6 6.12's stubs | In scope: the Self-typed errors in sysnotify.py and report.py (the brief). The other 6.12-only errors (a `pyqtSignal` stub bug in every QObject with signals, Self-typed parents) are recorded for when the lock moves to 6.12; CI's mypy runs the locked 6.11. |
| D15 | `default::ResourceWarning` | The leaks are closed in phase A; the line stays until phase B has run the whole suite with it removed, since M8's files and their tests may leak. |
| D16 | Imports and Qt 6.4 | The coordinator's rules: a fresh-interpreter test imports every module on each OS CI runs; mypy can't see Qt versions, so new calls in changed lines are reviewed against Qt 6.4 and the distribution CI job is the check. |
| D17 | Concurrency | Four helpers converted disjoint sets of modules in the same worktree, each with the same brief (conventions, mypy rules, privacy rules), never touching M8's files, pyproject.toml or git; the M6B worker reviewed every diff, ran the gates and committed. |

## Failure behaviour, terminology and coverage

- Failure behaviour is specified: a log that can't be opened leaves Chatmon running (setup returns None); a full
  log starts over; a module whose platform library is missing imports and fails only when used; a handler's
  behaviour is unchanged when a log call is added.
- Terms: *phase A/B*, *hidden error* (convention 3), *left* (convention 4), *gated module* (not on mypy's list).
- Coverage: every acceptance criterion in the ledger has an owning task, behaviour checks and red drills (pytest
  drills through `tests/drills/run.py`, Linux-only ones in WSL, and ruff and mypy through `gate_drills.py`);
  phase B's three criteria are owned by the blocked task.
- Conflicts: none found between the item, the roadmap's owner decisions (no new runtime dependencies; plain-English
  comments) and M8's rule (logs are not translated).
