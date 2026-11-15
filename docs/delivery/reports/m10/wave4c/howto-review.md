# M10-03.A3, round three: the how-to for the next stubs, reviewed at 3586a0d (2026-11-15)

The followups worker's review is [../howto-review.md](../howto-review.md), at `d15d7a9` (2026-11-14). Its receipt went
stale because it was hashed on a CRLF checkout, and the rules and files it was bound to changed since. This review
checks, line by line, what CONTRIBUTING.md ("Lint and types") and the plan's integration note 2 tell people to do. It
checks them against 3586a0d and against the commands run there. It is a manual check: there's no behaviour of Chatmon's
to execute.

CONTRIBUTING.md's "Lint and types" section is unchanged since `d15d7a9`. The file's two later edits are to other
sections: testing's `ResourceWarning` sentence (`22ca843`) and translation's Qt packages (`f9e60d9`).

## CONTRIBUTING.md

| Line | Checked against, at 3586a0d | Verdict |
|---|---|---|
| "mypy checks every module, with nothing exempted, on each platform" | `pyproject.toml`'s `[tool.mypy]` has no `overrides` and no `ignore_errors`; [mypy-611.log](mypy-611.log): no issues in 70 files on linux, win32 and darwin; CI run 43729628408's three `types` jobs: the same | True |
| "It also passes with the next PyQt6's stubs (6.12.1)" | [mypy-6121.log](mypy-6121.log), on the tree itself. Integration note 1's changes are in it (the wayland worker's `964510f`; `wayland-files-qt6121.diff` applies in reverse), and `layer.py` and `penguin.py` pass. But one error on each platform: `chatmon/app.py:3173`, the crash fix's `widget.removeEventFilter(self)`, `Argument 1 to "removeEventFilter" of "QObject" has incompatible type "Companion"; expected "AskBox"  [arg-type]` | **False at 3586a0d**, by one line of later code, not by the how-to. M10-03.A1 records it as failing. M6A-10.A1, the review of CONTRIBUTING.md's claims, records it too. |
| "which CI doesn't lock until the release is two weeks old" | PyPI: 6.12.1 uploaded 2026-11-14, so lockable from 2026-11-28; CONTRIBUTING.md's "Dependencies" rule; [../mypy-6120.log](../mypy-6120.log): 6.12.0, the newest lockable today, doesn't parse | True |
| The five commands | Run as written by [howto-replay.sh](howto-replay.sh) in WSL Arch on a copy of 3586a0d's tracked files, nothing applied ([howto-replay.log](howto-replay.log)). Under Linux 6.18 (WSL2), Python 3.14.9 and uv 0.13.6, the compile resolves PyQt6 6.12.1, PyQt6-Qt6 6.12.0, sip 13.13.1, mypy 2.4.1 and its dependencies (10 packages), with hashes. The venv installs them `--require-hashes`. mypy then reports one error on each platform: `chatmon/app.py:3173`'s `removeEventFilter` | Work as written. They show what the tree has: at 3586a0d, one error per platform. The compile has no `--exclude-newer`, on purpose, as in the first review. |
| "a signal is declared with the pyqtSignal of chatmon/qtsignal.py … its docstring says why" | `chatmon/qtsignal.py`, unchanged. The first review's gate drill `signal-from-qtcore` ([../gate-drills.log](../gate-drills.log)) showed importing it from `PyQt6.QtCore` fails with 6.12.1. Round three's couldn't start: mypy with 6.12.1 isn't green on 3586a0d's copy ([gate-drills.log](gate-drills.log)) | True as advice |
| "a value from a static constructor … is given its type" | the first review's gate drill `constructor-untyped`: untyped, `Need type annotation for "bus"`; round three's couldn't start, as above | True as advice |
| "a parent, or another argument the stubs type as Self, gets `# type: ignore[arg-type]` with the reason" | the first review's gate drill `parent-unignored`: without it, `Argument 1 to "__init__" of "QObject" has incompatible type`. Round three's couldn't start, as above. But [mypy-6121.log](mypy-6121.log) shows the same thing on the tree: `removeEventFilter(self)` at `chatmon/app.py:3173`, an argument typed as `Self` without the ignore, fails | True: the advice is what that line needs |

## Integration note 2 (the CI entry for later)

| Point | Checked against | Verdict |
|---|---|---|
| Can't be hash-locked today under the two-week rule | unchanged since the first review: 6.12.1 is lockable from 2026-11-28, and 6.12.0 fails ([../mypy-6120.log](../mypy-6120.log)) | True; the plan's pending operation P-CI-NEXT-STUBS names the date and the owner |
| The list: PyQt6 6.12.1, psutil 7.2.2, mypy 2.4.1 | `chatmon`'s third-party imports are still PyQt6 and psutil (the crash fix adds only `weakref`, from the standard library); the replay installs the same three | Right |
| The lock command | the documented command with the list's name, as in the first review | Right; the date is "two weeks back" on the day it's made |
| The `types` job's `stubs` axis | `ci.yml`'s `types` job is unchanged since bf9d8ac: one matrix axis (`platform`), one install step from `requirements-dev.txt`, `mypy --platform "$PLATFORM"` | Fits the job as it is. Not added yet: that's the pending operation. |
| The test change | `tests/test_requirements.py`'s `LISTS` and its one-version test, unchanged | Right |

## Result

Pass for M10-03.A3, which asks that CONTRIBUTING.md say how to check a change against the next stubs, and that the plan
give the coordinator the list and the CI entry. It does both, and the commands work as written. Run on 3586a0d, they
report the one error a change brought in after the how-to was written, which is what the how-to is for. The
sentence that mypy also passes with 6.12.1's stubs is false at 3586a0d. That is recorded where it belongs: M10-03.A1
(mypy with each stubs) fails, and so does M6A-10.A1 (CONTRIBUTING.md's claims hold).

Reviewed on 3586a0d plus round three's evidence files, 2026-11-15.
