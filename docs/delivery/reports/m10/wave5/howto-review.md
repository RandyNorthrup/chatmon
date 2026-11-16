# M10-03.A3, the plans round for v0.10.0: the how-to for the next stubs, reviewed at 7816159 (2026-11-15)

The final round's review is [../wave4f/howto-review.md](../wave4f/howto-review.md) (at 45a17b3, pass). Its receipt
went stale because files this plan binds changed with PR #22, and the plans it takes as inputs were re-bound. This
review checks, line by line, what CONTRIBUTING.md ("Lint and types") and the plan's integration note 2 tell people to
do. It checks them against 7816159 and against the commands run there. It is a manual check: there's no behaviour of
Chatmon's to execute.

What changed since 45a17b3, as it bears on this:

- CONTRIBUTING.md's "Lint and types" section is unchanged; PR #22 changed only its Dependencies section.
- `ci.yml` and `pyproject.toml` are unchanged.
- `tests/test_requirements.py`'s `LISTS` gains `requirements-pins.txt`, the pins check's uv lock.
- The new code in `chatmon/` (`a11y.py`, `bubble.py`, `cli.py`, `clickthrough.py`, `layer.py`, `macnative.py`,
  `penguin.py`) is what the stubs now have to check.

## CONTRIBUTING.md

| Line | Checked against, at 7816159 | Verdict |
|---|---|---|
| "mypy checks every module, with nothing exempted, on each platform" | `pyproject.toml`'s `[tool.mypy]` has no `overrides` and no `ignore_errors`. [mypy-611.log](mypy-611.log): no issues in 70 files on linux, win32 and darwin. main's CI run 43778643147's three `types` jobs: the same. | True |
| "It also passes with the next PyQt6's stubs (6.12.1)" | [mypy-6121.log](mypy-6121.log) and the replay below: two errors on each platform, `chatmon/layer.py:824: error: Need type annotation for "app"  [var-annotated]` and `:917` the same. Both lines are `app = QGuiApplication.instance()` in PR #22's KWin and Hyprland fixes (6f7dd3f). 6.12.1's stubs type the static `instance()` as returning `Self`, the case of the second workaround below, and these lines don't have it. | **False at 7816159** |
| "which CI doesn't lock until the release is two weeks old" | 6.12.1 was uploaded 2026-11-14, so it is lockable from 2026-11-28; the pins check proposes it from that day ([../../m6a/pins/skip-check.log](../../m6a/pins/skip-check.log)). 6.12.0, lockable today, doesn't parse ([../mypy-6120.log](../mypy-6120.log)). | True |
| The five commands | [howto-replay.sh](howto-replay.sh) ran them as written in WSL Arch, on a copy of 7816159's tracked files, nothing applied ([howto-replay.log](howto-replay.log)). The compile resolves PyQt6 6.12.1 and mypy 2.4.1 with hashes, and the venv installs them `--require-hashes`. Then mypy finds the two errors above on each platform, and the script exits 1. | The commands work as written. What they find is the failure above. |
| "a signal is declared with the pyqtSignal of chatmon/qtsignal.py … its docstring says why" | `chatmon/qtsignal.py` is unchanged. Its gate drill couldn't run: its first step, mypy green with 6.12.1's stubs, fails on `layer.py` ([gate-drills.log](gate-drills.log)). | True as an instruction; its drill waits for the fix |
| "a value from a static constructor … is given its type" | `layer.py:824` and `:917` are exactly where this applies and isn't done | True as an instruction; PR #22's two lines don't follow it |
| "a parent, or another argument the stubs type as Self, gets `# type: ignore[arg-type]` with the reason" | Unchanged. Its gate drill waits for the fix, as above. | True as an instruction |

## Integration note 2 (the CI entry for later)

| Point | Checked against | Verdict |
|---|---|---|
| Can't be hash-locked today under the two-week rule | Unchanged: 6.12.1 is lockable from 2026-11-28, and 6.12.0 fails. | True. The plan's pending operation P-CI-NEXT-STUBS names the date and the owner. It is the check that would have caught these two lines in CI. |
| The list: PyQt6 6.12.1, psutil 7.2.2, mypy 2.4.1 | `chatmon`'s third-party imports are still PyQt6 and psutil; the replay installs the same three | Right |
| The lock command | the documented command with the list's name | Right. The date is "two weeks back" on the day it's made, and the lock is made in `packaging/`, as CONTRIBUTING.md now says. |
| The `types` job's `stubs` axis | `ci.yml`'s `types` job is unchanged: one matrix axis (`platform`), one install step from `requirements-dev.txt`, `mypy --platform "$PLATFORM"` | Fits the job as it is. Not added yet: that's the pending operation. |
| The test change | `tests/test_requirements.py`'s `LISTS` now has `requirements-pins.txt` too. Adding `requirements-types-next.txt` beside it, and its one-version test, is as the note says. | Right |

## Integration note 4 (the upstream report)

Posted. [stub-report.log](stub-report.log) has the three archive pages, read again here without addresses. The
owner's follow-up of 2026-11-16 (046579) carries the plan's own findings, as mypy `--strict` shows them. It waits on
Riverbank. Not a criterion.

## Result

**Fail**, on the same sentence as round three. The how-to and note 2 are right, and the commands work as written. On
7816159 they find two errors, in lines PR #22 added without the plan's own workaround. The fix is in the code, which
this round doesn't change.

Next: the coordinator gives `app` its type at `chatmon/layer.py:824` and `:917`
(`app: QCoreApplication | None = QGuiApplication.instance()`). Then this review, mypy_runs.py with the 6.12.1 venv
and the gate drills run again.

Reviewed on 7816159 plus this round's evidence files, 2026-11-15.
