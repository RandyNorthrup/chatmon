# Python pins: a weekly uv check in place of Dependabot's pip updates

Evidence for branch `wave5/pins`, 2026-11-15: the check at `806bb34`, and its workflow's types job at `b85ec7e`
(`b85ec7e985cd43a8edf5cee7780c2e8925c5fe9f`), which puts `pyproject.toml` back as `main` has it. Nothing here is pushed, the workflow hasn't run on GitHub, and the M6A plan, ROADMAP.md and OUTCOME.md are untouched: P-DEPENDABOT's
outcome is bound with P-RELEASE's in one round after the release.

## Why

`.github/dependabot.yml` reached `main` with 0.10.0 (65ed989), and Dependabot's first run opened three pull requests.
The owner closed all three, each with a comment:

- **#19** (the `/` pip entry) moved PyQt6 to 6.12.0, which the `/packaging` entry ignores on purpose (its QtDBus.pyi
  stops mypy), and moved the `.in` pins without locking the `.txt` files again.
- **#20 and #21** were the same nuitka 4.3.1 → 4.3.4, opened once by each entry. Dependabot locked
  `packaging/requirements.txt` again with plain pip-compile, which dropped every macOS-only build package
  (pyinstaller, pyinstaller-hooks-contrib, altgraph, macholib, packaging, setuptools) and nuitka's
  `sys_platform == 'win32'` marker.

Dependabot can't make these locks: each is `uv pip compile --universal --generate-hashes`, and its pip support locks
with pip-compile for one platform, while its uv support covers only `uv.lock`.

## What replaced it

- **`.github/dependabot.yml`**: the github-actions entry as it was; both pip entries gone, with a comment saying why and
  where Python updates come from now. Alerts and security updates are repository settings and still come.
- **`packaging/pins.py`** (standard library, uv as a subprocess; `mypy --strict` clean on linux, win32 and darwin). For each `packaging/requirements*.in` it runs the command at the top of its `.txt` in a scratch folder, on a
  copy of the `.in` with every pin's version taken off and its marker kept, with `--exclude-newer` 14 days back (to
  the minute), and compares name==version with the current lock. Rules on the way, each fed back to uv as a
  constraint until the locks settle: the skip list (PyQt6 6.12.0, with its reason); PyQt6 and PyQt6-Qt6 on one
  release line; one version per package across the locks (`tests/test_requirements.py`); nothing moves backwards (a
  release newer than the cutoff, a security fix say, stays, and uv is told to look past the cutoff for it). The
  report is Markdown: package, now, proposed, locks, where it's pinned, what's held back and why, and the exact
  commands. `--apply` moves the `.in` pins and `pyproject.toml`'s `dev` extra, hands uv the report's versions in the
  lock it reads first, runs each changed list's header command with the cutoff, checks the lock came out as
  reported, and puts every file back if anything fails. It refuses a lock whose header isn't uv's universal one with
  hashes. Exit 0 nothing to move, 3 something can, 2 an error.
- **`packaging/requirements-pins.in` / `.txt`**: uv 0.13.6, locked with uv like the others (and moved by `pins.py`
  like the others); `tests/test_requirements.py` now checks it too.
- **`.github/workflows/pins.yml`**, `permissions: {}` at the top, two jobs, actions at ci.yml's SHAs,
  `persist-credentials: false`:
  - **pins** (schedule, Mondays 06:37 UTC, and `workflow_dispatch` only): `contents: read` and `issues: write`, 15
    minutes, one run at a time (its own concurrency group), uv installed `--require-hashes` from
    `requirements-pins.txt`. It runs `pins.py`; on 3 it opens or edits the one open issue titled "Python pins ready
    to move" that github-actions opened, on 0 it closes it, on anything else the run fails and the issue is left
    alone. `gh` with `GITHUB_TOKEN`; every expression goes through `env:`. The author is matched as
    `app/github-actions` (what `gh issue list` reports, [gh-author.log](gh-author.log)), `github-actions` and
    `github-actions[bot]`, so a gh that names the bot another way can't open a second issue.
  - **types** (pull requests, and pushes to main, touching `pins.py`, `requirements-pins.*`, `tests/test_pins.py`,
    `tests/fake_uv.py` or `pins.yml`): `contents: read`, 10 minutes, the hash-locked dev list as ci.yml installs it,
    `mypy --strict` on `pins.py` for linux, win32 and darwin, then `tests/test_pins.py` and
    `tests/test_requirements.py`.
- **`pyproject.toml`** is as `main` has it (sha256 `e80d68be…` both). 806bb34 had added `packaging/pins.py` to mypy's
  `files`; every delivery plan binds `pyproject.toml`, so that line made all thirteen plans' receipts stale, and
  b85ec7e takes it out in favour of the types job.
- **CONTRIBUTING.md**, Dependencies: what Dependabot does now, the pins workflow and `--apply`, and relocking a
  Dependabot security update with uv before merging it. Its relock example now runs in `packaging/`, as every header
  was made (a command run from the root records `packaging/` paths, which `pins.py` refuses).

## Evidence

| File | What it shows |
| --- | --- |
| [report.md](report.md), [real-run.log](real-run.log) | The real run, with uv installed hash-locked as the workflow does: **nuitka 4.3.1 → 4.3.4** in requirements.txt, nothing else; PyQt6 6.12.0 held by the skip. Exit 3. packaging/ untouched. |
| [apply-scratch.log](apply-scratch.log) | `--apply` for real at that cutoff, in a scratch copy of 806bb34 (not the branch): the nuitka pin and lock line move (hash `e98e0c9a…`, the file Dependabot had), the header gains the cutoff, the macOS packages and the win32 marker stay; `test_requirements.py` passes on it; a second check finds nothing. |
| [skip-check.log](skip-check.log) | Against PyPI at the same cutoff: without the skip uv takes PyQt6 6.12.0 with Qt 6.12.0; with it, 6.11.0 with 6.11.2. 6.12.1 was uploaded 2026-11-14T14:52Z, so the check proposes it from 2026-11-28. |
| [tests.log](tests.log) | The types job's test step at b85ec7e: `tests/test_pins.py` (22 passed, the opt-in one skipped) and `tests/test_requirements.py` (6 passed), by name, on Windows with Python 3.14. |
| [tests-py311.log](tests-py311.log), [tests-linux.log](tests-linux.log) | The same 28 passing at 806bb34 on Python 3.11.16 (CI's oldest leg) and on Linux (WSL Arch, Python 3.14.9). |
| [network-test.log](network-test.log) | The opt-in test (`CHATMON_PINS_NETWORK=1`) with the real uv 0.13.6 on the real lists: passed. |
| [suite-windows.log](suite-windows.log) | The whole suite on Windows at 806bb34: **1281 passed, 180 skipped**, exit 0. The skips are other platforms' tests and opt-ins, the new real-uv test among them. (b85ec7e changes only mypy's `files` and pins.yml, which no test reads.) |
| [drill-spec.json](drill-spec.json), [drills.log](drills.log), [drills-results.json](drills-results.json) | Nine red drills with `tests/drills/run.py`, each green, red, green, on `packaging/pins.py` at sha256 `0557011e…`. |
| [lint.log](lint.log) | At b85ec7e: `ruff check .`; mypy on linux, win32 and darwin as `pyproject.toml` has it (70 files); `mypy --strict` on pins.py on each, as the types job runs it. |
| [types_drill.sh](types_drill.sh), [types-drill.log](types-drill.log) | The types job's own mypy step, read out of pins.yml and run on a copy of b85ec7e: green; red with `release_line` handing back a str for an int (an error on each of linux, win32 and darwin, exit 1); green again, pins.py's bytes put back (sha256 checked). |
| [gh-author.log](gh-author.log) | Read-only queries of a public repository's existing github-actions issues: `gh issue list --json author` gives `app/github-actions`, gh's REST search `github-actions[bot]`; pins.yml's filter finds an existing title and nothing for a missing one. |
| [workflow-lint.log](workflow-lint.log) | At b85ec7e: actionlint 1.7.12 (ci.yml's tarball and SHA-256) with shellcheck 0.11.0 on Linux, and `zizmor --no-online-audits`: no findings. Then each gate fails on a mutated copy of pins.yml (an inlined expression, persist-credentials dropped, an unquoted variable). dependabot.yml validates against SchemaStore's schema. |

### The drills

| Drill | The defect | Caught by |
| --- | --- | --- |
| PINS-skip | PyQt6 6.12.0's skip removed | `test_the_skip_list_holds_pyqt6_6_12_0_back_and_says_why`: PyQt6 6.11.0 → 6.12.0 |
| PINS-qt-group | The Qt group rule dropped | `test_pyqt6_and_its_qt_stay_on_one_release_line`: PyQt6-Qt6 6.11.2 → 6.12.0 beside PyQt6 6.11.0 |
| PINS-universal | `--apply` runs without `--universal` | `test_apply_moves_the_pins_and_locks_each_list_with_its_own_command`: the one-platform lock drops comtypes (win32), and `--apply` refuses it |
| PINS-cooldown | COOLDOWN of 0 days | `test_each_pin_moves_to_its_newest_release_two_weeks_old` (nuitka → 4.3.5, a week old) and `test_the_cutoff_is_fourteen_days_back` |
| PINS-cutoff-to-uv | `--exclude-newer` never passed to uv | `test_each_pin_moves_to_its_newest_release_two_weeks_old`: nuitka → 4.3.5 |
| PINS-backwards | The never-backwards rule dropped | `test_nothing_moves_backwards`: nuitka 4.3.5 → 4.3.4 |
| PINS-one-version | One version per package dropped | `test_a_package_in_more_than_one_lock_stays_at_one_version`: psutil 7.3.0 in the 3.14 lock only |
| PINS-dev-extra | `--apply` leaves the dev extra behind | the apply test and `test_after_apply_the_lists_agree_as_tests_test_requirements_wants` |
| PINS-seed | `--apply` doesn't hand uv the report's versions | the apply test: uv read the old lock's versions |

The logs are as the tools wrote them, with Windows' CRLF line endings turned into LF.

## Bindings

Files at b85ec7e, by sha256 (all but pins.yml and pyproject.toml as they were at 806bb34):

```
0557011eb8534ed39cd657126fc29ceb3a231b410821708f8768eaa532ddb0b1  packaging/pins.py
a6d28fc8e0fa3155db7b7fc7c0f73f8e3d8ebb81ed06079960104afacb9aead5  tests/test_pins.py
71a73820d4b91b8f5ed9ef91fa838c765ed94e3df2842dfc4c63042458180855  tests/fake_uv.py
bc5e1f69851046a72af16bbc79b57db6bdcb9c73148fae046460ddadee7818fe  .github/workflows/pins.yml   (806bb34: f7a59957…)
e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3  pyproject.toml   (as main's 65ed989)
96f643aa73236b66d327478fa2c1bd75be8774975fb2f2ef59dbd6d0d7b80b42  .github/dependabot.yml
01b5e91201bcf4e6188d793beab7b79fef6961475b67b00cb4f650aead4efe76  packaging/requirements-pins.in
57f69d75ff9012b7ce057abe9bbf3052a44829094f0e3869930e9e4e3bdb1b7e  packaging/requirements-pins.txt
```

## Left for later

- **The workflow's first runs on GitHub.** The report job runs from `main` only (schedule and `workflow_dispatch`),
  so its first run is a pending operation after the merge, like Dependabot's own first run was. The types job first
  runs on the pull request that brings this branch to `main`.
- **Applying nuitka 4.3.4** to the branch: a separate decision after the release (`python packaging/pins.py --apply
  --cutoff 2026-11-01T20:47:00Z` reproduces this report).
- **Binding** P-DEPENDABOT's outcome in `docs/delivery/m6a-ci-tooling.md`, ROADMAP.md and OUTCOME.md, in the round
  after the release.
- The local venv's ruff is 0.17.4; CI's is 0.17.3 (requirements-dev.txt). Both pass.
