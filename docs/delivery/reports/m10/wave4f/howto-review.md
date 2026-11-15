# M10-03.A3, the final round (after M6A's section): the how-to for the next stubs, reviewed at 45a17b3 (2026-11-15)

This round's first review is [../wave4e/howto-review.md](../wave4e/howto-review.md). Its receipt went stale when M6A's
plan, an input of this one, gained its final-round section, so the review and the replay were done again. Round
three's review is [../wave4c/howto-review.md](../wave4c/howto-review.md), at 3586a0d. It passed for the how-to, and
found CONTRIBUTING.md's "It also passes with the next PyQt6's stubs" false, because of one line of the crash fix. This review checks, line by line, what
CONTRIBUTING.md ("Lint and types") and the plan's integration note 2 tell people to do. It checks them against
45a17b3 and against the commands run there. It is a manual check: there's no behaviour of Chatmon's to execute.

CONTRIBUTING.md, `ci.yml`, `pyproject.toml` and `tests/test_requirements.py` are unchanged since 3586a0d.

## CONTRIBUTING.md

| Line | Checked against, at 45a17b3 | Verdict |
|---|---|---|
| "mypy checks every module, with nothing exempted, on each platform" | `pyproject.toml`'s `[tool.mypy]` has no `overrides` and no `ignore_errors`; [mypy-611.log](mypy-611.log): no issues in 70 files on linux, win32 and darwin; CI run 43743804662's three `types` jobs: the same | True |
| "It also passes with the next PyQt6's stubs (6.12.1)" | [mypy-6121.log](mypy-6121.log): "Success: no issues found in 70 source files" on each platform, on the tree itself. The quit guard (`86e84e0`) gave `chatmon/app.py`'s `removeEventFilter(self)`, round three's one error, the `# type: ignore[arg-type]` with its reason | **True again** |
| "which CI doesn't lock until the release is two weeks old" | 6.12.1 uploaded 2026-11-14, so lockable from 2026-11-28; [../mypy-6120.log](../mypy-6120.log): 6.12.0, the newest lockable today, doesn't parse | True |
| The five commands | Run as written by [howto-replay.sh](howto-replay.sh) in WSL Arch on a copy of 45a17b3's tracked files, nothing applied ([howto-replay.log](howto-replay.log)). Under Linux 6.18 (WSL2), Python 3.14.9 and uv 0.13.6, the compile resolves PyQt6 6.12.1, PyQt6-Qt6 6.12.0, sip 13.13.1, mypy 2.4.1 and its dependencies (10 packages), with hashes. The venv installs them `--require-hashes`. mypy then finds no issues in 70 files on each platform | Work as written. The compile has no `--exclude-newer`, on purpose, as in the first review. |
| "a signal is declared with the pyqtSignal of chatmon/qtsignal.py … its docstring says why" | `chatmon/qtsignal.py`, unchanged; gate drill `signal-from-qtcore` ([gate-drills.log](gate-drills.log)): importing it from `PyQt6.QtCore` again fails with 6.12.1 | True |
| "a value from a static constructor … is given its type" | gate drill `constructor-untyped`: untyped, `Need type annotation for "bus"` | True |
| "a parent, or another argument the stubs type as Self, gets `# type: ignore[arg-type]` with the reason" | gate drill `parent-unignored`: without it, `Argument 1 to "__init__" of "QObject" has incompatible type`. The quit guard's `removeEventFilter(self)` now follows it too | True |

## Integration note 2 (the CI entry for later)

| Point | Checked against | Verdict |
|---|---|---|
| Can't be hash-locked today under the two-week rule | unchanged: 6.12.1 is lockable from 2026-11-28, and 6.12.0 fails ([../mypy-6120.log](../mypy-6120.log)) | True; the plan's pending operation P-CI-NEXT-STUBS names the date and the owner |
| The list: PyQt6 6.12.1, psutil 7.2.2, mypy 2.4.1 | `chatmon`'s third-party imports are still PyQt6 and psutil; the replay installs the same three | Right |
| The lock command | the documented command with the list's name, as in the first review | Right; the date is "two weeks back" on the day it's made |
| The `types` job's `stubs` axis | `ci.yml`'s `types` job is unchanged: one matrix axis (`platform`), one install step from `requirements-dev.txt`, `mypy --platform "$PLATFORM"` | Fits the job as it is. Not added yet: that's the pending operation. |
| The test change | `tests/test_requirements.py`'s `LISTS` and its one-version test, unchanged | Right |

## Result

Pass. CONTRIBUTING.md says how to check a change against the next stubs, and the plan gives the coordinator the list
and the CI entry. The commands work as written, and on 45a17b3 they find nothing.

Reviewed on 45a17b3 plus the final round's evidence files, 2026-11-15.
