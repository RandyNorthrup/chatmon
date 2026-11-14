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
        "revision": "4fdf790"
      }
    ],
    "inputs": [
      "tests/conftest.py",
      "tests/drills/run.py",
      "chatmon/changelog.py",
      "tests/test_cli.py"
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
        "RED-MYPY"
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
        "RED-PIP"
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
        "RED-COMMANDS"
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
        "M-WINUPDATE"
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
        "M-WORKFLOWS"
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
        "M-SDE"
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
        "M-DOCS"
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
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "B-ZIZMOR",
      "acceptance": [
        "M6A-01.A1",
        "M6A-12.A1"
      ],
      "kind": "behavior",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "RED-ZIZMOR",
      "acceptance": [
        "M6A-01.A1",
        "M6A-12.A1"
      ],
      "kind": "red",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "B-PYTEST-WIN",
      "acceptance": [
        "M6A-01.A3"
      ],
      "kind": "behavior",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "RED-WARNINGS",
      "acceptance": [
        "M6A-01.A3"
      ],
      "kind": "red",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "RED-MARKS",
      "acceptance": [
        "M6A-01.A3"
      ],
      "kind": "red",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "B-DISTRO-UBUNTU",
      "acceptance": [
        "M6A-03.A1"
      ],
      "kind": "behavior",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "B-DISTRO-DEBIAN",
      "acceptance": [
        "M6A-03.A1"
      ],
      "kind": "behavior",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "B-DISTRO-FEDORA",
      "acceptance": [
        "M6A-03.A1"
      ],
      "kind": "behavior",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "RED-DISTRO",
      "acceptance": [
        "M6A-03.A1"
      ],
      "kind": "red",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "B-COVERAGE",
      "acceptance": [
        "M6A-04.A1"
      ],
      "kind": "behavior",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "RED-FLOOR",
      "acceptance": [
        "M6A-04.A1"
      ],
      "kind": "red",
      "status": "pass",
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
      "reason": null
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
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "RED-QT",
      "acceptance": [
        "M6A-05.A1"
      ],
      "kind": "red",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "RED-HASH",
      "acceptance": [
        "M6A-06.A1"
      ],
      "kind": "red",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "RED-STALE",
      "acceptance": [
        "M6A-06.A1"
      ],
      "kind": "red",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "RED-DEV",
      "acceptance": [
        "M6A-10.A2"
      ],
      "kind": "red",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "RED-GLOB",
      "acceptance": [
        "M6A-08.A1"
      ],
      "kind": "red",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "B-INSTALL",
      "acceptance": [
        "M6A-06.A2"
      ],
      "kind": "behavior",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "RED-PIP",
      "acceptance": [
        "M6A-06.A2"
      ],
      "kind": "red",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "B-WHEEL-JOB",
      "acceptance": [
        "M6A-08.A2",
        "M6A-09.A1"
      ],
      "kind": "behavior",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "RED-WHEEL",
      "acceptance": [
        "M6A-08.A2"
      ],
      "kind": "red",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "RED-TWINE",
      "acceptance": [
        "M6A-08.A2"
      ],
      "kind": "red",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "RED-COMMANDS",
      "acceptance": [
        "M6A-09.A1"
      ],
      "kind": "red",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "B-ACTIONLINT",
      "acceptance": [
        "M6A-12.A1"
      ],
      "kind": "behavior",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "RED-ACTIONLINT",
      "acceptance": [
        "M6A-12.A1"
      ],
      "kind": "red",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "B-MYPY",
      "acceptance": [
        "M6A-13.A1"
      ],
      "kind": "behavior",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "RED-MYPY",
      "acceptance": [
        "M6A-13.A1"
      ],
      "kind": "red",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "B-CHECKSUMS",
      "acceptance": [
        "M6A-I1.A1"
      ],
      "kind": "behavior",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "RED-CHECKSUMS",
      "acceptance": [
        "M6A-I1.A1"
      ],
      "kind": "red",
      "status": "pass",
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
      "reason": null
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
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "M-DEPENDABOT",
      "acceptance": [
        "M6A-02.A1"
      ],
      "kind": "manual",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "M-SDE",
      "acceptance": [
        "M6A-06.A3"
      ],
      "kind": "manual",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "M-DOCS",
      "acceptance": [
        "M6A-10.A1"
      ],
      "kind": "manual",
      "status": "pass",
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
      "reason": null
    },
    {
      "id": "M-WINUPDATE",
      "acceptance": [
        "M6A-11.A1"
      ],
      "kind": "manual",
      "status": "pass",
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
      "reason": null
    }
  ],
  "checkpoint": {
    "scope_sha256": "5fea0f739ac821f4482e76b7daa7c6e694d254fa74a558224458076003fcba0f",
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
      },
      {
        "path": "tests/test_windows.py",
        "sha256": "8ae5b99db789282121ab2069d517205160ddfc2fca8b4511ebfc045c33097d99"
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
        "id": "P-CI-FIRST",
        "description": "ci.yml's first run on GitHub (lint, types x3, nine test legs, coverage, distro x3, gnome) has not happened: pushes no longer start CI on a branch.",
        "next_action": "After merging wave1/m6a, the coordinator runs `gh workflow run ci.yml --ref improve/assessment-fixes` (or opens the PR as a draft) and sends any failing job back to M6A; M7 owns the Windows app-smoke and bubble failures already known."
      },
      {
        "id": "P-COVERAGE-FLOOR",
        "description": "The combined coverage of the three OSes in CI is not yet observed; fail_under is 72 from Windows alone (74.9%); Windows with Linux measured 82.7%.",
        "next_action": "Read the coverage job's summary on the first CI run; if well above 72, raise fail_under to about two points under it."
      },
      {
        "id": "P-PACKAGES-PR",
        "description": "packages.yml's changed jobs (locked installs, SOURCE_DATE_EPOCH, twine and the dist tests, test-install-update.sh in the Linux job, M1A's macOS checks) have not run on GitHub.",
        "next_action": "The final PR touches packaging/ and pyproject.toml, so packages.yml runs on it (or `gh workflow run packages.yml --ref improve/assessment-fixes`); read the python, windows, macos and linux jobs."
      },
      {
        "id": "P-RELEASE",
        "description": "The first tag-pushed release (0.10.0) will be the first to draft, attest and publish through the new jobs.",
        "next_action": "At the 0.10.0 release, push the tag, watch attest and publish, then `gh attestation verify <file> --repo RandyNorthrup/chatmon` on one file."
      },
      {
        "id": "P-DEPENDABOT",
        "description": "Dependabot's first run, including whether it relocks the uv-compiled, hash-locked packaging/requirements*.txt from their .in files, is not observed.",
        "next_action": "After the change reaches main, read Dependabot's first pull requests; if it can't relock the uv-made files, lock them by hand on its proposals (CONTRIBUTING.md has the command)."
      },
      {
        "id": "P-MYPY-MERGES",
        "description": "The mypy gate (18 gated, 47 exempt) is provisional while M4A is unmerged.",
        "next_action": "At each later merge, run mypy --platform linux, win32 and darwin and move modules on or off the exemption list (integration note 5)."
      }
    ],
    "next_action": "Coordinator: merge wave1/m6a, then start CI by hand (integration note 1) and read the first runs (P-CI-FIRST, P-PACKAGES-PR, P-COVERAGE-FLOOR).",
    "source_revision": "22aa63b"
  }
}
```
