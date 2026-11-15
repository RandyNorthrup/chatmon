# M6A: CI, tooling and repo hygiene

Milestone M6A of the [improvement roadmap](ROADMAP.md), items M6A-01 to M6A-15 of the [assessment](ASSESSMENT.md)
except M6A-14, which moved to M1A with `packaging/build.py` (commit `5346385`; M1A delivered it, and
`tests/test_packaging.py::test_release_notes_pin_the_pipx_install_to_the_release` covers it). Branch `wave1/m6a`,
from `improve/assessment-fixes` at `5346385`, brought up by the coordinator's authorized merges to `4fdf790` (M0,
M1A, M1B, M5 and the sounds), then `fc7fc3c` (M2 and M3), then `c6ca786` (M4B). The ledger at the end owns every requirement, task, state and receipt.
Reports, logs and the drill spec are in [reports/m6a/](reports/m6a/).

## Rationale

### Scope

CI that is pinned, bounded and tests what ships; locked, reproducible build inputs; releases that are never
seen half-made; checks on what the wheel holds; contributor files; and a type checker gating what already
passes. M6A owns `.github/**`, `pyproject.toml`'s `[tool.*]` sections, optional dependencies, scripts and
package data, `packaging/requirements*`, the root `penguin-companion`, `SECURITY.md`, `CONTRIBUTING.md`,
`tests/conftest.py`, `tests/test_windows.py` and the new `tests/test_package_data.py`. It also creates
`tests/test_requirements.py`, `.github/scripts/distro-tests.sh` and the `packaging/requirements*.in` files.

One file outside that list changes: `tests/gnome-session.sh` gains `python3-pytest-timeout`. It is CI's own
helper, run only by `ci.yml`'s `gnome` job, nobody owns it, and without the plugin pytest now refuses to start
(below). Everything else needed in other files is under [Integration notes](#integration-notes).

Every finding was re-checked on `4fdf790` before it was changed; all are real. Two numbers moved since the
assessment: mypy now finds errors in 40 of 56 modules on at least one platform (16 pass everywhere, not 17:
the assessment's count was Linux only, on fewer modules), and the Windows Update test takes about 10 s here,
not 19. [reports/m6a/readiness.md](reports/m6a/readiness.md) has the re-check and the decisions.

### Design

**Pinned and locked inputs (M6A-01, M6A-05, M6A-06).** Every action in both workflows is pinned to a full commit
SHA, resolved with `gh api repos/<owner>/<repo>/git/ref/tags/<tag>` (annotated tags dereferenced). Each version is
at least two weeks old, and the SHAs match the ones `packages.yml` already used:

| Action | Version | Commit |
|---|---|---|
| actions/checkout | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| actions/setup-python | v7.1.0 | `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` |
| actions/upload-artifact | v7.0.2 | `cf430e030ddbb5b0abf93d22962f4752f3646cd9` |
| actions/download-artifact | v8.0.2 | `9000827ccba6bdab643e8b6fd33ac0654aef8333` |
| actions/attest-build-provenance | v4.2.2 (2026-08-06) | `4d101475d8b20a2381f78447822ac1eab6504dd8` |
| azure/login (unchanged) | v3.1.0 | `a641126d1b8aa4d1fa005f4f92df94a3a4c4c906` |

Python tools come from four hash-locked lists, each locked from a `.in` file beside it with
`uv pip compile --universal --generate-hashes`, choosing only releases from before 2026-10-31 (`--exclude-newer`):

| List | What installs it | What it holds |
|---|---|---|
| `requirements.txt` | the Windows and macOS installer builds | the shipped Qt (PyQt6 6.11.0, Qt 6.11.2), psutil, Nuitka or PyInstaller |
| `requirements-build.txt` | the wheel job; first, on Windows and macOS | build, setuptools 84.2.1, wheel, twine, pytest |
| `requirements-test.txt` | every pip test leg | the shipped Qt, pytest, pytest-timeout, coverage, Hypothesis, tzdata |
| `requirements-dev.txt` | lint, types; contributors | the test list, ruff, mypy, zizmor |

Everything is installed with `--require-hashes`. Nuitka is published only as source, which pip would build with
setuptools and wheel fetched unchecked, so the build jobs install the build list first and Nuitka's source with
`--no-build-isolation`. The wheel is built the same way (`python -m build --no-isolation`) with the locked
setuptools. Each build job sets `SOURCE_DATE_EPOCH` from its commit: with it, two wheels built from copies whose
files carry different times were byte-identical here, and without it they differed. The sdist is not reproducible
(setuptools' tarball), which is recorded, not claimed.

Every pip leg installs `requirements-test.txt`, so every leg runs the Qt that ships, at Python 3.11, 3.14 and
3.15. The 3.14 legs (Windows, macOS, `ubuntu-24.04-arm`) are what the installers carry. `tests/test_requirements.py`
keeps the lists honest: every line pinned and hashed, each lock at its `.in` file's versions, one version per
package across the lists (so the tests' Qt is the shipped Qt), and the `dev` extra equal to `requirements-dev.in`.

**Test settings (M6A-01).** `pyproject.toml` now gives every run `-rs`, `--strict-markers`, warnings as errors,
and a 120 s limit per test (the slowest test here takes 8 s). pytest-timeout is a `required_plugins` entry, so a
run without it stops with "Missing required plugins: pytest-timeout" rather than an internal error. One warning
class is shown instead of failing: `ResourceWarning`. The garbage collector reports an unclosed socket in
whichever test it happens to run during, not the test that left it, so a failure there blames the wrong test.
On `4fdf790` with every warning an error, 5 tests failed and 15 errored this way, all `ResourceWarning`; the
sources are listed in the integration notes for their owners.

**CI jobs (M6A-01, -03, -04, -05, -12, -13, -15).** `ci.yml` runs on pull requests, pushes to main and by hand.
A newer push to a pull request cancels its older run, and every job has a time limit.

| Job | What it runs |
|---|---|
| `lint` | ruff; actionlint (a pinned, checksum-checked binary, with the runner's shellcheck); zizmor |
| `types` × linux, win32, darwin | `mypy --platform <p>` |
| `test` | 6 legs (Ubuntu, Windows, macOS × 3.11, 3.15) plus 3.14 on Windows, macOS and Ubuntu Arm; the 3.14 legs, one per OS, under coverage |
| `coverage` | combines the three legs' data, writes the table to the run's summary, and holds `fail_under` |
| `distro` × ubuntu:24.04, debian:trixie, fedora:44 | the whole suite on each one's own Python and PyQt6, as an ordinary user |
| `gnome` | unchanged, apart from pinning and the sparse checkout |

Test jobs check out without `art/` and `docs/` (sparse, partial clone), which no test reads. The Linux legs install
the Wayland protocol files (the overlay's opcode test reads them), `dbus` and `dbus-x11` (`dbus-run-session` and
`dbus-monitor`, for M1B's Secret Service and M4B's GlobalShortcuts portal tests), `xvfb` and `libxtst6`, and run under
`xvfb-run -a`, as M3 and M4B asked: Qt stays offscreen, while M3's click-through test and M4B's XGrabKey test, which
talk to X themselves (the latter pressing keys through XTest), run instead of skipping.

**Coverage (M6A-04).** Branch coverage of `chatmon`, relative paths, and a `[tool.coverage.paths]` entry so
Windows' and POSIX paths combine. Each OS's 3.14 leg runs under coverage, where Python's `sys.monitoring` makes it
cheap; the other legs run plain. A few tests time what they wait for (one asserts a call returns within 0.25 s),
and a slower tracer on every leg would only add noise to them. The floor is set from the local Windows run (see
Results), a little under it: the combined CI figure covers more platform code and is expected to be higher, and is
the pending check that may raise the floor.

**mypy (M6A-13).** Python 3.11, all of `chatmon`, with `strict_equality`, `warn_redundant_casts` and the
error codes `redundant-expr`, `truthy-bool`, `unused-awaitable`, `exhaustive-match`, `ignore-without-code` and
`possibly-undefined`. `warn_unreachable` is off because each `--platform` run reads other platforms' code as
unreachable (10 false findings in the gated modules), and `explicit-override` is off because `@override` needs
Python 3.12 or `typing_extensions`, a new dependency. After merging `c6ca786` (M2, M3 and M4B in), the 47 of 65
modules that fail on any platform are listed with `ignore_errors`, and the 18 that pass on all three are gated:
`__init__`, `__main__`, `asking`, `autostart`, `behavior`, `changelog`, `chats`, `companions`, `highlight`,
`localefmt`, `memory`, `releasecheck`, `report`, `shortcutportal`, `styles`, `sysnotify`, `wincaret`, `winfiles`
([mypy.log](reports/m6a/mypy.log)). Since `4fdf790`: M3's changes to `stagemenu.py` made it fail (now exempt); of
the new modules, `highlight.py` (M2), `shortcutportal.py` and `wincaret.py` (M4B) pass and are gated, and
`richtext.py` (M2), `hotkey.py`, `libdbus.py`, `sound.py`, `winrt.py` and `wintoast.py` (M4B) fail and are exempt.
**This list is provisional:** M4A is still to merge, so it is checked again then (Integration notes).

**Releases (M6A-07).** `packages.yml` now starts on a pushed `v*` tag, not a published release. The `python` job
checks the tag against the version; the build, sign and checksum jobs run as before; then `attest` makes a build
provenance attestation for every file, and `publish` creates a draft release with the changelog's notes, attaches
every file, checks the draft holds exactly those files, and only then publishes it. A rerun after a failure
finishes an existing draft and refuses to touch a published release. The "last release" lookups skip drafts. Run
by hand from a `v*` tag, the workflow still signs without releasing.

**What ships (M6A-08, M6A-09).** `tests/test_package_data.py` reads the package-data globs exactly as setuptools'
`build_py` does (the standard library's recursive glob from the package folder) and checks every tracked file under
`chatmon/` that isn't top-level Python is taken, and every glob takes something. Given `CHATMON_DIST`, it also opens
the built wheel and sdist: every tracked file is in each, nothing else is in the wheel, and the wheel installs only
`chatmon` and `chatmonw`. The wheel job runs it, and `twine check --strict`. The globs `phrases/*.json` and
`sounds/*.wav` are added; both folders exist on `4fdf790`, so nothing is skipped. The old `penguin-companion` command
and root script are gone; the migration code in `agents.py`, `autostart.py` and the rename tests stays until 1.0.

**Reuse.** The existing apt fallback, mirror comment and container pattern (`gnome-session.sh`, the packages Linux
job) are kept and extended rather than replaced; `distro-tests.sh` follows `gnome-session.sh`'s form. The drill
harness `tests/drills/run.py` runs the test drills ([drill-spec.json](reports/m6a/drill-spec.json)). The harness only
runs pytest, so the other gates (zizmor, actionlint, mypy, strict marks, pip's hashes, the coverage floor, the checksum
step, and the wheel job's build, twine and dist checks) are drilled by [gate_drills.py](reports/m6a/gate_drills.py), in
temporary copies the same way, and the distro script by a podman run on a broken copy.

### Not real, deferred, or moved

- **M6A-14** moved to M1A (above).
- **The sdist is not reproducible** with `SOURCE_DATE_EPOCH`; the wheel is. Not in the item's done-when; noted.
- **Container images are pinned by tag, not digest**, so the distro job tests what users of each release get today.

## Results

Run on the Windows 11 workstation (Python 3.14.10, PyQt6 6.11.0), and for Linux in its WSL Arch (Python 3.14.9) and
podman containers. Logs are in [reports/m6a/](reports/m6a/); the ledger binds each one.

**The suite.**

| Where | Result |
|---|---|
| Windows, final tree | 1064 passed, 126 skipped ([pytest-windows-final.log](reports/m6a/pytest-windows-final.log)) |
| Linux (WSL Arch), pip's Qt 6.11 from `requirements-test.txt`, under `xvfb-run -a` and coverage, as the CI 3.14 leg | 1085 passed, 105 skipped ([linux-xvfb-run.log](reports/m6a/linux-xvfb-run.log)); M3's X shape test and M4B's XGrabKey test run there, and the shape test skips without it |
| ubuntu:24.04, PyQt6 6.6.1 on Qt 6.4.2 | 1078 passed, 112 skipped ([final-distro-ubuntu-24.04.log](reports/m6a/final-distro-ubuntu-24.04.log)) |
| debian:trixie, PyQt6 6.9.0 on Qt 6.8.2 | 1078 passed, 112 skipped ([final-distro-debian-trixie.log](reports/m6a/final-distro-debian-trixie.log)) |
| fedora:44, PyQt6 6.11.0 on Qt 6.11.2 | 1078 passed, 112 skipped ([final-distro-fedora-44.log](reports/m6a/final-distro-fedora-44.log)) |

Before the merge of `fc7fc3c`, Ubuntu's run failed one test on Qt 6.4 (integration note 3, since resolved by M2's
change), and Debian and Fedora passed 838 each ([distro-ubuntu-24.04.log](reports/m6a/distro-ubuntu-24.04.log) and
its neighbours). Two timing tests owned by M1B failed once each on this PC while other workers' suites ran, and
passed on every rerun: `test_streaming.py::test_a_brain_test_says_how_long_the_answer_took_or_whats_wrong` (no
answer within 10 s) and, under coverage, `test_brains.py::test_finding_the_brain_never_probes_on_the_screens_thread_and_remembers`
(0.28 s against a 0.25 s bound). That second one is why coverage runs only on the 3.14 legs.

**Gates.** ruff passes; mypy passes for linux, win32 and darwin ([mypy.log](reports/m6a/mypy.log)); actionlint
(with shellcheck) and zizmor find nothing ([workflow-lint.log](reports/m6a/workflow-lint.log)); the Dependabot file
validates against SchemaStore's schema ([dependabot-schema.log](reports/m6a/dependabot-schema.log)); zizmor's online
audits (impostor commits, known-vulnerable actions) pass too; pip-audit finds no known vulnerability in any lock
([pip-audit.log](reports/m6a/pip-audit.log)).

**Coverage** ([coverage.log](reports/m6a/coverage.log)): Windows alone 74.9%, Linux alone 75.6%, the two combined 82.7%, each of the 65 modules once (Windows' and POSIX paths mapped together). `fail_under = 72`.

**Builds.** The Windows job's locked install works in a fresh venv, Nuitka built from source with the locked
setuptools ([install-windows-build.log](reports/m6a/install-windows-build.log)). The wheel job passes `twine check
--strict` and the dist tests ([wheel-job.log](reports/m6a/wheel-job.log)). With `SOURCE_DATE_EPOCH`, two wheels from
copies with different file times are byte-identical; without it they differ
([source-date-epoch.log](reports/m6a/source-date-epoch.log)).

**Red drills.** Every drill went green, then red for the intended reason, then green again with the drilled file's
bytes restored and checked:

- 6 test drills through the harness ([drills.log](reports/m6a/drills.log)): a package-data glob removed, a warning
  raised in `changelog.py`, a different Qt in the test lock, a lock line without hashes, a lock behind its `.in`
  file, and a dev-extra pin that drifted.
- 10 gate drills ([gate-drills.log](reports/m6a/gate-drills.log)): an action pinned to a tag (zizmor), a misspelt
  matrix property (actionlint), a type error in a gated module (mypy), an unregistered mark (pytest), changed hashes
  (pip), the checksum job looking in `updates.py` again, `fail_under` above the total (coverage), and, through the wheel
  job, a wheel without the sounds, the old command put back, and a README `twine` can't render.
- 1 container drill ([final-distro-drill.log](reports/m6a/final-distro-drill.log)): a broken assertion makes the distro
  script, and so the job, fail.

**Opt-in.** The Windows Update test skips by default with its reason, and passes when asked for, in 58 s
([windows-update-optin.log](reports/m6a/windows-update-optin.log)).

## Integration notes

1. **Coordinator: CI no longer starts on a branch push.** After this merges, pushing `improve/assessment-fixes`
   starts nothing by itself (M6A-01: pushes run only on main). Start CI with
   `gh workflow run ci.yml --ref improve/assessment-fixes`, and the packages workflow the same way
   (`gh workflow run packages.yml --ref improve/assessment-fixes`), or open the final PR as a draft early: pull
   requests run CI on every push.
2. **Everyone: the suite needs pytest-timeout, and warnings are errors.** `required_plugins` stops a run without
   pytest-timeout. The shared venv now has pytest-timeout 2.4.0, coverage 7.17.0, mypy 2.4.1 and zizmor 1.31.1.
   Any warning other than `ResourceWarning` fails the test that raised it, so each wave-1 branch merged after this
   one should run the whole suite with this `pyproject.toml` first.
3. **M3 (`penguin.py`) and M2 (`bubble.py`): Qt 6.4 gives a QLineEdit's menu actions no names.** The distro job
   found this on `4fdf790`: on Ubuntu 24.04 (PyQt6 6.6.1 on Qt 6.4.2),
   `test_overlay_stage.py::test_the_box_uses_the_overlays_clipboard` failed, because Qt 6.4's standard context menu
   for a QLineEdit names none of its actions ([qt64-context-menu.log](reports/m6a/qt64-context-menu.log)), and
   `penguin.py`'s `_context_menu` and `bubble.py`'s `contextMenuEvent` find Copy, Cut and Paste by those names
   (`edit-copy`, `edit-cut`, `edit-paste`). M2's multi-line ask box, a QTextEdit, has named actions on Qt 6.4, so after
   the `fc7fc3c` merge the test passes there ([final-distro-ubuntu-24.04.log](reports/m6a/final-distro-ubuntu-24.04.log)).
   What's left is low priority: any QLineEdit put on the overlay would lose the overlay's clipboard on Qt 6.4. If one
   is, recognise an unnamed action by the standard shortcut after the tab in its text. Also worth knowing: Ubuntu's
   PyQt6 6.6.1 satisfies `PyQt6>=6.5`, but runs on Qt 6.4.2.
4. **M1A, M1B and M6B: unclosed resources.** Shown, not failed, under `default::ResourceWarning`; each was seen on
   Windows and in the containers ([pytest-werror-4fdf790.log](reports/m6a/pytest-werror-4fdf790.log),
   [pytest-windows.log](reports/m6a/pytest-windows.log)):
   - `tests/test_updates.py` (M1A): a socket per test from the local release server, left open at teardown.
   - `tests/test_brains.py` and `brains.py` (M1B): sockets from the redirect tests; an `HTTPError 302` never closed
     ("Implicitly cleaning up"); a subprocess still running after the Windows tree test; an unclosed text file.
   - `tests/test_events.py` (M1A): the stdin file of `test_notify_never_waits_on_an_open_stdin`, the lock file of
     `test_only_one_chatmon_holds_the_lock`, and the pipe of `test_a_shell_that_never_answers_is_stopped_whole`.
   Once they're closed, M6B can drop the `default::ResourceWarning` line so they fail like any other warning.
5. **Every merge: the mypy gate is provisional.** At each wave-1 merge, run `mypy --platform linux`, `win32` and
   `darwin`. A gated module that now fails is fixed or, with a reason, added to the exemptions; an exempt module that
   now passes comes off the list (M6B-02). A new module is gated by default, so anything new from M4A must pass on
   all three platforms or be listed. The list as delivered (after M4B) is in [Design](#design).
6. **M4B: QtMultimedia in the containers (optional).** `sound.py` plays through QSoundEffect where QtMultimedia is
   installed and falls back to `pw-play`, `paplay` or `canberra-gtk-play`, so the distro job needs nothing more. To
   test the QSoundEffect path on the distributions too, add `python3-pyqt6.qtmultimedia` to
   `.github/scripts/distro-tests.sh`'s apt line (Fedora's `python3-pyqt6` already has it); pip's PyQt6 wheel has it.
7. **M1A (`agents.py`): one docstring.** It says "penguin-companion stays as an alias for now". The command is gone;
   the migration it describes stays, so only that sentence changes.
8. **Coordinator: `packaging/README.md` (unowned).** "How releases get them" should say a pushed `v*` tag releases
   (not a published release): the workflow drafts the release, attaches every file with its attestation, and
   publishes it last. "Making them yourself" should install with
   `python -m pip install --require-hashes -r packaging/requirements-build.txt`, then
   `python -m pip install --require-hashes --no-build-isolation -r packaging/requirements.txt`.
9. **Coordinator: `.gitignore` (unowned).** Add `.hypothesis/`, `.coverage`, `.coverage.*` and `.mypy_cache/`.
10. **After the first CI run: the coverage floor.** Read the combined total from the `coverage` job's summary. If it is
    well above `fail_under`, raise the floor to about two points under it.
11. **After the next release: the Linux job's update step.** "Install the last release, update it to this one" runs the
    last release's own `install-update FILE SHA256`. Once a release with M1A's helper is the last one, that step needs
    a signed list, as `test-install-update.sh` makes one (the step's comment says so).
12. **Not taken up here.** M1B note 14 (an autouse in-memory keychain in `tests/conftest.py`) needs the real-backend
    tests in `test_keychain.py` to opt out, so it's left for M7 or M1B to do with them. M5's optional Hypothesis
    profile in `conftest.py` isn't needed: the property tests load their own.
13. **APIs.** None: M6A changes no module of Chatmon.
14. **Known red on CI, not from M6A.** The feature branch's latest CI run before this merge (43645270996, `c6ca786`)
    failed only on Windows: `test_app_smoke.py` and `test_bubble_styles.py` (M7 is fixing them; M6A changes neither and
    loosens no limit for them) and two `test_wintoast.py` tests (M4B). They will fail the same way in the new CI.
15. **Owner decisions (repository settings, left as they are).** Read with `gh api`, changed by nobody: secret scanning
    and push protection are off (free for public repositories); Dependabot security updates are off (the new
    `dependabot.yml` version updates work without them); and no branch protection requires the new checks. Turning
    any of them on is a settings page, the owner's call. Private vulnerability reporting is on, which SECURITY.md
    relies on.

## Changelog notes

- **Releases appear complete.** A new release is published only once every installer, package and checksum is
  attached, so neither you nor Chatmon's update check ever sees one half made.
- **Each release file can be traced to its build.** Every file comes with a signed build provenance attestation:
  `gh attestation verify <file> --repo RandyNorthrup/chatmon` names the workflow, commit and tag that made it.
- **pip and pipx installs include the sounds and the offline phrases.**
- **The `penguin-companion` command is gone.** It was Chatmon's old name, kept since 0.3.0; use `chatmon`. Agents'
  hooks set up under the old name are still moved over the first time Chatmon runs.
- **Tested on more systems:** Linux on Arm, and Ubuntu 24.04's, Debian 13's and Fedora 44's own PyQt6, as the .deb
  and .rpm use them.

## README notes

- **Running the tests** ("How it's put together"): replace `python3 -m pip install pytest ruff` and
  `python3 -m pytest && ruff check .` with `python3 -m pip install -e ".[dev]"`, then `python3 -m pytest`,
  `ruff check .` and `mypy --platform linux` (or `win32`, `darwin`), and link [CONTRIBUTING.md](../../CONTRIBUTING.md).
- **What CI runs:** "on Linux, Windows and macOS with Python 3.11 and 3.15" becomes "on Linux (x64 and Arm),
  Windows and macOS with Python 3.11, 3.14 (what the installers carry) and 3.15, and on Ubuntu 24.04, Debian 13 and
  Fedora 44 with their own PyQt6".
- **Coming from Penguin companion:** drop "`penguin-companion` is still installed as another name for `chatmon`,
  for now". Say instead that hooks connected under the old name stop working once the old package is gone, until
  Chatmon has run once and moved them.
- **Privacy and security:** after "Found a security problem?", point to [SECURITY.md](../../SECURITY.md), which also
  says how to check a download (`SHA256SUMS.txt`, its signature, and `gh attestation verify`).

## Reconciliation, wave 4 (2026-11-14)

Wave 4 read the workflows' first runs, which this plan's checkpoint was waiting for, and re-ran every check whose receipt
had gone stale. The evidence is for **fb19cb9** (`improve/assessment-fixes`), bound to the repository's own bytes: LF, as
git stores them (ROADMAP.md, *Canonical bytes*). Two other workers were changing code at the same time. The wayland
worker is changing `ci.yml`. The followups worker is changing packaging, the requirements and the mypy settings in
`pyproject.toml`. Their merges will make many of these receipts stale again.

**What the runs answered.** CI run 43677128712 on fb19cb9, Packages run 43675230966 on d3f6a6e (the same `.github/`,
`packaging/` and `pyproject.toml`), and PR #18's own checks. The PR's test merge has fb19cb9's tree, and its 23 checks
passed, with the 5 release jobs skipped. That includes Packages run 43677664360 on exactly these files. Their logs and job lists are in
[reports/wave4/ci/](reports/wave4/ci/), and the review is [wave4/ci-review.md](reports/m6a/wave4/ci-review.md).

- **P-CI-FIRST: resolved.** All 18 jobs succeeded: lint, types ×3, test ×9, distro ×3, gnome and coverage. They are the
  same 18 checks `main` now requires.
- **P-COVERAGE-FLOOR: answered.** Windows, macOS and Arm Linux combined measure 86.2% against `fail_under = 72`. The same
  data, combined here, gives the same total. The plan's next action, raising the floor to about 84, is a change to
  `pyproject.toml`, which the followups worker now owns. It is left to them, and the Outcome in ROADMAP.md lists it.
- **P-PACKAGES-PR: resolved.** The python, windows, macos (macos-latest and macos-15-intel) and linux jobs succeeded:
  locked installs, `SOURCE_DATE_EPOCH`, twine and the dist tests, `test-install-update.sh` in three containers, and
  M1A's macOS checks.
- **P-MYPY-MERGES: resolved.** M6B removed the exemption list, and mypy passes on linux, win32 and darwin (CI's types
  jobs).
- **P-RELEASE: still open.** No tag has been pushed. The Packages run skipped the five release jobs, as designed.
- **P-DEPENDABOT: still open.** Dependabot reads `.github/dependabot.yml` from `main`, which doesn't have it yet. The
  owner's 2026-11-14 settings turned on Dependabot alerts and security updates, which are separate from these version
  updates.

**What was re-run.** The whole suite on Windows ([wave4/suite-windows.log](reports/wave4/suite-windows.log): 1241
passed, 148 skipped). The 6 pytest drills and the 10 gate drills (zizmor, actionlint, mypy, strict marks, pip's hashes,
the checksums step, the coverage floor on CI's own combined data, and the wheel job's three), every one green, red and
green again. The distribution drill: `distro-tests.sh` in debian:trixie under podman, green, then red with a failing
test, then green again. Also the reproducible-wheel check (`SOURCE_DATE_EPOCH`), the Windows Update opt-in both ways,
and Dependabot's schema. The requirements were reviewed again ([wave4/readiness.md](reports/m6a/wave4/readiness.md)).

**What remains.**

- **M6A-10.A1 fails its re-review.** CONTRIBUTING.md still says warnings are errors "all but ResourceWarning" and that
  mypy exempts modules with `ignore_errors`. M6B ended both. See [wave4/docs-review.md](reports/m6a/wave4/docs-review.md).
  T7 stays implemented until someone outside `docs/delivery/` rewrites those two sentences (the coordinator, or the
  followups worker).
- **P-RELEASE.** Randy or the coordinator, at the 0.10.0 tag.
- **P-DEPENDABOT.** The coordinator, after the PR reaches `main`.

**Receipts.** Every earlier passing receipt is now marked stale, as history, with its hashes untouched. The W4-
receipts replace them.

## Reconciliation, wave 4, round two (2026-11-15)

Round two re-bound this plan at **bf9d8ac**: `improve/assessment-fixes` after the wayland, followups, a11y and
sway-ci merges, and round one's own. Its earlier receipts went stale, because `pyproject.toml` (a rule) and files they
were bound to changed. The evidence is for bf9d8ac only. wave4/crash, not merged yet, fixes an intermittent Qt crash
in `chatmon/app.py`, `chatmon/brains.py`, `tests/app_harness.py` and `tests/test_app_smoke.py`. The checkpoint's next
action names the receipts that bind those files, and only those need a refresh when it merges.

**What was re-run.** The whole suite on Windows ([wave4b/suite-windows.log](reports/wave4b/suite-windows.log): 1256 passed, 178 skipped), then 16 Windows drills and 1 Linux ones (in WSL). Every one went green, red and green again. CI run 43701523023 (PR #18 at bf9d8ac, all 19
jobs green) was read for its lint, types, distro, coverage and test legs, with Packages run 43701523037 (the build jobs) ([reports/m6a/ci/observed-bf9d8ac.txt](reports/m6a/ci/observed-bf9d8ac.txt)). The
requirements were reviewed again ([wave4b/readiness.md](reports/m6a/wave4b/readiness.md)).

**M6A-10.A1 passes again** ([wave4b/docs-review.md](reports/m6a/wave4b/docs-review.md)). CONTRIBUTING.md's two
sentences are rewritten. Its new claim, that mypy passes with PyQt6 6.12.1's stubs, was checked on linux, win32 and
darwin in WSL. The rest of round two's runs:

- the 10 gate drills, on CI's own combined coverage data and against `fail_under = 84`;
- the distro drill, under podman;
- the reproducible wheel;
- the Windows Update opt-in;
- Dependabot's schema, with its new PyQt6 6.12.0 ignore.

**What remains: two pending operations, with their owners, not passing.**

- **P-RELEASE.** No v0.10.0 tag exists yet. Owner: Randy or the coordinator, at the release.
- **P-DEPENDABOT.** `.github/dependabot.yml` isn't on `main` yet. Owner: the coordinator, after the merge.

**Receipts.** Round one's W4- receipts are now stale history, with their hashes untouched. The W4B- receipts replace
them.

```quality-ledger
{
  "schema_version": 1,
  "work": {
    "id": "M6A",
    "title": "CI, tooling and repo hygiene",
    "scope_revision": 1,
    "brief": "docs/delivery/ASSESSMENT.md",
    "brief_reason": null,
    "rules": [
      {
        "path": "docs/delivery/ROADMAP.md",
        "revision": "bf9d8ac+wave4b"
      }
    ],
    "inputs": [
      "tests/conftest.py",
      "tests/drills/run.py",
      "chatmon/changelog.py",
      "tests/test_cli.py",
      "docs/delivery/reports/wave4/cilog.py"
    ],
    "environment": {
      "platform": "windows",
      "tools": {
        "python": "3.14.10",
        "pytest": "9.2.0",
        "pyqt6": "6.11.0",
        "pytest-timeout": "2.4.0",
        "coverage": "7.17.0",
        "mypy": "2.4.1",
        "ruff": "0.17.4",
        "zizmor": "1.31.1",
        "actionlint": "1.7.12",
        "uv": "0.12.7",
        "shellcheck": "0.11.0",
        "podman": "6.2.0"
      }
    }
  },
  "requirements": [
    {
      "id": "M6A-01",
      "statement": "CI is pinned and bounded: actions pinned to commit SHAs without persisted credentials, a time limit on every job, pull-request runs cancelled by newer ones, pushes run only on main, ruff, pytest and Qt pinned, tests run with pytest-timeout, -rs, warnings as errors and strict markers, and the Linux legs have the Wayland protocol files",
      "priority": "critical",
      "acceptance": [
        "M6A-01.A1",
        "M6A-01.A2",
        "M6A-01.A3"
      ],
      "superseded_by": null
    },
    {
      "id": "M6A-02",
      "statement": "Dependabot keeps github-actions and pip dependencies up to date, each update at least 14 days old",
      "priority": "normal",
      "acceptance": [
        "M6A-02.A1"
      ],
      "superseded_by": null
    },
    {
      "id": "M6A-03",
      "statement": "The whole suite runs in ubuntu:24.04, debian:trixie and fedora:44 containers on each one's own PyQt6",
      "priority": "critical",
      "acceptance": [
        "M6A-03.A1"
      ],
      "superseded_by": null
    },
    {
      "id": "M6A-04",
      "statement": "Coverage from every OS job is combined and written to the job summary, and held to a fail_under set from the measured baseline",
      "priority": "normal",
      "acceptance": [
        "M6A-04.A1",
        "M6A-04.A2"
      ],
      "superseded_by": null
    },
    {
      "id": "M6A-05",
      "statement": "CI tests what ships: a Python 3.14 leg on the Qt packaging/requirements.txt ships, and an ubuntu-24.04-arm leg",
      "priority": "normal",
      "acceptance": [
        "M6A-05.A1",
        "M6A-05.A2"
      ],
      "superseded_by": null
    },
    {
      "id": "M6A-06",
      "statement": "Build dependencies are hash-locked and installed with --require-hashes, setuptools is pinned, and SOURCE_DATE_EPOCH is set",
      "priority": "critical",
      "acceptance": [
        "M6A-06.A1",
        "M6A-06.A2",
        "M6A-06.A3"
      ],
      "superseded_by": null
    },
    {
      "id": "M6A-07",
      "statement": "A tag push uploads to a draft release that is published at the end, and actions/attest-build-provenance runs",
      "priority": "critical",
      "acceptance": [
        "M6A-07.A1"
      ],
      "superseded_by": null
    },
    {
      "id": "M6A-08",
      "statement": "A test checks every tracked non-.py file under chatmon/ matches a package-data glob, and the wheel job runs twine check",
      "priority": "critical",
      "acceptance": [
        "M6A-08.A1",
        "M6A-08.A2"
      ],
      "superseded_by": null
    },
    {
      "id": "M6A-09",
      "statement": "The penguin-companion console script and root file are removed, keeping the migration code until 1.0",
      "priority": "normal",
      "acceptance": [
        "M6A-09.A1"
      ],
      "superseded_by": null
    },
    {
      "id": "M6A-10",
      "statement": "SECURITY.md and CONTRIBUTING.md exist, the issue template links to security advisories, and a pinned dev extra exists",
      "priority": "normal",
      "acceptance": [
        "M6A-10.A1",
        "M6A-10.A2"
      ],
      "superseded_by": null
    },
    {
      "id": "M6A-11",
      "statement": "The test that runs a real Windows Update search is opt-in behind an environment variable",
      "priority": "normal",
      "acceptance": [
        "M6A-11.A1"
      ],
      "superseded_by": null
    },
    {
      "id": "M6A-12",
      "statement": "CI runs actionlint and zizmor on the workflows",
      "priority": "normal",
      "acceptance": [
        "M6A-12.A1"
      ],
      "superseded_by": null
    },
    {
      "id": "M6A-13",
      "statement": "mypy is configured with --platform legs, the modules that pass gated and the rest listed as exemptions",
      "priority": "normal",
      "acceptance": [
        "M6A-13.A1"
      ],
      "superseded_by": null
    },
    {
      "id": "M6A-15",
      "statement": "Test jobs use a sparse checkout without art/ and docs/",
      "priority": "low",
      "acceptance": [
        "M6A-15.A1"
      ],
      "superseded_by": null
    },
    {
      "id": "M6A-I1",
      "statement": "packages.yml keeps working with M1A's update checks: the Linux job runs packaging/linux/test-install-update.sh, and the checksums job finds the release key in chatmon/releasecheck.py, where it now lives",
      "priority": "critical",
      "acceptance": [
        "M6A-I1.A1",
        "M6A-I1.A2"
      ],
      "superseded_by": null
    }
  ],
  "acceptance": [
    {
      "id": "M6A-01.A1",
      "requirement": "M6A-01",
      "given": "ci.yml and packages.yml",
      "when": "zizmor audits .github offline at its regular persona",
      "then": "it reports nothing, so every action is pinned to a full commit SHA and no checkout keeps its credentials; a workflow with an action pinned only to a tag fails the audit",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6A-01.A2",
      "requirement": "M6A-01",
      "given": "ci.yml",
      "when": "it is reviewed against the done-when and validated by actionlint with shellcheck",
      "then": "every job has timeout-minutes, a pull request's newer run cancels its older one, pushes run only on main (with workflow_dispatch for any branch), and the Linux legs install wayland-protocols, libwayland-dev, dbus, dbus-x11, xvfb and libxtst6, and run the tests under xvfb-run",
      "checks": [
        "manual"
      ],
      "manual_reason": "GitHub Actions' scheduling, triggers and runners exist only on GitHub: locally the workflow is reviewed against the done-when and validated with actionlint (with shellcheck) and zizmor; its first CI run is a pending operation."
    },
    {
      "id": "M6A-01.A3",
      "requirement": "M6A-01",
      "given": "pyproject.toml's pytest settings and the hash-locked test tools",
      "when": "the suite runs",
      "then": "the session uses a 120 s per-test timeout, prints each skip's reason, refuses an unregistered mark and a run without pytest-timeout, and a warning raised in Chatmon's code fails the test that set it off, while ResourceWarning is shown, not failed",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6A-02.A1",
      "requirement": "M6A-02",
      "given": ".github/dependabot.yml",
      "when": "it is validated against SchemaStore's Dependabot schema and reviewed",
      "then": "github-actions, pip in /packaging and pip in / are each updated weekly with a 14-day cooldown, the PyQt6 packages move together, and the PyQt6>=6.5 floor is never raised just because a newer release exists",
      "checks": [
        "manual"
      ],
      "manual_reason": "Dependabot runs only on GitHub: locally the configuration is schema-validated and reviewed; its first run is a pending operation."
    },
    {
      "id": "M6A-03.A1",
      "requirement": "M6A-03",
      "given": ".github/scripts/distro-tests.sh and a tree without art/ and docs/",
      "when": "it runs in fresh ubuntu:24.04, debian:trixie and fedora:44 containers",
      "then": "it installs the distribution's own python3-pyqt6 and test tools, runs the whole suite as an ordinary user, and exits with pytest's status; a failing test makes it exit non-zero",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6A-04.A1",
      "requirement": "M6A-04",
      "given": "pyproject.toml's coverage settings",
      "when": "coverage data from Windows and from Linux are combined and reported",
      "then": "each module appears once (Windows' and POSIX paths mapped together), and the report fails below fail_under, which is set from the measured Windows baseline",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6A-04.A2",
      "requirement": "M6A-04",
      "given": "ci.yml",
      "when": "it is reviewed and validated",
      "then": "each OS's Python 3.14 leg runs under coverage and uploads its data, and the coverage job combines them, writes the table to the job summary and fails below the floor",
      "checks": [
        "manual"
      ],
      "manual_reason": "GitHub Actions' scheduling, triggers and runners exist only on GitHub: locally the workflow is reviewed against the done-when and validated with actionlint (with shellcheck) and zizmor; its first CI run is a pending operation."
    },
    {
      "id": "M6A-05.A1",
      "requirement": "M6A-05",
      "given": "the hash-locked lists",
      "when": "tests/test_requirements.py runs",
      "then": "requirements-test.txt locks the same PyQt6, PyQt6-Qt6, PyQt6-sip and psutil as requirements.txt, and a list locking a different Qt fails",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6A-05.A2",
      "requirement": "M6A-05",
      "given": "ci.yml's test matrix",
      "when": "it is reviewed and validated",
      "then": "Python 3.14 legs run on windows-latest, macos-latest and ubuntu-24.04-arm, and every pip leg installs requirements-test.txt with --require-hashes",
      "checks": [
        "manual"
      ],
      "manual_reason": "GitHub Actions' scheduling, triggers and runners exist only on GitHub: locally the workflow is reviewed against the done-when and validated with actionlint (with shellcheck) and zizmor; its first CI run is a pending operation."
    },
    {
      "id": "M6A-06.A1",
      "requirement": "M6A-06",
      "given": "packaging/requirements*.in and their locks",
      "when": "tests/test_requirements.py runs",
      "then": "every locked requirement is pinned with at least one hash, each lock holds its .in file's versions, and setuptools is pinned within pyproject.toml's build-system range; a lock line without a hash fails",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6A-06.A2",
      "requirement": "M6A-06",
      "given": "a fresh virtual environment on Windows",
      "when": "requirements-build.txt and then requirements.txt are installed with --require-hashes (the second with --no-build-isolation), as the Windows build job does",
      "then": "everything installs and Nuitka is built from source with the locked setuptools and wheel; a lock with a changed hash is refused by pip",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6A-06.A3",
      "requirement": "M6A-06",
      "given": "the wheel built twice from the same commit",
      "when": "SOURCE_DATE_EPOCH is set to the commit's time, as every packages.yml build job sets it",
      "then": "the two wheels are byte-identical, where without it they differ",
      "checks": [
        "manual"
      ],
      "manual_reason": "SOURCE_DATE_EPOCH is set by the workflow's build jobs, which run only on GitHub: locally its effect is observed, two wheels byte-identical with it and different without, and there is no file in the tree to break for a red drill."
    },
    {
      "id": "M6A-07.A1",
      "requirement": "M6A-07",
      "given": "packages.yml",
      "when": "it is reviewed against the done-when and validated by actionlint with shellcheck and zizmor",
      "then": "a pushed v* tag builds and signs as before, attest-build-provenance attests every file, and publish creates a draft with the changelog's notes and every file, checks the draft holds exactly those files, and only then publishes it; a rerun finishes a draft and never changes a published release",
      "checks": [
        "manual"
      ],
      "manual_reason": "A release needs a pushed v* tag on GitHub, the release environment's secrets and GitHub's attestation service: locally the workflow is reviewed and validated; the first tagged release is a pending operation."
    },
    {
      "id": "M6A-08.A1",
      "requirement": "M6A-08",
      "given": "pyproject.toml's package-data globs and the files git tracks under chatmon/",
      "when": "tests/test_package_data.py runs",
      "then": "every tracked file that isn't top-level Python is taken by a glob read as setuptools reads it, and every glob takes a tracked file; removing a needed glob fails the test",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6A-08.A2",
      "requirement": "M6A-08",
      "given": "a wheel and sdist built with the locked tools",
      "when": "twine check --strict and tests/test_package_data.py with CHATMON_DIST run on them, as the wheel job does",
      "then": "both pass: every tracked file is in each, nothing else is in the wheel; a wheel built without the sounds glob fails the test, and a wheel with broken metadata fails twine",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6A-09.A1",
      "requirement": "M6A-09",
      "given": "a wheel built from this tree",
      "when": "its entry points are read",
      "then": "it installs exactly chatmon and chatmonw, the root penguin-companion script is gone, and the migration code in agents.py and autostart.py remains; a wheel that still installs penguin-companion fails the test",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6A-10.A1",
      "requirement": "M6A-10",
      "given": "SECURITY.md, CONTRIBUTING.md and the issue template's config",
      "when": "they are reviewed against the workflows, pyproject.toml and the repository's settings",
      "then": "SECURITY.md says how to report privately and how to check a download, CONTRIBUTING.md says how to set up, test, lint, lock and release as CI does, and the issue chooser links to a private security advisory, which the repository accepts",
      "checks": [
        "manual"
      ],
      "manual_reason": "These are documents: their accuracy is checked by reading them against the code, the workflows and the repository's settings (private vulnerability reporting observed enabled through gh api)."
    },
    {
      "id": "M6A-10.A2",
      "requirement": "M6A-10",
      "given": "pyproject.toml's dev extra",
      "when": "tests/test_requirements.py runs",
      "then": "it names exactly requirements-dev.in's packages, each pinned to the version CI locks; a drifted pin fails",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6A-11.A1",
      "requirement": "M6A-11",
      "given": "tests/test_windows.py's Windows Update test",
      "when": "the suite runs on Windows without and then with CHATMON_TEST_WINDOWS_UPDATE=1",
      "then": "without it the test is skipped with a reason naming the variable; with it the test runs and passes, under its own 330 s limit",
      "checks": [
        "manual"
      ],
      "manual_reason": "A skip condition, observed both ways on Windows: there is no product behaviour to break for a red drill."
    },
    {
      "id": "M6A-12.A1",
      "requirement": "M6A-12",
      "given": "the workflows and ci.yml's lint job",
      "when": "actionlint (with shellcheck) and zizmor run on them",
      "then": "both pass, and each fails on a representative violation: an expression error for actionlint, a tag-pinned action for zizmor",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6A-13.A1",
      "requirement": "M6A-13",
      "given": "pyproject.toml's mypy settings",
      "when": "mypy runs with --platform linux, win32 and darwin",
      "then": "all three pass with the 18 passing modules checked and the 47 others exempt; a type error in a gated module fails it, and the same error in an exempt module doesn't",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6A-15.A1",
      "requirement": "M6A-15",
      "given": "ci.yml's test, types, distro and gnome jobs",
      "when": "their checkouts are reviewed, and the suite is run on a tree without art/ and docs/",
      "then": "each checks out sparsely without art/ and docs/, and the whole suite passes without them (the distro runs and the drill harness's copy have neither)",
      "checks": [
        "manual"
      ],
      "manual_reason": "Sparse checkout acts only on GitHub's runners: locally the patterns are reviewed and the suite is observed passing on a tree without those folders."
    },
    {
      "id": "M6A-I1.A1",
      "requirement": "M6A-I1",
      "given": "the checksums job's signing script",
      "when": "it runs with a throwaway Ed25519 key over a set of files",
      "then": "it signs and verifies when chatmon/releasecheck.py holds the key's public half, and stops with RELEASE_SIGNING_KEY isn't a key in RELEASE_KEYS when it doesn't",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M6A-I1.A2",
      "requirement": "M6A-I1",
      "given": "a .deb and an .rpm built from this tree",
      "when": "the Linux job's container steps run in ubuntu:24.04 and fedora:44",
      "then": "each installs, starts, passes packaging/linux/test-install-update.sh and is removed without a trace",
      "checks": [
        "manual"
      ],
      "manual_reason": "Building the packages needs nfpm and the release jobs' containers: M1A ran test-install-update.sh in containers itself; here the wiring is reviewed and validated, and the Linux packages job's run is a pending operation."
    }
  ],
  "tasks": [
    {
      "id": "T1",
      "purpose": "pyproject.toml: pytest settings, coverage, mypy, the test and dev extras, one console script, and the new package-data globs; gnome-session.sh gets pytest-timeout",
      "acceptance": [
        "M6A-01.A3",
        "M6A-04.A1",
        "M6A-13.A1"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "pyproject.toml",
          "action": "modify"
        },
        {
          "path": "tests/gnome-session.sh",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "B-PYTEST-WIN",
        "RED-WARNINGS",
        "RED-MARKS",
        "B-COVERAGE",
        "RED-FLOOR",
        "B-MYPY",
        "RED-MYPY",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-BEH-CI-COVERAGE",
        "W4-BEH-CI-TYPES",
        "W4-RED-G-coverage-floor",
        "W4-RED-G-mypy-gated",
        "W4-RED-G-pytest-strict-markers",
        "W4-RED-M6A-01-warnings",
        "W4B-READY",
        "W4B-BEH-WINDOWS",
        "W4B-BEH-CI-COVERAGE",
        "W4B-BEH-CI-TYPES",
        "W4B-RED-G-coverage-floor",
        "W4B-RED-G-mypy-gated",
        "W4B-RED-G-pytest-strict-markers",
        "W4B-RED-M6A-01-warnings"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T2",
      "purpose": "Hash-locked requirement lists for builds, tests and development, and the test that keeps them, and the dev extra, in step",
      "acceptance": [
        "M6A-05.A1",
        "M6A-06.A1",
        "M6A-06.A2",
        "M6A-10.A2"
      ],
      "depends_on": [
        "T1"
      ],
      "changes": [
        {
          "path": "packaging/requirements.in",
          "action": "create"
        },
        {
          "path": "packaging/requirements.txt",
          "action": "modify"
        },
        {
          "path": "packaging/requirements-build.in",
          "action": "create"
        },
        {
          "path": "packaging/requirements-build.txt",
          "action": "create"
        },
        {
          "path": "packaging/requirements-test.in",
          "action": "create"
        },
        {
          "path": "packaging/requirements-test.txt",
          "action": "create"
        },
        {
          "path": "packaging/requirements-dev.in",
          "action": "create"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "action": "create"
        },
        {
          "path": "tests/test_requirements.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "B-NEW-TESTS",
        "RED-QT",
        "RED-HASH",
        "RED-STALE",
        "RED-DEV",
        "B-INSTALL",
        "RED-PIP",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-BEH-PKG-INSTALL",
        "W4-RED-G-pip-hashes",
        "W4-RED-M6A-05-qt",
        "W4-RED-M6A-06-hash",
        "W4-RED-M6A-06-stale",
        "W4-RED-M6A-10-dev",
        "W4B-READY",
        "W4B-BEH-WINDOWS",
        "W4B-BEH-PKG-INSTALL",
        "W4B-RED-G-pip-hashes",
        "W4B-RED-M6A-05-qt",
        "W4B-RED-M6A-06-hash",
        "W4B-RED-M6A-06-stale",
        "W4B-RED-M6A-10-dev"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T3",
      "purpose": "What ships: the package-data test, the built wheel's and sdist's contents and commands, and the old command's removal",
      "acceptance": [
        "M6A-08.A1",
        "M6A-08.A2",
        "M6A-09.A1"
      ],
      "depends_on": [
        "T1",
        "T2"
      ],
      "changes": [
        {
          "path": "tests/test_package_data.py",
          "action": "create"
        },
        {
          "path": "penguin-companion",
          "action": "delete"
        }
      ],
      "status": "verified",
      "evidence": [
        "B-NEW-TESTS",
        "RED-GLOB",
        "B-WHEEL-JOB",
        "RED-WHEEL",
        "RED-TWINE",
        "RED-COMMANDS",
        "W4-READY",
        "W4-BEH-WINDOWS",
        "W4-BEH-PKG-WHEEL",
        "W4-RED-M6A-08-glob",
        "W4-RED-W-entry-points",
        "W4-RED-W-twine-markup",
        "W4-RED-W-wheel-sounds",
        "W4B-READY",
        "W4B-BEH-WINDOWS",
        "W4B-BEH-PKG-WHEEL",
        "W4B-RED-M6A-08-glob",
        "W4B-RED-W-entry-points",
        "W4B-RED-W-twine-markup",
        "W4B-RED-W-wheel-sounds"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T4",
      "purpose": "The Windows Update test runs only when asked for",
      "acceptance": [
        "M6A-11.A1"
      ],
      "depends_on": [
        "T1"
      ],
      "changes": [
        {
          "path": "tests/test_windows.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "M-WINUPDATE",
        "W4-READY",
        "W4-MAN-WINUPDATE",
        "W4B-READY",
        "W4B-MAN-WINUPDATE"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T5",
      "purpose": "ci.yml: pinned and bounded jobs for lint, types per platform, tests with coverage, the combined coverage report, the distributions' own PyQt6, and GNOME",
      "acceptance": [
        "M6A-01.A2",
        "M6A-03.A1",
        "M6A-04.A2",
        "M6A-05.A2",
        "M6A-15.A1"
      ],
      "depends_on": [
        "T1",
        "T2"
      ],
      "changes": [
        {
          "path": ".github/workflows/ci.yml",
          "action": "modify"
        },
        {
          "path": ".github/scripts/distro-tests.sh",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "B-DISTRO-UBUNTU",
        "B-DISTRO-DEBIAN",
        "B-DISTRO-FEDORA",
        "RED-DISTRO",
        "M-WORKFLOWS",
        "W4-READY",
        "W4-MAN-CI-REVIEW",
        "W4-BEH-CI-DISTRO-UBUNTU",
        "W4-BEH-CI-DISTRO-DEBIAN",
        "W4-BEH-CI-DISTRO-FEDORA",
        "W4-RED-M6A-03-distro-fails-on-a-failed-test",
        "W4B-READY",
        "W4B-MAN-CI-REVIEW",
        "W4B-BEH-CI-DISTRO-UBUNTU",
        "W4B-BEH-CI-DISTRO-DEBIAN",
        "W4B-BEH-CI-DISTRO-FEDORA",
        "W4B-RED-M6A-03-distro-fails-on-a-failed-test"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T6",
      "purpose": "packages.yml: locked and dated builds, the wheel's checks, M1A's update checks, attestations, and a draft release published last; both workflows audited",
      "acceptance": [
        "M6A-01.A1",
        "M6A-06.A3",
        "M6A-07.A1",
        "M6A-12.A1",
        "M6A-I1.A1",
        "M6A-I1.A2"
      ],
      "depends_on": [
        "T2",
        "T3",
        "T5"
      ],
      "changes": [
        {
          "path": ".github/workflows/packages.yml",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "B-ZIZMOR",
        "RED-ZIZMOR",
        "B-ACTIONLINT",
        "RED-ACTIONLINT",
        "B-CHECKSUMS",
        "RED-CHECKSUMS",
        "M-WORKFLOWS",
        "M-SDE",
        "W4-READY",
        "W4-BEH-CHECKSUMS",
        "W4-MAN-CI-REVIEW",
        "W4-MAN-SDE",
        "W4-BEH-CI-LINT",
        "W4-RED-G-actionlint-expression",
        "W4-RED-G-checksums-key",
        "W4-RED-G-zizmor-unpinned",
        "W4B-READY",
        "W4B-BEH-CHECKSUMS",
        "W4B-MAN-CI-REVIEW",
        "W4B-MAN-SDE",
        "W4B-BEH-CI-LINT",
        "W4B-RED-G-actionlint-expression",
        "W4B-RED-G-checksums-key",
        "W4B-RED-G-zizmor-unpinned"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T7",
      "purpose": "Dependabot, SECURITY.md, CONTRIBUTING.md and the security advisory link",
      "acceptance": [
        "M6A-02.A1",
        "M6A-10.A1"
      ],
      "depends_on": [
        "T2"
      ],
      "changes": [
        {
          "path": ".github/dependabot.yml",
          "action": "create"
        },
        {
          "path": "SECURITY.md",
          "action": "create"
        },
        {
          "path": "CONTRIBUTING.md",
          "action": "create"
        },
        {
          "path": ".github/ISSUE_TEMPLATE/config.yml",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "M-DEPENDABOT",
        "M-DOCS",
        "W4-READY",
        "W4-MAN-DEPENDABOT",
        "W4-MAN-DOCS",
        "W4B-READY",
        "W4B-MAN-DEPENDABOT",
        "W4B-MAN-DOCS"
      ],
      "blocker": null,
      "superseded_by": null
    }
  ],
  "evidence": [
    {
      "id": "R-READY-1",
      "acceptance": [
        "M6A-01.A1",
        "M6A-01.A2",
        "M6A-01.A3",
        "M6A-02.A1",
        "M6A-03.A1",
        "M6A-04.A1",
        "M6A-04.A2",
        "M6A-05.A1",
        "M6A-05.A2",
        "M6A-06.A1",
        "M6A-06.A2",
        "M6A-06.A3",
        "M6A-07.A1",
        "M6A-08.A1",
        "M6A-08.A2",
        "M6A-09.A1",
        "M6A-10.A1",
        "M6A-10.A2",
        "M6A-11.A1",
        "M6A-12.A1",
        "M6A-13.A1",
        "M6A-15.A1",
        "M6A-I1.A1",
        "M6A-I1.A2"
      ],
      "kind": "readiness",
      "status": "stale",
      "command": [],
      "method": "Requirements review of M6A-01..M6A-15 (less M6A-14, moved to M1A) against the assessment, the roadmap's owner decisions, file ownership and rules, the coordinator's brief, and other plans' notes to M6A: every finding re-checked on 4fdf790 (findings-recheck.log, mypy-baseline.log, pytest-werror-4fdf790.log), conflicts and gaps decided (readiness.md decisions 1-10), failure behaviour, terminology, scope and coverage checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m6a/readiness.md",
        "sha256": "4daf4249e153abc687a75e006f04a7a7dab00162886a9623dfe4a43a9f8d51e3"
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
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        }
      ],
      "scope_sha256": "4885c9534e60fb4b384664c8fca2d673b897bdbc9eecaddc822832cb6483f1f9",
      "red": null,
      "reason": "Bound to the plan before its results, the merge of fc7fc3c and the drilled files as inputs; superseded by R-READY-2 after the re-review at closure."
    },
    {
      "id": "R-READY-2",
      "acceptance": [
        "M6A-01.A1",
        "M6A-01.A2",
        "M6A-01.A3",
        "M6A-02.A1",
        "M6A-03.A1",
        "M6A-04.A1",
        "M6A-04.A2",
        "M6A-05.A1",
        "M6A-05.A2",
        "M6A-06.A1",
        "M6A-06.A2",
        "M6A-06.A3",
        "M6A-07.A1",
        "M6A-08.A1",
        "M6A-08.A2",
        "M6A-09.A1",
        "M6A-10.A1",
        "M6A-10.A2",
        "M6A-11.A1",
        "M6A-12.A1",
        "M6A-13.A1",
        "M6A-15.A1",
        "M6A-I1.A1",
        "M6A-I1.A2"
      ],
      "kind": "readiness",
      "status": "stale",
      "command": [],
      "method": "Requirements review repeated at closure on the merged tree (fc7fc3c, then c6ca786): readiness.md's re-review section; the 15 requirements and 24 criteria unchanged in intent, three amended in detail (M6A-06.A3 made manual, M6A-04.A2 coverage on the 3.14 legs, M6A-01.A2 xvfb, libxtst6 and dbus-x11), and the drilled files declared as work inputs.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m6a/readiness.md",
        "sha256": "da69ac57a566c0bc335206186e4b1566a62f6e6090d40ace3655a4b02e08988d"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        }
      ],
      "scope_sha256": "5fea0f739ac821f4482e76b7daa7c6e694d254fa74a558224458076003fcba0f",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "B-ZIZMOR",
      "acceptance": [
        "M6A-01.A1",
        "M6A-12.A1"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "zizmor",
        "--no-online-audits",
        ".github"
      ],
      "method": "zizmor 1.31.1 audited .github offline at its regular persona: no findings, so no unpinned action and no checkout keeping credentials (unpinned-uses, artipacked).",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/workflow-lint.log",
        "sha256": "27b0f27c27e33b9e53ec398c5ed9e6be4386b67fdf1a965a4a5f8cca2facee60"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
        },
        {
          "path": ".github/workflows/packages.yml",
          "sha256": "79530800d34ee2a4bebbfbf404ef287417678d3e8112a054c3ff14c2674be632"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "0f685010773f51d4d56a5b00b03eb7c5c5151e88b65d380107bee2ae42d70121",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "RED-ZIZMOR",
      "acceptance": [
        "M6A-01.A1",
        "M6A-12.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "docs/delivery/reports/m6a/gate_drills.py",
        "--coverage-data",
        "build/m6a-coverage/.coverage.combined",
        "--build-python",
        "<venv with requirements-build.txt>/python.exe"
      ],
      "method": "Gate drill G-zizmor-unpinned (gate_drills.py): green, then the mutation in a temporary copy (the tree untouched, its file's bytes checked after), then restored green; the drill runner exits 0 only when all three hold. The drilled check: C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\zizmor.exe --no-online-audits .github",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/gate-drills.log",
        "sha256": "4a1f1a3b631565aa6c4a6bae8941be1432f2a93d37d278406d74cec8742156ea"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
        },
        {
          "path": ".github/workflows/packages.yml",
          "sha256": "79530800d34ee2a4bebbfbf404ef287417678d3e8112a054c3ff14c2674be632"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "0f685010773f51d4d56a5b00b03eb7c5c5151e88b65d380107bee2ae42d70121",
      "red": {
        "mutation": "the lint job's checkout pinned to the tag v7 instead of its commit",
        "baseline_exit": 0,
        "mutated_exit": 14,
        "restored_exit": 0,
        "expected_diagnostic": "unpinned-uses",
        "observed_diagnostic": "error[unpinned-uses]: unpinned action reference",
        "before": [
          {
            "path": ".github/workflows/ci.yml",
            "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
          }
        ],
        "mutated": [
          {
            "path": ".github/workflows/ci.yml",
            "sha256": "89a1cfa59b16a30181570647ee0d97aa8b768eb9fde5c686477a0426f32e7a4d"
          }
        ],
        "after": [
          {
            "path": ".github/workflows/ci.yml",
            "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "B-PYTEST-WIN",
      "acceptance": [
        "M6A-01.A3"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider"
      ],
      "method": "The whole suite on Windows 11 with pyproject.toml's settings: the session header shows the 120 s timeout, the summary lists every skip's reason, ResourceWarnings appear in the warnings summary without failing, and every test passes.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/pytest-windows-final.log",
        "sha256": "06c13d412beb5464789d5cb31e04e82b679ffb07283ca37058094a2e57af1f2b"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        }
      ],
      "scope_sha256": "9533479d20765331e05367c34adb9ed6e2e9c148cd710f0a97f3718bcb97c5b4",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "RED-WARNINGS",
      "acceptance": [
        "M6A-01.A3"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m6a/drill-spec.json",
        "--log",
        "docs/delivery/reports/m6a/drills.log",
        "--python",
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe"
      ],
      "method": "Harness drill M6A-01-warnings (tests/drills/run.py, drill-spec.json): green, then the mutation in a temporary copy (the tree untouched, its file's bytes checked after), then restored green; the drill runner exits 0 only when all three hold. The drilled check: C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_packaging.py::test_release_notes_pin_the_pipx_install_to_the_release",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/drills.log",
        "sha256": "43181bb7d354af780f80861d7fc0732ea907ed7237281a965c395729fb27edc9"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        }
      ],
      "scope_sha256": "9533479d20765331e05367c34adb9ed6e2e9c148cd710f0a97f3718bcb97c5b4",
      "red": {
        "mutation": "in chatmon/changelog.py, '    key = version_key(version)' replaced with '    __import__(\"warnings\").warn(\"an old way to call find\", DeprecationWarning, stacklevel=2)\\n    key = version_key(version)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DeprecationWarning: an old way to call find",
        "observed_diagnostic": "E       DeprecationWarning: an old way to call find",
        "before": [
          {
            "path": "chatmon/changelog.py",
            "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/changelog.py",
            "sha256": "c1b980e7f12bccf6676e6ae09c3e0bc9c51b3724c419152f549c2c84ad955471"
          }
        ],
        "after": [
          {
            "path": "chatmon/changelog.py",
            "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "RED-MARKS",
      "acceptance": [
        "M6A-01.A3"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "docs/delivery/reports/m6a/gate_drills.py",
        "--coverage-data",
        "build/m6a-coverage/.coverage.combined",
        "--build-python",
        "<venv with requirements-build.txt>/python.exe"
      ],
      "method": "Gate drill G-pytest-strict-markers: green, then the mutation in a temporary copy (the tree untouched, its file's bytes checked after), then restored green; the drill runner exits 0 only when all three hold. The drilled check: C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider tests/test_cli.py",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/gate-drills.log",
        "sha256": "4a1f1a3b631565aa6c4a6bae8941be1432f2a93d37d278406d74cec8742156ea"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        }
      ],
      "scope_sha256": "9533479d20765331e05367c34adb9ed6e2e9c148cd710f0a97f3718bcb97c5b4",
      "red": {
        "mutation": "an unregistered mark on test_cli.py's first test",
        "baseline_exit": 0,
        "mutated_exit": 2,
        "restored_exit": 0,
        "expected_diagnostic": "'drillmark' not found in `markers` configuration option",
        "observed_diagnostic": "'drillmark' not found in `markers` configuration option",
        "before": [
          {
            "path": "tests/test_cli.py",
            "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
          }
        ],
        "mutated": [
          {
            "path": "tests/test_cli.py",
            "sha256": "176ef7540e4b1637b7972b5936daf90c48a51f15b9884bb73e02ff7316583a59"
          }
        ],
        "after": [
          {
            "path": "tests/test_cli.py",
            "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "B-DISTRO-UBUNTU",
      "acceptance": [
        "M6A-03.A1"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "podman",
        "run",
        "--rm",
        "-v",
        "<tree>:/src:ro",
        "ubuntu:24.04",
        "sh",
        "/src/.github/scripts/distro-tests.sh"
      ],
      "method": "The distro job's script in a fresh ubuntu:24.04 container (podman in WSL Arch standing in for docker), on an LF snapshot of the merged tree without art/ and docs/: Ubuntu's python3-pyqt6 (PyQt6 6.6.1 on Qt 6.4.2) installed, the whole suite run as an ordinary user, pytest's status returned.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/final-distro-ubuntu-24.04.log",
        "sha256": "86ca0ae2a3ce3493b42e55e9988bd3845ade11da4907dbd370c8e7374574a354"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "9a340ca37fd9b0b8963bf3a4db0efe37eb5db56bd475f8bee7062ec8a72b9efb",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "B-DISTRO-DEBIAN",
      "acceptance": [
        "M6A-03.A1"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "podman",
        "run",
        "--rm",
        "-v",
        "<tree>:/src:ro",
        "debian:trixie",
        "sh",
        "/src/.github/scripts/distro-tests.sh"
      ],
      "method": "The distro job's script in a fresh debian:trixie container (podman in WSL Arch standing in for docker), on a snapshot of the merged tree without art/ and docs/: Debian's python3-pyqt6 installed, the whole suite run as an ordinary user, pytest's status returned.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/final-distro-debian-trixie.log",
        "sha256": "d1da608ec1a5ebe8b4b92fd199985ba9249a7b27606e0c574677b9e54f59aaf2"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "9a340ca37fd9b0b8963bf3a4db0efe37eb5db56bd475f8bee7062ec8a72b9efb",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "B-DISTRO-FEDORA",
      "acceptance": [
        "M6A-03.A1"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "podman",
        "run",
        "--rm",
        "-v",
        "<tree>:/src:ro",
        "fedora:44",
        "sh",
        "/src/.github/scripts/distro-tests.sh"
      ],
      "method": "The same in a fresh fedora:44 container: Fedora's python3-pyqt6, the whole suite as an ordinary user.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/final-distro-fedora-44.log",
        "sha256": "373b7089fc8f924bdabed5f5d0b36b30f1a0cad44e66e8d04897fd8acc83ceb1"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "9a340ca37fd9b0b8963bf3a4db0efe37eb5db56bd475f8bee7062ec8a72b9efb",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "RED-DISTRO",
      "acceptance": [
        "M6A-03.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "sh",
        "run-distro-campaign.sh"
      ],
      "method": "Drill on the distro script's failure path (podman run --rm -v <tree>:/src:ro debian:trixie sh /src/.github/scripts/distro-tests.sh): debian:trixie green on the untouched tree, then a copy with one tests/test_cli.py assertion broken, where the script exited 1, then the untouched tree green again. The containers ran an LF snapshot of the tree; the worktree's file is the same text with CRLF ends.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/final-distro-drill.log",
        "sha256": "99fdce8c0fc76f861d3e1a206aea831ae1682a8c936ef051f79d4cb95bb28284"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "9a340ca37fd9b0b8963bf3a4db0efe37eb5db56bd475f8bee7062ec8a72b9efb",
      "red": {
        "mutation": "in a copy, tests/test_cli.py's assert cli.main([\"--help\"]) == 0 made == 1",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "1 failed, ",
        "observed_diagnostic": "1 failed, 1077 passed, 112 skipped, 23 warnings in 145.29s (0:02:25)",
        "before": [
          {
            "path": "tests/test_cli.py",
            "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
          }
        ],
        "mutated": [
          {
            "path": "tests/test_cli.py",
            "sha256": "faa2c56764fab8aa0201b3eaef694c285427510e83dde5231b40705f0800c88c"
          }
        ],
        "after": [
          {
            "path": "tests/test_cli.py",
            "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "B-COVERAGE",
      "acceptance": [
        "M6A-04.A1"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "coverage",
        "combine",
        "--keep",
        ".coverage.windows",
        ".coverage.linux"
      ],
      "method": "The whole suite under coverage on Windows and on Linux (WSL Arch, the hash-locked test list, under xvfb-run), combined: each module listed once, Windows' and POSIX paths mapped together; coverage report passes fail_under = 72.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/coverage.log",
        "sha256": "646e0c7865041547f5a7291724fa210e7cc89a720bb761a01833818aa044d91f"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        }
      ],
      "scope_sha256": "9533479d20765331e05367c34adb9ed6e2e9c148cd710f0a97f3718bcb97c5b4",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "RED-FLOOR",
      "acceptance": [
        "M6A-04.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "docs/delivery/reports/m6a/gate_drills.py",
        "--coverage-data",
        "build/m6a-coverage/.coverage.combined",
        "--build-python",
        "<venv with requirements-build.txt>/python.exe"
      ],
      "method": "Gate drill G-coverage-floor: green, then the mutation in a temporary copy (the tree untouched, its file's bytes checked after), then restored green; the drill runner exits 0 only when all three hold. The drilled check: C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe -m coverage report --data-file build/m6a-coverage/.coverage.combined",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/gate-drills.log",
        "sha256": "4a1f1a3b631565aa6c4a6bae8941be1432f2a93d37d278406d74cec8742156ea"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        }
      ],
      "scope_sha256": "9533479d20765331e05367c34adb9ed6e2e9c148cd710f0a97f3718bcb97c5b4",
      "red": {
        "mutation": "fail_under raised to 99, above the measured total",
        "baseline_exit": 0,
        "mutated_exit": 2,
        "restored_exit": 0,
        "expected_diagnostic": "Coverage failure: total of",
        "observed_diagnostic": "Coverage failure: total of 82.7 is less than fail-under=99.0",
        "before": [
          {
            "path": "pyproject.toml",
            "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
          }
        ],
        "mutated": [
          {
            "path": "pyproject.toml",
            "sha256": "20b11c04e39c81dca6b08caa3b0589a86fa5425c54e41d4fe1c8af1b233d20e8"
          }
        ],
        "after": [
          {
            "path": "pyproject.toml",
            "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "B-NEW-TESTS",
      "acceptance": [
        "M6A-05.A1",
        "M6A-06.A1",
        "M6A-10.A2",
        "M6A-08.A1"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        "-v",
        "tests/test_requirements.py",
        "tests/test_package_data.py"
      ],
      "method": "tests/test_requirements.py (every lock pinned and hashed, at its .in versions, one version per package across the locks, the dev extra equal to requirements-dev.in, setuptools within the build-system range) and tests/test_package_data.py (every tracked file taken by a glob, every glob used) pass; the dist tests skip without CHATMON_DIST, saying so.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/new-tests.log",
        "sha256": "47af3d6e73a275ed461e6e6bd91a9fb55ede7ba9246616765c2d3c5406235fd9"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "a1c661819c8ea446715a003235a61cd284110bba205bca75f0f958bebeb053f0",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "RED-QT",
      "acceptance": [
        "M6A-05.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m6a/drill-spec.json",
        "--log",
        "docs/delivery/reports/m6a/drills.log",
        "--python",
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe"
      ],
      "method": "Harness drill M6A-05-qt: green, then the mutation in a temporary copy (the tree untouched, its file's bytes checked after), then restored green; the drill runner exits 0 only when all three hold. The drilled check: C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_requirements.py::test_a_package_in_more_than_one_lock_is_the_same_version_in_each",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/drills.log",
        "sha256": "43181bb7d354af780f80861d7fc0732ea907ed7237281a965c395729fb27edc9"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "91abf7c3e78a4ac3b8d62a12c2c5b17d2e3283db8e0cd9e230a9317333fcdc45",
      "red": {
        "mutation": "in packaging/requirements-test.txt, 'pyqt6==6.11.0 \\\\' replaced with 'pyqt6==6.12.0 \\\\'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "locked at different versions",
        "observed_diagnostic": "E       AssertionError: locked at different versions: {'pyqt6': {'requirements': '6.11.0', 'requirements-test': '6.12.0', 'requirements-dev': '6.11.0'}}",
        "before": [
          {
            "path": "packaging/requirements-test.txt",
            "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
          }
        ],
        "mutated": [
          {
            "path": "packaging/requirements-test.txt",
            "sha256": "c3d80af9ac38db9b4b11c1334657ae36f66cb444320d6ae624e1e7beaec569b0"
          }
        ],
        "after": [
          {
            "path": "packaging/requirements-test.txt",
            "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "RED-HASH",
      "acceptance": [
        "M6A-06.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m6a/drill-spec.json",
        "--log",
        "docs/delivery/reports/m6a/drills.log",
        "--python",
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe"
      ],
      "method": "Harness drill M6A-06-hash: green, then the mutation in a temporary copy (the tree untouched, its file's bytes checked after), then restored green; the drill runner exits 0 only when all three hold. The drilled check: C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_requirements.py::test_every_locked_requirement_is_pinned_and_hashed",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/drills.log",
        "sha256": "43181bb7d354af780f80861d7fc0732ea907ed7237281a965c395729fb27edc9"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "91abf7c3e78a4ac3b8d62a12c2c5b17d2e3283db8e0cd9e230a9317333fcdc45",
      "red": {
        "mutation": "in packaging/requirements-build.txt, 'wheel==0.48.0 \\\\' replaced with 'wheel==0.48.0  # \\\\'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "requirements-build.txt has no hash for ['wheel']",
        "observed_diagnostic": "E           AssertionError: requirements-build.txt has no hash for ['wheel']: pip --require-hashes would refuse it",
        "before": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
          }
        ],
        "mutated": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "cb4b66cf0f4fea9d3649ca600f01137d24634c6cb7b76e07164281d22b0e9055"
          }
        ],
        "after": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "RED-STALE",
      "acceptance": [
        "M6A-06.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m6a/drill-spec.json",
        "--log",
        "docs/delivery/reports/m6a/drills.log",
        "--python",
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe"
      ],
      "method": "Harness drill M6A-06-stale: green, then the mutation in a temporary copy (the tree untouched, its file's bytes checked after), then restored green; the drill runner exits 0 only when all three hold. The drilled check: C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_requirements.py::test_each_lock_holds_the_versions_its_in_file_names",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/drills.log",
        "sha256": "43181bb7d354af780f80861d7fc0732ea907ed7237281a965c395729fb27edc9"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "91abf7c3e78a4ac3b8d62a12c2c5b17d2e3283db8e0cd9e230a9317333fcdc45",
      "red": {
        "mutation": "in packaging/requirements-build.txt, 'setuptools==84.2.1 \\\\' replaced with 'setuptools==84.2.0 \\\\'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "requirements-build.txt doesn't lock these at the versions requirements-build.in pins",
        "observed_diagnostic": "E           AssertionError: requirements-build.txt doesn't lock these at the versions requirements-build.in pins: {'setuptools': '84.2.1'}",
        "before": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
          }
        ],
        "mutated": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "e00f483b8019c215f05414102f6a04d218c0c2ee4b46120c135c3d90c494c005"
          }
        ],
        "after": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "RED-DEV",
      "acceptance": [
        "M6A-10.A2"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m6a/drill-spec.json",
        "--log",
        "docs/delivery/reports/m6a/drills.log",
        "--python",
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe"
      ],
      "method": "Harness drill M6A-10-dev: green, then the mutation in a temporary copy (the tree untouched, its file's bytes checked after), then restored green; the drill runner exits 0 only when all three hold. The drilled check: C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_requirements.py::test_the_dev_extra_pins_what_ci_runs",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/drills.log",
        "sha256": "43181bb7d354af780f80861d7fc0732ea907ed7237281a965c395729fb27edc9"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "91abf7c3e78a4ac3b8d62a12c2c5b17d2e3283db8e0cd9e230a9317333fcdc45",
      "red": {
        "mutation": "in pyproject.toml, '\"ruff==0.17.3\",' replaced with '\"ruff==0.17.4\",'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "dev extra: ruff==0.17.4, but CI runs ruff==0.17.3",
        "observed_diagnostic": "E           AssertionError: dev extra: ruff==0.17.4, but CI runs ruff==0.17.3",
        "before": [
          {
            "path": "pyproject.toml",
            "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
          }
        ],
        "mutated": [
          {
            "path": "pyproject.toml",
            "sha256": "ead53a6f08cc478cc53ab3822e2bda39a62f538f4b9eab3fb46cc22bc10bf7ce"
          }
        ],
        "after": [
          {
            "path": "pyproject.toml",
            "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "RED-GLOB",
      "acceptance": [
        "M6A-08.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "tests/drills/run.py",
        "docs/delivery/reports/m6a/drill-spec.json",
        "--log",
        "docs/delivery/reports/m6a/drills.log",
        "--python",
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe"
      ],
      "method": "Harness drill M6A-08-glob: green, then the mutation in a temporary copy (the tree untouched, its file's bytes checked after), then restored green; the drill runner exits 0 only when all three hold. The drilled check: C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_package_data.py::test_every_tracked_file_of_chatmon_ships",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/drills.log",
        "sha256": "43181bb7d354af780f80861d7fc0732ea907ed7237281a965c395729fb27edc9"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "a1c661819c8ea446715a003235a61cd284110bba205bca75f0f958bebeb053f0",
      "red": {
        "mutation": "in pyproject.toml, '\"bubbles/manifest.json\",' replaced with ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "bubbles/manifest.json",
        "observed_diagnostic": "E       AssertionError: no package-data glob in pyproject.toml takes these, so pip and pipx installs would lack them: ['bubbles/manifest.json']",
        "before": [
          {
            "path": "pyproject.toml",
            "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
          }
        ],
        "mutated": [
          {
            "path": "pyproject.toml",
            "sha256": "d995a4e0c2dd1c8e4850943ceb0b666e21573ef1c51efc43af511495171f9f3f"
          }
        ],
        "after": [
          {
            "path": "pyproject.toml",
            "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "B-INSTALL",
      "acceptance": [
        "M6A-06.A2"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pip",
        "install",
        "--require-hashes",
        "--no-build-isolation",
        "-r",
        "packaging/requirements.txt"
      ],
      "method": "A fresh venv on Windows: requirements-build.txt, then requirements.txt with --no-build-isolation, both --require-hashes, as the Windows job does; Nuitka built from its source with the locked setuptools and wheel. The test list installed the same way on Linux.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/install-windows-build.log",
        "sha256": "4ba353a33abceac5aa8af35c8ea61119b85eeef3de67e9758b4e0f49c3f834af"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "91abf7c3e78a4ac3b8d62a12c2c5b17d2e3283db8e0cd9e230a9317333fcdc45",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "RED-PIP",
      "acceptance": [
        "M6A-06.A2"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "docs/delivery/reports/m6a/gate_drills.py",
        "--coverage-data",
        "build/m6a-coverage/.coverage.combined",
        "--build-python",
        "<venv with requirements-build.txt>/python.exe"
      ],
      "method": "Gate drill G-pip-hashes: green, then the mutation in a temporary copy (the tree untouched, its file's bytes checked after), then restored green; the drill runner exits 0 only when all three hold. The drilled check: C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe -m pip install --dry-run --ignore-installed --no-cache-dir --require-hashes -r packaging/requirements-build.txt",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/gate-drills.log",
        "sha256": "4a1f1a3b631565aa6c4a6bae8941be1432f2a93d37d278406d74cec8742156ea"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "91abf7c3e78a4ac3b8d62a12c2c5b17d2e3283db8e0cd9e230a9317333fcdc45",
      "red": {
        "mutation": "every hash of wheel 0.48.0 in requirements-build.txt changed",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "THESE PACKAGES DO NOT MATCH THE HASHES FROM THE REQUIREMENTS FILE",
        "observed_diagnostic": "ERROR: THESE PACKAGES DO NOT MATCH THE HASHES FROM THE REQUIREMENTS FILE. If you have updated the package versions, please update the hashes. Otherwise, examine the package contents carefully; someone may have tampered with them.",
        "before": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
          }
        ],
        "mutated": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "e381417403dec7ee8fc699cb26bcfd605b52c70fd9ae8f44d63aef5a53570367"
          }
        ],
        "after": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "B-WHEEL-JOB",
      "acceptance": [
        "M6A-08.A2",
        "M6A-09.A1"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        "-v",
        "tests/test_package_data.py"
      ],
      "method": "The wheel job on a copy of the tree: build --no-isolation with the locked tools, twine check --strict, then tests/test_package_data.py with CHATMON_DIST: every tracked file in the wheel and the sdist, nothing else in the wheel, only chatmon and chatmonw installed; the root script is untracked and the migration code present.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wheel-job.log",
        "sha256": "2cd6ce16c395267b8978b794bd6a74e71631111fcc013fec6468754879c1e53f"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "a1c661819c8ea446715a003235a61cd284110bba205bca75f0f958bebeb053f0",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "RED-WHEEL",
      "acceptance": [
        "M6A-08.A2"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "docs/delivery/reports/m6a/gate_drills.py",
        "--coverage-data",
        "build/m6a-coverage/.coverage.combined",
        "--build-python",
        "<venv with requirements-build.txt>/python.exe"
      ],
      "method": "Build drill W-wheel-sounds: green, then the mutation in a temporary copy (the tree untouched, its file's bytes checked after), then restored green; the drill runner exits 0 only when all three hold. The drilled check: C:\\Program Files\\Git\\usr\\bin\\bash.exe -ec 'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/venv-win-build2/Scripts/python.exe' -m build --no-isolation --outdir dist . >build.log 2>&1 || { tail -20 build.log; exit 1; }; 'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/venv-win-build2/Scripts/python.exe' -m twine check --strict dist/*; CHATMON_DIST=dist 'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/venv-win-build2/Scripts/python.exe' -m pytest -q -p no:cacheprovider tests/test_package_data.py -k 'wheel_holds'",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/gate-drills.log",
        "sha256": "4a1f1a3b631565aa6c4a6bae8941be1432f2a93d37d278406d74cec8742156ea"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "a1c661819c8ea446715a003235a61cd284110bba205bca75f0f958bebeb053f0",
      "red": {
        "mutation": "the sounds/*.wav package-data glob removed, so the wheel is built without the sounds",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "AssertionError: left out of the wheel",
        "observed_diagnostic": "E       AssertionError: left out of the wheel",
        "before": [
          {
            "path": "pyproject.toml",
            "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
          }
        ],
        "mutated": [
          {
            "path": "pyproject.toml",
            "sha256": "600043d308e7d75671c95311f70f5d137fa0b8f303bd68766e5ba5dc10a4092a"
          }
        ],
        "after": [
          {
            "path": "pyproject.toml",
            "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "RED-TWINE",
      "acceptance": [
        "M6A-08.A2"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "docs/delivery/reports/m6a/gate_drills.py",
        "--coverage-data",
        "build/m6a-coverage/.coverage.combined",
        "--build-python",
        "<venv with requirements-build.txt>/python.exe"
      ],
      "method": "Build drill W-twine-markup: green, then the mutation in a temporary copy (the tree untouched, its file's bytes checked after), then restored green; the drill runner exits 0 only when all three hold. The drilled check: C:\\Program Files\\Git\\usr\\bin\\bash.exe -ec 'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/venv-win-build2/Scripts/python.exe' -m build --no-isolation --outdir dist . >build.log 2>&1 || { tail -20 build.log; exit 1; }; 'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/venv-win-build2/Scripts/python.exe' -m twine check --strict dist/*; CHATMON_DIST=dist 'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/venv-win-build2/Scripts/python.exe' -m pytest -q -p no:cacheprovider tests/test_package_data.py -k 'wheel_holds'",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/gate-drills.log",
        "sha256": "4a1f1a3b631565aa6c4a6bae8941be1432f2a93d37d278406d74cec8742156ea"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "a1c661819c8ea446715a003235a61cd284110bba205bca75f0f958bebeb053f0",
      "red": {
        "mutation": "the README declared as reStructuredText, which its Markdown isn't",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "`long_description` has syntax errors in markup",
        "observed_diagnostic": "ERROR    `long_description` has syntax errors in markup and would not be",
        "before": [
          {
            "path": "pyproject.toml",
            "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
          }
        ],
        "mutated": [
          {
            "path": "pyproject.toml",
            "sha256": "69c8acbe2058f5d5854dcd733d6ce33e08fb729f5aa1f75981ee062dfc3830c7"
          }
        ],
        "after": [
          {
            "path": "pyproject.toml",
            "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "RED-COMMANDS",
      "acceptance": [
        "M6A-09.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "docs/delivery/reports/m6a/gate_drills.py",
        "--coverage-data",
        "build/m6a-coverage/.coverage.combined",
        "--build-python",
        "<venv with requirements-build.txt>/python.exe"
      ],
      "method": "Build drill W-entry-points: green, then the mutation in a temporary copy (the tree untouched, its file's bytes checked after), then restored green; the drill runner exits 0 only when all three hold. The drilled check: C:\\Program Files\\Git\\usr\\bin\\bash.exe -ec 'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/venv-win-build2/Scripts/python.exe' -m build --no-isolation --outdir dist . >build.log 2>&1 || { tail -20 build.log; exit 1; }; 'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/venv-win-build2/Scripts/python.exe' -m twine check --strict dist/*; CHATMON_DIST=dist 'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/venv-win-build2/Scripts/python.exe' -m pytest -q -p no:cacheprovider tests/test_package_data.py -k 'commands'",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/gate-drills.log",
        "sha256": "4a1f1a3b631565aa6c4a6bae8941be1432f2a93d37d278406d74cec8742156ea"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "a1c661819c8ea446715a003235a61cd284110bba205bca75f0f958bebeb053f0",
      "red": {
        "mutation": "the penguin-companion console script put back",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "'penguin-companion': ('console_scripts', 'chatmon.cli:main')",
        "observed_diagnostic": "E         {'penguin-companion': ('console_scripts', 'chatmon.cli:main')}",
        "before": [
          {
            "path": "pyproject.toml",
            "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
          }
        ],
        "mutated": [
          {
            "path": "pyproject.toml",
            "sha256": "c97bad7df06c672a817f971559ab7f9dae334b18a677ab3667c5c38b5caa05b7"
          }
        ],
        "after": [
          {
            "path": "pyproject.toml",
            "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "B-ACTIONLINT",
      "acceptance": [
        "M6A-12.A1"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "actionlint",
        "-verbose"
      ],
      "method": "actionlint 1.7.12 on Linux with shellcheck 0.11.0 checking every run: script: no errors in either workflow.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/workflow-lint.log",
        "sha256": "27b0f27c27e33b9e53ec398c5ed9e6be4386b67fdf1a965a4a5f8cca2facee60"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
        },
        {
          "path": ".github/workflows/packages.yml",
          "sha256": "79530800d34ee2a4bebbfbf404ef287417678d3e8112a054c3ff14c2674be632"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "0f685010773f51d4d56a5b00b03eb7c5c5151e88b65d380107bee2ae42d70121",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "RED-ACTIONLINT",
      "acceptance": [
        "M6A-12.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "docs/delivery/reports/m6a/gate_drills.py",
        "--coverage-data",
        "build/m6a-coverage/.coverage.combined",
        "--build-python",
        "<venv with requirements-build.txt>/python.exe"
      ],
      "method": "Gate drill G-actionlint-expression: green, then the mutation in a temporary copy (the tree untouched, its file's bytes checked after), then restored green; the drill runner exits 0 only when all three hold. The drilled check: actionlint .github/workflows/ci.yml",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/gate-drills.log",
        "sha256": "4a1f1a3b631565aa6c4a6bae8941be1432f2a93d37d278406d74cec8742156ea"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
        },
        {
          "path": ".github/workflows/packages.yml",
          "sha256": "79530800d34ee2a4bebbfbf404ef287417678d3e8112a054c3ff14c2674be632"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "0f685010773f51d4d56a5b00b03eb7c5c5151e88b65d380107bee2ae42d70121",
      "red": {
        "mutation": "the types job reads matrix.platfrom, a property its matrix doesn't have",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "property \"platfrom\" is not defined",
        "observed_diagnostic": ".github/workflows/ci.yml:75:25: property \"platfrom\" is not defined in object type {platform: string} [expression]",
        "before": [
          {
            "path": ".github/workflows/ci.yml",
            "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
          }
        ],
        "mutated": [
          {
            "path": ".github/workflows/ci.yml",
            "sha256": "83c192fe1fbc771535d18c78138273fb51eb53391e516d8102c9e8beabb05e3c"
          }
        ],
        "after": [
          {
            "path": ".github/workflows/ci.yml",
            "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "B-MYPY",
      "acceptance": [
        "M6A-13.A1"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "mypy",
        "--platform",
        "linux"
      ],
      "method": "mypy 2.4.1 with pyproject.toml's settings for --platform linux, win32 and darwin: no issues in 65 files, 18 gated, 47 exempt.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/mypy.log",
        "sha256": "201cca9bb517fc7f91428866e09e19f0ff2924285b932f59a1a04e37da0fd2be"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        }
      ],
      "scope_sha256": "9533479d20765331e05367c34adb9ed6e2e9c148cd710f0a97f3718bcb97c5b4",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "RED-MYPY",
      "acceptance": [
        "M6A-13.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "docs/delivery/reports/m6a/gate_drills.py",
        "--coverage-data",
        "build/m6a-coverage/.coverage.combined",
        "--build-python",
        "<venv with requirements-build.txt>/python.exe"
      ],
      "method": "Gate drill G-mypy-gated: green, then the mutation in a temporary copy (the tree untouched, its file's bytes checked after), then restored green; the drill runner exits 0 only when all three hold. The drilled check: C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe -m mypy --platform linux --no-incremental --cache-dir <copy>/.mypy",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/gate-drills.log",
        "sha256": "4a1f1a3b631565aa6c4a6bae8941be1432f2a93d37d278406d74cec8742156ea"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        }
      ],
      "scope_sha256": "9533479d20765331e05367c34adb9ed6e2e9c148cd710f0a97f3718bcb97c5b4",
      "red": {
        "mutation": "a str assigned to an int in changelog.py, a gated module",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "chatmon\\changelog.py",
        "observed_diagnostic": "chatmon\\changelog.py:84: error: Incompatible types in assignment (expression has type \"str\", variable has type \"int\")  [assignment]",
        "before": [
          {
            "path": "chatmon/changelog.py",
            "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/changelog.py",
            "sha256": "8c25d7794410e6867a5e9b7745d5f80e0e0b5d76a421ed65b43195431629d8af"
          }
        ],
        "after": [
          {
            "path": "chatmon/changelog.py",
            "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "B-CHECKSUMS",
      "acceptance": [
        "M6A-I1.A1"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:\\Program Files\\Git\\usr\\bin\\bash.exe",
        "<copy>/run-step.sh"
      ],
      "method": "packages.yml's checksum step, extracted from the workflow and run with a throwaway Ed25519 key that the copy's chatmon/releasecheck.py trusts: it lists, signs and verifies (green runs in the log).",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/gate-drills.log",
        "sha256": "4a1f1a3b631565aa6c4a6bae8941be1432f2a93d37d278406d74cec8742156ea"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
        },
        {
          "path": ".github/workflows/packages.yml",
          "sha256": "79530800d34ee2a4bebbfbf404ef287417678d3e8112a054c3ff14c2674be632"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "0f685010773f51d4d56a5b00b03eb7c5c5151e88b65d380107bee2ae42d70121",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "RED-CHECKSUMS",
      "acceptance": [
        "M6A-I1.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "docs/delivery/reports/m6a/gate_drills.py",
        "--coverage-data",
        "build/m6a-coverage/.coverage.combined",
        "--build-python",
        "<venv with requirements-build.txt>/python.exe"
      ],
      "method": "Gate drill G-checksums-key: green, then the mutation in a temporary copy (the tree untouched, its file's bytes checked after), then restored green; the drill runner exits 0 only when all three hold. The drilled check: C:\\Program Files\\Git\\usr\\bin\\bash.exe <copy>/run-step.sh",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/gate-drills.log",
        "sha256": "4a1f1a3b631565aa6c4a6bae8941be1432f2a93d37d278406d74cec8742156ea"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
        },
        {
          "path": ".github/workflows/packages.yml",
          "sha256": "79530800d34ee2a4bebbfbf404ef287417678d3e8112a054c3ff14c2674be632"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "0f685010773f51d4d56a5b00b03eb7c5c5151e88b65d380107bee2ae42d70121",
      "red": {
        "mutation": "the checksums job looks for the key in chatmon/updates.py again, where it was before M1A moved it",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "RELEASE_SIGNING_KEY isn't a key in RELEASE_KEYS",
        "observed_diagnostic": "RELEASE_SIGNING_KEY isn't a key in RELEASE_KEYS",
        "before": [
          {
            "path": ".github/workflows/packages.yml",
            "sha256": "79530800d34ee2a4bebbfbf404ef287417678d3e8112a054c3ff14c2674be632"
          }
        ],
        "mutated": [
          {
            "path": ".github/workflows/packages.yml",
            "sha256": "e6a4f987d816082c21b059dff5c7e29f58e67e9d952fbae0dadf25ccd09429d2"
          }
        ],
        "after": [
          {
            "path": ".github/workflows/packages.yml",
            "sha256": "79530800d34ee2a4bebbfbf404ef287417678d3e8112a054c3ff14c2674be632"
          }
        ]
      },
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "M-WORKFLOWS",
      "acceptance": [
        "M6A-01.A2",
        "M6A-04.A2",
        "M6A-05.A2",
        "M6A-07.A1",
        "M6A-15.A1",
        "M6A-I1.A2"
      ],
      "kind": "manual",
      "status": "stale",
      "command": [],
      "method": "Manual review of both workflows against each done-when, line by line (workflow-review.md), with actionlint, shellcheck and zizmor clean (workflow-lint.log); the suite observed passing without art/ and docs/ (distro and Linux runs on such a tree, and the drill harness's copy).",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m6a/workflow-review.md",
        "sha256": "855862af0d0d73cfbb90e2d2fd4d5b732cb61cba02e5df9757d3a74dbdd94322"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
        },
        {
          "path": ".github/workflows/packages.yml",
          "sha256": "79530800d34ee2a4bebbfbf404ef287417678d3e8112a054c3ff14c2674be632"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "0f685010773f51d4d56a5b00b03eb7c5c5151e88b65d380107bee2ae42d70121",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "M-DEPENDABOT",
      "acceptance": [
        "M6A-02.A1"
      ],
      "kind": "manual",
      "status": "stale",
      "command": [],
      "method": "check-jsonschema 0.39.0 validated .github/dependabot.yml against SchemaStore's Dependabot schema (and rejected two deliberate errors), and the configuration was reviewed: three entries, weekly, 14-day cooldown, PyQt6 grouped, increase-if-necessary at the root.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m6a/dependabot-schema.log",
        "sha256": "3ceb11c0265b3e15cdee139b8d97e71349b87dff0756ef2e2e29ca15b917dc53"
      },
      "inputs": [
        {
          "path": ".github/ISSUE_TEMPLATE/config.yml",
          "sha256": "dfb4459764a36a156444342afc57092d314a4072359bf87a219d186c134b4af0"
        },
        {
          "path": ".github/dependabot.yml",
          "sha256": "d9ff80fb4d342e18b5cc599d88d817488ad54db633bb9f8a506fa522d95ac9ec"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "ead31a436eb5d98f9812c2684eb8dd8dafc4e497bdf694e5329091cde37a23ca"
        },
        {
          "path": "SECURITY.md",
          "sha256": "4f70d856b2157dbe76ebd4e42157fe1e38efc5aa794867119cc147660f274427"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "d0c7c68ba49b9f3153e13902e480ff7ec2d2537d9f08044ff05114472bf66030",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "M-SDE",
      "acceptance": [
        "M6A-06.A3"
      ],
      "kind": "manual",
      "status": "stale",
      "command": [],
      "method": "Two copies of one tree with different file times, each built into a wheel: different without SOURCE_DATE_EPOCH, byte-identical with it set to the commit's time, as packages.yml sets it.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m6a/source-date-epoch.log",
        "sha256": "b4b3ffafbf33d8734c8a9ca38b265eb65082154bb87e1916321dae7430ad370a"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
        },
        {
          "path": ".github/workflows/packages.yml",
          "sha256": "79530800d34ee2a4bebbfbf404ef287417678d3e8112a054c3ff14c2674be632"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "0f685010773f51d4d56a5b00b03eb7c5c5151e88b65d380107bee2ae42d70121",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "M-DOCS",
      "acceptance": [
        "M6A-10.A1"
      ],
      "kind": "manual",
      "status": "stale",
      "command": [],
      "method": "SECURITY.md, CONTRIBUTING.md and the issue chooser's config read claim by claim against the code, workflows and settings (docs-review.md); private vulnerability reporting observed enabled.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m6a/docs-review.md",
        "sha256": "5cf2dd618b73223989667ecbe8f674308ffeca1afa0f6ddcc3f573c8f7bcbfc4"
      },
      "inputs": [
        {
          "path": ".github/ISSUE_TEMPLATE/config.yml",
          "sha256": "dfb4459764a36a156444342afc57092d314a4072359bf87a219d186c134b4af0"
        },
        {
          "path": ".github/dependabot.yml",
          "sha256": "d9ff80fb4d342e18b5cc599d88d817488ad54db633bb9f8a506fa522d95ac9ec"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "ead31a436eb5d98f9812c2684eb8dd8dafc4e497bdf694e5329091cde37a23ca"
        },
        {
          "path": "SECURITY.md",
          "sha256": "4f70d856b2157dbe76ebd4e42157fe1e38efc5aa794867119cc147660f274427"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "d0c7c68ba49b9f3153e13902e480ff7ec2d2537d9f08044ff05114472bf66030",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: artifact-stale, inputs-stale, scope-stale)"
    },
    {
      "id": "M-WINUPDATE",
      "acceptance": [
        "M6A-11.A1"
      ],
      "kind": "manual",
      "status": "stale",
      "command": [],
      "method": "On Windows: the test skipped by default with its reason; with CHATMON_TEST_WINDOWS_UPDATE=1 it ran (58 s) and passed.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m6a/windows-update-optin.log",
        "sha256": "45078ebd0a6659f121ebd59f9260e946989509fe77381234bf74500612a9282f"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "81df1532f5ccab3d0a6a87cb33450760752774e6701ff5d6a4a82233984a599a"
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
          "path": "pyproject.toml",
          "sha256": "f6b599e65ffb1d8dc901a38fb3da130cb9f25b51c8a0db78a960572b082e7fa5"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "4b1c29237f7c8024a68ab5404bc6a5b305e4a6951e92da0d9dc215143e5909df"
        },
        {
          "path": "tests/test_windows.py",
          "sha256": "8ae5b99db789282121ab2069d517205160ddfc2fca8b4511ebfc045c33097d99"
        }
      ],
      "scope_sha256": "d9110224a974b8e8b81b131d1f01856f3fceda5a588a76ee4d3ca74505bffc12",
      "red": null,
      "reason": "Stale at wave 4's reconciliation (2026-11-14): the files it was bound to differ from the repository's bytes at fb19cb9 (later merges changed them, and hashes taken on a CRLF checkout never match git's LF), and the plan's rules and narrative were amended; the W4- receipts re-ran its check on fb19cb9 or read it from CI (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-READY",
      "acceptance": [
        "M6A-01.A1",
        "M6A-01.A2",
        "M6A-01.A3",
        "M6A-02.A1",
        "M6A-03.A1",
        "M6A-04.A1",
        "M6A-04.A2",
        "M6A-05.A1",
        "M6A-05.A2",
        "M6A-06.A1",
        "M6A-06.A2",
        "M6A-06.A3",
        "M6A-07.A1",
        "M6A-08.A1",
        "M6A-08.A2",
        "M6A-09.A1",
        "M6A-10.A1",
        "M6A-10.A2",
        "M6A-11.A1",
        "M6A-12.A1",
        "M6A-13.A1",
        "M6A-15.A1",
        "M6A-I1.A1",
        "M6A-I1.A2"
      ],
      "kind": "readiness",
      "status": "stale",
      "command": [],
      "method": "Requirements review again at fb19cb9 (readiness.md): M6A-01 to M6A-15 and M6A-I1 re-read against ASSESSMENT.md, the amended ROADMAP.md (the owner's security settings and the 18 required checks included) and pyproject.toml as they are now; no conflict or gap; the workflows' first runs answer most of the manual criteria; CONTRIBUTING.md has two stale sentences (docs-review.md).",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4/readiness.md",
        "sha256": "9dd63899008e93eae5e81a0e362c0059a3eabbd6967230689619a2e9e3c4ad45"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        }
      ],
      "scope_sha256": "f6ac2e2dea53566fd02189a2733c4570895d47d7b6c636ea9b1ea5966086e50b",
      "red": null,
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-BEH-WINDOWS",
      "acceptance": [
        "M6A-01.A3",
        "M6A-05.A1",
        "M6A-06.A1",
        "M6A-08.A1",
        "M6A-10.A2"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider"
      ],
      "method": "The whole suite on fb19cb9's source on this Windows 11 workstation (offscreen Qt, the shared venv), which runs every test these criteria's earlier receipts named: 1241 passed, 148 skipped (other platforms' tests, each skip with its reason), exit 0; per-test results are mapped from the log by docs/delivery/reports/wave4/cilog.py. For these criteria the suite is the check itself: pyproject.toml's settings (every warning an error, strict marks, the time limit) hold the whole run, and tests/test_requirements.py and tests/test_package_data.py passed in it. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/wave4/suite-windows.log",
        "sha256": "2d041d737c4983f9a73256c95d51463d4792262b3a54516e77e796950e87713b"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "3999b3b53eca7f25f1425c162ec51bda46cc6e5223575e0d91cdec319d3811d9",
      "red": null,
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-BEH-CHECKSUMS",
      "acceptance": [
        "M6A-I1.A1"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:/Program Files/Git/usr/bin/bash.exe",
        "<copy>/run-step.sh"
      ],
      "method": "The checksums job's own run: block from packages.yml at fb19cb9, run by gate_drills.py's G-checksums-key setup on a copy with a throwaway Ed25519 key that chatmon/releasecheck.py trusts. Its green run (gate-drills.log, section G-checksums-key) listed and signed both files and found the signing key in RELEASE_KEYS. The real job runs only on a pushed tag; it was skipped in Packages run 43675230966. Evidence for fb19cb9: two other workers are changing code at the same time, so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4/gate-drills.log",
        "sha256": "840a945920513ac5f1f78dd9f42fe873c64665fcf60e20761f53979fb42f33fb"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
        },
        {
          "path": ".github/workflows/packages.yml",
          "sha256": "94bcdad7acf546995487231368557e7275c171b241874a7f85846d3840d58ed9"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "40c4a5b25ff328cef6cec854feed9070828947dac0cd8fe7a45bdc3aeff56534",
      "red": null,
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-MAN-CI-REVIEW",
      "acceptance": [
        "M6A-01.A2",
        "M6A-04.A2",
        "M6A-05.A2",
        "M6A-07.A1",
        "M6A-15.A1",
        "M6A-I1.A2"
      ],
      "kind": "manual",
      "status": "stale",
      "command": [],
      "method": "Each criterion read again, line by line in ci-review.md, against ci.yml and packages.yml at fb19cb9, then against what the workflows' first runs did (CI run 43677128712, PR #18's Packages run 43677664360 on fb19cb9's tree, and the earlier Packages run 43675230966; their logs are in wave4/ci/). That covers: timeouts, triggers and concurrency; the coverage legs, their upload and the combine; the 3.14 legs and hash-checked installs; the sparse checkouts; the release jobs as written (their tagged run is still P-RELEASE); and the Linux packages installed, run, checked and removed.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4/ci-review.md",
        "sha256": "4ed3d735f18a43a412c85bc81a84e56c56a00150f77401f70f0ba84f77b55c5f"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
        },
        {
          "path": ".github/workflows/packages.yml",
          "sha256": "94bcdad7acf546995487231368557e7275c171b241874a7f85846d3840d58ed9"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "40c4a5b25ff328cef6cec854feed9070828947dac0cd8fe7a45bdc3aeff56534",
      "red": null,
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-MAN-DEPENDABOT",
      "acceptance": [
        "M6A-02.A1"
      ],
      "kind": "manual",
      "status": "stale",
      "command": [],
      "method": "check-jsonschema 0.39.0 validated .github/dependabot.yml, unchanged since M6A, against SchemaStore's Dependabot schema. The file was read again (ci-review.md): three entries, weekly, a 14-day cooldown, the PyQt6 groups, and versioning-strategy increase-if-necessary keeping the PyQt6>=6.5 floor. Dependabot's first run on main is still P-DEPENDABOT.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4/dependabot-schema.log",
        "sha256": "c86575d925fd9764d46d2f2d19baac57f29ec6e2a662865f04474ad8b336acdc"
      },
      "inputs": [
        {
          "path": ".github/ISSUE_TEMPLATE/config.yml",
          "sha256": "dfb4459764a36a156444342afc57092d314a4072359bf87a219d186c134b4af0"
        },
        {
          "path": ".github/dependabot.yml",
          "sha256": "d9ff80fb4d342e18b5cc599d88d817488ad54db633bb9f8a506fa522d95ac9ec"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "7f3d4190d629e649e534e9859a5263b90c1566f2ffbfd6463c7ed40c7e91d6ec"
        },
        {
          "path": "SECURITY.md",
          "sha256": "4f70d856b2157dbe76ebd4e42157fe1e38efc5aa794867119cc147660f274427"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "099a982d93950b4b490718b8f68571ea0e45a7d499d718aad5659c3fcea1ba39",
      "red": null,
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-MAN-SDE",
      "acceptance": [
        "M6A-06.A3"
      ],
      "kind": "manual",
      "status": "stale",
      "command": [],
      "method": "sde_check.py made two copies of fb19cb9's wheel inputs with file times a fortnight apart, and built each with python -m build --no-isolation --wheel on the hash-locked build tools. The wheels differed without SOURCE_DATE_EPOCH and were byte-identical with it set to the commit's time, which is how packages.yml's 'Date the build by its commit' step sets it (observed in Packages run 43675230966).",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4/source-date-epoch.log",
        "sha256": "1cd96ba9413107b0aa4042238a0f8dc4732bc2eb6bd37bc4a4c17198f4cf4f3d"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
        },
        {
          "path": ".github/workflows/packages.yml",
          "sha256": "94bcdad7acf546995487231368557e7275c171b241874a7f85846d3840d58ed9"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "40c4a5b25ff328cef6cec854feed9070828947dac0cd8fe7a45bdc3aeff56534",
      "red": null,
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-MAN-DOCS",
      "acceptance": [
        "M6A-10.A1"
      ],
      "kind": "manual",
      "status": "fail",
      "command": [],
      "method": "SECURITY.md, CONTRIBUTING.md and the issue chooser read claim by claim against fb19cb9 and the repository's settings (docs-review.md): SECURITY.md and the chooser hold; two of CONTRIBUTING.md's sentences no longer do.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4/docs-review.md",
        "sha256": "34d47ccc6b2536c90b8d4219e7add6f76c67c32c88545fa16d66324a3ee5df10"
      },
      "inputs": [
        {
          "path": ".github/ISSUE_TEMPLATE/config.yml",
          "sha256": "dfb4459764a36a156444342afc57092d314a4072359bf87a219d186c134b4af0"
        },
        {
          "path": ".github/dependabot.yml",
          "sha256": "d9ff80fb4d342e18b5cc599d88d817488ad54db633bb9f8a506fa522d95ac9ec"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "7f3d4190d629e649e534e9859a5263b90c1566f2ffbfd6463c7ed40c7e91d6ec"
        },
        {
          "path": "SECURITY.md",
          "sha256": "4f70d856b2157dbe76ebd4e42157fe1e38efc5aa794867119cc147660f274427"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "099a982d93950b4b490718b8f68571ea0e45a7d499d718aad5659c3fcea1ba39",
      "red": null,
      "reason": "CONTRIBUTING.md says pyproject.toml makes warnings errors 'all but ResourceWarning' (lines 35-36), and that mypy checks every module but those exempted with ignore_errors. Since M6B, every warning is an error and no module is exempt. Next action: whoever next edits CONTRIBUTING.md (the coordinator, or the followups worker, who owns the mypy settings) rewrites those two sentences, and then this review is repeated. Until then T7 stays implemented."
    },
    {
      "id": "W4-MAN-WINUPDATE",
      "acceptance": [
        "M6A-11.A1"
      ],
      "kind": "manual",
      "status": "stale",
      "command": [],
      "method": "On this Windows workstation at fb19cb9, tests/test_windows.py -k windows_update_check skipped by default, with its reason naming CHATMON_TEST_WINDOWS_UPDATE=1. With the variable set, it ran against Windows Update and passed; its duration is in the log.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4/windows-update-optin.log",
        "sha256": "790338d84a10c2dedcce060adaf90aee16851ab215970d83cc3ab77b96b7bcfe"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_windows.py",
          "sha256": "9c5d58910d17a72b9b186440c3266d3a67eeb25ca053e287c1fc5c1e6389699f"
        }
      ],
      "scope_sha256": "acbf5b1f69b446f893e5a8be9ae101026e9ac3dbdac090535b3e720765309123",
      "red": null,
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-BEH-CI-LINT",
      "acceptance": [
        "M6A-01.A1",
        "M6A-12.A1"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "gh",
        "run",
        "view",
        "43677128712",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132699632169",
        "--log"
      ],
      "method": "CI run 43677128712 on fb19cb9, job lint. Two steps ran on .github and passed: 'actionlint, on the workflows (and shellcheck, the runner's, on their scripts)' and 'zizmor, the workflows' security audit'. zizmor v1.31.1 completed .github/dependabot.yml, ci.yml and packages.yml with no finding, and the job succeeded. These clean runs check that every action is pinned to a commit SHA and credentials aren't persisted, and they are themselves the actionlint and zizmor runs in CI. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/ci/ci-132699632169-lint.log",
        "sha256": "15b70a10875bda3aa06928fcd7c729dc660fecf3cebf2f8dddbd82734be3f18d"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
        },
        {
          "path": ".github/workflows/packages.yml",
          "sha256": "94bcdad7acf546995487231368557e7275c171b241874a7f85846d3840d58ed9"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "40c4a5b25ff328cef6cec854feed9070828947dac0cd8fe7a45bdc3aeff56534",
      "red": null,
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-BEH-CI-DISTRO-UBUNTU",
      "acceptance": [
        "M6A-03.A1"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "gh",
        "run",
        "view",
        "43677128712",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132699632400",
        "--log"
      ],
      "method": "CI run 43677128712 on fb19cb9, job distro (ubuntu:24.04). The whole suite ran in the container on Ubuntu 24.04's own python3-pyqt6: 1259 passed, 130 skipped (each with its reason), and the job succeeded. Read from the job's log (fetched here with the command above, exit 0) by docs/delivery/reports/wave4/cilog.py, which maps pytest's progress characters onto fb19cb9's collection and checks the run's own counts and skip lines; every leg's result for these tests is in ci/observed.txt. The CI run's own platform and versions are in the log; this receipt's environment is the plan's profile, the workstation that fetched and read it (ROADMAP: evidence from elsewhere). Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/ci/ci-132699632400-distro-ubuntu-24.04.log",
        "sha256": "582663d3a1b281211df59e262bb9da32800b41ef9b8193a4862042475d12d40b"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "062a23f383f81a32376da4fbeccde82fa412ccbe94387acea99b2b591ad688fd",
      "red": null,
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-BEH-CI-DISTRO-DEBIAN",
      "acceptance": [
        "M6A-03.A1"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "gh",
        "run",
        "view",
        "43677128712",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132699632406",
        "--log"
      ],
      "method": "CI run 43677128712 on fb19cb9, job distro (debian:trixie). The whole suite ran on Debian trixie's own PyQt6: 1259 passed, 130 skipped, and the job succeeded. Read from the job's log (fetched here with the command above, exit 0) by docs/delivery/reports/wave4/cilog.py, which maps pytest's progress characters onto fb19cb9's collection and checks the run's own counts and skip lines; every leg's result for these tests is in ci/observed.txt. The CI run's own platform and versions are in the log; this receipt's environment is the plan's profile, the workstation that fetched and read it (ROADMAP: evidence from elsewhere). Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/ci/ci-132699632406-distro-debian-trixie.log",
        "sha256": "4b696d5b0fcc3bbaa98b0b6b9cc70e174d836f51d4d932ae6c2333b44e97b455"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "062a23f383f81a32376da4fbeccde82fa412ccbe94387acea99b2b591ad688fd",
      "red": null,
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-BEH-CI-DISTRO-FEDORA",
      "acceptance": [
        "M6A-03.A1"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "gh",
        "run",
        "view",
        "43677128712",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132699632424",
        "--log"
      ],
      "method": "CI run 43677128712 on fb19cb9, job distro (fedora:44). The whole suite ran on Fedora 44's own PyQt6: 1259 passed, 130 skipped, and the job succeeded. Read from the job's log (fetched here with the command above, exit 0) by docs/delivery/reports/wave4/cilog.py, which maps pytest's progress characters onto fb19cb9's collection and checks the run's own counts and skip lines; every leg's result for these tests is in ci/observed.txt. The CI run's own platform and versions are in the log; this receipt's environment is the plan's profile, the workstation that fetched and read it (ROADMAP: evidence from elsewhere). Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/ci/ci-132699632424-distro-fedora-44.log",
        "sha256": "2bd70e69b6febc906e50a1b94ad918a7be6969351bc78dba1dcfbde17dfca92a"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "062a23f383f81a32376da4fbeccde82fa412ccbe94387acea99b2b591ad688fd",
      "red": null,
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-BEH-CI-COVERAGE",
      "acceptance": [
        "M6A-04.A1"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "gh",
        "run",
        "view",
        "43677128712",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132701046885",
        "--log"
      ],
      "method": "CI run 43677128712 on fb19cb9, job coverage. It downloaded the three Python 3.14 legs' data (Windows, macOS, ubuntu-24.04-arm), combined it, wrote the table to the summary, and held the total to pyproject.toml's fail_under = 72. TOTAL was 20434 statements with 2270 missed, 86.2%, and the job succeeded. The same data, downloaded and combined here, gives the same total (wave4/coverage-combined.log). This answers P-COVERAGE-FLOOR. Raising the floor to about 84, two points under the measure, is a change to pyproject.toml, which isn't this worker's to make. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/ci/ci-132701046885-coverage.log",
        "sha256": "a597ebfc0d86e1f2cbaf1eea7d6bae42cdbce5f0910e3f73050f4d59f2107221"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        }
      ],
      "scope_sha256": "eff8538c15b2ba780e2cee4366bb88c17f4c8bab621261aa627ad4437f952f35",
      "red": null,
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-BEH-PKG-INSTALL",
      "acceptance": [
        "M6A-06.A2"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "gh",
        "run",
        "view",
        "43677664360",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132701246110",
        "--log"
      ],
      "method": "Packages run 43677664360, the pull_request run on PR #18. Its head is fb19cb9, and its test merge with main (df72534) has fb19cb9's own tree, 5d0d6b2 (reports/wave4/ci/pr18-checks.txt), so it built exactly these files. Job windows, from log line 206. It ran python -m pip install --require-hashes -r packaging/requirements-build.txt, then --require-hashes --no-build-isolation -r packaging/requirements.txt, and both succeeded. The macos-latest and macos-15-intel jobs ran the same installs. The earlier workflow_dispatch run 43675230966 on d3f6a6e (the same packaging/ and pyproject.toml) gave the same results; its logs are in reports/wave4/ci/ too. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/ci/pkgpr-132701246110-windows.log",
        "sha256": "f86b7b9f95f17df341e01f2c7d5267089c157f188ecea9e3d3f77176a0ab505b"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "1f1bf0c7eef4ade5a1d5af7b2e5310117b63bb0802352364c26505d201b1379b",
      "red": null,
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-BEH-PKG-WHEEL",
      "acceptance": [
        "M6A-08.A2",
        "M6A-09.A1"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "gh",
        "run",
        "view",
        "43677664360",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132701246303",
        "--log"
      ],
      "method": "Packages run 43677664360, the pull_request run on PR #18. Its head is fb19cb9, and its test merge with main (df72534) has fb19cb9's own tree, 5d0d6b2 (reports/wave4/ci/pr18-checks.txt), so it built exactly these files. Job python. It dated the build by the commit (SOURCE_DATE_EPOCH) and built the wheel and sdist without isolation on the hash-locked setuptools. twine check --strict passed for both (log lines 1155-1156). tests/test_package_data.py then passed on what was built (line 1183: 5 passed); those tests check that every tracked file under chatmon/ is in the wheel and that the only console script is chatmon. This resolves P-PACKAGES-PR, with the windows, macos and linux jobs, which also succeeded. The earlier workflow_dispatch run 43675230966 on d3f6a6e (the same packaging/ and pyproject.toml) gave the same results; its logs are in reports/wave4/ci/ too. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/ci/pkgpr-132701246303-python.log",
        "sha256": "bf0770ab7374b6080edb1c3ed59038b1dd1ec0c4cae43c82d0d354902ec91861"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "3999b3b53eca7f25f1425c162ec51bda46cc6e5223575e0d91cdec319d3811d9",
      "red": null,
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-BEH-CI-TYPES",
      "acceptance": [
        "M6A-13.A1"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "gh",
        "run",
        "view",
        "43677128712",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132699632396",
        "--log"
      ],
      "method": "CI run 43677128712 on fb19cb9, job types (linux): mypy --platform linux on pyproject.toml's [tool.mypy] passed. The types (win32) and types (darwin) jobs, whose logs are in wave4/ci/, passed too. M6B took every module off the exemption list, so the gate as it stands passes on all three platforms. This resolves P-MYPY-MERGES. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/ci/ci-132699632396-types-linux.log",
        "sha256": "d81d943e09c53b8354343a5758fe7e4963c03fe0e8c880933ac34e32d5a9e3b8"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        }
      ],
      "scope_sha256": "eff8538c15b2ba780e2cee4366bb88c17f4c8bab621261aa627ad4437f952f35",
      "red": null,
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-G-actionlint-expression",
      "acceptance": [
        "M6A-12.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "actionlint",
        ".github/workflows/ci.yml"
      ],
      "method": "Red drill G-actionlint-expression through gate_drills.py (a byte-for-byte copy of docs/delivery/reports/m6a/gate_drills.py in wave4/, so its logs land there and the earlier ones stay as they were) on this Windows workstation: the gate green on a temporary copy, the violation put in and the gate failing with the expected finding, the file's bytes put back and the gate green again, the tree's file checked unchanged, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4/gate-drills.log",
        "sha256": "840a945920513ac5f1f78dd9f42fe873c64665fcf60e20761f53979fb42f33fb"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
        },
        {
          "path": ".github/workflows/packages.yml",
          "sha256": "94bcdad7acf546995487231368557e7275c171b241874a7f85846d3840d58ed9"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "40c4a5b25ff328cef6cec854feed9070828947dac0cd8fe7a45bdc3aeff56534",
      "red": {
        "mutation": "G-actionlint-expression: in .github/workflows/ci.yml, the types job reads matrix.platfrom, a property its matrix doesn't have",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "property \"platfrom\" is not defined",
        "observed_diagnostic": ".github/workflows/ci.yml:75:25: property \"platfrom\" is not defined in object type {platform: string} [expression]",
        "before": [
          {
            "path": ".github/workflows/ci.yml",
            "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
          }
        ],
        "mutated": [
          {
            "path": ".github/workflows/ci.yml",
            "sha256": "83c192fe1fbc771535d18c78138273fb51eb53391e516d8102c9e8beabb05e3c"
          }
        ],
        "after": [
          {
            "path": ".github/workflows/ci.yml",
            "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-G-checksums-key",
      "acceptance": [
        "M6A-I1.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Program Files\\Git\\usr\\bin\\bash.exe",
        "<copy>/run-step.sh"
      ],
      "method": "Red drill G-checksums-key through gate_drills.py (a byte-for-byte copy of docs/delivery/reports/m6a/gate_drills.py in wave4/, so its logs land there and the earlier ones stay as they were) on this Windows workstation: the gate green on a temporary copy, the violation put in and the gate failing with the expected finding, the file's bytes put back and the gate green again, the tree's file checked unchanged, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4/gate-drills.log",
        "sha256": "840a945920513ac5f1f78dd9f42fe873c64665fcf60e20761f53979fb42f33fb"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
        },
        {
          "path": ".github/workflows/packages.yml",
          "sha256": "94bcdad7acf546995487231368557e7275c171b241874a7f85846d3840d58ed9"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "40c4a5b25ff328cef6cec854feed9070828947dac0cd8fe7a45bdc3aeff56534",
      "red": {
        "mutation": "G-checksums-key: in .github/workflows/packages.yml, the checksums job looks for the key in chatmon/updates.py again, where it was before M1A moved it",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "RELEASE_SIGNING_KEY isn't a key in RELEASE_KEYS",
        "observed_diagnostic": "RELEASE_SIGNING_KEY isn't a key in RELEASE_KEYS",
        "before": [
          {
            "path": ".github/workflows/packages.yml",
            "sha256": "94bcdad7acf546995487231368557e7275c171b241874a7f85846d3840d58ed9"
          }
        ],
        "mutated": [
          {
            "path": ".github/workflows/packages.yml",
            "sha256": "5638e82440300c20872539ed59403ae29207efb80313b757352875cfdf2bd6a9"
          }
        ],
        "after": [
          {
            "path": ".github/workflows/packages.yml",
            "sha256": "94bcdad7acf546995487231368557e7275c171b241874a7f85846d3840d58ed9"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-G-coverage-floor",
      "acceptance": [
        "M6A-04.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "coverage",
        "report",
        "--data-file",
        "build/wave4-coverage/.coverage.combined"
      ],
      "method": "Red drill G-coverage-floor through gate_drills.py (a byte-for-byte copy of docs/delivery/reports/m6a/gate_drills.py in wave4/, so its logs land there and the earlier ones stay as they were) on this Windows workstation: the gate green on a temporary copy, the violation put in and the gate failing with the expected finding, the file's bytes put back and the gate green again, the tree's file checked unchanged, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4/gate-drills.log",
        "sha256": "840a945920513ac5f1f78dd9f42fe873c64665fcf60e20761f53979fb42f33fb"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        }
      ],
      "scope_sha256": "eff8538c15b2ba780e2cee4366bb88c17f4c8bab621261aa627ad4437f952f35",
      "red": {
        "mutation": "G-coverage-floor: in pyproject.toml, fail_under raised to 99, above the measured total",
        "baseline_exit": 0,
        "mutated_exit": 2,
        "restored_exit": 0,
        "expected_diagnostic": "Coverage failure: total of",
        "observed_diagnostic": "Coverage failure: total of 86.2 is less than fail-under=99.0",
        "before": [
          {
            "path": "pyproject.toml",
            "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
          }
        ],
        "mutated": [
          {
            "path": "pyproject.toml",
            "sha256": "7b6d31b0a19eddc419bb1e43956462baa0c18246cec9534b1e8b3a9e0c8380ca"
          }
        ],
        "after": [
          {
            "path": "pyproject.toml",
            "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-G-mypy-gated",
      "acceptance": [
        "M6A-13.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "mypy",
        "--platform",
        "linux",
        "--no-incremental",
        "--cache-dir",
        "<copy>/.mypy"
      ],
      "method": "Red drill G-mypy-gated through gate_drills.py (a byte-for-byte copy of docs/delivery/reports/m6a/gate_drills.py in wave4/, so its logs land there and the earlier ones stay as they were) on this Windows workstation: the gate green on a temporary copy, the violation put in and the gate failing with the expected finding, the file's bytes put back and the gate green again, the tree's file checked unchanged, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4/gate-drills.log",
        "sha256": "840a945920513ac5f1f78dd9f42fe873c64665fcf60e20761f53979fb42f33fb"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        }
      ],
      "scope_sha256": "eff8538c15b2ba780e2cee4366bb88c17f4c8bab621261aa627ad4437f952f35",
      "red": {
        "mutation": "G-mypy-gated: in chatmon/changelog.py, a str assigned to an int in changelog.py, a gated module",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "chatmon\\changelog.py",
        "observed_diagnostic": "chatmon\\changelog.py:88: error: Incompatible types in assignment (expression has type \"str\", variable has type \"int\")  [assignment]",
        "before": [
          {
            "path": "chatmon/changelog.py",
            "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/changelog.py",
            "sha256": "42f0cd2f029dc43f098065f425e1772ef3497ceef31214d29f3b9dc3fed608b8"
          }
        ],
        "after": [
          {
            "path": "chatmon/changelog.py",
            "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-G-pip-hashes",
      "acceptance": [
        "M6A-06.A2"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pip",
        "install",
        "--dry-run",
        "--ignore-installed",
        "--no-cache-dir",
        "--require-hashes",
        "-r",
        "packaging/requirements-build.txt"
      ],
      "method": "Red drill G-pip-hashes through gate_drills.py (a byte-for-byte copy of docs/delivery/reports/m6a/gate_drills.py in wave4/, so its logs land there and the earlier ones stay as they were) on this Windows workstation: the gate green on a temporary copy, the violation put in and the gate failing with the expected finding, the file's bytes put back and the gate green again, the tree's file checked unchanged, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4/gate-drills.log",
        "sha256": "840a945920513ac5f1f78dd9f42fe873c64665fcf60e20761f53979fb42f33fb"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "1f1bf0c7eef4ade5a1d5af7b2e5310117b63bb0802352364c26505d201b1379b",
      "red": {
        "mutation": "G-pip-hashes: in packaging/requirements-build.txt, every hash of wheel 0.48.0 in requirements-build.txt changed",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "THESE PACKAGES DO NOT MATCH THE HASHES FROM THE REQUIREMENTS FILE",
        "observed_diagnostic": "ERROR: THESE PACKAGES DO NOT MATCH THE HASHES FROM THE REQUIREMENTS FILE. If you have updated the package versions, please update the hashes. Otherwise, examine the package contents carefully; someone may have tampered with them.",
        "before": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
          }
        ],
        "mutated": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "e381417403dec7ee8fc699cb26bcfd605b52c70fd9ae8f44d63aef5a53570367"
          }
        ],
        "after": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-G-pytest-strict-markers",
      "acceptance": [
        "M6A-01.A3"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_cli.py"
      ],
      "method": "Red drill G-pytest-strict-markers through gate_drills.py (a byte-for-byte copy of docs/delivery/reports/m6a/gate_drills.py in wave4/, so its logs land there and the earlier ones stay as they were) on this Windows workstation: the gate green on a temporary copy, the violation put in and the gate failing with the expected finding, the file's bytes put back and the gate green again, the tree's file checked unchanged, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4/gate-drills.log",
        "sha256": "840a945920513ac5f1f78dd9f42fe873c64665fcf60e20761f53979fb42f33fb"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        }
      ],
      "scope_sha256": "eff8538c15b2ba780e2cee4366bb88c17f4c8bab621261aa627ad4437f952f35",
      "red": {
        "mutation": "G-pytest-strict-markers: in tests/test_cli.py, an unregistered mark on test_cli.py's first test",
        "baseline_exit": 0,
        "mutated_exit": 2,
        "restored_exit": 0,
        "expected_diagnostic": "'drillmark' not found in `markers` configuration option",
        "observed_diagnostic": "'drillmark' not found in `markers` configuration option",
        "before": [
          {
            "path": "tests/test_cli.py",
            "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
          }
        ],
        "mutated": [
          {
            "path": "tests/test_cli.py",
            "sha256": "1919b97202778925b1d7495c78ed6cde1eacc54623692d004e6d866420e398fa"
          }
        ],
        "after": [
          {
            "path": "tests/test_cli.py",
            "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-G-zizmor-unpinned",
      "acceptance": [
        "M6A-01.A1",
        "M6A-12.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\zizmor.exe",
        "--no-online-audits",
        ".github"
      ],
      "method": "Red drill G-zizmor-unpinned through gate_drills.py (a byte-for-byte copy of docs/delivery/reports/m6a/gate_drills.py in wave4/, so its logs land there and the earlier ones stay as they were) on this Windows workstation: the gate green on a temporary copy, the violation put in and the gate failing with the expected finding, the file's bytes put back and the gate green again, the tree's file checked unchanged, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4/gate-drills.log",
        "sha256": "840a945920513ac5f1f78dd9f42fe873c64665fcf60e20761f53979fb42f33fb"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
        },
        {
          "path": ".github/workflows/packages.yml",
          "sha256": "94bcdad7acf546995487231368557e7275c171b241874a7f85846d3840d58ed9"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "40c4a5b25ff328cef6cec854feed9070828947dac0cd8fe7a45bdc3aeff56534",
      "red": {
        "mutation": "G-zizmor-unpinned: in .github/workflows/ci.yml, the lint job's checkout pinned to the tag v7 instead of its commit",
        "baseline_exit": 0,
        "mutated_exit": 14,
        "restored_exit": 0,
        "expected_diagnostic": "unpinned-uses",
        "observed_diagnostic": "error[unpinned-uses]: unpinned action reference",
        "before": [
          {
            "path": ".github/workflows/ci.yml",
            "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
          }
        ],
        "mutated": [
          {
            "path": ".github/workflows/ci.yml",
            "sha256": "89a1cfa59b16a30181570647ee0d97aa8b768eb9fde5c686477a0426f32e7a4d"
          }
        ],
        "after": [
          {
            "path": ".github/workflows/ci.yml",
            "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-M6A-01-warnings",
      "acceptance": [
        "M6A-01.A3"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_packaging.py::test_release_notes_pin_the_pipx_install_to_the_release"
      ],
      "method": "Red drill M6A-01-warnings through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4/drills.log",
        "sha256": "92e470cbb4f4c9cb77c3942540fe9b0258309bcdc23b006d1776ba12591b416b"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        }
      ],
      "scope_sha256": "eff8538c15b2ba780e2cee4366bb88c17f4c8bab621261aa627ad4437f952f35",
      "red": {
        "mutation": "M6A-01-warnings: in chatmon/changelog.py, '    key = version_key(version)' became '    __import__(\"warnings\").warn(\"an old way to call find\", DeprecationWarning, stacklevel=2)\\n    key = version_key(version)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DeprecationWarning: an old way to call find",
        "observed_diagnostic": "E       DeprecationWarning: an old way to call find",
        "before": [
          {
            "path": "chatmon/changelog.py",
            "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/changelog.py",
            "sha256": "dc9ce419c0c9ad8400453c4df4e18ddc0a8a4f0a5d4b6fa1eafb214619b48163"
          }
        ],
        "after": [
          {
            "path": "chatmon/changelog.py",
            "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-M6A-05-qt",
      "acceptance": [
        "M6A-05.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_requirements.py::test_a_package_in_more_than_one_lock_is_the_same_version_in_each"
      ],
      "method": "Red drill M6A-05-qt through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4/drills.log",
        "sha256": "92e470cbb4f4c9cb77c3942540fe9b0258309bcdc23b006d1776ba12591b416b"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "1f1bf0c7eef4ade5a1d5af7b2e5310117b63bb0802352364c26505d201b1379b",
      "red": {
        "mutation": "M6A-05-qt: in packaging/requirements-test.txt, 'pyqt6==6.11.0 \\\\' became 'pyqt6==6.12.0 \\\\'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "locked at different versions",
        "observed_diagnostic": ">       assert not differ, f\"locked at different versions: {differ}\"",
        "before": [
          {
            "path": "packaging/requirements-test.txt",
            "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
          }
        ],
        "mutated": [
          {
            "path": "packaging/requirements-test.txt",
            "sha256": "c3d80af9ac38db9b4b11c1334657ae36f66cb444320d6ae624e1e7beaec569b0"
          }
        ],
        "after": [
          {
            "path": "packaging/requirements-test.txt",
            "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-M6A-06-hash",
      "acceptance": [
        "M6A-06.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_requirements.py::test_every_locked_requirement_is_pinned_and_hashed"
      ],
      "method": "Red drill M6A-06-hash through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4/drills.log",
        "sha256": "92e470cbb4f4c9cb77c3942540fe9b0258309bcdc23b006d1776ba12591b416b"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "1f1bf0c7eef4ade5a1d5af7b2e5310117b63bb0802352364c26505d201b1379b",
      "red": {
        "mutation": "M6A-06-hash: in packaging/requirements-build.txt, 'wheel==0.48.0 \\\\' became 'wheel==0.48.0  # \\\\'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "requirements-build.txt has no hash for ['wheel']",
        "observed_diagnostic": "E           AssertionError: requirements-build.txt has no hash for ['wheel']: pip --require-hashes would refuse it",
        "before": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
          }
        ],
        "mutated": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "cb4b66cf0f4fea9d3649ca600f01137d24634c6cb7b76e07164281d22b0e9055"
          }
        ],
        "after": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-M6A-06-stale",
      "acceptance": [
        "M6A-06.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_requirements.py::test_each_lock_holds_the_versions_its_in_file_names"
      ],
      "method": "Red drill M6A-06-stale through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4/drills.log",
        "sha256": "92e470cbb4f4c9cb77c3942540fe9b0258309bcdc23b006d1776ba12591b416b"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "1f1bf0c7eef4ade5a1d5af7b2e5310117b63bb0802352364c26505d201b1379b",
      "red": {
        "mutation": "M6A-06-stale: in packaging/requirements-build.txt, 'setuptools==84.2.1 \\\\' became 'setuptools==84.2.0 \\\\'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "requirements-build.txt doesn't lock these at the versions requirements-build.in pins",
        "observed_diagnostic": "E           AssertionError: requirements-build.txt doesn't lock these at the versions requirements-build.in pins: {'setuptools': '84.2.1'}",
        "before": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
          }
        ],
        "mutated": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "e00f483b8019c215f05414102f6a04d218c0c2ee4b46120c135c3d90c494c005"
          }
        ],
        "after": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-M6A-08-glob",
      "acceptance": [
        "M6A-08.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_package_data.py::test_every_tracked_file_of_chatmon_ships"
      ],
      "method": "Red drill M6A-08-glob through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4/drills.log",
        "sha256": "92e470cbb4f4c9cb77c3942540fe9b0258309bcdc23b006d1776ba12591b416b"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "3999b3b53eca7f25f1425c162ec51bda46cc6e5223575e0d91cdec319d3811d9",
      "red": {
        "mutation": "M6A-08-glob: in pyproject.toml, '\"bubbles/manifest.json\",' became ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "no package-data glob in pyproject.toml takes these",
        "observed_diagnostic": ">       assert not left_out, f\"no package-data glob in pyproject.toml takes these, so pip and pipx installs would lack them: {left_out}\"",
        "before": [
          {
            "path": "pyproject.toml",
            "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
          }
        ],
        "mutated": [
          {
            "path": "pyproject.toml",
            "sha256": "58b991c8e87866a0f9655fc57ebff4fc8c87666d7c8144b4f2642349797b4a16"
          }
        ],
        "after": [
          {
            "path": "pyproject.toml",
            "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-M6A-10-dev",
      "acceptance": [
        "M6A-10.A2"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_requirements.py::test_the_dev_extra_pins_what_ci_runs"
      ],
      "method": "Red drill M6A-10-dev through tests/drills/run.py on this Windows workstation, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4/drills.log",
        "sha256": "92e470cbb4f4c9cb77c3942540fe9b0258309bcdc23b006d1776ba12591b416b"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "1f1bf0c7eef4ade5a1d5af7b2e5310117b63bb0802352364c26505d201b1379b",
      "red": {
        "mutation": "M6A-10-dev: in pyproject.toml, '\"ruff==0.17.3\",' became '\"ruff==0.17.4\",'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "dev extra: ruff==0.17.4, but CI runs ruff==0.17.3",
        "observed_diagnostic": "E           AssertionError: dev extra: ruff==0.17.4, but CI runs ruff==0.17.3",
        "before": [
          {
            "path": "pyproject.toml",
            "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
          }
        ],
        "mutated": [
          {
            "path": "pyproject.toml",
            "sha256": "5ca7025111db40e78ce8a8183304e9881c86bab2bbc820a0d8b074bbc8c8f73d"
          }
        ],
        "after": [
          {
            "path": "pyproject.toml",
            "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-W-entry-points",
      "acceptance": [
        "M6A-09.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Program Files\\Git\\usr\\bin\\bash.exe",
        "-ec",
        "'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/buildvenv/Scripts/python.exe' -m build --no-isolation --outdir dist . >build.log 2>&1 || { tail -20 build.log; exit 1; }; 'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/buildvenv/Scripts/python.exe' -m twine check --strict dist/*; CHATMON_DIST=dist 'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/buildvenv/Scripts/python.exe' -m pytest -q -p no:cacheprovider tests/test_package_data.py -k 'commands'"
      ],
      "method": "Red drill W-entry-points through gate_drills.py (a byte-for-byte copy of docs/delivery/reports/m6a/gate_drills.py in wave4/, so its logs land there and the earlier ones stay as they were) on this Windows workstation: the gate green on a temporary copy, the violation put in and the gate failing with the expected finding, the file's bytes put back and the gate green again, the tree's file checked unchanged, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4/gate-drills.log",
        "sha256": "840a945920513ac5f1f78dd9f42fe873c64665fcf60e20761f53979fb42f33fb"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "3999b3b53eca7f25f1425c162ec51bda46cc6e5223575e0d91cdec319d3811d9",
      "red": {
        "mutation": "W-entry-points: in pyproject.toml, the penguin-companion console script put back",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "'penguin-companion': ('console_scripts', 'chatmon.cli:main')",
        "observed_diagnostic": "E         {'penguin-companion': ('console_scripts', 'chatmon.cli:main')}",
        "before": [
          {
            "path": "pyproject.toml",
            "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
          }
        ],
        "mutated": [
          {
            "path": "pyproject.toml",
            "sha256": "50b997e8af040dd37286d2151b1f7a68eb4a2f27b1ec2d89cc0c10576d9f8f6b"
          }
        ],
        "after": [
          {
            "path": "pyproject.toml",
            "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-W-twine-markup",
      "acceptance": [
        "M6A-08.A2"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Program Files\\Git\\usr\\bin\\bash.exe",
        "-ec",
        "'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/buildvenv/Scripts/python.exe' -m build --no-isolation --outdir dist . >build.log 2>&1 || { tail -20 build.log; exit 1; }; 'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/buildvenv/Scripts/python.exe' -m twine check --strict dist/*; CHATMON_DIST=dist 'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/buildvenv/Scripts/python.exe' -m pytest -q -p no:cacheprovider tests/test_package_data.py -k 'wheel_holds'"
      ],
      "method": "Red drill W-twine-markup through gate_drills.py (a byte-for-byte copy of docs/delivery/reports/m6a/gate_drills.py in wave4/, so its logs land there and the earlier ones stay as they were) on this Windows workstation: the gate green on a temporary copy, the violation put in and the gate failing with the expected finding, the file's bytes put back and the gate green again, the tree's file checked unchanged, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4/gate-drills.log",
        "sha256": "840a945920513ac5f1f78dd9f42fe873c64665fcf60e20761f53979fb42f33fb"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "3999b3b53eca7f25f1425c162ec51bda46cc6e5223575e0d91cdec319d3811d9",
      "red": {
        "mutation": "W-twine-markup: in pyproject.toml, the README declared as reStructuredText, which its Markdown isn't",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "`long_description` has syntax errors in markup",
        "observed_diagnostic": "ERROR    `long_description` has syntax errors in markup and would not be",
        "before": [
          {
            "path": "pyproject.toml",
            "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
          }
        ],
        "mutated": [
          {
            "path": "pyproject.toml",
            "sha256": "b87eac77cc193be2dc5ac405ce6710a8e32ca1928fb49c8a56135e795eff2805"
          }
        ],
        "after": [
          {
            "path": "pyproject.toml",
            "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-W-wheel-sounds",
      "acceptance": [
        "M6A-08.A2"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Program Files\\Git\\usr\\bin\\bash.exe",
        "-ec",
        "'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/buildvenv/Scripts/python.exe' -m build --no-isolation --outdir dist . >build.log 2>&1 || { tail -20 build.log; exit 1; }; 'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/buildvenv/Scripts/python.exe' -m twine check --strict dist/*; CHATMON_DIST=dist 'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/buildvenv/Scripts/python.exe' -m pytest -q -p no:cacheprovider tests/test_package_data.py -k 'wheel_holds'"
      ],
      "method": "Red drill W-wheel-sounds through gate_drills.py (a byte-for-byte copy of docs/delivery/reports/m6a/gate_drills.py in wave4/, so its logs land there and the earlier ones stay as they were) on this Windows workstation: the gate green on a temporary copy, the violation put in and the gate failing with the expected finding, the file's bytes put back and the gate green again, the tree's file checked unchanged, in a temporary copy of fb19cb9's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4/gate-drills.log",
        "sha256": "840a945920513ac5f1f78dd9f42fe873c64665fcf60e20761f53979fb42f33fb"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "3999b3b53eca7f25f1425c162ec51bda46cc6e5223575e0d91cdec319d3811d9",
      "red": {
        "mutation": "W-wheel-sounds: in pyproject.toml, the sounds/*.wav package-data glob removed, so the wheel is built without the sounds",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "AssertionError: left out of the wheel",
        "observed_diagnostic": "E       AssertionError: left out of the wheel",
        "before": [
          {
            "path": "pyproject.toml",
            "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
          }
        ],
        "mutated": [
          {
            "path": "pyproject.toml",
            "sha256": "667a2747ab2e5a8c889789d9904899800b736d5ff46aa11503ceb514a59e7351"
          }
        ],
        "after": [
          {
            "path": "pyproject.toml",
            "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4-RED-M6A-03-distro-fails-on-a-failed-test",
      "acceptance": [
        "M6A-03.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "podman",
        "run",
        "--rm",
        "-v",
        "<copy>:/src:ro",
        "debian:trixie",
        "sh",
        "/src/.github/scripts/distro-tests.sh"
      ],
      "method": "Red drill on .github/scripts/distro-tests.sh as CI's distro jobs run it (docs/delivery/reports/m6a/wave4/distro_drill.sh, in WSL with podman 6.2.0). Each run was a fresh debian:trixie container on its own PyQt6, against a copy of fb19cb9's files with LF as git stores them. The script went green; then red, with tests/test_cli.py's '--help' assertion made '== 1' in the copy, so the script failed and the job would; then green again, with the file's bytes put back and checked by SHA-256. The three runs' logs are distro-drill-green.log, -red.log and -restored.log, beside the summary. Evidence for fb19cb9: two other workers are changing code at the same time (wayland: the overlay's files and ci.yml; followups: packaging, requirements and the mypy settings in pyproject.toml), so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4/distro-drill.log",
        "sha256": "a0466980d13ebbba25e5352813e82386b8465a8e4670f479a01c84f5aeb12951"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "1a9dead72fb6efc0a8868222f110f4c866fae867e2253699e80cc5d89f1d373c"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "8d0b2e3ee8658378667dccbd8090a11235a71ca371a2d307f765ae482f7bed8f"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b26425d7375158a7819aa0acfc29cf4a0329f268b7d16a07aa2d0a9a351b5f26"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "f5673f6a907fc67de9b9bfad33c1f589a70dd0b01dd56ef14198fefba763317d"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "b65c2595044d1096d3ecbd49c26bb50366f06090f7e5c3124301f03b825152ea"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "6748a152142386e6e48b20bbc9c0913b4076c2bc18f67e890f4190bfa9962ced"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e78f7f0648a81de889e7313bed1d524d761405359ac769a6cba66fc6ba6d7b01"
        }
      ],
      "scope_sha256": "062a23f383f81a32376da4fbeccde82fa412ccbe94387acea99b2b591ad688fd",
      "red": {
        "mutation": "W4-M6A-03-distro-fails-on-a-failed-test: in tests/test_cli.py, '    assert cli.main([\"--help\"]) == 0' became '    assert cli.main([\"--help\"]) == 1'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_help_version_and_what_it_doesnt_know",
        "observed_diagnostic": "__________________ test_help_version_and_what_it_doesnt_know ___________________",
        "before": [
          {
            "path": "tests/test_cli.py",
            "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
          }
        ],
        "mutated": [
          {
            "path": "tests/test_cli.py",
            "sha256": "be6e77fecee4bcf7b4652e93bb1e0b86f37c19f5625e5ecdfac1112619409832"
          }
        ],
        "after": [
          {
            "path": "tests/test_cli.py",
            "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
          }
        ]
      },
      "reason": "Stale at wave 4's second round (2026-11-15): the files it was bound to changed by bf9d8ac (the wayland, followups, a11y and sway merges, pyproject.toml's coverage floor among them), and the plan's rules and narrative were amended; the W4B- receipts re-ran its check on bf9d8ac or read it from CI run 43701523023 (the validator's findings: inputs-stale, scope-stale)"
    },
    {
      "id": "W4B-READY",
      "acceptance": [
        "M6A-01.A1",
        "M6A-01.A2",
        "M6A-01.A3",
        "M6A-02.A1",
        "M6A-03.A1",
        "M6A-04.A1",
        "M6A-04.A2",
        "M6A-05.A1",
        "M6A-05.A2",
        "M6A-06.A1",
        "M6A-06.A2",
        "M6A-06.A3",
        "M6A-07.A1",
        "M6A-08.A1",
        "M6A-08.A2",
        "M6A-09.A1",
        "M6A-10.A1",
        "M6A-10.A2",
        "M6A-11.A1",
        "M6A-12.A1",
        "M6A-13.A1",
        "M6A-15.A1",
        "M6A-I1.A1",
        "M6A-I1.A2"
      ],
      "kind": "readiness",
      "status": "pass",
      "command": [],
      "method": "Requirements review, round two, at bf9d8ac (readiness.md): M6A-01 to M6A-15 and M6A-I1 re-read against ASSESSMENT.md, the amended ROADMAP.md (main's 19 required checks) and pyproject.toml as they are now (fail_under 84); no conflict or gap; CONTRIBUTING.md's two sentences fixed; P-RELEASE and P-DEPENDABOT still the owner's and after the merge.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4b/readiness.md",
        "sha256": "685bcc92093650292f566ae4d1b60127919499670bdaf400944fad8e8af59897"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        }
      ],
      "scope_sha256": "af0b599a0fa2e58c680e0bfcfc2596745696f08a9c9f53559df16c48bd4296c4",
      "red": null,
      "reason": null
    },
    {
      "id": "W4B-BEH-WINDOWS",
      "acceptance": [
        "M6A-01.A3",
        "M6A-05.A1",
        "M6A-06.A1",
        "M6A-08.A1",
        "M6A-10.A2"
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
      "method": "The whole suite on bf9d8ac's source on this Windows 11 workstation (offscreen Qt, the shared venv), which runs every test these criteria's earlier receipts named: 1256 passed, 178 skipped (other platforms' tests, each skip with its reason), exit 0; per-test results are mapped from the log by docs/delivery/reports/wave4/cilog.py. For these criteria the suite is the check itself: pyproject.toml's settings (every warning an error, strict marks, the time limit) hold the whole run, and tests/test_requirements.py and tests/test_package_data.py passed in it. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/wave4b/suite-windows.log",
        "sha256": "7f503b5d1a475b727e01e7b972cf58f5c756082c5dabfdcb6be93c57621c00ad"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "edd9e8c60d616f892bc6ff98d7fea4a10f3e7125b04e063d7e710ef25ce67f96",
      "red": null,
      "reason": null
    },
    {
      "id": "W4B-BEH-CHECKSUMS",
      "acceptance": [
        "M6A-I1.A1"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Program Files/Git/usr/bin/bash.exe",
        "<copy>/run-step.sh"
      ],
      "method": "The checksums job's own run: block from packages.yml at bf9d8ac, run by gate_drills.py's G-checksums-key setup on a copy with a throwaway Ed25519 key that chatmon/releasecheck.py trusts. Its green run (gate-drills.log, section G-checksums-key) listed and signed both files and found the signing key in RELEASE_KEYS. The real job runs only on a pushed tag; it was skipped in Packages run 43675230966. Evidence for fb19cb9: two other workers are changing code at the same time, so their merges will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4b/gate-drills.log",
        "sha256": "58a6d87a5983f88a7cafb5bf4e80847ca6282b932fb455dfa8f1392bbe3dd11e"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "201cea2d0a24ddc42bae81775fa0ec81069dba07905e6bf31053daaf236964aa"
        },
        {
          "path": ".github/workflows/packages.yml",
          "sha256": "94bcdad7acf546995487231368557e7275c171b241874a7f85846d3840d58ed9"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "b64d0413d3064052aa313673df441312ed4072e795f00a23954d48bf799149b2",
      "red": null,
      "reason": null
    },
    {
      "id": "W4B-MAN-CI-REVIEW",
      "acceptance": [
        "M6A-01.A2",
        "M6A-04.A2",
        "M6A-05.A2",
        "M6A-07.A1",
        "M6A-15.A1",
        "M6A-I1.A2"
      ],
      "kind": "manual",
      "status": "pass",
      "command": [],
      "method": "Each criterion read again, line by line in ci-review.md, against ci.yml and packages.yml at bf9d8ac, then against what PR #18's runs on bf9d8ac did: CI run 43701523023 (19 jobs, the new sway job among them) and Packages run 43701523037 (the five build jobs; their logs are in wave4b/ci/). That covers: timeouts (the sway job's too), triggers and concurrency; the coverage legs, their upload and the combine; the 3.14 legs and hash-checked installs; the sparse checkouts; the release jobs as written (their tagged run is still P-RELEASE); and the Linux packages installed, run, checked and removed.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4b/ci-review.md",
        "sha256": "46a6027df66c761ef8393c2f49377de41cf0b149001ac07e91ba44e0724b1bc4"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "201cea2d0a24ddc42bae81775fa0ec81069dba07905e6bf31053daaf236964aa"
        },
        {
          "path": ".github/workflows/packages.yml",
          "sha256": "94bcdad7acf546995487231368557e7275c171b241874a7f85846d3840d58ed9"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "b64d0413d3064052aa313673df441312ed4072e795f00a23954d48bf799149b2",
      "red": null,
      "reason": null
    },
    {
      "id": "W4B-MAN-DEPENDABOT",
      "acceptance": [
        "M6A-02.A1"
      ],
      "kind": "manual",
      "status": "pass",
      "command": [],
      "method": "check-jsonschema 0.39.0 validated .github/dependabot.yml at bf9d8ac against SchemaStore's Dependabot schema (dependabot-schema.log). The file was read again (ci-review.md): three entries, weekly, a 14-day cooldown, the PyQt6 groups, versioning-strategy increase-if-necessary keeping the PyQt6>=6.5 floor, and since round one an ignore for PyQt6 6.12.0, whose own QtDBus stub stops mypy. Dependabot's first run on main is still P-DEPENDABOT.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4b/dependabot-schema.log",
        "sha256": "9d3188d9505847b9012628ac0af0916b94d0397b168dcf315115270df3ff9661"
      },
      "inputs": [
        {
          "path": ".github/ISSUE_TEMPLATE/config.yml",
          "sha256": "dfb4459764a36a156444342afc57092d314a4072359bf87a219d186c134b4af0"
        },
        {
          "path": ".github/dependabot.yml",
          "sha256": "91ae644a18999583a7d99128ed0eee5ac891fa2dd8deeb040fca818ef2a32172"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1f7c6d84755fadc007d43edb37d8a196ea947201c82039bfa5bdc3d7fee179b2"
        },
        {
          "path": "SECURITY.md",
          "sha256": "4f70d856b2157dbe76ebd4e42157fe1e38efc5aa794867119cc147660f274427"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "c09b315819ff7d7e220e58ffd1216ef30a351edcc39f3240038a9fe36cf38b82",
      "red": null,
      "reason": null
    },
    {
      "id": "W4B-MAN-SDE",
      "acceptance": [
        "M6A-06.A3"
      ],
      "kind": "manual",
      "status": "pass",
      "command": [],
      "method": "sde_check.py made two copies of bf9d8ac's wheel inputs with file times a fortnight apart, and built each with python -m build --no-isolation --wheel on the hash-locked build tools. The wheels differed without SOURCE_DATE_EPOCH and were byte-identical with it set to the commit's time, which is how packages.yml's 'Date the build by its commit' step sets it (observed in Packages run 43675230966).",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4b/source-date-epoch.log",
        "sha256": "45ab593053823fe34a07a49aa434bea777a8066f17f9fbe79321b1948d851735"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "201cea2d0a24ddc42bae81775fa0ec81069dba07905e6bf31053daaf236964aa"
        },
        {
          "path": ".github/workflows/packages.yml",
          "sha256": "94bcdad7acf546995487231368557e7275c171b241874a7f85846d3840d58ed9"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "b64d0413d3064052aa313673df441312ed4072e795f00a23954d48bf799149b2",
      "red": null,
      "reason": null
    },
    {
      "id": "W4B-MAN-WINUPDATE",
      "acceptance": [
        "M6A-11.A1"
      ],
      "kind": "manual",
      "status": "pass",
      "command": [],
      "method": "On this Windows workstation at bf9d8ac, tests/test_windows.py -k windows_update_check skipped by default, with its reason naming CHATMON_TEST_WINDOWS_UPDATE=1. With the variable set, it ran against Windows Update and passed; its duration is in the log.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4b/windows-update-optin.log",
        "sha256": "d1cad60d633615461768e5674103a71d6872061f3d292046c5f6a74b28119c19"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_windows.py",
          "sha256": "9c5d58910d17a72b9b186440c3266d3a67eeb25ca053e287c1fc5c1e6389699f"
        }
      ],
      "scope_sha256": "f1ea74365984220e08d85ff66db7a06345aac1acc6560dfe3eef9baf648cba0c",
      "red": null,
      "reason": null
    },
    {
      "id": "W4B-MAN-DOCS",
      "acceptance": [
        "M6A-10.A1"
      ],
      "kind": "manual",
      "status": "pass",
      "command": [],
      "method": "SECURITY.md, CONTRIBUTING.md and the issue chooser read claim by claim against bf9d8ac and the repository's settings (docs-review.md). Round one's two stale sentences are rewritten and true. The new paragraph's claim, that mypy passes with PyQt6 6.12.1's stubs, was checked with mypy 2.4.1 and PyQt6 6.12.1 on linux, win32 and darwin in WSL (mypy-pyqt6-6.12.1-*.log).",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4b/docs-review.md",
        "sha256": "274ec0038011a700f267b24f77aebbb1b7a416a9beaaf96c2be04cac8fefa91c"
      },
      "inputs": [
        {
          "path": ".github/ISSUE_TEMPLATE/config.yml",
          "sha256": "dfb4459764a36a156444342afc57092d314a4072359bf87a219d186c134b4af0"
        },
        {
          "path": ".github/dependabot.yml",
          "sha256": "91ae644a18999583a7d99128ed0eee5ac891fa2dd8deeb040fca818ef2a32172"
        },
        {
          "path": "CONTRIBUTING.md",
          "sha256": "1f7c6d84755fadc007d43edb37d8a196ea947201c82039bfa5bdc3d7fee179b2"
        },
        {
          "path": "SECURITY.md",
          "sha256": "4f70d856b2157dbe76ebd4e42157fe1e38efc5aa794867119cc147660f274427"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "c09b315819ff7d7e220e58ffd1216ef30a351edcc39f3240038a9fe36cf38b82",
      "red": null,
      "reason": null
    },
    {
      "id": "W4B-BEH-CI-LINT",
      "acceptance": [
        "M6A-01.A1",
        "M6A-12.A1"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "gh",
        "run",
        "view",
        "43701523023",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132773560250",
        "--log"
      ],
      "method": "CI run 43701523023 on bf9d8ac, job lint. Two steps ran on .github and passed: 'actionlint, on the workflows (and shellcheck, the runner's, on their scripts)' and 'zizmor, the workflows' security audit'. zizmor v1.31.1 completed .github/dependabot.yml, ci.yml and packages.yml with no finding, and the job succeeded. These clean runs check that every action is pinned to a commit SHA and credentials aren't persisted, and they are themselves the actionlint and zizmor runs in CI. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/ci/ci-132773560250-lint.log",
        "sha256": "4051ed4b0bb5b0203d523e5c2365dcf1bd1200a043f40e9ea796c43c78dba3a9"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "201cea2d0a24ddc42bae81775fa0ec81069dba07905e6bf31053daaf236964aa"
        },
        {
          "path": ".github/workflows/packages.yml",
          "sha256": "94bcdad7acf546995487231368557e7275c171b241874a7f85846d3840d58ed9"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "b64d0413d3064052aa313673df441312ed4072e795f00a23954d48bf799149b2",
      "red": null,
      "reason": null
    },
    {
      "id": "W4B-BEH-CI-DISTRO-UBUNTU",
      "acceptance": [
        "M6A-03.A1"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "gh",
        "run",
        "view",
        "43701523023",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132773560216",
        "--log"
      ],
      "method": "CI run 43701523023 on bf9d8ac, job distro (ubuntu:24.04). The whole suite ran in the container on Ubuntu 24.04's own python3-pyqt6: 1280 passed, 154 skipped (each with its reason), and the job succeeded. Read from the job's log (fetched here with the command above, exit 0) by docs/delivery/reports/wave4/cilog.py, which maps pytest's progress characters onto bf9d8ac's collection and checks the run's own counts and skip lines; every leg's result for these tests is in ci/observed-bf9d8ac.txt. The CI run's own platform and versions are in the log; this receipt's environment is the plan's profile, the workstation that fetched and read it (ROADMAP: evidence from elsewhere). Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/ci/ci-132773560216-distro-ubuntu-24.04.log",
        "sha256": "60cd2fbbf0fef0e6c787cb333d858adc8fe98c935c5e6c9ff8ce7a4355399f1e"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "201cea2d0a24ddc42bae81775fa0ec81069dba07905e6bf31053daaf236964aa"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "e397fb3b78db7444572d3051871f100f6be252c4c99d9dac832012f7d9b0db7d",
      "red": null,
      "reason": null
    },
    {
      "id": "W4B-BEH-CI-DISTRO-DEBIAN",
      "acceptance": [
        "M6A-03.A1"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "gh",
        "run",
        "view",
        "43701523023",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132773560171",
        "--log"
      ],
      "method": "CI run 43701523023 on bf9d8ac, job distro (debian:trixie). The whole suite ran on Debian trixie's own PyQt6: 1280 passed, 154 skipped, and the job succeeded. Read from the job's log (fetched here with the command above, exit 0) by docs/delivery/reports/wave4/cilog.py, which maps pytest's progress characters onto bf9d8ac's collection and checks the run's own counts and skip lines; every leg's result for these tests is in ci/observed-bf9d8ac.txt. The CI run's own platform and versions are in the log; this receipt's environment is the plan's profile, the workstation that fetched and read it (ROADMAP: evidence from elsewhere). Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/ci/ci-132773560171-distro-debian-trixie.log",
        "sha256": "f72ebabda9d536b8221b0b006bba1f592602206fa682c2fb649294d2698e00e5"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "201cea2d0a24ddc42bae81775fa0ec81069dba07905e6bf31053daaf236964aa"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "e397fb3b78db7444572d3051871f100f6be252c4c99d9dac832012f7d9b0db7d",
      "red": null,
      "reason": null
    },
    {
      "id": "W4B-BEH-CI-DISTRO-FEDORA",
      "acceptance": [
        "M6A-03.A1"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "gh",
        "run",
        "view",
        "43701523023",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132773560180",
        "--log"
      ],
      "method": "CI run 43701523023 on bf9d8ac, job distro (fedora:44). The whole suite ran on Fedora 44's own PyQt6: 1282 passed, 152 skipped, and the job succeeded. Read from the job's log (fetched here with the command above, exit 0) by docs/delivery/reports/wave4/cilog.py, which maps pytest's progress characters onto bf9d8ac's collection and checks the run's own counts and skip lines; every leg's result for these tests is in ci/observed-bf9d8ac.txt. The CI run's own platform and versions are in the log; this receipt's environment is the plan's profile, the workstation that fetched and read it (ROADMAP: evidence from elsewhere). Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/ci/ci-132773560180-distro-fedora-44.log",
        "sha256": "379aaff52b50109584b2e638b1281a6647e61b8d1fca0292014a1d70abe06f29"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "201cea2d0a24ddc42bae81775fa0ec81069dba07905e6bf31053daaf236964aa"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "e397fb3b78db7444572d3051871f100f6be252c4c99d9dac832012f7d9b0db7d",
      "red": null,
      "reason": null
    },
    {
      "id": "W4B-BEH-CI-COVERAGE",
      "acceptance": [
        "M6A-04.A1"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "gh",
        "run",
        "view",
        "43701523023",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132775142433",
        "--log"
      ],
      "method": "CI run 43701523023 on bf9d8ac, job coverage. It downloaded the three Python 3.14 legs' data (Windows, macOS, ubuntu-24.04-arm), combined it, wrote the table to the summary, and held the total to pyproject.toml's fail_under = 84. TOTAL was 20758 statements with 2261 missed, 86.5%, and the job succeeded. The same data, downloaded and combined here, gives the same total (wave4b/coverage-combined.log). Round one's follow-up is done: the floor went from 72 to 84 (the followups worker, from run 43694278702's 86.2%). Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/ci/ci-132775142433-coverage.log",
        "sha256": "074140d0d4d5aa0a3db76322c3e8ae240999f88537a9b1359da092891f52acec"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        }
      ],
      "scope_sha256": "42e47aea2c5f39f5184e1e2aea785279daaaf7d61d5efeba05ce1da155ad9f40",
      "red": null,
      "reason": null
    },
    {
      "id": "W4B-BEH-PKG-INSTALL",
      "acceptance": [
        "M6A-06.A2"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "gh",
        "run",
        "view",
        "43701523037",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132773549252",
        "--log"
      ],
      "method": "Packages run 43701523037, the pull_request run on PR #18 at bf9d8ac, whose test merge has bf9d8ac's own tree (reports/wave4b/ci: the merge's tree equals bf9d8ac's). Job windows, from log line 267: python -m pip install --require-hashes -r packaging/requirements-build.txt, then --require-hashes --no-build-isolation -r packaging/requirements.txt; both succeeded, and the job built the installer. The macos-latest and macos-15-intel jobs ran the same installs (pkg-132773549569-macos-macos-latest.log, line 173). Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/ci/pkg-132773549252-windows.log",
        "sha256": "527f491b741587f0a16a823092193566349d421a910aecb048f2715b9deb7d0e"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "174a0edb9754f53cfc28283910f052133a28305207b534a51bfa6f769d3ed9a4",
      "red": null,
      "reason": null
    },
    {
      "id": "W4B-BEH-PKG-WHEEL",
      "acceptance": [
        "M6A-08.A2",
        "M6A-09.A1"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "gh",
        "run",
        "view",
        "43701523037",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132773549529",
        "--log"
      ],
      "method": "Packages run 43701523037, the pull_request run on PR #18 at bf9d8ac, whose test merge has bf9d8ac's own tree (reports/wave4b/ci: the merge's tree equals bf9d8ac's). Job python. It dated the build by the commit (SOURCE_DATE_EPOCH) and built the wheel and sdist without isolation on the hash-locked setuptools. twine check --strict passed for both (log lines 1161-1162). tests/test_package_data.py then passed on what was built (line 1189). Those tests check that every tracked file under chatmon/ is in the wheel and that the only console script is chatmon. The windows, macos and linux jobs also succeeded, and the five release jobs were skipped, as designed for a run that isn't a tag. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/ci/pkg-132773549529-python.log",
        "sha256": "718d1b929316bdf3c3cb907006b312120a70da148f40e6975cdcec572adef6d9"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "edd9e8c60d616f892bc6ff98d7fea4a10f3e7125b04e063d7e710ef25ce67f96",
      "red": null,
      "reason": null
    },
    {
      "id": "W4B-BEH-CI-TYPES",
      "acceptance": [
        "M6A-13.A1"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "gh",
        "run",
        "view",
        "43701523023",
        "--repo",
        "RandyNorthrup/chatmon",
        "--job",
        "132773560129",
        "--log"
      ],
      "method": "CI run 43701523023 on bf9d8ac, job types (linux): mypy --platform linux on pyproject.toml's [tool.mypy] passed. The types (win32) and types (darwin) jobs, whose logs are in wave4b/ci/, passed too. M6B took every module off the exemption list, so the gate as it stands passes on all three platforms. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/ci/ci-132773560129-types-linux.log",
        "sha256": "4d344882aaa2a350ca61c8d26f2d51b1ad4224b713e1f2992b85ad5051a945a2"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        }
      ],
      "scope_sha256": "42e47aea2c5f39f5184e1e2aea785279daaaf7d61d5efeba05ce1da155ad9f40",
      "red": null,
      "reason": null
    },
    {
      "id": "W4B-RED-G-actionlint-expression",
      "acceptance": [
        "M6A-12.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "actionlint",
        ".github/workflows/ci.yml"
      ],
      "method": "Red drill G-actionlint-expression through gate_drills.py (a byte-for-byte copy of docs/delivery/reports/m6a/gate_drills.py in wave4b/, so its logs land there and the earlier ones stay as they were) on this Windows workstation: the gate green on a temporary copy, the violation put in and the gate failing with the expected finding, the file's bytes put back and the gate green again, the tree's file checked unchanged, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4b/gate-drills.log",
        "sha256": "58a6d87a5983f88a7cafb5bf4e80847ca6282b932fb455dfa8f1392bbe3dd11e"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "201cea2d0a24ddc42bae81775fa0ec81069dba07905e6bf31053daaf236964aa"
        },
        {
          "path": ".github/workflows/packages.yml",
          "sha256": "94bcdad7acf546995487231368557e7275c171b241874a7f85846d3840d58ed9"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "b64d0413d3064052aa313673df441312ed4072e795f00a23954d48bf799149b2",
      "red": {
        "mutation": "G-actionlint-expression: in .github/workflows/ci.yml, the types job reads matrix.platfrom, a property its matrix doesn't have",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "property \"platfrom\" is not defined",
        "observed_diagnostic": ".github/workflows/ci.yml:75:25: property \"platfrom\" is not defined in object type {platform: string} [expression]",
        "before": [
          {
            "path": ".github/workflows/ci.yml",
            "sha256": "201cea2d0a24ddc42bae81775fa0ec81069dba07905e6bf31053daaf236964aa"
          }
        ],
        "mutated": [
          {
            "path": ".github/workflows/ci.yml",
            "sha256": "a7583f91671f352cddf7a12c2184e3c933a8f494014caef747fe908a705b9090"
          }
        ],
        "after": [
          {
            "path": ".github/workflows/ci.yml",
            "sha256": "201cea2d0a24ddc42bae81775fa0ec81069dba07905e6bf31053daaf236964aa"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4B-RED-G-checksums-key",
      "acceptance": [
        "M6A-I1.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Program Files\\Git\\usr\\bin\\bash.exe",
        "<copy>/run-step.sh"
      ],
      "method": "Red drill G-checksums-key through gate_drills.py (a byte-for-byte copy of docs/delivery/reports/m6a/gate_drills.py in wave4b/, so its logs land there and the earlier ones stay as they were) on this Windows workstation: the gate green on a temporary copy, the violation put in and the gate failing with the expected finding, the file's bytes put back and the gate green again, the tree's file checked unchanged, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4b/gate-drills.log",
        "sha256": "58a6d87a5983f88a7cafb5bf4e80847ca6282b932fb455dfa8f1392bbe3dd11e"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "201cea2d0a24ddc42bae81775fa0ec81069dba07905e6bf31053daaf236964aa"
        },
        {
          "path": ".github/workflows/packages.yml",
          "sha256": "94bcdad7acf546995487231368557e7275c171b241874a7f85846d3840d58ed9"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "b64d0413d3064052aa313673df441312ed4072e795f00a23954d48bf799149b2",
      "red": {
        "mutation": "G-checksums-key: in .github/workflows/packages.yml, the checksums job looks for the key in chatmon/updates.py again, where it was before M1A moved it",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "RELEASE_SIGNING_KEY isn't a key in RELEASE_KEYS",
        "observed_diagnostic": "RELEASE_SIGNING_KEY isn't a key in RELEASE_KEYS",
        "before": [
          {
            "path": ".github/workflows/packages.yml",
            "sha256": "94bcdad7acf546995487231368557e7275c171b241874a7f85846d3840d58ed9"
          }
        ],
        "mutated": [
          {
            "path": ".github/workflows/packages.yml",
            "sha256": "5638e82440300c20872539ed59403ae29207efb80313b757352875cfdf2bd6a9"
          }
        ],
        "after": [
          {
            "path": ".github/workflows/packages.yml",
            "sha256": "94bcdad7acf546995487231368557e7275c171b241874a7f85846d3840d58ed9"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4B-RED-G-coverage-floor",
      "acceptance": [
        "M6A-04.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "coverage",
        "report",
        "--data-file",
        "build/wave4b-coverage/.coverage.combined"
      ],
      "method": "Red drill G-coverage-floor through gate_drills.py (a byte-for-byte copy of docs/delivery/reports/m6a/gate_drills.py in wave4b/, so its logs land there and the earlier ones stay as they were) on this Windows workstation: the gate green on a temporary copy, the violation put in and the gate failing with the expected finding, the file's bytes put back and the gate green again, the tree's file checked unchanged, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4b/gate-drills.log",
        "sha256": "58a6d87a5983f88a7cafb5bf4e80847ca6282b932fb455dfa8f1392bbe3dd11e"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        }
      ],
      "scope_sha256": "42e47aea2c5f39f5184e1e2aea785279daaaf7d61d5efeba05ce1da155ad9f40",
      "red": {
        "mutation": "G-coverage-floor: in pyproject.toml, fail_under raised to 99, above the measured total",
        "baseline_exit": 0,
        "mutated_exit": 2,
        "restored_exit": 0,
        "expected_diagnostic": "Coverage failure: total of",
        "observed_diagnostic": "Coverage failure: total of 86.5 is less than fail-under=99.0",
        "before": [
          {
            "path": "pyproject.toml",
            "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
          }
        ],
        "mutated": [
          {
            "path": "pyproject.toml",
            "sha256": "7e9342544db4d11cd0cc75cb58a3438d1ac19b89b2f33207c92a8040d199a19d"
          }
        ],
        "after": [
          {
            "path": "pyproject.toml",
            "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4B-RED-G-mypy-gated",
      "acceptance": [
        "M6A-13.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "mypy",
        "--platform",
        "linux",
        "--no-incremental",
        "--cache-dir",
        "<copy>/.mypy"
      ],
      "method": "Red drill G-mypy-gated through gate_drills.py (a byte-for-byte copy of docs/delivery/reports/m6a/gate_drills.py in wave4b/, so its logs land there and the earlier ones stay as they were) on this Windows workstation: the gate green on a temporary copy, the violation put in and the gate failing with the expected finding, the file's bytes put back and the gate green again, the tree's file checked unchanged, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4b/gate-drills.log",
        "sha256": "58a6d87a5983f88a7cafb5bf4e80847ca6282b932fb455dfa8f1392bbe3dd11e"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        }
      ],
      "scope_sha256": "42e47aea2c5f39f5184e1e2aea785279daaaf7d61d5efeba05ce1da155ad9f40",
      "red": {
        "mutation": "G-mypy-gated: in chatmon/changelog.py, a str assigned to an int in changelog.py, a gated module",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "chatmon\\changelog.py",
        "observed_diagnostic": "chatmon\\changelog.py:88: error: Incompatible types in assignment (expression has type \"str\", variable has type \"int\")  [assignment]",
        "before": [
          {
            "path": "chatmon/changelog.py",
            "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/changelog.py",
            "sha256": "42f0cd2f029dc43f098065f425e1772ef3497ceef31214d29f3b9dc3fed608b8"
          }
        ],
        "after": [
          {
            "path": "chatmon/changelog.py",
            "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4B-RED-G-pip-hashes",
      "acceptance": [
        "M6A-06.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pip",
        "install",
        "--dry-run",
        "--ignore-installed",
        "--no-cache-dir",
        "--require-hashes",
        "-r",
        "packaging/requirements-build.txt"
      ],
      "method": "Red drill G-pip-hashes through gate_drills.py (a byte-for-byte copy of docs/delivery/reports/m6a/gate_drills.py in wave4b/, so its logs land there and the earlier ones stay as they were) on this Windows workstation: the gate green on a temporary copy, the violation put in and the gate failing with the expected finding, the file's bytes put back and the gate green again, the tree's file checked unchanged, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4b/gate-drills.log",
        "sha256": "58a6d87a5983f88a7cafb5bf4e80847ca6282b932fb455dfa8f1392bbe3dd11e"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "174a0edb9754f53cfc28283910f052133a28305207b534a51bfa6f769d3ed9a4",
      "red": {
        "mutation": "G-pip-hashes: in packaging/requirements-build.txt, every hash of wheel 0.48.0 in requirements-build.txt changed",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "THESE PACKAGES DO NOT MATCH THE HASHES FROM THE REQUIREMENTS FILE",
        "observed_diagnostic": "ERROR: THESE PACKAGES DO NOT MATCH THE HASHES FROM THE REQUIREMENTS FILE. If you have updated the package versions, please update the hashes. Otherwise, examine the package contents carefully; someone may have tampered with them.",
        "before": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
          }
        ],
        "mutated": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "e381417403dec7ee8fc699cb26bcfd605b52c70fd9ae8f44d63aef5a53570367"
          }
        ],
        "after": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4B-RED-G-pytest-strict-markers",
      "acceptance": [
        "M6A-01.A3"
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
        "tests/test_cli.py"
      ],
      "method": "Red drill G-pytest-strict-markers through gate_drills.py (a byte-for-byte copy of docs/delivery/reports/m6a/gate_drills.py in wave4b/, so its logs land there and the earlier ones stay as they were) on this Windows workstation: the gate green on a temporary copy, the violation put in and the gate failing with the expected finding, the file's bytes put back and the gate green again, the tree's file checked unchanged, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4b/gate-drills.log",
        "sha256": "58a6d87a5983f88a7cafb5bf4e80847ca6282b932fb455dfa8f1392bbe3dd11e"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        }
      ],
      "scope_sha256": "42e47aea2c5f39f5184e1e2aea785279daaaf7d61d5efeba05ce1da155ad9f40",
      "red": {
        "mutation": "G-pytest-strict-markers: in tests/test_cli.py, an unregistered mark on test_cli.py's first test",
        "baseline_exit": 0,
        "mutated_exit": 2,
        "restored_exit": 0,
        "expected_diagnostic": "'drillmark' not found in `markers` configuration option",
        "observed_diagnostic": "'drillmark' not found in `markers` configuration option",
        "before": [
          {
            "path": "tests/test_cli.py",
            "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
          }
        ],
        "mutated": [
          {
            "path": "tests/test_cli.py",
            "sha256": "1919b97202778925b1d7495c78ed6cde1eacc54623692d004e6d866420e398fa"
          }
        ],
        "after": [
          {
            "path": "tests/test_cli.py",
            "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4B-RED-G-zizmor-unpinned",
      "acceptance": [
        "M6A-01.A1",
        "M6A-12.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\zizmor.exe",
        "--no-online-audits",
        ".github"
      ],
      "method": "Red drill G-zizmor-unpinned through gate_drills.py (a byte-for-byte copy of docs/delivery/reports/m6a/gate_drills.py in wave4b/, so its logs land there and the earlier ones stay as they were) on this Windows workstation: the gate green on a temporary copy, the violation put in and the gate failing with the expected finding, the file's bytes put back and the gate green again, the tree's file checked unchanged, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4b/gate-drills.log",
        "sha256": "58a6d87a5983f88a7cafb5bf4e80847ca6282b932fb455dfa8f1392bbe3dd11e"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "201cea2d0a24ddc42bae81775fa0ec81069dba07905e6bf31053daaf236964aa"
        },
        {
          "path": ".github/workflows/packages.yml",
          "sha256": "94bcdad7acf546995487231368557e7275c171b241874a7f85846d3840d58ed9"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "b64d0413d3064052aa313673df441312ed4072e795f00a23954d48bf799149b2",
      "red": {
        "mutation": "G-zizmor-unpinned: in .github/workflows/ci.yml, the lint job's checkout pinned to the tag v7 instead of its commit",
        "baseline_exit": 0,
        "mutated_exit": 14,
        "restored_exit": 0,
        "expected_diagnostic": "unpinned-uses",
        "observed_diagnostic": "error[unpinned-uses]: unpinned action reference",
        "before": [
          {
            "path": ".github/workflows/ci.yml",
            "sha256": "201cea2d0a24ddc42bae81775fa0ec81069dba07905e6bf31053daaf236964aa"
          }
        ],
        "mutated": [
          {
            "path": ".github/workflows/ci.yml",
            "sha256": "d00f3a12c834b53ce4afc46cbb1365e2faa6d8fea5a5dc0130b8da48fb0fda6a"
          }
        ],
        "after": [
          {
            "path": ".github/workflows/ci.yml",
            "sha256": "201cea2d0a24ddc42bae81775fa0ec81069dba07905e6bf31053daaf236964aa"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4B-RED-M6A-01-warnings",
      "acceptance": [
        "M6A-01.A3"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_packaging.py::test_release_notes_pin_the_pipx_install_to_the_release"
      ],
      "method": "Red drill M6A-01-warnings through tests/drills/run.py on this Windows workstation, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4b/drills.log",
        "sha256": "373ad98ec1b6c1beaeb225e1c67b660ba51772ca59c6d64ccdd9f610de654cc2"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        }
      ],
      "scope_sha256": "42e47aea2c5f39f5184e1e2aea785279daaaf7d61d5efeba05ce1da155ad9f40",
      "red": {
        "mutation": "M6A-01-warnings: in chatmon/changelog.py, '    key = version_key(version)' became '    __import__(\"warnings\").warn(\"an old way to call find\", DeprecationWarning, stacklevel=2)\\n    key = version_key(version)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "DeprecationWarning: an old way to call find",
        "observed_diagnostic": "E       DeprecationWarning: an old way to call find",
        "before": [
          {
            "path": "chatmon/changelog.py",
            "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/changelog.py",
            "sha256": "dc9ce419c0c9ad8400453c4df4e18ddc0a8a4f0a5d4b6fa1eafb214619b48163"
          }
        ],
        "after": [
          {
            "path": "chatmon/changelog.py",
            "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4B-RED-M6A-05-qt",
      "acceptance": [
        "M6A-05.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_requirements.py::test_a_package_in_more_than_one_lock_is_the_same_version_in_each"
      ],
      "method": "Red drill M6A-05-qt through tests/drills/run.py on this Windows workstation, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4b/drills.log",
        "sha256": "373ad98ec1b6c1beaeb225e1c67b660ba51772ca59c6d64ccdd9f610de654cc2"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "174a0edb9754f53cfc28283910f052133a28305207b534a51bfa6f769d3ed9a4",
      "red": {
        "mutation": "M6A-05-qt: in packaging/requirements-test.txt, 'pyqt6==6.11.0 \\\\' became 'pyqt6==6.12.0 \\\\'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "locked at different versions",
        "observed_diagnostic": ">       assert not differ, f\"locked at different versions: {differ}\"",
        "before": [
          {
            "path": "packaging/requirements-test.txt",
            "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
          }
        ],
        "mutated": [
          {
            "path": "packaging/requirements-test.txt",
            "sha256": "9d35f1ccc9f0c8adba3138ffb75c6ea2e4d601ddda968f33e8fff5b0808efab0"
          }
        ],
        "after": [
          {
            "path": "packaging/requirements-test.txt",
            "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4B-RED-M6A-06-hash",
      "acceptance": [
        "M6A-06.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_requirements.py::test_every_locked_requirement_is_pinned_and_hashed"
      ],
      "method": "Red drill M6A-06-hash through tests/drills/run.py on this Windows workstation, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4b/drills.log",
        "sha256": "373ad98ec1b6c1beaeb225e1c67b660ba51772ca59c6d64ccdd9f610de654cc2"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "174a0edb9754f53cfc28283910f052133a28305207b534a51bfa6f769d3ed9a4",
      "red": {
        "mutation": "M6A-06-hash: in packaging/requirements-build.txt, 'wheel==0.48.0 \\\\' became 'wheel==0.48.0  # \\\\'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "requirements-build.txt has no hash for ['wheel']",
        "observed_diagnostic": "E           AssertionError: requirements-build.txt has no hash for ['wheel']: pip --require-hashes would refuse it",
        "before": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
          }
        ],
        "mutated": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "cb4b66cf0f4fea9d3649ca600f01137d24634c6cb7b76e07164281d22b0e9055"
          }
        ],
        "after": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4B-RED-M6A-06-stale",
      "acceptance": [
        "M6A-06.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_requirements.py::test_each_lock_holds_the_versions_its_in_file_names"
      ],
      "method": "Red drill M6A-06-stale through tests/drills/run.py on this Windows workstation, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4b/drills.log",
        "sha256": "373ad98ec1b6c1beaeb225e1c67b660ba51772ca59c6d64ccdd9f610de654cc2"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "174a0edb9754f53cfc28283910f052133a28305207b534a51bfa6f769d3ed9a4",
      "red": {
        "mutation": "M6A-06-stale: in packaging/requirements-build.txt, 'setuptools==84.2.1 \\\\' became 'setuptools==84.2.0 \\\\'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "requirements-build.txt doesn't lock these at the versions requirements-build.in pins",
        "observed_diagnostic": "E           AssertionError: requirements-build.txt doesn't lock these at the versions requirements-build.in pins: {'setuptools': '84.2.1'}",
        "before": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
          }
        ],
        "mutated": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "e00f483b8019c215f05414102f6a04d218c0c2ee4b46120c135c3d90c494c005"
          }
        ],
        "after": [
          {
            "path": "packaging/requirements-build.txt",
            "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4B-RED-M6A-08-glob",
      "acceptance": [
        "M6A-08.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_package_data.py::test_every_tracked_file_of_chatmon_ships"
      ],
      "method": "Red drill M6A-08-glob through tests/drills/run.py on this Windows workstation, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4b/drills.log",
        "sha256": "373ad98ec1b6c1beaeb225e1c67b660ba51772ca59c6d64ccdd9f610de654cc2"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "edd9e8c60d616f892bc6ff98d7fea4a10f3e7125b04e063d7e710ef25ce67f96",
      "red": {
        "mutation": "M6A-08-glob: in pyproject.toml, '\"bubbles/manifest.json\",' became ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "no package-data glob in pyproject.toml takes these",
        "observed_diagnostic": ">       assert not left_out, f\"no package-data glob in pyproject.toml takes these, so pip and pipx installs would lack them: {left_out}\"",
        "before": [
          {
            "path": "pyproject.toml",
            "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
          }
        ],
        "mutated": [
          {
            "path": "pyproject.toml",
            "sha256": "b7777c2e2a1fe58b192afe63815f110d3550cd9de894e5ff66b46956d970047a"
          }
        ],
        "after": [
          {
            "path": "pyproject.toml",
            "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4B-RED-M6A-10-dev",
      "acceptance": [
        "M6A-10.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_requirements.py::test_the_dev_extra_pins_what_ci_runs"
      ],
      "method": "Red drill M6A-10-dev through tests/drills/run.py on this Windows workstation, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4b/drills.log",
        "sha256": "373ad98ec1b6c1beaeb225e1c67b660ba51772ca59c6d64ccdd9f610de654cc2"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "174a0edb9754f53cfc28283910f052133a28305207b534a51bfa6f769d3ed9a4",
      "red": {
        "mutation": "M6A-10-dev: in pyproject.toml, '\"ruff==0.17.3\",' became '\"ruff==0.17.4\",'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "dev extra: ruff==0.17.4, but CI runs ruff==0.17.3",
        "observed_diagnostic": "E           AssertionError: dev extra: ruff==0.17.4, but CI runs ruff==0.17.3",
        "before": [
          {
            "path": "pyproject.toml",
            "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
          }
        ],
        "mutated": [
          {
            "path": "pyproject.toml",
            "sha256": "712a07ff6bd558fb98cf315a7c40e14b56fc2f18676566132fe9386d9fb056ee"
          }
        ],
        "after": [
          {
            "path": "pyproject.toml",
            "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4B-RED-W-entry-points",
      "acceptance": [
        "M6A-09.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Program Files\\Git\\usr\\bin\\bash.exe",
        "-ec",
        "'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/buildvenv/Scripts/python.exe' -m build --no-isolation --outdir dist . >build.log 2>&1 || { tail -20 build.log; exit 1; }; 'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/buildvenv/Scripts/python.exe' -m twine check --strict dist/*; CHATMON_DIST=dist 'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/buildvenv/Scripts/python.exe' -m pytest -q -p no:cacheprovider tests/test_package_data.py -k 'commands'"
      ],
      "method": "Red drill W-entry-points through gate_drills.py (a byte-for-byte copy of docs/delivery/reports/m6a/gate_drills.py in wave4b/, so its logs land there and the earlier ones stay as they were) on this Windows workstation: the gate green on a temporary copy, the violation put in and the gate failing with the expected finding, the file's bytes put back and the gate green again, the tree's file checked unchanged, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4b/gate-drills.log",
        "sha256": "58a6d87a5983f88a7cafb5bf4e80847ca6282b932fb455dfa8f1392bbe3dd11e"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "edd9e8c60d616f892bc6ff98d7fea4a10f3e7125b04e063d7e710ef25ce67f96",
      "red": {
        "mutation": "W-entry-points: in pyproject.toml, the penguin-companion console script put back",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "'penguin-companion': ('console_scripts', 'chatmon.cli:main')",
        "observed_diagnostic": "E         {'penguin-companion': ('console_scripts', 'chatmon.cli:main')}",
        "before": [
          {
            "path": "pyproject.toml",
            "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
          }
        ],
        "mutated": [
          {
            "path": "pyproject.toml",
            "sha256": "c5f4c8593b681e48c7c0efd359ad6b1d1d8394ff762771f19c900f7888fa4d58"
          }
        ],
        "after": [
          {
            "path": "pyproject.toml",
            "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4B-RED-W-twine-markup",
      "acceptance": [
        "M6A-08.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Program Files\\Git\\usr\\bin\\bash.exe",
        "-ec",
        "'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/buildvenv/Scripts/python.exe' -m build --no-isolation --outdir dist . >build.log 2>&1 || { tail -20 build.log; exit 1; }; 'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/buildvenv/Scripts/python.exe' -m twine check --strict dist/*; CHATMON_DIST=dist 'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/buildvenv/Scripts/python.exe' -m pytest -q -p no:cacheprovider tests/test_package_data.py -k 'wheel_holds'"
      ],
      "method": "Red drill W-twine-markup through gate_drills.py (a byte-for-byte copy of docs/delivery/reports/m6a/gate_drills.py in wave4b/, so its logs land there and the earlier ones stay as they were) on this Windows workstation: the gate green on a temporary copy, the violation put in and the gate failing with the expected finding, the file's bytes put back and the gate green again, the tree's file checked unchanged, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4b/gate-drills.log",
        "sha256": "58a6d87a5983f88a7cafb5bf4e80847ca6282b932fb455dfa8f1392bbe3dd11e"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "edd9e8c60d616f892bc6ff98d7fea4a10f3e7125b04e063d7e710ef25ce67f96",
      "red": {
        "mutation": "W-twine-markup: in pyproject.toml, the README declared as reStructuredText, which its Markdown isn't",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "`long_description` has syntax errors in markup",
        "observed_diagnostic": "ERROR    `long_description` has syntax errors in markup and would not be",
        "before": [
          {
            "path": "pyproject.toml",
            "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
          }
        ],
        "mutated": [
          {
            "path": "pyproject.toml",
            "sha256": "6eadf45a2ef3f302449ce6dfe94ce71253e94588d2cd3f2a2268a7d6bde7d74e"
          }
        ],
        "after": [
          {
            "path": "pyproject.toml",
            "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4B-RED-W-wheel-sounds",
      "acceptance": [
        "M6A-08.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Program Files\\Git\\usr\\bin\\bash.exe",
        "-ec",
        "'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/buildvenv/Scripts/python.exe' -m build --no-isolation --outdir dist . >build.log 2>&1 || { tail -20 build.log; exit 1; }; 'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/buildvenv/Scripts/python.exe' -m twine check --strict dist/*; CHATMON_DIST=dist 'C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad/buildvenv/Scripts/python.exe' -m pytest -q -p no:cacheprovider tests/test_package_data.py -k 'wheel_holds'"
      ],
      "method": "Red drill W-wheel-sounds through gate_drills.py (a byte-for-byte copy of docs/delivery/reports/m6a/gate_drills.py in wave4b/, so its logs land there and the earlier ones stay as they were) on this Windows workstation: the gate green on a temporary copy, the violation put in and the gate failing with the expected finding, the file's bytes put back and the gate green again, the tree's file checked unchanged, in a temporary copy of bf9d8ac's files: green, the defect put in, the named tests failing with pytest's tests-failed exit and the expected test named, the file's bytes put back (checked by SHA-256) and green again. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4b/gate-drills.log",
        "sha256": "58a6d87a5983f88a7cafb5bf4e80847ca6282b932fb455dfa8f1392bbe3dd11e"
      },
      "inputs": [
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "penguin-companion",
          "sha256": null
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_package_data.py",
          "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "edd9e8c60d616f892bc6ff98d7fea4a10f3e7125b04e063d7e710ef25ce67f96",
      "red": {
        "mutation": "W-wheel-sounds: in pyproject.toml, the sounds/*.wav package-data glob removed, so the wheel is built without the sounds",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "AssertionError: left out of the wheel",
        "observed_diagnostic": "E       AssertionError: left out of the wheel",
        "before": [
          {
            "path": "pyproject.toml",
            "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
          }
        ],
        "mutated": [
          {
            "path": "pyproject.toml",
            "sha256": "a44c9842ecbfcd898950ddb013e83cccd87b9987cd71c88929ad2aaf96cd5e7f"
          }
        ],
        "after": [
          {
            "path": "pyproject.toml",
            "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "W4B-RED-M6A-03-distro-fails-on-a-failed-test",
      "acceptance": [
        "M6A-03.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "podman",
        "run",
        "--rm",
        "-v",
        "<copy>:/src:ro",
        "debian:trixie",
        "sh",
        "/src/.github/scripts/distro-tests.sh"
      ],
      "method": "Red drill on .github/scripts/distro-tests.sh as CI's distro jobs run it (docs/delivery/reports/m6a/wave4b/distro_drill.sh, in WSL with podman 6.2.0). Each run was a fresh debian:trixie container on its own PyQt6, against a copy of bf9d8ac's files with LF as git stores them. The script went green; then red, with tests/test_cli.py's '--help' assertion made '== 1' in the copy, so the script failed and the job would; then green again, with the file's bytes put back and checked by SHA-256. The three runs' logs are distro-drill-green.log, -red.log and -restored.log, beside the summary. Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pytest": "9.2.0",
          "pyqt6": "6.11.0",
          "pytest-timeout": "2.4.0",
          "coverage": "7.17.0",
          "mypy": "2.4.1",
          "ruff": "0.17.4",
          "zizmor": "1.31.1",
          "actionlint": "1.7.12",
          "uv": "0.12.7",
          "shellcheck": "0.11.0",
          "podman": "6.2.0"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m6a/wave4b/distro-drill.log",
        "sha256": "ae8a0d3fba61e0cc669ef65275fd70855ae7d5fab00df5be4b50edb630027107"
      },
      "inputs": [
        {
          "path": ".github/scripts/distro-tests.sh",
          "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
        },
        {
          "path": ".github/workflows/ci.yml",
          "sha256": "201cea2d0a24ddc42bae81775fa0ec81069dba07905e6bf31053daaf236964aa"
        },
        {
          "path": "chatmon/changelog.py",
          "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
        },
        {
          "path": "docs/delivery/reports/wave4/cilog.py",
          "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
        },
        {
          "path": "packaging/requirements-build.in",
          "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.in",
          "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
        },
        {
          "path": "pyproject.toml",
          "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
        },
        {
          "path": "tests/gnome-session.sh",
          "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
        },
        {
          "path": "tests/test_cli.py",
          "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
        }
      ],
      "scope_sha256": "e397fb3b78db7444572d3051871f100f6be252c4c99d9dac832012f7d9b0db7d",
      "red": {
        "mutation": "W4-M6A-03-distro-fails-on-a-failed-test: in tests/test_cli.py, '    assert cli.main([\"--help\"]) == 0' became '    assert cli.main([\"--help\"]) == 1'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_help_version_and_what_it_doesnt_know",
        "observed_diagnostic": "__________________ test_help_version_and_what_it_doesnt_know ___________________",
        "before": [
          {
            "path": "tests/test_cli.py",
            "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
          }
        ],
        "mutated": [
          {
            "path": "tests/test_cli.py",
            "sha256": "be6e77fecee4bcf7b4652e93bb1e0b86f37c19f5625e5ecdfac1112619409832"
          }
        ],
        "after": [
          {
            "path": "tests/test_cli.py",
            "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
          }
        ]
      },
      "reason": null
    }
  ],
  "checkpoint": {
    "scope_sha256": "af0b599a0fa2e58c680e0bfcfc2596745696f08a9c9f53559df16c48bd4296c4",
    "inputs": [
      {
        "path": ".github/ISSUE_TEMPLATE/config.yml",
        "sha256": "dfb4459764a36a156444342afc57092d314a4072359bf87a219d186c134b4af0"
      },
      {
        "path": ".github/dependabot.yml",
        "sha256": "91ae644a18999583a7d99128ed0eee5ac891fa2dd8deeb040fca818ef2a32172"
      },
      {
        "path": ".github/scripts/distro-tests.sh",
        "sha256": "9ba9519b34db8c7cce0a6a225f5b77f4cd8aa0e116761d335cf0d6a7653637e6"
      },
      {
        "path": ".github/workflows/ci.yml",
        "sha256": "201cea2d0a24ddc42bae81775fa0ec81069dba07905e6bf31053daaf236964aa"
      },
      {
        "path": ".github/workflows/packages.yml",
        "sha256": "94bcdad7acf546995487231368557e7275c171b241874a7f85846d3840d58ed9"
      },
      {
        "path": "CONTRIBUTING.md",
        "sha256": "1f7c6d84755fadc007d43edb37d8a196ea947201c82039bfa5bdc3d7fee179b2"
      },
      {
        "path": "SECURITY.md",
        "sha256": "4f70d856b2157dbe76ebd4e42157fe1e38efc5aa794867119cc147660f274427"
      },
      {
        "path": "chatmon/changelog.py",
        "sha256": "98a924c4355056ff2e39060d8260c0e09653ccd4a70ea2368f11d5d19a2c5bc0"
      },
      {
        "path": "docs/delivery/ASSESSMENT.md",
        "sha256": "3f50d961e313923c81d920fbd8e9caee3de8766db57c6db97dd1b75a83d22049"
      },
      {
        "path": "docs/delivery/ROADMAP.md",
        "sha256": "aeddfd8c784b6b58d2a61c65d8f0b590ad1a17f30aa8c90884d9eca915e73732"
      },
      {
        "path": "docs/delivery/reports/wave4/cilog.py",
        "sha256": "277c48f700e6c2dbd4d7f9023215d5ec3c01e1cfb48d6c5ec5a13123dd93ab2b"
      },
      {
        "path": "packaging/requirements-build.in",
        "sha256": "644e53fecb1cde0e8e18b45313781de0e894056e1c979ba347b25e97adbb7170"
      },
      {
        "path": "packaging/requirements-build.txt",
        "sha256": "89f1b9b029139ec711cd61e345b19a93da4ec5e0d52a3828817bfdf430eb6878"
      },
      {
        "path": "packaging/requirements-dev.in",
        "sha256": "18704975ac44d668322416d822cb60b9e73a86f7d54086ff57460cc052577603"
      },
      {
        "path": "packaging/requirements-dev.txt",
        "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
      },
      {
        "path": "packaging/requirements-test.in",
        "sha256": "2e5ee19900964cfa23a30c32bd2edbd56f323f670e93bdb4f0f1ab1728261ed5"
      },
      {
        "path": "packaging/requirements-test.txt",
        "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
      },
      {
        "path": "packaging/requirements.in",
        "sha256": "7f076c6f27456a9a53fe8aea080ac0ec20f8ccf3b9d18f61ea95444b4eb1d630"
      },
      {
        "path": "packaging/requirements.txt",
        "sha256": "4efc7ab88dca615a4bf7046924db20e701af1bd7924bf38205f7648a0ed312b2"
      },
      {
        "path": "penguin-companion",
        "sha256": null
      },
      {
        "path": "pyproject.toml",
        "sha256": "e80d68be3601bb2210e68ce5826c78a38ef61cf98840248738f352f85f8e69e3"
      },
      {
        "path": "tests/conftest.py",
        "sha256": "21f00681f57c439daf6eae23a37b69cd8b0837774f1c61ea861177c85cae028f"
      },
      {
        "path": "tests/drills/run.py",
        "sha256": "2909484227b450f48269dd8b703e7da1051dc6ed07088cb30235f4b28594a5cc"
      },
      {
        "path": "tests/gnome-session.sh",
        "sha256": "f8cd51b37bbdf6e6ed55cef24d3e7bc94dbabdeb33ec3a9e3cce567d0c354268"
      },
      {
        "path": "tests/test_cli.py",
        "sha256": "d05913174b90ab7b1de137e33dac49e7c41cf68d2ca495d98602664adf6699f2"
      },
      {
        "path": "tests/test_package_data.py",
        "sha256": "581e17eff3de3b38a5751a9577652c2916b62dd508c5dbdee6905f3d5fd01633"
      },
      {
        "path": "tests/test_requirements.py",
        "sha256": "0be1e397090e56c2e8b7aa9b9a27b7522deaaa10ac0ffcf6d654f61728f78281"
      },
      {
        "path": "tests/test_windows.py",
        "sha256": "9c5d58910d17a72b9b186440c3266d3a67eeb25ca053e287c1fc5c1e6389699f"
      }
    ],
    "environment": {
      "platform": "windows",
      "tools": {
        "python": "3.14.10",
        "pytest": "9.2.0",
        "pyqt6": "6.11.0",
        "pytest-timeout": "2.4.0",
        "coverage": "7.17.0",
        "mypy": "2.4.1",
        "ruff": "0.17.4",
        "zizmor": "1.31.1",
        "actionlint": "1.7.12",
        "uv": "0.12.7",
        "shellcheck": "0.11.0",
        "podman": "6.2.0"
      }
    },
    "verified_tasks": [
      "T1",
      "T2",
      "T3",
      "T4",
      "T5",
      "T6",
      "T7"
    ],
    "pending_operations": [
      {
        "id": "P-RELEASE",
        "description": "The first tag-pushed release (0.10.0) will be the first to draft, attest and publish through the new jobs. PR #18's Packages run 43701523037 at bf9d8ac ran every build job and, as designed for a run that isn't a tag, skipped sign-windows, test-signed-windows, checksums, attest and publish. No v0.10.0 tag exists yet (the newest is v0.9.2; reports/wave4b/github-settings.txt).",
        "next_action": "At the 0.10.0 release (Randy or the coordinator): push the tag, watch attest and publish, then run gh attestation verify <file> --repo RandyNorthrup/chatmon on one file."
      },
      {
        "id": "P-DEPENDABOT",
        "description": "Dependabot's first run, including whether it relocks the uv-compiled, hash-locked packaging/requirements*.txt from their .in files, is not observed. Dependabot reads .github/dependabot.yml from main, which doesn't have it yet (reports/wave4b/github-settings.txt, 2026-11-15). The owner turned on Dependabot alerts and security updates on 2026-11-14.",
        "next_action": "After the PR reaches main (the coordinator), read Dependabot's first pull requests. If it can't relock the uv-made files, lock them by hand on its proposals (CONTRIBUTING.md has the command)."
      }
    ],
    "next_action": "Two outcomes remain, neither in reach before a tag and a merge: the 0.10.0 tag (P-RELEASE, Randy or the coordinator) and Dependabot's first run once .github/dependabot.yml is on main (P-DEPENDABOT, the coordinator). wave4/crash may change code: re-run this plan's checks on the merged tree. wave4/crash (not merged at bf9d8ac) changes none of the files this plan's receipts bind.",
    "source_revision": "bf9d8ac2cbb3a97cf8b38d02643f2bca9847d545"
  }
}
```
