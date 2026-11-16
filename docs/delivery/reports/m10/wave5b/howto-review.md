# M10-03.A3, the plans round for v0.10.0, bound again at 56caddd: the how-to for the next stubs (2026-11-15)

This round's first review is [../wave5/howto-review.md](../wave5/howto-review.md), at 7816159. It failed because
CONTRIBUTING.md's "It also passes with the next PyQt6's stubs (6.12.1)" was false: two lines of PR #22's
`chatmon/layer.py`, `app = QGuiApplication.instance()`, lacked the second workaround. The coordinator's df3e93c gives
both lines their type (`app: QCoreApplication | None = QGuiApplication.instance()`) and adds a row to CONTRIBUTING.md's
opt-in table. 56caddd changes a test only. CONTRIBUTING.md's "Lint and types" section, `ci.yml`, `pyproject.toml`
and `tests/test_requirements.py` are as at 7816159. This review checks, line by line, what that section and the plan's
integration note 2 tell people to do, against 56caddd and the commands run there. It is a manual check: there's no
behaviour of Chatmon's to execute.

## CONTRIBUTING.md

| Line | Checked against, at 56caddd | Verdict |
|---|---|---|
| "mypy checks every module, with nothing exempted, on each platform" | `[tool.mypy]` has no `overrides` and no `ignore_errors`; [mypy-611.log](mypy-611.log): no issues in 70 files on linux, win32 and darwin; PR #24's CI run 43794815103's three `types` jobs: the same | True |
| "It also passes with the next PyQt6's stubs (6.12.1)" | [mypy-6121.log](mypy-6121.log): "Success: no issues found in 70 source files" on each platform, on the tree itself, `layer.py`'s two typed lines included | **True again** |
| "which CI doesn't lock until the release is two weeks old" | 6.12.1 was uploaded 2026-11-14, so it is lockable from 2026-11-28; the pins check proposes it from that day ([../../m6a/pins/skip-check.log](../../m6a/pins/skip-check.log)). 6.12.0 doesn't parse ([../mypy-6120.log](../mypy-6120.log)). | True |
| The five commands | [howto-replay.sh](howto-replay.sh) ran them as written in WSL Arch on a copy of 56caddd's tracked files, nothing applied ([howto-replay.log](howto-replay.log)). With uv 0.13.6, the compile resolves PyQt6 6.12.1, PyQt6-Qt6 6.12.0, sip 13.13.1, mypy 2.4.1 and their dependencies, with hashes. The venv installs them `--require-hashes`, and mypy finds no issues in 70 files on each platform. | Work as written. The compile has no `--exclude-newer`, on purpose, as in earlier reviews. |
| "a signal is declared with the pyqtSignal of chatmon/qtsignal.py … its docstring says why" | `chatmon/qtsignal.py`, unchanged; gate drill `signal-from-qtcore` ([gate-drills.log](gate-drills.log)): importing it from `PyQt6.QtCore` again fails with 6.12.1 | True |
| "a value from a static constructor … is given its type" | gate drill `constructor-untyped`: untyped, `Need type annotation for "bus"`; and since df3e93c, `layer.py:824` and `:917` follow it | True |
| "a parent, or another argument the stubs type as Self, gets `# type: ignore[arg-type]` with the reason" | gate drill `parent-unignored`: without it, `Argument 1 to "__init__" of "QObject" has incompatible type` | True |

## Integration note 2 (the CI entry for later)

As in the first review: it can't be hash-locked before 2026-11-28 (P-CI-NEXT-STUBS names the date and the owner).
The list (PyQt6 6.12.1, psutil 7.2.2, mypy 2.4.1), the lock command and the `types` job's `stubs` axis fit the files
as they are. `tests/test_requirements.py`'s `LISTS` has `requirements-pins.txt` beside the others, and
`requirements-types-next.txt` would go there too. That CI check is the one that would have caught `layer.py`'s two
lines before a person did.

## Integration note 4 (the upstream report)

Posted, as recorded in the first binding ([../wave5/stub-report.log](../wave5/stub-report.log)): it waits on
Riverbank. Not a criterion.

## Result

Pass. CONTRIBUTING.md says how to check a change against the next stubs, and the plan gives the coordinator the list
and the CI entry. The commands work as written, and on 56caddd they find nothing.

Reviewed on 56caddd plus this round's evidence files, 2026-11-15.
