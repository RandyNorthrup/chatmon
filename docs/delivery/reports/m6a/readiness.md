# M6A readiness review

A review of the requirements, not of code: are items M6A-01..M6A-15 (less M6A-14) clear, consistent, in scope and
coverable, as the assessment states them and as the roadmap constrains them? Done on `4fdf790`, before any M6A
change was relied on. Inputs: [ASSESSMENT.md](../../ASSESSMENT.md) (M6A section), [ROADMAP.md](../../ROADMAP.md)
(owner decisions, file ownership, rules), the coordinator's brief and resume message, `pyproject.toml`, both
workflows, and the other milestones' plans' notes addressed to M6A (M1A notes 1, 2 and 7; M1B note 14; M5's
"Package data and test dependencies").

## Findings re-checked

[findings-recheck.log](findings-recheck.log) shows each finding on `4fdf790` from `git show`. All are real:

| Item | On 4fdf790 |
|---|---|
| M6A-01 | `ci.yml` uses `actions/checkout@v7` and `setup-python@v7` (tags), no `persist-credentials`, `timeout-minutes` only on `gnome`, no concurrency, `push:` on every branch, `pip install PyQt6 psutil pytest` and `ruff` unpinned, plain `pytest -q`, no Wayland packages. |
| M6A-02 | no `.github/dependabot.yml`. |
| M6A-03 ✓ | only `gnome-session.sh` uses a distribution's PyQt6, for one GNOME test. |
| M6A-04 | nothing measures coverage. |
| M6A-05 | Python 3.11 and 3.15 only; no Arm runner; Qt unpinned. |
| M6A-06 | `requirements.txt` has no hashes; `pip install build==1.6.1` and `-r requirements.txt` without `--require-hashes`; the isolated build fetches whatever `setuptools>=77` is newest; no `SOURCE_DATE_EPOCH`. |
| M6A-07 | `on: release: types: [published]`, then `gh release upload` at the end; no attestation. |
| M6A-08 | no such test, no `twine check`; `chatmon/sounds/*.wav` (7) and `chatmon/phrases/en.json` are tracked but taken by no glob, so today's wheel would lack them. |
| M6A-09 | `penguin-companion = "chatmon.cli:main"` and the root script, both "kept for one release" since 0.3.0. |
| M6A-10 | no `SECURITY.md` or `CONTRIBUTING.md`; `config.yml` links only the README; extras `battery` and `test = ["pytest"]`. |
| M6A-11 | the test runs the real search and passes on any non-zero exit. 10 s here (the assessment saw 19 s). |
| M6A-12 | neither actionlint nor zizmor runs. Locally zizmor finds 5 unpinned actions and 3 persisted credentials in `ci.yml`. |
| M6A-13 | no mypy configuration. [mypy-baseline.log](mypy-baseline.log): default settings, Python 3.11, errors in 38 files on Linux, 34 on Windows, 40 on macOS; 16 modules pass on all three. |
| M6A-15 | test jobs check out everything; `art/` is 90 MB and `docs/` 6.7 MB, and no test reads either (the drill harness already copies without them). |

Found while re-checking, outside the assessment: **the release-blocking key check.** `packages.yml`'s `checksums`
job sparse-checks-out `chatmon/updates.py` and greps it for the release key's public half. M1A moved
`RELEASE_KEYS` to `chatmon/releasecheck.py` (`updates.py` now says `RELEASE_KEYS = releasecheck.RELEASE_KEYS`),
so the next release's `checksums` job would stop with "RELEASE_SIGNING_KEY isn't a key in RELEASE_KEYS". It
becomes requirement M6A-I1, with M1A's request to run `test-install-update.sh` in the Linux job.

## Decisions on gaps and conflicts

1. **Pushes only on main vs. the owner's "push the branch so CI tests all three OSes".** M6A-01 says pushes run
   only on main. The roadmap's git decision has the coordinator push `improve/assessment-fixes` for CI. Both hold
   with `workflow_dispatch`: after this merges, a branch push no longer starts CI by itself, and the coordinator
   starts it with `gh workflow run ci.yml --ref improve/assessment-fixes` (or opens the PR as a draft). This is the
   first integration note, since it changes the coordinator's loop.
2. **"The 17 clean modules."** 16 modules pass on all three platforms on `4fdf790`; the assessment counted Linux
   only, on fewer modules. Platform legs need the union, so 16 are gated, recorded as provisional and re-checked at
   merge (other workers are changing modules now).
3. **`filterwarnings = error` and ResourceWarning.** On `4fdf790` every warning-as-error failure (5 failed, 15
   errors) is a `ResourceWarning` reported by the garbage collector in an unrelated test
   ([pytest-werror-4fdf790.log](pytest-werror-4fdf790.log)). Failing those blames the wrong test, and the leaks are in
   files other milestones own. Decision: every other warning is an error; `ResourceWarning` is shown in the summary
   (`default`), and the leak sources go to their owners in the integration notes.
4. **pytest-timeout becomes required.** With `timeout` in `pyproject.toml` and warnings as errors, a run without the
   plugin can't start. `required_plugins` makes that a one-line message. The plugin is in the `test` and `dev` extras,
   every lock, the distro containers (`python3-pytest-timeout`, packaged by all three) and `gnome-session.sh`.
5. **Which Qt the legs pin.** "Qt versions are pinned" and "a 3.14 leg constrained by requirements.txt": every pip leg
   installs `requirements-test.txt`, which locks the Qt `requirements.txt` ships, so all legs pin it and the 3.14 legs
   are exactly what the installers carry. Older Qt is covered by the distro job (Ubuntu's 6.6).
6. **Hash-locking a source-only package.** Nuitka has no wheel, and pip builds source packages with unhashed
   setuptools. The build jobs install the locked build list first and Nuitka with `--no-build-isolation`.
7. **Coverage floor.** Measured locally on Windows only (the brief: "measure the local Windows baseline and set
   fail_under conservatively"). The combined CI figure is a pending observation.
8. **`tests/gnome-session.sh`.** Owned by no one, run only by `ci.yml`; it needs `python3-pytest-timeout` because of
   decision 4. M6A changes that one line.
9. **Dependabot and pyproject's `PyQt6>=6.5`.** The root `pip` entry uses `increase-if-necessary`, so the floor that
   the distributions rely on is never raised by a version bump; the `dev` extra's exact pins still move.
10. **Package data.** Both new folders exist on `4fdf790`, so `phrases/*.json` and `sounds/*.wav` are added and the
    test skips nothing.

## Clarity, failure behaviour, terminology

- Each item's done-when is observable, but several are only observable on GitHub (triggers, timeouts, Dependabot,
  the release). Those acceptance criteria are `manual` with the reason, validated locally with actionlint (with
  shellcheck, in WSL) and zizmor, and their first real run is a pending operation in the checkpoint.
- Failure behaviour is specified for each new check: a missing glob names the files; a stale lock names the
  packages; the release job refuses to change a published release and names a draft's missing files; the distro
  script exits with pytest's status; the checksum job names a key it doesn't trust.
- Terms: "lock" is a `requirements*.txt` with hashes, "list" is its `.in`; "leg" is one matrix entry.

## Coverage

Every item maps to at least one acceptance criterion and an owning task in the plan's ledger: 15 requirements, 24
criteria, 7 tasks. Automated criteria pair a behaviour check with a red drill (the drill harness for test drills,
temporary copies for gate drills); manual ones carry their reason. No item is left without a check.

Result: ready, with decisions 1-10 recorded.

## Re-review at closure (merged tree, fc7fc3c and then c6ca786 in)

The requirements were read again against the plan as finished and the tree after merging `improve/assessment-fixes`
at `fc7fc3c` (M2 and M3 in), and the coordinator's later inputs:

- **M3's request:** the Linux test legs install `xvfb` and run under `xvfb-run -a`, so
  `test_clickthrough.py::test_the_x_server_gets_the_shape_in_device_pixels` runs. Added to M6A-01.A2's outcome.
- **Coverage on the 3.14 legs only** (one per OS, satisfying "every OS job"): measured on this PC, a test with a
  0.25 s bound failed once under coverage on a busy machine, so the other legs run plain. M6A-04.A2 says so.
- **M6A-06.A3 is manual.** `SOURCE_DATE_EPOCH` is set by the workflow; its effect is observed locally, but no file in
  the tree can be broken for a red drill of it.
- **Drilled files as inputs.** Two red drills break files no M6A task owns (`chatmon/changelog.py` for warnings as
  errors and the mypy gate, `tests/test_cli.py` for strict marks and the container script's failure path); they are
  declared as the work's inputs so the receipts bind them.
- **M4B's request (c6ca786):** the Linux legs also install `libxtst6` (its XGrabKey test presses keys through XTest
  under Xvfb) and `dbus-x11` (`dbus-monitor` and `dbus-run-session` for its portal tests). Added to M6A-01.A2.
- **mypy after the merges:** `stagemenu.py` now fails; of the new modules `highlight.py`, `shortcutportal.py` and
  `wincaret.py` pass and are gated, and `richtext.py`, `hotkey.py`, `libdbus.py`, `sound.py`, `winrt.py` and
  `wintoast.py` fail and are exempt: 18 gated, 47 exempt of 65. Package data: M4B adds no new kind of file.
- Not changed: the coordinator's note that M7 owns the Windows app-smoke and bubble failures on CI; M6A loosens no
  timeout and changes none of those tests.

Result: still ready; no requirement was rewritten to excuse a result.
