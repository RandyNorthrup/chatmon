# M10-03.A3: the how-to for the next stubs, reviewed

A line-by-line check of what CONTRIBUTING.md ("Lint and types") and the plan's integration note 2 tell people to do,
against what this work ran and what its logs show. A manual check: there's no behaviour of Chatmon's to execute.

## CONTRIBUTING.md

| Line | Checked against | Verdict |
|---|---|---|
| "mypy checks every module, with nothing exempted, on each platform" | `pyproject.toml`'s `[tool.mypy]` has no `overrides` and no `ignore_errors` (M6B removed the last); [mypy-611.log](mypy-611.log): 70 files on linux, win32 and darwin | True. It replaces a sentence that still spoke of exemptions, which M6B had removed. |
| "It also passes with the next PyQt6's stubs (6.12.1)" | [mypy-6121.log](mypy-6121.log): this branch alone has 14 errors, all in `layer.py` and `penguin.py`; [mypy-6121-wayland-copy.log](mypy-6121-wayland-copy.log) and [howto-replay.log](howto-replay.log): none once integration note 1's changes are made | True of the merged branch once note 1 is applied, which is the coordinator's step; not of this branch by itself. The note says so. |
| "which CI doesn't lock until the release is two weeks old" | PyPI: 6.12.1 uploaded 2026-11-14; CONTRIBUTING.md's "Dependencies" rule, `--exclude-newer` two weeks back; [mypy-6120.log](mypy-6120.log): 6.12.0, the newest lockable, doesn't parse | True |
| The five commands | Run as written by [howto-replay.sh](howto-replay.sh) in WSL Arch (Linux 6.18, Python 3.14.9, uv 0.13.6) on a copy of the tree with note 1's changes: the compile resolves PyQt6 6.12.1, PyQt6-Qt6 6.12.0, sip 13.13.1, mypy 2.4.1 and its five dependencies, with hashes; the venv installs them `--require-hashes`; mypy finds no issues in 70 files on each platform ([howto-replay.log](howto-replay.log)) | Work as written on Linux and macOS's shell. On Windows (Git Bash) the same with `Scripts/python.exe`, which is what this work ran ([context.log](context.log), `%TEMP%\m10-qt6121`), as the comment says; `printf` there is Git Bash's. The compile has no `--exclude-newer`, on purpose: it is the new release that's wanted. |
| "a signal is declared with the pyqtSignal of chatmon/qtsignal.py … its docstring says why" | `chatmon/qtsignal.py`; gate drill `signal-from-qtcore` ([gate-drills.log](gate-drills.log)): importing it from `PyQt6.QtCore` again fails with 6.12.1 | True |
| "a value from a static constructor … is given its type" | gate drill `constructor-untyped`: untyped, `Need type annotation for "bus"` | True |
| "a parent, or another argument the stubs type as Self, gets `# type: ignore[arg-type]` with the reason" | gate drill `parent-unignored`: without it, `Argument 1 to "__init__" of "QObject" has incompatible type` | True |

## Integration note 2 (the CI entry for later)

| Point | Checked against | Verdict |
|---|---|---|
| Can't be hash-locked today under the two-week rule | `uv pip compile` with `--exclude-newer 2026-10-31` resolves PyQt6 6.12.0, never 6.12.1 (readiness.md, D16); 6.12.0 fails ([mypy-6120.log](mypy-6120.log)) | True |
| The list: PyQt6 6.12.1, psutil 7.2.2, mypy 2.4.1 | what mypy needs to read `chatmon` (its only third-party imports are PyQt6 and psutil, checked by listing every import); the same three the replay installs, and mypy's own dependencies at the dev lock's versions but `mypy-extensions` (1.2.0, newer than the dev lock's 1.1.0, which `--exclude-newer` would settle) | Right |
| The lock command | the documented command with the list's name; tried while planning with `PyQt6>=6.12` and with 6.12.0 pinned, both under `--exclude-newer 2026-10-31`, where it resolved and locked 6.12.0 (then removed, as it can't pass) | Right; the date is "two weeks back" on the day it's made |
| The `types` job's `stubs` axis | `ci.yml`'s `types` job today: one matrix axis (`platform`), one install step from `requirements-dev.txt`, `mypy --platform "$PLATFORM"`; the axis passes the list's name through `env`, as the job already does for the platform (zizmor's template-injection rule) | Fits the job as it is; not run, as `ci.yml` is the wayland worker's |
| The test change | `tests/test_requirements.py`'s `LISTS` and its one-version test | Right: the new list must stay out of the one-version rule, since its PyQt6 differs on purpose |

Reviewed on the final tree (`d15d7a9` plus the evidence files), 2026-11-14.
