# M10: Follow-ups left for later

Three items earlier milestones handed on: comtypes for the Windows test legs ([M4A](m4a-platform-awareness.md#integration-notes)),
Qt's own translations in the installed apps ([M8](m8-translation.md#for-the-coordinator)), and mypy with PyQt6 6.12's
stubs ([M6B, note 3](m6b-static-analysis-logging.md#integration-notes)). Branch `wave4/followups`, from
`improve/assessment-fixes` at `fb19cb9` (0.10.0 merged, PR #18 open). The ledger at the end owns every requirement,
task, state and receipt. Reports, logs and the drill specs are in [reports/m10/](reports/m10/).

## Rationale

### Scope

- **M10-01, comtypes (test-only).** The Windows test legs install comtypes from the hash-locked test list, so M4A's
  UI Automation end-to-end test runs in CI instead of skipping.
- **M10-02, Qt's own translations.** For each language Chatmon has a catalog for (`chatmon/locale/<lang>.po`), the
  Windows (Nuitka) and macOS (PyInstaller) builds carry that language's `qtbase_<lang>.qm`, and no other Qt
  translation; i18n finds it in the frozen app. Linux's packages use the system's Qt translations.
- **M10-03, PyQt6 6.12's stubs.** `mypy --platform linux|win32|darwin` passes with 6.12.1's stubs as well as 6.11's,
  with no module exempted, and how to check against them is documented.

Non-goals: README.md and `chatmon/changelog.md` (notes below); `ci.yml`, `layer.py`, `wayland.py`, `xkb.py`,
`penguin.py`, `stagemenu.py` and `clickthrough.py`, which the wayland worker is changing (what they need is under
[Integration notes](#integration-notes)); `nfpm.yaml`; shipping a language. Every item was re-checked on `fb19cb9`
first, and the decisions are in [readiness.md](reports/m10/readiness.md) (D1-D19).

### Design

**comtypes (M10-01).** `requirements-test.in` pins `comtypes==1.4.17; sys_platform == 'win32'` (the newest release
before the locks' `--exclude-newer` date, 2026-10-31; 1.5.0 is five days old). The test and dev lists are locked again
with the documented command; nothing else in them moves, and their headers now record `--exclude-newer`. The `dev`
extra pins it too and the `test` extra names it, both for Windows. `ci.yml` needs nothing: every Windows test leg
installs `requirements-test.txt`. A new test in `tests/test_requirements.py` checks the test and dev locks hold
comtypes for Windows and no other platform, since losing it would turn the end-to-end test back into a quiet skip.

**Qt's own translations (M10-02).** Read in the locked tools' sources: Nuitka 4.3.1 copies Qt's translations only for
QtWebEngine, so the Windows app has carried none (`--noinclude-qt-translations` or not); PyInstaller 6.22.3 collects
every `qt_*`, `qtbase_*` and used module's translation, so the macOS app has carried all of Qt's languages, which
nothing loads.

| Where | What |
|---|---|
| `i18n.qt_translator(qtcore, code, folders)` | The one way a language's Qt file is found: `QTranslator.load(QLocale(code), "qtbase", "_", folder)` in each folder in turn, so "pt" is `qtbase_pt_BR.qm` and "zh" `qtbase_zh_CN.qm`, as Qt itself decides. |
| `i18n.qt_folders(qtcore)` | Where to look: `QLibraryInfo`'s TranslationsPath (pip's PyQt6, or a distribution's Qt for the .deb and .rpm), then, frozen only (`paths.frozen()`), `i18n.QT_FROZEN` under the folder holding the `chatmon` package. |
| `i18n.QT_FROZEN` | `PyQt6/Qt6/translations`: the wheel's own layout, where PyInstaller's qt.conf points Qt; Nuitka's dist folder gets the same, and i18n finds it there itself. |
| `build.qt_translations()` | For each language `i18n.available()` lists but English, the file `qt_translator` picks from the build's Qt. A language Qt doesn't translate adds nothing, and the build says so. |
| `build.nuitka()` | Adds `--include-data-files=<qm>=PyQt6/Qt6/translations/<name>` for each. |
| `build.pyinstaller_datas(datas)` | The spec's data files with Qt's translations narrowed to the same files. `chatmon.spec` loads build.py and applies it to `a.datas`. |

Only English ships, so both builds now carry no Qt translation at all; a `de.po` would add `qtbase_de.qm` and nothing
else.

**PyQt6 6.12.1's stubs (M10-03).** 6.12.1's stub generator writes `typing.Self` for the class's own name everywhere
(567 times in QtCore.pyi), and makes `pyqtSignal`'s `arguments` a keyword with no default. Fixed by kind, never by
exempting a module:

| Kind (per platform, before) | Fix |
|---|---|
| `pyqtSignal(...)` missing `arguments` (63) | `chatmon/qtsignal.py`: `pyqtSignal: Callable[..., QtCore.pyqtSignal] = QtCore.pyqtSignal`, the same object at run time. Modules import `pyqtSignal` from there; their declarations are unchanged. |
| a static constructor's unbound Self: "Need type annotation" (28) | the variable typed (`bus: QDBusConnection = QDBusConnection.sessionBus()`), as sysnotify.py and report.py already were |
| a parameter typed Self that takes any QObject or None (19) | `# type: ignore[arg-type]` on the line, with the reason, as sysnotify.py's parent already was |
| `QImage.constBits()` now optional | a real check: a null image has no rows |
| `QMenu.addMenu` now Self, so menus.py's cast is redundant | `# type: ignore[return-value]` for 6.11's optional result, which Qt never returns |

PyQt6 6.12.0 is not a target: its `QtDBus.pyi` has a syntax error (`*args, /`) that stops mypy before it reads
anything ([mypy-6120.log](reports/m10/mypy-6120.log)). So there's no hash-locked 6.12 check in CI yet: under the
two-week rule 6.12.0 is the newest that can be locked and it can't pass; 6.12.1 can be locked from 2026-11-28.
CONTRIBUTING.md says how to check against 6.12.1 meanwhile, and the coordinator's note has the list and the CI entry.

### Reuse

- `i18n.available()` decides which languages ship; `paths.frozen()` decides frozen; `tests/test_packaging.py`'s
  `build_module()` loads build.py for its tests, as the spec now does.
- The stub workarounds follow sysnotify.py's and report.py's (M4A, M6B).
- `tests/drills/run.py` runs the pytest drills (with `--python` for the CI-shaped venv); M6B's `gate_drills.py` is the
  model for this milestone's mypy drills.

New code with its own responsibility: `chatmon/qtsignal.py` (the one place the signal stub bug is handled), the three
build functions (what the installers carry), and `reports/m10/mypy_runs.py` and `gate_drills.py` (evidence tools).

## Results

Run on Windows 11 with Python 3.14.10, PyQt6 6.11.0 (Qt 6.11.2), pytest 9.2.0, ruff 0.17.4, mypy 2.4.1 and uv 0.12.7,
and a throwaway venv with PyQt6 6.12.1 (Qt 6.12.0) for the next stubs ([context.log](reports/m10/context.log)).
Commits: `983b95c` (comtypes, and this plan), `7972401` (Qt's translations), `d15d7a9` (6.12.1's stubs), then the
evidence and this plan, closed on 2026-11-15 after the owner's overnight pause
([pause-checkpoint.md](reports/m10/pause-checkpoint.md)); no code changed across the pause, and the tools were observed
again on resuming ([context.log](reports/m10/context.log)).

| Check | Command | Result |
|---|---|---|
| Whole suite | `python -m pytest -q -p no:cacheprovider` | 1244 passed, 148 skipped, every warning an error ([suite-final.log](reports/m10/suite-final.log)); fb19cb9 had 1241 and 148 ([suite-baseline-fb19cb9.log](reports/m10/suite-baseline-fb19cb9.log)). After each step: 1242 / 1244 / 1244 ([suite-comtypes.log](reports/m10/suite-comtypes.log), [suite-qt-translations.log](reports/m10/suite-qt-translations.log), [suite-qt6121-types.log](reports/m10/suite-qt6121-types.log)). |
| Locks | uv's compile again from the committed `.in` files; `pytest tests/test_requirements.py` | both locks identical to the committed ones; the diff against fb19cb9 is comtypes and the header line; 6 passed ([locks.log](reports/m10/locks.log)) |
| UI Automation in a CI-shaped venv | a fresh venv from `requirements-test.txt` with `--require-hashes`, then the end-to-end test with `-rs` | runs and passes, comtypes 1.4.17; from fb19cb9's lock it skips, "could not import 'comtypes'" ([uia-ci-venv.log](reports/m10/uia-ci-venv.log)) |
| Qt translations | `pytest tests/test_packaging.py tests/test_i18n.py` | 37 passed, 8 skipped (the macOS postinstall's, POSIX only) ([qt-translations.log](reports/m10/qt-translations.log)) |
| mypy, 6.11 | `mypy_runs.py` with the shared venv | no issues in 70 files on linux, win32 and darwin ([mypy-611.log](reports/m10/mypy-611.log)) |
| mypy, 6.12.1, the tree | `mypy_runs.py` with the throwaway venv | 14 errors on each platform, all in `layer.py` (2) and `penguin.py` (12), the wayland worker's; none elsewhere ([mypy-6121.log](reports/m10/mypy-6121.log)); before: 113 in 20 files ([mypy-6121-before.log](reports/m10/mypy-6121-before.log)). An observation, not a receipt: its exit is 1 by design. |
| mypy, 6.12.1 and 6.11, with the wayland files' changes | the same on a scratch copy with [wayland-files-qt6121.diff](reports/m10/wayland-files-qt6121.diff) applied | no issues in 70 files on all three platforms with either stub ([mypy-6121-wayland-copy.log](reports/m10/mypy-6121-wayland-copy.log)) |
| mypy, 6.12.0 | `mypy_runs.py` with a venv locked under the two-week rule | stops in PyQt6's own `QtDBus.pyi` (`'/' parameter must appear before '*' parameter`), before reading any module ([mypy-6120.log](reports/m10/mypy-6120.log)) |
| ruff, template | `ruff check .`; `python packaging/extract_strings.py --check` | clean; template current (no string changed) |
| Red drills | `python tests/drills/run.py docs/delivery/reports/m10/drill-spec.json --log docs/delivery/reports/m10/drills.log` | 9 of 9 green, red for the intended reason, green again with the file's bytes restored ([drills.log](reports/m10/drills.log)). The first run had two mistakes in the spec, not the tests: one expected message pytest abbreviates, and one two-line find written with LF for a CRLF file; both are kept ([drills-first.log](reports/m10/drills-first.log)) |
| Red drill, CI-shaped venv | the same harness with `--python %TEMP%\m10-ci-test\Scripts\python.exe` on [drill-spec-ci-venv.json](reports/m10/drill-spec-ci-venv.json) | 1 of 1: announcements raised as "All" instead of "ImportantAll" fail the end-to-end test, the client hearing `'processing': 2` ([drills-ci-venv.log](reports/m10/drills-ci-venv.log)) |
| Gate drills | `python docs/delivery/reports/m10/gate_drills.py %TEMP%\m10-qt6121\Scripts\python.exe` | 5 of 5: with 6.12.1, a signal from `PyQt6.QtCore`, a parent's ignore taken out, a constructor left untyped and the null-image check gone each fail naming the stub's error; with 6.11, the alias given the wrong type fails ([gate-drills.log](reports/m10/gate-drills.log)). The first run passed the same way, but its log kept only mypy's last lines, all notes, so the errors weren't in it; the rerun's log keeps them ([gate-drills-first.log](reports/m10/gate-drills-first.log)) |
| How-to | CONTRIBUTING.md's commands, as written ([howto-replay.sh](reports/m10/howto-replay.sh)), in WSL Arch (Python 3.14.9) on a copy with note 1's changes | the lock resolves PyQt6 6.12.1 with hashes, the venv installs it `--require-hashes`, and mypy finds no issues in 70 files on each platform, on Linux this time ([howto-replay.log](reports/m10/howto-replay.log)); every line reviewed in [howto-review.md](reports/m10/howto-review.md) |

**The frozen apps** (observations, Windows): packaging/build.py's own `nuitka()` on a copy of the tree with a
throwaway `de.po` and a probe in place of the entry built a program that carries `PyQt6/Qt6/translations/qtbase_de.qm`
and no other `.qm`; run, it chose German, `QLibraryInfo` pointed at that folder, and Qt's Cancel read "Abbrechen"
([frozen-nuitka.log](reports/m10/frozen-nuitka.log)). PyInstaller 6.22.3 on the real `chatmon.spec` (Windows standing in
for macOS: same spec and hooks, `_internal` for `Contents/Frameworks`): fb19cb9's spec carried 124 of Qt's translations
(64 `qt_*`, 32 `qtbase_*`, 28 `qtmultimedia_*`, 7.1 MB); this one carries none with English alone and only
`qtbase_de.qm` with a `de.po`, which the probe loaded: "Abbrechen" ([frozen-pyinstaller.log](reports/m10/frozen-pyinstaller.log)).
macOS itself wasn't run.

## Integration notes

1. **Coordinator, after the wayland worker merges: 6.12.1's stubs in `layer.py` and `penguin.py`.** Not changed
   here. [wayland-files-qt6121.diff](reports/m10/wayland-files-qt6121.diff) is the change on fb19cb9's files; by symbol,
   in case those lines moved:
   - both files: `pyqtSignal` imported from `.qtsignal`, not `PyQt6.QtCore`;
   - `layer.PipeReader.__init__`, `penguin.Hosted.__init__`: `super().__init__(parent)` / `(stage)` gets
     `# type: ignore[arg-type]  # PyQt6 6.12.1's stubs type QObject's parent as Self, this class`;
   - `penguin.StageWindow.__init__`: `super().__init__(None, flags)` gets the same ignore (a widget's parent as Self,
     never None);
   - `penguin.Hosted.cursor_at`: `child: QWidget | None = self.widget.childAt(...)` (6.12.1 says never None, so
     `child is not None` reads as always true);
   - `penguin.Stage.__init__`: `app: QCoreApplication | None = QGuiApplication.instance()`, with `QCoreApplication`
     added to the QtCore import.
   With these, mypy passes everything on all three platforms with 6.11's and 6.12.1's stubs, and CONTRIBUTING.md's
   "it also passes with the next PyQt6's stubs" is true of the merged branch. Any signal or QObject the wayland work
   adds follows the same three patterns (CONTRIBUTING.md, "Lint and types").
2. **Coordinator, from 2026-11-28 (6.12.1 two weeks old): a CI check against the next stubs.** It can't be hash-locked
   under the two-week rule today (6.12.0 can be and doesn't parse; 6.12.1 is new), so `ci.yml` (the wayland worker's)
   is unchanged. Then: `packaging/requirements-types-next.in` with `PyQt6==6.12.1`, `psutil==7.2.2` and
   `mypy==2.4.1` (the dev list's), locked like the rest (`uv pip compile requirements-types-next.in -o
   requirements-types-next.txt --universal --python-version 3.11 --generate-hashes --exclude-newer <two weeks back>`);
   `tests/test_requirements.py` checks it for hashes and its `.in` pins but leaves it out of the one-version rule (its
   Qt differs on purpose) and checks its mypy is the dev list's; and the `types` job gains an axis:
   ```yaml
       matrix:
         platform: [linux, win32, darwin]
         stubs: [requirements-dev.txt, requirements-types-next.txt]
       ...
         - env:
             STUBS: ${{ matrix.stubs }}
           run: python -m pip install --require-hashes -r "packaging/$STUBS"
   ```
   Drop the axis again once the shipped Qt is the next one.
3. **Dependabot will offer PyQt6 6.12.0** for the shipped Qt now (past its 14-day cooldown). Skip it: its `QtDBus.pyi`
   stops mypy, so every `types` job fails ([mypy-6120.log](reports/m10/mypy-6120.log)). 6.12.1 passes (note 1), from
   when Dependabot offers it.
4. **For the owner: an upstream report** (none found; sending it needs your PyQt mailing-list account). Draft:
   "PyQt6 6.12.1's stubs: `pyqtSignal.__init__` has `arguments: collections.abc.Sequence[str]` keyword-only with no
   default, so mypy rejects every `pyqtSignal(int)` with 'Missing named argument "arguments"'. The class's own name is
   written as `typing.Self` throughout, also where any QObject is meant (`QObject.__init__`'s parent,
   `installEventFilter`, `setParent`, which also lost `| None`) and in static methods (`QDBusConnection.sessionBus()`,
   `QCoreApplication.instance()`, `QPixmap.fromImage()`), where Self can't be bound. And 6.12.0's `QtDBus.pyi` has
   `*args: typing.Any, /` in `QDBusAbstractInterface.asyncCall` and `call`, which doesn't parse." Once a locked PyQt6 has
   it right, `chatmon/qtsignal.py` and the per-line ignores can go.
5. **`nfpm.yaml`'s owner, once a language ships:** recommend the distribution's Qt translations (`qt6-translations-l10n`
   for the .deb, `qt6-qttranslations` for the .rpm). The packages use the system's Qt, and i18n reads its folder first;
   without the package, Qt's buttons stay English there (as `test_qts_own_words...` skips in the distro containers).
6. **Two UI Automation tests at once.** The end-to-end test's client hears notifications from every window on the
   desktop, so two suites running it at the same moment on one computer (two workers' worktrees) can hear each
   other's announcer. CI's runners have one job each; on a shared workstation, a failure there with words from another
   run is that, not a regression.
7. **Small things.** In Nuitka's app `QLibraryInfo` gives the translations folder in 8.3 form (`M10-NU~1`), so the app's
   own copy, the same folder, is listed again in its long form: tried only if the first has nothing, so harmless.
   Evidence hashes are of the files as this worktree has them (CRLF for files Git checked out, LF for files written
   here); a fresh checkout changes the hashes, not the content.
8. **APIs.** `i18n.qt_folders(qtcore) -> list[str]`, `i18n.qt_translator(qtcore, code, folders) -> QTranslator | None`,
   `i18n.QT_FROZEN`; `build.LOCALE`, `build.qt_translations() -> list[Path]`, `build.nuitka_qt_translations()`,
   `build.pyinstaller_datas(datas)`; `chatmon.qtsignal.pyqtSignal`, which every module declares its signals with.

## Changelog notes

- **Qt's own buttons follow your language in the Windows and macOS apps,** once Chatmon ships a translation for it:
  the apps carry Qt's translation of its own words for each language Chatmon speaks (Linux's packages use your
  system's Qt translations).
- **The macOS app is smaller:** it no longer carries Qt's translations into languages Chatmon doesn't speak
  (124 files, about 7 MB, measured with the same spec on Windows).
- **Tested more:** CI's Windows tests now hear Chatmon's screen-reader announcements through UI Automation, as
  Narrator, NVDA and JAWS do, instead of skipping that test.

## README notes

- **Translation:** "Qt's own words (its dialogs' buttons) follow the language too: the Windows and macOS apps carry
  Qt's translation for each language Chatmon ships; on Linux they come from your distribution's Qt translations
  (`qt6-translations-l10n` on Debian and Ubuntu, `qt6-qttranslations` on Fedora)." Only once a language ships.
- **Running the tests / contributing:** "mypy also passes with the next PyQt6's stubs; CONTRIBUTING.md says how to
  check against them."


```quality-ledger
{
  "schema_version": 1,
  "work": {
    "id": "M10",
    "title": "Follow-ups: comtypes in CI, Qt's own translations in the installers, PyQt6 6.12's stubs",
    "scope_revision": 1,
    "brief": "docs/delivery/ASSESSMENT.md",
    "brief_reason": null,
    "rules": [
      {
        "path": "docs/delivery/ROADMAP.md",
        "revision": "fb19cb9"
      },
      {
        "path": "pyproject.toml",
        "revision": "wave4/followups"
      }
    ],
    "inputs": [
      "docs/delivery/m4a-platform-awareness.md",
      "docs/delivery/m6a-ci-tooling.md",
      "docs/delivery/m6b-static-analysis-logging.md",
      "docs/delivery/m8-translation.md",
      "tests/conftest.py",
      "tests/drills/run.py",
      "packaging/requirements.txt",
      "packaging/requirements-build.txt",
      "packaging/requirements-dev.in",
      "chatmon/winuia.py",
      "tests/test_platform_events.py",
      "tests/uia_client.py"
    ],
    "environment": {
      "platform": "windows",
      "tools": {
        "python": "3.14.10",
        "pytest": "9.2.0",
        "PyQt6": "6.11.0",
        "Qt": "6.11.2",
        "PyQt6-next": "6.12.1",
        "ruff": "0.17.4",
        "mypy": "2.4.1",
        "uv": "0.12.7"
      }
    }
  },
  "requirements": [
    {
      "id": "M10-01",
      "statement": "The Windows test legs install comtypes (test-only) from the hash-locked test list, so M4A's UI Automation end-to-end test runs in CI; the locks, .in files and dev extra keep agreeing",
      "priority": "normal",
      "acceptance": [
        "M10-01.A1",
        "M10-01.A2"
      ],
      "superseded_by": null
    },
    {
      "id": "M10-02",
      "statement": "The Windows and macOS builds carry qtbase_<lang>.qm for every language Chatmon has a catalog for, and no other Qt translation, and i18n finds them in the frozen app; Linux's packages use the system's Qt translations",
      "priority": "normal",
      "acceptance": [
        "M10-02.A1",
        "M10-02.A2"
      ],
      "superseded_by": null
    },
    {
      "id": "M10-03",
      "statement": "mypy --platform linux, win32 and darwin pass with PyQt6 6.12's stubs as well as 6.11's, with no module exempted, fixing the stub bugs precisely, and how to check against 6.12 is documented (a CI entry only if it can be hash-locked like the rest)",
      "priority": "normal",
      "acceptance": [
        "M10-03.A1",
        "M10-03.A2",
        "M10-03.A3"
      ],
      "superseded_by": null
    }
  ],
  "acceptance": [
    {
      "id": "M10-01.A1",
      "requirement": "M10-01",
      "given": "requirements-test.in pinning comtypes for Windows, locked again with CONTRIBUTING.md's uv command and --exclude-newer 2026-10-31",
      "when": "tests/test_requirements.py runs",
      "then": "The test and dev locks hold comtypes 1.4.17 with hashes for sys_platform == 'win32' alone, every other pin is unchanged, the dev extra pins it, and every lock test passes; a test lock that installs comtypes on every platform, or not at all, fails the new test",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M10-01.A2",
      "requirement": "M10-01",
      "given": "A fresh venv on Windows installed from requirements-test.txt with --require-hashes, as CI's Windows legs install it",
      "when": "test_a_ui_automation_client_hears_the_announcement runs there",
      "then": "It runs, not skipped, and passes: a UI Automation client in another process hears the announcement; with the announcer's notification broken it fails",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M10-02.A1",
      "requirement": "M10-02",
      "given": "A temporary copy of chatmon/locale: English alone, then with throwaway de.po and pt.po",
      "when": "build.py computes Nuitka's options and filters PyInstaller's data files",
      "then": "English alone carries no Qt translation; with de and pt, Nuitka's options include exactly qtbase_de.qm and qtbase_pt_BR.qm at PyQt6/Qt6/translations, and PyInstaller's data files keep only those two of Qt's translations, adding any the hooks missed, and every other data file",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M10-02.A2",
      "requirement": "M10-02",
      "given": "A frozen app's layout: Qt's own translations folder without qtbase_de.qm, and the app's PyQt6/Qt6/translations with it",
      "when": "i18n.setup('de') runs frozen, and then not frozen",
      "then": "Frozen, Qt's own words are German; not frozen, the app's folder isn't searched and they stay English; QLibraryInfo's folder comes first in either case",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M10-03.A1",
      "requirement": "M10-03",
      "given": "The shared venv's PyQt6 6.11 stubs, and a throwaway venv's PyQt6 6.12.1 stubs",
      "when": "mypy --platform linux, win32 and darwin runs with each",
      "then": "6.11 passes all three; 6.12.1 passes all three on every module but the wayland worker's layer.py and penguin.py, and on those too once their listed changes are applied in a copy; no module is exempted; a signal declared from PyQt6.QtCore again fails with 6.12.1, and a type error fails with 6.11",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M10-03.A2",
      "requirement": "M10-03",
      "given": "Every signal declared through chatmon/qtsignal.py",
      "when": "The whole suite runs",
      "then": "Every test passes as on fb19cb9 (1241 passed, 148 skipped, plus the new tests): the alias is PyQt6's pyqtSignal itself, so every signal connects and emits; an alias that isn't fails the signal tests",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "M10-03.A3",
      "requirement": "M10-03",
      "given": "No hash-locked 6.12 list can pass under the two-week rule today (6.12.0's QtDBus stub doesn't parse; 6.12.1 is new)",
      "when": "A contributor wants to check a change against the next stubs",
      "then": "CONTRIBUTING.md says how, in a venv of its own installed with hashes, and the plan gives the coordinator the list and the types job's CI entry for when 6.12.1 can be locked",
      "checks": [
        "manual"
      ],
      "manual_reason": "A how-to in CONTRIBUTING.md and an integration note: reviewed line by line against the commands this work actually ran (their logs are in reports/m10/); there is no behaviour to execute"
    }
  ],
  "tasks": [
    {
      "id": "T1-comtypes",
      "purpose": "comtypes for Windows in the test list, the locks redone, the extras, and a test that keeps it in",
      "acceptance": [
        "M10-01.A1",
        "M10-01.A2"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "packaging/requirements-test.in",
          "action": "modify"
        },
        {
          "path": "packaging/requirements-test.txt",
          "action": "modify"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "action": "modify"
        },
        {
          "path": "pyproject.toml",
          "action": "modify"
        },
        {
          "path": "tests/test_requirements.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-locks",
        "E-red-M10-01-announcement-not-important",
        "E-red-M10-01-comtypes-left-out-of-the-dev-lock",
        "E-red-M10-01-comtypes-on-every-platform",
        "E-suite",
        "E-uia-ci-venv"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T2-qt-translations",
      "purpose": "The builds carry each shipped language's qtbase file and no other, found the way Qt finds it, and i18n looks in the frozen app's own folder",
      "acceptance": [
        "M10-02.A1",
        "M10-02.A2"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/i18n.py",
          "action": "modify"
        },
        {
          "path": "packaging/build.py",
          "action": "modify"
        },
        {
          "path": "packaging/chatmon.spec",
          "action": "modify"
        },
        {
          "path": "tests/test_i18n.py",
          "action": "modify"
        },
        {
          "path": "tests/test_packaging.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-qt-translations",
        "E-red-M10-02-app-folder-before-qts",
        "E-red-M10-02-english-carries-qts-english",
        "E-red-M10-02-frozen-app-folder-never-looked-in",
        "E-red-M10-02-nuitka-left-without-them",
        "E-red-M10-02-pyinstaller-keeps-every-language",
        "E-red-M10-02-translator-only-asks-qt",
        "E-suite"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T3-qt612-types",
      "purpose": "Every module but the wayland worker's two passes mypy with PyQt6 6.12.1's stubs and 6.11's: the signal alias, typed constructors, per-line ignores for Self-typed parameters, and the how-to",
      "acceptance": [
        "M10-03.A1",
        "M10-03.A2",
        "M10-03.A3"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/qtsignal.py",
          "action": "create"
        },
        {
          "path": "chatmon/a11y.py",
          "action": "modify"
        },
        {
          "path": "chatmon/app.py",
          "action": "modify"
        },
        {
          "path": "chatmon/brains.py",
          "action": "modify"
        },
        {
          "path": "chatmon/bubble.py",
          "action": "modify"
        },
        {
          "path": "chatmon/chatswin.py",
          "action": "modify"
        },
        {
          "path": "chatmon/hotkey.py",
          "action": "modify"
        },
        {
          "path": "chatmon/keychain.py",
          "action": "modify"
        },
        {
          "path": "chatmon/linuxsession.py",
          "action": "modify"
        },
        {
          "path": "chatmon/macnative.py",
          "action": "modify"
        },
        {
          "path": "chatmon/menus.py",
          "action": "modify"
        },
        {
          "path": "chatmon/packagekit.py",
          "action": "modify"
        },
        {
          "path": "chatmon/portal.py",
          "action": "modify"
        },
        {
          "path": "chatmon/presence.py",
          "action": "modify"
        },
        {
          "path": "chatmon/settingswin.py",
          "action": "modify"
        },
        {
          "path": "chatmon/sound.py",
          "action": "modify"
        },
        {
          "path": "chatmon/sprites.py",
          "action": "modify"
        },
        {
          "path": "chatmon/updates.py",
          "action": "modify"
        },
        {
          "path": "chatmon/wintoast.py",
          "action": "modify"
        },
        {
          "path": "CONTRIBUTING.md",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "E-howto",
        "E-mypy-611",
        "E-mypy-6121-copy",
        "E-red-M10-03-alias-not-pyqts-signal",
        "E-red-gate-alias-mistyped",
        "E-red-gate-constructor-untyped",
        "E-red-gate-null-image-unchecked",
        "E-red-gate-parent-unignored",
        "E-red-gate-signal-from-qtcore",
        "E-suite"
      ],
      "blocker": null,
      "superseded_by": null
    }
  ],
  "evidence": [
    {
      "id": "E-readiness",
      "acceptance": [
        "M10-01.A1",
        "M10-01.A2",
        "M10-02.A1",
        "M10-02.A2",
        "M10-03.A1",
        "M10-03.A2",
        "M10-03.A3"
      ],
      "kind": "readiness",
      "status": "pass",
      "command": [],
      "method": "Requirements review of the three follow-ups against M4A's, M6B's and M8's notes, the roadmap's rules and the wave-4 brief: each re-checked on fb19cb9 (the locked Nuitka's and PyInstaller's sources read, mypy run with 6.12.0's and 6.12.1's stubs), decisions D1-D19, failure behaviour, terms, coverage and the files left to the wayland worker (readiness.md).",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m10/readiness.md",
        "sha256": "a0a7561095389770b4776545ddf3b73847950dd46e754b194e636ed4626dad1b"
      },
      "inputs": [
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "9130daf8ba42d6fea1f889a520c950eaffd04692dfb5bd007e5e6f1ae80b3cb9",
      "red": null,
      "reason": null
    },
    {
      "id": "E-locks",
      "acceptance": [
        "M10-01.A1"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_requirements.py"
      ],
      "method": "The lock tests on the final tree, after locking the test and dev lists again with the documented uv command: every lock pinned and hashed, at its .in file's versions, one version per package, the dev extra in step, and comtypes for Windows alone; the log also shows the relock's diff against fb19cb9 (comtypes and its header line only).",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/locks.log",
        "sha256": "6cc4ef11e9c7baef7dad146d6fb25bceeedbfc56db4e8fdc6e96582723d235e5"
      },
      "inputs": [
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "af1dc11bd8f63827bd4e5cf4b4f124b3bc7fb60000f9377ea96b804a68a81afa"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e7923dce3696b85dc93b177e154d62a323504d56697385d085f8768449d8af2b"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "f5122c3d510e439ddc7b0f33c77a66d32944bb33969c4e70161b8652c150c046",
      "red": null,
      "reason": null
    },
    {
      "id": "E-uia-ci-venv",
      "acceptance": [
        "M10-01.A2"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "%TEMP%/m10-ci-test/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_platform_events.py::test_a_ui_automation_client_hears_the_announcement"
      ],
      "method": "A fresh venv from C:\\Python314, installed from packaging/requirements-test.txt with --require-hashes as CI's Windows legs install it (comtypes 1.4.17 among them), runs the UI Automation end-to-end test on the final tree with -rs: it runs, not skipped, and passes.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/uia-ci-venv.log",
        "sha256": "f87f4e02f368834573362c0f02a42e14fa22aad8eaf77790ef86aee4df6f8f14"
      },
      "inputs": [
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "af1dc11bd8f63827bd4e5cf4b4f124b3bc7fb60000f9377ea96b804a68a81afa"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e7923dce3696b85dc93b177e154d62a323504d56697385d085f8768449d8af2b"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "f5122c3d510e439ddc7b0f33c77a66d32944bb33969c4e70161b8652c150c046",
      "red": null,
      "reason": null
    },
    {
      "id": "E-qt-translations",
      "acceptance": [
        "M10-02.A1",
        "M10-02.A2"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_packaging.py",
        "tests/test_i18n.py"
      ],
      "method": "The build's and i18n's tests on the final tree, real Qt (6.11.2) offscreen: build.py's Nuitka options and PyInstaller data files for a temporary locale folder, English alone and with throwaway de.po and pt.po, and i18n.setup in a frozen app's layout, frozen and not.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/qt-translations.log",
        "sha256": "f68ee418922e386df520340ffab54e6e1e9f93ea8571a218fe3523f331af5a84"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "81a5cddbc39774996891111e8fa77911be56008e1f2d06609fa5fe867bd74dff"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "4d340c2aa6c3165e315ce83d10d52e5e40f1e3d30b9ba13e3dcc5176b58ed3f7"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "d5ccbdca187a3daefcae4c556348984bb0abbef04646072d5dce67b24f53445a"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "d97f091ad1d74165b3d184d522c45bbe2f451a2caa5e981bc6bc3b225c6e86c2",
      "red": null,
      "reason": null
    },
    {
      "id": "E-mypy-611",
      "acceptance": [
        "M10-03.A1"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m10/mypy_runs.py",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m10/mypy-611.log"
      ],
      "method": "mypy for linux, win32 and darwin on the final tree with the shared venv's PyQt6 6.11.0 stubs (CI's lock) and pyproject.toml's settings, no module exempted: no issues in 70 files on each.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/mypy-611.log",
        "sha256": "1ce2a79a9d7149321b3cbfaa62d40d050d5a1797950ad4fdedd6163a3e1e33fc"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "e9a7e11d8a806144ca3ba837d4e7d2d1ea2d5a9f31f8462c24228b96f7b6eddd"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "eea305a08e3d5539258148b2bcb424971b5b99b7352b02273dc7823ea7c67508"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "539cc6e36fbb2a4c9087ded0fe23df91c1cab864f83a8246651ccb5f9b2866ad"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "a08f4083367cf24d7f24bdef5ad57f7278ac72443a4b150ecffeec7ac9173590"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "92e78ff220c4adf2bd3a48b4340a3e5cd3107ad517442c03c33a0b641d680e87"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "57c7e766ae1363dc2ff4deae52b3497f5667cb791ee7a796cd7b7f218dba2c93"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "88eba42ee487cc12ef34144c1e8b5ba4d8e81e4b73c346a051fc2a7ce682c501"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "49eea3fb007441614be3175d28d3d8819ffed95c94fa55a2e848948543cababf"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "c5a4bdd645c2acf29c8036724d12eb4b35d966878560f63ca77cb93fdd86bc7b"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "6a8ebada5c700063ebe9580ecba664012f4ae38843007070f445a6c2771ed81c"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "3cf6ee06d581a446d3e38948ee6dca818e586959cd70c63bb5db22498bb832dd"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "bc9070b1bc8259512adb12fbb872e8246801213b071242a7162c4aabda26b912"
        },
        {
          "path": "chatmon/qtsignal.py",
          "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "e951e136e4a2c89c6b660ac8e4af02078d92fd8f6baf83bba9e7c1ba8c0434f7"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "589baea64239425f4ca99bee706bfdb3d908043d00795011e98e4c8ea1cf4d85"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "7fc4b92b45f08189111888c993ad1e6ef92e8ca553f95a8c61b5f99258ce87c4"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "fa430d69bec693f4fcb862b52ba673beda00b775df43f106ed6a46a49bcdd2ea",
      "red": null,
      "reason": null
    },
    {
      "id": "E-mypy-6121-copy",
      "acceptance": [
        "M10-03.A1"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m10/mypy_runs.py",
        "%TEMP%/m10-qt6121/Scripts/python.exe",
        "docs/delivery/reports/m10/mypy-6121-wayland-copy.log",
        "--root",
        "%TEMP%/m10probe/wcopy"
      ],
      "method": "mypy for linux, win32 and darwin with the throwaway venv's PyQt6 6.12.1 stubs on a scratch copy of the final chatmon/ and pyproject.toml with the integration note's changes to layer.py and penguin.py applied (wayland-files-qt6121.diff): no issues in 70 files on each; then the shared venv's 6.11 stubs on the same copy: none either.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/mypy-6121-wayland-copy.log",
        "sha256": "1becada573c205c7dc925122d292876c890392535d83cdd7865cc601d4dc3663"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "e9a7e11d8a806144ca3ba837d4e7d2d1ea2d5a9f31f8462c24228b96f7b6eddd"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "eea305a08e3d5539258148b2bcb424971b5b99b7352b02273dc7823ea7c67508"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "539cc6e36fbb2a4c9087ded0fe23df91c1cab864f83a8246651ccb5f9b2866ad"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "a08f4083367cf24d7f24bdef5ad57f7278ac72443a4b150ecffeec7ac9173590"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "92e78ff220c4adf2bd3a48b4340a3e5cd3107ad517442c03c33a0b641d680e87"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "57c7e766ae1363dc2ff4deae52b3497f5667cb791ee7a796cd7b7f218dba2c93"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "88eba42ee487cc12ef34144c1e8b5ba4d8e81e4b73c346a051fc2a7ce682c501"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "49eea3fb007441614be3175d28d3d8819ffed95c94fa55a2e848948543cababf"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "c5a4bdd645c2acf29c8036724d12eb4b35d966878560f63ca77cb93fdd86bc7b"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "6a8ebada5c700063ebe9580ecba664012f4ae38843007070f445a6c2771ed81c"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "3cf6ee06d581a446d3e38948ee6dca818e586959cd70c63bb5db22498bb832dd"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "bc9070b1bc8259512adb12fbb872e8246801213b071242a7162c4aabda26b912"
        },
        {
          "path": "chatmon/qtsignal.py",
          "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "e951e136e4a2c89c6b660ac8e4af02078d92fd8f6baf83bba9e7c1ba8c0434f7"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "589baea64239425f4ca99bee706bfdb3d908043d00795011e98e4c8ea1cf4d85"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "7fc4b92b45f08189111888c993ad1e6ef92e8ca553f95a8c61b5f99258ce87c4"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "fa430d69bec693f4fcb862b52ba673beda00b775df43f106ed6a46a49bcdd2ea",
      "red": null,
      "reason": null
    },
    {
      "id": "E-suite",
      "acceptance": [
        "M10-01.A1",
        "M10-02.A1",
        "M10-02.A2",
        "M10-03.A2"
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
      "method": "The whole suite on the final tree in the shared venv (real Qt objects offscreen, every warning an error): it runs the lock tests, the build's and i18n's new tests, and every test of a module whose signals moved to chatmon/qtsignal.py.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/suite-final.log",
        "sha256": "69214d49a814d0d0a6c7203be9147e2513bbdf00c356930c4f357fbd4c2999d1"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "e9a7e11d8a806144ca3ba837d4e7d2d1ea2d5a9f31f8462c24228b96f7b6eddd"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "eea305a08e3d5539258148b2bcb424971b5b99b7352b02273dc7823ea7c67508"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "539cc6e36fbb2a4c9087ded0fe23df91c1cab864f83a8246651ccb5f9b2866ad"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "a08f4083367cf24d7f24bdef5ad57f7278ac72443a4b150ecffeec7ac9173590"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "92e78ff220c4adf2bd3a48b4340a3e5cd3107ad517442c03c33a0b641d680e87"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "57c7e766ae1363dc2ff4deae52b3497f5667cb791ee7a796cd7b7f218dba2c93"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "88eba42ee487cc12ef34144c1e8b5ba4d8e81e4b73c346a051fc2a7ce682c501"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "49eea3fb007441614be3175d28d3d8819ffed95c94fa55a2e848948543cababf"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "c5a4bdd645c2acf29c8036724d12eb4b35d966878560f63ca77cb93fdd86bc7b"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "6a8ebada5c700063ebe9580ecba664012f4ae38843007070f445a6c2771ed81c"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "3cf6ee06d581a446d3e38948ee6dca818e586959cd70c63bb5db22498bb832dd"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "bc9070b1bc8259512adb12fbb872e8246801213b071242a7162c4aabda26b912"
        },
        {
          "path": "chatmon/qtsignal.py",
          "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "e951e136e4a2c89c6b660ac8e4af02078d92fd8f6baf83bba9e7c1ba8c0434f7"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "589baea64239425f4ca99bee706bfdb3d908043d00795011e98e4c8ea1cf4d85"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "7fc4b92b45f08189111888c993ad1e6ef92e8ca553f95a8c61b5f99258ce87c4"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "81a5cddbc39774996891111e8fa77911be56008e1f2d06609fa5fe867bd74dff"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "af1dc11bd8f63827bd4e5cf4b4f124b3bc7fb60000f9377ea96b804a68a81afa"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "4d340c2aa6c3165e315ce83d10d52e5e40f1e3d30b9ba13e3dcc5176b58ed3f7"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "d5ccbdca187a3daefcae4c556348984bb0abbef04646072d5dce67b24f53445a"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e7923dce3696b85dc93b177e154d62a323504d56697385d085f8768449d8af2b"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "9130daf8ba42d6fea1f889a520c950eaffd04692dfb5bd007e5e6f1ae80b3cb9",
      "red": null,
      "reason": null
    },
    {
      "id": "E-howto",
      "acceptance": [
        "M10-03.A3"
      ],
      "kind": "manual",
      "status": "pass",
      "command": [],
      "method": "Review of CONTRIBUTING.md's how-to for the next stubs and of the integration note's CI entry, line by line against the commands this work ran (mypy_runs.py with the throwaway venv; uv's compile with and without --exclude-newer) and the logs they wrote.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m10/howto-review.md",
        "sha256": "8ec08b4f8ebe35b10fab547fc8e1520bb4708c3ce595372792eedf07566277d8"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "e9a7e11d8a806144ca3ba837d4e7d2d1ea2d5a9f31f8462c24228b96f7b6eddd"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "eea305a08e3d5539258148b2bcb424971b5b99b7352b02273dc7823ea7c67508"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "539cc6e36fbb2a4c9087ded0fe23df91c1cab864f83a8246651ccb5f9b2866ad"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "a08f4083367cf24d7f24bdef5ad57f7278ac72443a4b150ecffeec7ac9173590"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "92e78ff220c4adf2bd3a48b4340a3e5cd3107ad517442c03c33a0b641d680e87"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "57c7e766ae1363dc2ff4deae52b3497f5667cb791ee7a796cd7b7f218dba2c93"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "88eba42ee487cc12ef34144c1e8b5ba4d8e81e4b73c346a051fc2a7ce682c501"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "49eea3fb007441614be3175d28d3d8819ffed95c94fa55a2e848948543cababf"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "c5a4bdd645c2acf29c8036724d12eb4b35d966878560f63ca77cb93fdd86bc7b"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "6a8ebada5c700063ebe9580ecba664012f4ae38843007070f445a6c2771ed81c"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "3cf6ee06d581a446d3e38948ee6dca818e586959cd70c63bb5db22498bb832dd"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "bc9070b1bc8259512adb12fbb872e8246801213b071242a7162c4aabda26b912"
        },
        {
          "path": "chatmon/qtsignal.py",
          "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "e951e136e4a2c89c6b660ac8e4af02078d92fd8f6baf83bba9e7c1ba8c0434f7"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "589baea64239425f4ca99bee706bfdb3d908043d00795011e98e4c8ea1cf4d85"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "7fc4b92b45f08189111888c993ad1e6ef92e8ca553f95a8c61b5f99258ce87c4"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "fa430d69bec693f4fcb862b52ba673beda00b775df43f106ed6a46a49bcdd2ea",
      "red": null,
      "reason": null
    },
    {
      "id": "E-red-M10-01-comtypes-on-every-platform",
      "acceptance": [
        "M10-01.A1"
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
        "tests/test_requirements.py::test_the_windows_test_legs_install_the_screen_readers_ui_automation_client"
      ],
      "method": "Red drill M10-01-comtypes-on-every-platform through tests/drills/run.py in a temporary copy: green, packaging/requirements-test.txt mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/drills.log",
        "sha256": "4ad0c473b52a34ddea5887f9862987cee9c98013df2d3aed3cb0e911e0846fdb"
      },
      "inputs": [
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "af1dc11bd8f63827bd4e5cf4b4f124b3bc7fb60000f9377ea96b804a68a81afa"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e7923dce3696b85dc93b177e154d62a323504d56697385d085f8768449d8af2b"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "f5122c3d510e439ddc7b0f33c77a66d32944bb33969c4e70161b8652c150c046",
      "red": {
        "mutation": "M10-01-comtypes-on-every-platform: in packaging/requirements-test.txt, \"comtypes==1.4.17 ; sys_platform == 'win32' \\\\\" became 'comtypes==1.4.17 \\\\'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "requirements-test.txt installs comtypes on ['win32', 'linux', 'darwin'], not on Windows alone",
        "observed_diagnostic": "E           AssertionError: requirements-test.txt installs comtypes on ['win32', 'linux', 'darwin'], not on Windows alone: comtypes==1.4.17",
        "before": [
          {
            "path": "packaging/requirements-test.txt",
            "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
          }
        ],
        "mutated": [
          {
            "path": "packaging/requirements-test.txt",
            "sha256": "751fb1f89357494005610a336325ba5e0cdbf208cce6e3cb0f6050deeba63226"
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
      "id": "E-red-M10-01-comtypes-left-out-of-the-dev-lock",
      "acceptance": [
        "M10-01.A1"
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
        "tests/test_requirements.py::test_the_windows_test_legs_install_the_screen_readers_ui_automation_client",
        "tests/test_requirements.py::test_each_lock_holds_the_versions_its_in_file_names"
      ],
      "method": "Red drill M10-01-comtypes-left-out-of-the-dev-lock through tests/drills/run.py in a temporary copy: green, packaging/requirements-dev.txt mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/drills.log",
        "sha256": "4ad0c473b52a34ddea5887f9862987cee9c98013df2d3aed3cb0e911e0846fdb"
      },
      "inputs": [
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "af1dc11bd8f63827bd4e5cf4b4f124b3bc7fb60000f9377ea96b804a68a81afa"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e7923dce3696b85dc93b177e154d62a323504d56697385d085f8768449d8af2b"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "f5122c3d510e439ddc7b0f33c77a66d32944bb33969c4e70161b8652c150c046",
      "red": {
        "mutation": "M10-01-comtypes-left-out-of-the-dev-lock: in packaging/requirements-dev.txt, \"comtypes==1.4.17 ; sys_platform == 'win32' \\\\\" became \"comtypez==1.4.17 ; sys_platform == 'win32' \\\\\"",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "requirements-dev.txt doesn't lock comtypes",
        "observed_diagnostic": "E           AssertionError: requirements-dev.txt doesn't lock comtypes",
        "before": [
          {
            "path": "packaging/requirements-dev.txt",
            "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
          }
        ],
        "mutated": [
          {
            "path": "packaging/requirements-dev.txt",
            "sha256": "175f9524053c95f13d54ca20991379d6a5e578b95b6d3b990bb48675856edaea"
          }
        ],
        "after": [
          {
            "path": "packaging/requirements-dev.txt",
            "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M10-02-english-carries-qts-english",
      "acceptance": [
        "M10-02.A1"
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
        "tests/test_packaging.py::test_the_installers_carry_qts_own_words_for_each_language_chatmon_speaks_and_no_other"
      ],
      "method": "Red drill M10-02-english-carries-qts-english through tests/drills/run.py in a temporary copy: green, packaging/build.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/drills.log",
        "sha256": "4ad0c473b52a34ddea5887f9862987cee9c98013df2d3aed3cb0e911e0846fdb"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "81a5cddbc39774996891111e8fa77911be56008e1f2d06609fa5fe867bd74dff"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "4d340c2aa6c3165e315ce83d10d52e5e40f1e3d30b9ba13e3dcc5176b58ed3f7"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "d5ccbdca187a3daefcae4c556348984bb0abbef04646072d5dce67b24f53445a"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "d97f091ad1d74165b3d184d522c45bbe2f451a2caa5e981bc6bc3b225c6e86c2",
      "red": {
        "mutation": "M10-02-english-carries-qts-english: in packaging/build.py, '    for code in i18n.available(LOCALE)[1:]:' became '    for code in i18n.available(LOCALE):'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "English alone: Qt's own language",
        "observed_diagnostic": ">       assert build.qt_translations() == [], \"English alone: Qt's own language\"",
        "before": [
          {
            "path": "packaging/build.py",
            "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
          }
        ],
        "mutated": [
          {
            "path": "packaging/build.py",
            "sha256": "63b6b4a866a98aad2c901e68666424a5896748ccc5984a988b3f9e0a564308f3"
          }
        ],
        "after": [
          {
            "path": "packaging/build.py",
            "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M10-02-pyinstaller-keeps-every-language",
      "acceptance": [
        "M10-02.A1"
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
        "tests/test_packaging.py::test_the_installers_carry_qts_own_words_for_each_language_chatmon_speaks_and_no_other"
      ],
      "method": "Red drill M10-02-pyinstaller-keeps-every-language through tests/drills/run.py in a temporary copy: green, packaging/build.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/drills.log",
        "sha256": "4ad0c473b52a34ddea5887f9862987cee9c98013df2d3aed3cb0e911e0846fdb"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "81a5cddbc39774996891111e8fa77911be56008e1f2d06609fa5fe867bd74dff"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "4d340c2aa6c3165e315ce83d10d52e5e40f1e3d30b9ba13e3dcc5176b58ed3f7"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "d5ccbdca187a3daefcae4c556348984bb0abbef04646072d5dce67b24f53445a"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "d97f091ad1d74165b3d184d522c45bbe2f451a2caa5e981bc6bc3b225c6e86c2",
      "red": {
        "mutation": "M10-02-pyinstaller-keeps-every-language: in packaging/build.py, '    kept = [d for d in datas if not (Path(d[0]).parent == i18n.QT_FROZEN and Path(d[0]).suffix == \".qm\")]' became '    kept = list(datas)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "none of Qt's translations, and everything else kept",
        "observed_diagnostic": ">       assert build.pyinstaller_datas(hooked + own) == own, \"none of Qt's translations, and everything else kept\"",
        "before": [
          {
            "path": "packaging/build.py",
            "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
          }
        ],
        "mutated": [
          {
            "path": "packaging/build.py",
            "sha256": "80f79a525b7231a42d1565b378bd665291ef130023cdeefc24243e530bc5cd8c"
          }
        ],
        "after": [
          {
            "path": "packaging/build.py",
            "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M10-02-nuitka-left-without-them",
      "acceptance": [
        "M10-02.A1"
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
        "tests/test_packaging.py::test_the_installers_carry_qts_own_words_for_each_language_chatmon_speaks_and_no_other"
      ],
      "method": "Red drill M10-02-nuitka-left-without-them through tests/drills/run.py in a temporary copy: green, packaging/build.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/drills.log",
        "sha256": "4ad0c473b52a34ddea5887f9862987cee9c98013df2d3aed3cb0e911e0846fdb"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "81a5cddbc39774996891111e8fa77911be56008e1f2d06609fa5fe867bd74dff"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "4d340c2aa6c3165e315ce83d10d52e5e40f1e3d30b9ba13e3dcc5176b58ed3f7"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "d5ccbdca187a3daefcae4c556348984bb0abbef04646072d5dce67b24f53445a"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "d97f091ad1d74165b3d184d522c45bbe2f451a2caa5e981bc6bc3b225c6e86c2",
      "red": {
        "mutation": "M10-02-nuitka-left-without-them: in packaging/build.py, '\"--noinclude-qt-translations\", *nuitka_qt_translations(),' became '\"--noinclude-qt-translations\",'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "AssertionError: assert [] == ['--include-d",
        "observed_diagnostic": "E       AssertionError: assert [] == ['--include-d...ase_pt_BR.qm']",
        "before": [
          {
            "path": "packaging/build.py",
            "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
          }
        ],
        "mutated": [
          {
            "path": "packaging/build.py",
            "sha256": "cd45467f066cdc09218d9fa42977c7087024e72aaaecfea3c0383a017ac37f01"
          }
        ],
        "after": [
          {
            "path": "packaging/build.py",
            "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M10-02-frozen-app-folder-never-looked-in",
      "acceptance": [
        "M10-02.A2"
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
        "tests/test_i18n.py::test_an_installers_app_finds_qts_own_words_in_its_own_folder"
      ],
      "method": "Red drill M10-02-frozen-app-folder-never-looked-in through tests/drills/run.py in a temporary copy: green, chatmon/i18n.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/drills.log",
        "sha256": "4ad0c473b52a34ddea5887f9862987cee9c98013df2d3aed3cb0e911e0846fdb"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "81a5cddbc39774996891111e8fa77911be56008e1f2d06609fa5fe867bd74dff"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "4d340c2aa6c3165e315ce83d10d52e5e40f1e3d30b9ba13e3dcc5176b58ed3f7"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "d5ccbdca187a3daefcae4c556348984bb0abbef04646072d5dce67b24f53445a"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "d97f091ad1d74165b3d184d522c45bbe2f451a2caa5e981bc6bc3b225c6e86c2",
      "red": {
        "mutation": "M10-02-frozen-app-folder-never-looked-in: in chatmon/i18n.py, '    if paths.frozen():' became '    if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "Qt's own folder first",
        "observed_diagnostic": ">       assert i18n.qt_folders(QtCore) == [str(elsewhere), str(app / i18n.QT_FROZEN)], \"Qt's own folder first\"",
        "before": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "51efe7298d1bc7a6fd66c4fcc3bebefb82aee6ea089cfaa7a90fb13bfd83b609"
          }
        ],
        "after": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M10-02-app-folder-before-qts",
      "acceptance": [
        "M10-02.A2"
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
        "tests/test_i18n.py::test_an_installers_app_finds_qts_own_words_in_its_own_folder"
      ],
      "method": "Red drill M10-02-app-folder-before-qts through tests/drills/run.py in a temporary copy: green, chatmon/i18n.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/drills.log",
        "sha256": "4ad0c473b52a34ddea5887f9862987cee9c98013df2d3aed3cb0e911e0846fdb"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "81a5cddbc39774996891111e8fa77911be56008e1f2d06609fa5fe867bd74dff"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "4d340c2aa6c3165e315ce83d10d52e5e40f1e3d30b9ba13e3dcc5176b58ed3f7"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "d5ccbdca187a3daefcae4c556348984bb0abbef04646072d5dce67b24f53445a"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "d97f091ad1d74165b3d184d522c45bbe2f451a2caa5e981bc6bc3b225c6e86c2",
      "red": {
        "mutation": "M10-02-app-folder-before-qts: in chatmon/i18n.py, '        folders.append(str(_APP_FOLDER / QT_FROZEN))' became '        folders.insert(0, str(_APP_FOLDER / QT_FROZEN))'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "Qt's own folder first",
        "observed_diagnostic": ">       assert i18n.qt_folders(QtCore) == [str(elsewhere), str(app / i18n.QT_FROZEN)], \"Qt's own folder first\"",
        "before": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "7ea6af071b6b4d872b65a32713625d574e2c4c71204297fbf1b75123f2771f12"
          }
        ],
        "after": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M10-02-translator-only-asks-qt",
      "acceptance": [
        "M10-02.A2"
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
        "tests/test_i18n.py::test_an_installers_app_finds_qts_own_words_in_its_own_folder"
      ],
      "method": "Red drill M10-02-translator-only-asks-qt through tests/drills/run.py in a temporary copy: green, chatmon/i18n.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/drills.log",
        "sha256": "4ad0c473b52a34ddea5887f9862987cee9c98013df2d3aed3cb0e911e0846fdb"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "81a5cddbc39774996891111e8fa77911be56008e1f2d06609fa5fe867bd74dff"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "4d340c2aa6c3165e315ce83d10d52e5e40f1e3d30b9ba13e3dcc5176b58ed3f7"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "d5ccbdca187a3daefcae4c556348984bb0abbef04646072d5dce67b24f53445a"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "d97f091ad1d74165b3d184d522c45bbe2f451a2caa5e981bc6bc3b225c6e86c2",
      "red": {
        "mutation": "M10-02-translator-only-asks-qt: in chatmon/i18n.py, '    translator = qt_translator(qtcore, code, qt_folders(qtcore))' became '    translator = qt_translator(qtcore, code, [_qt_library_folder(qtcore)])'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert 'Cancel' == 'Abbrechen'",
        "observed_diagnostic": "E       AssertionError: assert 'Cancel' == 'Abbrechen'",
        "before": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "19f39bc92cd43e4425fdab768d158b49d97ba14c22346c134bea86ee1a3c9323"
          }
        ],
        "after": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M10-03-alias-not-pyqts-signal",
      "acceptance": [
        "M10-03.A2"
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
        "tests/test_platform_events.py::test_each_workspace_notification_is_its_own_signal"
      ],
      "method": "Red drill M10-03-alias-not-pyqts-signal through tests/drills/run.py in a temporary copy: green, chatmon/qtsignal.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/drills.log",
        "sha256": "4ad0c473b52a34ddea5887f9862987cee9c98013df2d3aed3cb0e911e0846fdb"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "e9a7e11d8a806144ca3ba837d4e7d2d1ea2d5a9f31f8462c24228b96f7b6eddd"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "eea305a08e3d5539258148b2bcb424971b5b99b7352b02273dc7823ea7c67508"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "539cc6e36fbb2a4c9087ded0fe23df91c1cab864f83a8246651ccb5f9b2866ad"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "a08f4083367cf24d7f24bdef5ad57f7278ac72443a4b150ecffeec7ac9173590"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "92e78ff220c4adf2bd3a48b4340a3e5cd3107ad517442c03c33a0b641d680e87"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "57c7e766ae1363dc2ff4deae52b3497f5667cb791ee7a796cd7b7f218dba2c93"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "88eba42ee487cc12ef34144c1e8b5ba4d8e81e4b73c346a051fc2a7ce682c501"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "49eea3fb007441614be3175d28d3d8819ffed95c94fa55a2e848948543cababf"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "c5a4bdd645c2acf29c8036724d12eb4b35d966878560f63ca77cb93fdd86bc7b"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "6a8ebada5c700063ebe9580ecba664012f4ae38843007070f445a6c2771ed81c"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "3cf6ee06d581a446d3e38948ee6dca818e586959cd70c63bb5db22498bb832dd"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "bc9070b1bc8259512adb12fbb872e8246801213b071242a7162c4aabda26b912"
        },
        {
          "path": "chatmon/qtsignal.py",
          "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "e951e136e4a2c89c6b660ac8e4af02078d92fd8f6baf83bba9e7c1ba8c0434f7"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "589baea64239425f4ca99bee706bfdb3d908043d00795011e98e4c8ea1cf4d85"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "7fc4b92b45f08189111888c993ad1e6ef92e8ca553f95a8c61b5f99258ce87c4"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "fa430d69bec693f4fcb862b52ba673beda00b775df43f106ed6a46a49bcdd2ea",
      "red": {
        "mutation": "M10-03-alias-not-pyqts-signal: in chatmon/qtsignal.py, '= QtCore.pyqtSignal' became '= lambda *types, **named: QtCore.pyqtSignal()'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_each_workspace_notification_is_its_own_signal",
        "observed_diagnostic": "_____________ test_each_workspace_notification_is_its_own_signal ______________",
        "before": [
          {
            "path": "chatmon/qtsignal.py",
            "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/qtsignal.py",
            "sha256": "24ddab68965c23c232333bead93acddf23d5887716f93418a095604ff14e9293"
          }
        ],
        "after": [
          {
            "path": "chatmon/qtsignal.py",
            "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-M10-01-announcement-not-important",
      "acceptance": [
        "M10-01.A2"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\AppData\\Local\\Temp/m10-ci-test/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_platform_events.py::test_a_ui_automation_client_hears_the_announcement"
      ],
      "method": "Red drill M10-01-announcement-not-important through tests/drills/run.py in a temporary copy: green, chatmon/winuia.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/drills-ci-venv.log",
        "sha256": "1a1c65c8b823f5a08ef62b2c01b2550ab5efee1b181d65082ea88fbab80ec108"
      },
      "inputs": [
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "af1dc11bd8f63827bd4e5cf4b4f124b3bc7fb60000f9377ea96b804a68a81afa"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e7923dce3696b85dc93b177e154d62a323504d56697385d085f8768449d8af2b"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "f5122c3d510e439ddc7b0f33c77a66d32944bb33969c4e70161b8652c150c046",
      "red": {
        "mutation": "M10-01-announcement-not-important: in chatmon/winuia.py, 'IMPORTANT_ALL if important else ALL, words, activity)' became 'ALL if important else ALL, words, activity)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "'processing': 2",
        "observed_diagnostic": "E       AssertionError: [{'kind': 4, 'processing': 2, 'words': 'Reminder. Stretch your legs.', 'activity': 'chatmon.announcement'}]",
        "before": [
          {
            "path": "chatmon/winuia.py",
            "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/winuia.py",
            "sha256": "d0f20c188adee9c4e4544b8d6c6331e577add8d787893e83a3eb0870bb498e60"
          }
        ],
        "after": [
          {
            "path": "chatmon/winuia.py",
            "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-gate-signal-from-qtcore",
      "acceptance": [
        "M10-03.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m10/gate_drills.py"
      ],
      "method": "Gate drill signal-from-qtcore (gate_drills.py) in a temporary copy of chatmon/ and pyproject.toml: mypy with PyQt6 6.12.1's stubs green, then failing on one change and naming Missing named argument \"arguments\" for \"pyqtSignal\", then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/gate-drills.log",
        "sha256": "9f535f3e0dd827d39f069b4034ec581bd45add8f182b2eabfbfc3b99ae107478"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "e9a7e11d8a806144ca3ba837d4e7d2d1ea2d5a9f31f8462c24228b96f7b6eddd"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "eea305a08e3d5539258148b2bcb424971b5b99b7352b02273dc7823ea7c67508"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "539cc6e36fbb2a4c9087ded0fe23df91c1cab864f83a8246651ccb5f9b2866ad"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "a08f4083367cf24d7f24bdef5ad57f7278ac72443a4b150ecffeec7ac9173590"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "92e78ff220c4adf2bd3a48b4340a3e5cd3107ad517442c03c33a0b641d680e87"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "57c7e766ae1363dc2ff4deae52b3497f5667cb791ee7a796cd7b7f218dba2c93"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "88eba42ee487cc12ef34144c1e8b5ba4d8e81e4b73c346a051fc2a7ce682c501"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "49eea3fb007441614be3175d28d3d8819ffed95c94fa55a2e848948543cababf"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "c5a4bdd645c2acf29c8036724d12eb4b35d966878560f63ca77cb93fdd86bc7b"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "6a8ebada5c700063ebe9580ecba664012f4ae38843007070f445a6c2771ed81c"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "3cf6ee06d581a446d3e38948ee6dca818e586959cd70c63bb5db22498bb832dd"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "bc9070b1bc8259512adb12fbb872e8246801213b071242a7162c4aabda26b912"
        },
        {
          "path": "chatmon/qtsignal.py",
          "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "e951e136e4a2c89c6b660ac8e4af02078d92fd8f6baf83bba9e7c1ba8c0434f7"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "589baea64239425f4ca99bee706bfdb3d908043d00795011e98e4c8ea1cf4d85"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "7fc4b92b45f08189111888c993ad1e6ef92e8ca553f95a8c61b5f99258ce87c4"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "fa430d69bec693f4fcb862b52ba673beda00b775df43f106ed6a46a49bcdd2ea",
      "red": {
        "mutation": "signal-from-qtcore: in chatmon/hotkey.py, 'from .qtsignal import pyqtSignal' became 'from PyQt6.QtCore import pyqtSignal'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "Missing named argument \"arguments\" for \"pyqtSignal\"",
        "observed_diagnostic": "chatmon\\hotkey.py:460: error: Missing named argument \"arguments\" for \"pyqtSignal\"  [call-arg]",
        "before": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "f9a2a1065975eefef7e1bb6961c4e67268b322891fb32269185b15eb3975cba5"
          }
        ],
        "after": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-gate-parent-unignored",
      "acceptance": [
        "M10-03.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m10/gate_drills.py"
      ],
      "method": "Gate drill parent-unignored (gate_drills.py) in a temporary copy of chatmon/ and pyproject.toml: mypy with PyQt6 6.12.1's stubs green, then failing on one change and naming Argument 1 to \"__init__\" of \"QObject\" has incompatible type, then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/gate-drills.log",
        "sha256": "9f535f3e0dd827d39f069b4034ec581bd45add8f182b2eabfbfc3b99ae107478"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "e9a7e11d8a806144ca3ba837d4e7d2d1ea2d5a9f31f8462c24228b96f7b6eddd"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "eea305a08e3d5539258148b2bcb424971b5b99b7352b02273dc7823ea7c67508"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "539cc6e36fbb2a4c9087ded0fe23df91c1cab864f83a8246651ccb5f9b2866ad"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "a08f4083367cf24d7f24bdef5ad57f7278ac72443a4b150ecffeec7ac9173590"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "92e78ff220c4adf2bd3a48b4340a3e5cd3107ad517442c03c33a0b641d680e87"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "57c7e766ae1363dc2ff4deae52b3497f5667cb791ee7a796cd7b7f218dba2c93"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "88eba42ee487cc12ef34144c1e8b5ba4d8e81e4b73c346a051fc2a7ce682c501"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "49eea3fb007441614be3175d28d3d8819ffed95c94fa55a2e848948543cababf"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "c5a4bdd645c2acf29c8036724d12eb4b35d966878560f63ca77cb93fdd86bc7b"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "6a8ebada5c700063ebe9580ecba664012f4ae38843007070f445a6c2771ed81c"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "3cf6ee06d581a446d3e38948ee6dca818e586959cd70c63bb5db22498bb832dd"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "bc9070b1bc8259512adb12fbb872e8246801213b071242a7162c4aabda26b912"
        },
        {
          "path": "chatmon/qtsignal.py",
          "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "e951e136e4a2c89c6b660ac8e4af02078d92fd8f6baf83bba9e7c1ba8c0434f7"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "589baea64239425f4ca99bee706bfdb3d908043d00795011e98e4c8ea1cf4d85"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "7fc4b92b45f08189111888c993ad1e6ef92e8ca553f95a8c61b5f99258ce87c4"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "fa430d69bec693f4fcb862b52ba673beda00b775df43f106ed6a46a49bcdd2ea",
      "red": {
        "mutation": "parent-unignored: in chatmon/updates.py, '        super().__init__(parent)  # type: ignore[arg-type]' became '        super().__init__(parent)  # noqa: drill'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "Argument 1 to \"__init__\" of \"QObject\" has incompatible type",
        "observed_diagnostic": "chatmon\\updates.py:366: error: Argument 1 to \"__init__\" of \"QObject\" has incompatible type \"QObject | None\"; expected \"Updater\"  [arg-type]",
        "before": [
          {
            "path": "chatmon/updates.py",
            "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/updates.py",
            "sha256": "9ea84025e524efca7c04d4d8d8ba071a623118d385d1e2f92a479f87a4563552"
          }
        ],
        "after": [
          {
            "path": "chatmon/updates.py",
            "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-gate-constructor-untyped",
      "acceptance": [
        "M10-03.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m10/gate_drills.py"
      ],
      "method": "Gate drill constructor-untyped (gate_drills.py) in a temporary copy of chatmon/ and pyproject.toml: mypy with PyQt6 6.12.1's stubs green, then failing on one change and naming Need type annotation for \"bus\", then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/gate-drills.log",
        "sha256": "9f535f3e0dd827d39f069b4034ec581bd45add8f182b2eabfbfc3b99ae107478"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "e9a7e11d8a806144ca3ba837d4e7d2d1ea2d5a9f31f8462c24228b96f7b6eddd"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "eea305a08e3d5539258148b2bcb424971b5b99b7352b02273dc7823ea7c67508"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "539cc6e36fbb2a4c9087ded0fe23df91c1cab864f83a8246651ccb5f9b2866ad"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "a08f4083367cf24d7f24bdef5ad57f7278ac72443a4b150ecffeec7ac9173590"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "92e78ff220c4adf2bd3a48b4340a3e5cd3107ad517442c03c33a0b641d680e87"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "57c7e766ae1363dc2ff4deae52b3497f5667cb791ee7a796cd7b7f218dba2c93"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "88eba42ee487cc12ef34144c1e8b5ba4d8e81e4b73c346a051fc2a7ce682c501"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "49eea3fb007441614be3175d28d3d8819ffed95c94fa55a2e848948543cababf"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "c5a4bdd645c2acf29c8036724d12eb4b35d966878560f63ca77cb93fdd86bc7b"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "6a8ebada5c700063ebe9580ecba664012f4ae38843007070f445a6c2771ed81c"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "3cf6ee06d581a446d3e38948ee6dca818e586959cd70c63bb5db22498bb832dd"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "bc9070b1bc8259512adb12fbb872e8246801213b071242a7162c4aabda26b912"
        },
        {
          "path": "chatmon/qtsignal.py",
          "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "e951e136e4a2c89c6b660ac8e4af02078d92fd8f6baf83bba9e7c1ba8c0434f7"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "589baea64239425f4ca99bee706bfdb3d908043d00795011e98e4c8ea1cf4d85"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "7fc4b92b45f08189111888c993ad1e6ef92e8ca553f95a8c61b5f99258ce87c4"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "fa430d69bec693f4fcb862b52ba673beda00b775df43f106ed6a46a49bcdd2ea",
      "red": {
        "mutation": "constructor-untyped: in chatmon/a11y.py, 'bus: QDBusConnection = QDBusConnection.sessionBus()' became 'bus = QDBusConnection.sessionBus()'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "Need type annotation for \"bus\"",
        "observed_diagnostic": "chatmon\\a11y.py:123: error: Need type annotation for \"bus\"  [var-annotated]",
        "before": [
          {
            "path": "chatmon/a11y.py",
            "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/a11y.py",
            "sha256": "234231e6fc1bd5ef0f899479a8d7887611f7cb94857296908656661fe54d1a4d"
          }
        ],
        "after": [
          {
            "path": "chatmon/a11y.py",
            "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-gate-null-image-unchecked",
      "acceptance": [
        "M10-03.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m10/gate_drills.py"
      ],
      "method": "Gate drill null-image-unchecked (gate_drills.py) in a temporary copy of chatmon/ and pyproject.toml: mypy with PyQt6 6.12.1's stubs green, then failing on one change and naming Item \"None\" of \"voidptr | None\" has no attribute \"asstring\", then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/gate-drills.log",
        "sha256": "9f535f3e0dd827d39f069b4034ec581bd45add8f182b2eabfbfc3b99ae107478"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "e9a7e11d8a806144ca3ba837d4e7d2d1ea2d5a9f31f8462c24228b96f7b6eddd"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "eea305a08e3d5539258148b2bcb424971b5b99b7352b02273dc7823ea7c67508"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "539cc6e36fbb2a4c9087ded0fe23df91c1cab864f83a8246651ccb5f9b2866ad"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "a08f4083367cf24d7f24bdef5ad57f7278ac72443a4b150ecffeec7ac9173590"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "92e78ff220c4adf2bd3a48b4340a3e5cd3107ad517442c03c33a0b641d680e87"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "57c7e766ae1363dc2ff4deae52b3497f5667cb791ee7a796cd7b7f218dba2c93"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "88eba42ee487cc12ef34144c1e8b5ba4d8e81e4b73c346a051fc2a7ce682c501"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "49eea3fb007441614be3175d28d3d8819ffed95c94fa55a2e848948543cababf"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "c5a4bdd645c2acf29c8036724d12eb4b35d966878560f63ca77cb93fdd86bc7b"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "6a8ebada5c700063ebe9580ecba664012f4ae38843007070f445a6c2771ed81c"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "3cf6ee06d581a446d3e38948ee6dca818e586959cd70c63bb5db22498bb832dd"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "bc9070b1bc8259512adb12fbb872e8246801213b071242a7162c4aabda26b912"
        },
        {
          "path": "chatmon/qtsignal.py",
          "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "e951e136e4a2c89c6b660ac8e4af02078d92fd8f6baf83bba9e7c1ba8c0434f7"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "589baea64239425f4ca99bee706bfdb3d908043d00795011e98e4c8ea1cf4d85"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "7fc4b92b45f08189111888c993ad1e6ef92e8ca553f95a8c61b5f99258ce87c4"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "fa430d69bec693f4fcb862b52ba673beda00b775df43f106ed6a46a49bcdd2ea",
      "red": {
        "mutation": "null-image-unchecked: in chatmon/sprites.py, '    if bits is None:  # a null image: no rows' became '    if False:  # a null image: no rows'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "Item \"None\" of \"voidptr | None\" has no attribute \"asstring\"",
        "observed_diagnostic": "chatmon\\sprites.py:74: error: Item \"None\" of \"voidptr | None\" has no attribute \"asstring\"  [union-attr]",
        "before": [
          {
            "path": "chatmon/sprites.py",
            "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sprites.py",
            "sha256": "131a4a806923f35c4adc26d7d2b493cafd6aaa30cb89b2bdc98bf20602b91f4b"
          }
        ],
        "after": [
          {
            "path": "chatmon/sprites.py",
            "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-red-gate-alias-mistyped",
      "acceptance": [
        "M10-03.A1"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m10/gate_drills.py"
      ],
      "method": "Gate drill alias-mistyped (gate_drills.py) in a temporary copy of chatmon/ and pyproject.toml: mypy with PyQt6 6.11's stubs green, then failing on one change and naming Incompatible types in assignment, then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/gate-drills.log",
        "sha256": "9f535f3e0dd827d39f069b4034ec581bd45add8f182b2eabfbfc3b99ae107478"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "e9a7e11d8a806144ca3ba837d4e7d2d1ea2d5a9f31f8462c24228b96f7b6eddd"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "eea305a08e3d5539258148b2bcb424971b5b99b7352b02273dc7823ea7c67508"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "539cc6e36fbb2a4c9087ded0fe23df91c1cab864f83a8246651ccb5f9b2866ad"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "a08f4083367cf24d7f24bdef5ad57f7278ac72443a4b150ecffeec7ac9173590"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "92e78ff220c4adf2bd3a48b4340a3e5cd3107ad517442c03c33a0b641d680e87"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "57c7e766ae1363dc2ff4deae52b3497f5667cb791ee7a796cd7b7f218dba2c93"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "88eba42ee487cc12ef34144c1e8b5ba4d8e81e4b73c346a051fc2a7ce682c501"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "49eea3fb007441614be3175d28d3d8819ffed95c94fa55a2e848948543cababf"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "c5a4bdd645c2acf29c8036724d12eb4b35d966878560f63ca77cb93fdd86bc7b"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "6a8ebada5c700063ebe9580ecba664012f4ae38843007070f445a6c2771ed81c"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "3cf6ee06d581a446d3e38948ee6dca818e586959cd70c63bb5db22498bb832dd"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "bc9070b1bc8259512adb12fbb872e8246801213b071242a7162c4aabda26b912"
        },
        {
          "path": "chatmon/qtsignal.py",
          "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "e951e136e4a2c89c6b660ac8e4af02078d92fd8f6baf83bba9e7c1ba8c0434f7"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "589baea64239425f4ca99bee706bfdb3d908043d00795011e98e4c8ea1cf4d85"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "7fc4b92b45f08189111888c993ad1e6ef92e8ca553f95a8c61b5f99258ce87c4"
        },
        {
          "path": "chatmon/winuia.py",
          "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_platform_events.py",
          "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
        },
        {
          "path": "tests/uia_client.py",
          "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
        }
      ],
      "scope_sha256": "fa430d69bec693f4fcb862b52ba673beda00b775df43f106ed6a46a49bcdd2ea",
      "red": {
        "mutation": "alias-mistyped: in chatmon/qtsignal.py, '= QtCore.pyqtSignal' became '= QtCore.pyqtSlot'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "Incompatible types in assignment",
        "observed_diagnostic": "chatmon\\qtsignal.py:15: error: Incompatible types in assignment (expression has type \"def pyqtSlot(*types: Any, name: str | None = ..., result: str | None = ...) -> Callable[[FuncT], FuncT]\", variable has type \"Callable[..., pyqtSignal]\")  [assignment]",
        "before": [
          {
            "path": "chatmon/qtsignal.py",
            "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/qtsignal.py",
            "sha256": "704e3d0da9eef6f21940603196403dc04548e941ca0bfc31a046a21813741665"
          }
        ],
        "after": [
          {
            "path": "chatmon/qtsignal.py",
            "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "E-readiness.0bcea36d",
      "acceptance": [
        "M10-01.A1",
        "M10-01.A2",
        "M10-02.A1",
        "M10-02.A2",
        "M10-03.A1",
        "M10-03.A2",
        "M10-03.A3"
      ],
      "kind": "readiness",
      "status": "stale",
      "command": [],
      "method": "Requirements review of the three follow-ups against M4A's, M6B's and M8's notes, the roadmap's rules and the wave-4 brief: each re-checked on fb19cb9 (the locked Nuitka's and PyInstaller's sources read, mypy run with 6.12.0's and 6.12.1's stubs), decisions D1-D19, failure behaviour, terms, coverage and the files left to the wayland worker (readiness.md).",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m10/readiness.md",
        "sha256": "682649886dde237327104b1f49690a8bc4f5c5e56cbcb498588dff082dcc294d"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "d2def4c309773d8c542807447a4c1ab105392bfd72e4687f4b02ed87a5043d70"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        }
      ],
      "scope_sha256": "0bcea36dd397248577f1df3a0c2b6bbaaab644c48a4943717a3babd3dc93e9e5",
      "red": null,
      "reason": "Bound to an earlier scope (the plan or a file it covers changed since); the check was run or reviewed again on the current scope as E-readiness. Next action: none."
    },
    {
      "id": "E-readiness.e55f1557",
      "acceptance": [
        "M10-01.A1",
        "M10-01.A2",
        "M10-02.A1",
        "M10-02.A2",
        "M10-03.A1",
        "M10-03.A2",
        "M10-03.A3"
      ],
      "kind": "readiness",
      "status": "stale",
      "command": [],
      "method": "Requirements review of the three follow-ups against M4A's, M6B's and M8's notes, the roadmap's rules and the wave-4 brief: each re-checked on fb19cb9 (the locked Nuitka's and PyInstaller's sources read, mypy run with 6.12.0's and 6.12.1's stubs), decisions D1-D19, failure behaviour, terms, coverage and the files left to the wayland worker (readiness.md).",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m10/readiness.md",
        "sha256": "a0a7561095389770b4776545ddf3b73847950dd46e754b194e636ed4626dad1b"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        }
      ],
      "scope_sha256": "e55f15575043c5f6a07c093415d34eb58d2bd59e28182ce3c466db110796c59d",
      "red": null,
      "reason": "Bound to an earlier scope (the plan or a file it covers changed since); the check was run or reviewed again on the current scope as E-readiness. Next action: none."
    },
    {
      "id": "E-locks.6e5e20a4",
      "acceptance": [
        "M10-01.A1"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_requirements.py"
      ],
      "method": "The lock tests on the final tree, after locking the test and dev lists again with the documented uv command: every lock pinned and hashed, at its .in file's versions, one version per package, the dev extra in step, and comtypes for Windows alone; the log also shows the relock's diff against fb19cb9 (comtypes and its header line only).",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/locks.log",
        "sha256": "6cc4ef11e9c7baef7dad146d6fb25bceeedbfc56db4e8fdc6e96582723d235e5"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "af1dc11bd8f63827bd4e5cf4b4f124b3bc7fb60000f9377ea96b804a68a81afa"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e7923dce3696b85dc93b177e154d62a323504d56697385d085f8768449d8af2b"
        }
      ],
      "scope_sha256": "6e5e20a40b9138ce63daca35e58b416b0d533fd0ef8b1f02f838394a2a671d35",
      "red": null,
      "reason": "Bound to an earlier scope (the plan or a file it covers changed since); the check was run or reviewed again on the current scope as E-locks. Next action: none."
    },
    {
      "id": "E-uia-ci-venv.6e5e20a4",
      "acceptance": [
        "M10-01.A2"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "%TEMP%/m10-ci-test/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_platform_events.py::test_a_ui_automation_client_hears_the_announcement"
      ],
      "method": "A fresh venv from C:\\Python314, installed from packaging/requirements-test.txt with --require-hashes as CI's Windows legs install it (comtypes 1.4.17 among them), runs the UI Automation end-to-end test on the final tree with -rs: it runs, not skipped, and passes.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/uia-ci-venv.log",
        "sha256": "f87f4e02f368834573362c0f02a42e14fa22aad8eaf77790ef86aee4df6f8f14"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "af1dc11bd8f63827bd4e5cf4b4f124b3bc7fb60000f9377ea96b804a68a81afa"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e7923dce3696b85dc93b177e154d62a323504d56697385d085f8768449d8af2b"
        }
      ],
      "scope_sha256": "6e5e20a40b9138ce63daca35e58b416b0d533fd0ef8b1f02f838394a2a671d35",
      "red": null,
      "reason": "Bound to an earlier scope (the plan or a file it covers changed since); the check was run or reviewed again on the current scope as E-uia-ci-venv. Next action: none."
    },
    {
      "id": "E-qt-translations.ed979ee5",
      "acceptance": [
        "M10-02.A1",
        "M10-02.A2"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_packaging.py",
        "tests/test_i18n.py"
      ],
      "method": "The build's and i18n's tests on the final tree, real Qt (6.11.2) offscreen: build.py's Nuitka options and PyInstaller data files for a temporary locale folder, English alone and with throwaway de.po and pt.po, and i18n.setup in a frozen app's layout, frozen and not.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/qt-translations.log",
        "sha256": "f68ee418922e386df520340ffab54e6e1e9f93ea8571a218fe3523f331af5a84"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "81a5cddbc39774996891111e8fa77911be56008e1f2d06609fa5fe867bd74dff"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "4d340c2aa6c3165e315ce83d10d52e5e40f1e3d30b9ba13e3dcc5176b58ed3f7"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "d5ccbdca187a3daefcae4c556348984bb0abbef04646072d5dce67b24f53445a"
        }
      ],
      "scope_sha256": "ed979ee531435f3405cdcd71a55fab6f369b98dda7ce347c80f0eadc4c8fd468",
      "red": null,
      "reason": "Bound to an earlier scope (the plan or a file it covers changed since); the check was run or reviewed again on the current scope as E-qt-translations. Next action: none."
    },
    {
      "id": "E-mypy-611.c9678a9d",
      "acceptance": [
        "M10-03.A1"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m10/mypy_runs.py",
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m10/mypy-611.log"
      ],
      "method": "mypy for linux, win32 and darwin on the final tree with the shared venv's PyQt6 6.11.0 stubs (CI's lock) and pyproject.toml's settings, no module exempted: no issues in 70 files on each.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/mypy-611.log",
        "sha256": "1ce2a79a9d7149321b3cbfaa62d40d050d5a1797950ad4fdedd6163a3e1e33fc"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "e9a7e11d8a806144ca3ba837d4e7d2d1ea2d5a9f31f8462c24228b96f7b6eddd"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "eea305a08e3d5539258148b2bcb424971b5b99b7352b02273dc7823ea7c67508"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "539cc6e36fbb2a4c9087ded0fe23df91c1cab864f83a8246651ccb5f9b2866ad"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "a08f4083367cf24d7f24bdef5ad57f7278ac72443a4b150ecffeec7ac9173590"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "92e78ff220c4adf2bd3a48b4340a3e5cd3107ad517442c03c33a0b641d680e87"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "57c7e766ae1363dc2ff4deae52b3497f5667cb791ee7a796cd7b7f218dba2c93"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "88eba42ee487cc12ef34144c1e8b5ba4d8e81e4b73c346a051fc2a7ce682c501"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "49eea3fb007441614be3175d28d3d8819ffed95c94fa55a2e848948543cababf"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "c5a4bdd645c2acf29c8036724d12eb4b35d966878560f63ca77cb93fdd86bc7b"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "6a8ebada5c700063ebe9580ecba664012f4ae38843007070f445a6c2771ed81c"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "3cf6ee06d581a446d3e38948ee6dca818e586959cd70c63bb5db22498bb832dd"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "bc9070b1bc8259512adb12fbb872e8246801213b071242a7162c4aabda26b912"
        },
        {
          "path": "chatmon/qtsignal.py",
          "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "e951e136e4a2c89c6b660ac8e4af02078d92fd8f6baf83bba9e7c1ba8c0434f7"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "589baea64239425f4ca99bee706bfdb3d908043d00795011e98e4c8ea1cf4d85"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "7fc4b92b45f08189111888c993ad1e6ef92e8ca553f95a8c61b5f99258ce87c4"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        }
      ],
      "scope_sha256": "c9678a9dafa54474a9f2b17a6123e0b1c8c05e96e33400e395198bbe1fb9b888",
      "red": null,
      "reason": "Bound to an earlier scope (the plan or a file it covers changed since); the check was run or reviewed again on the current scope as E-mypy-611. Next action: none."
    },
    {
      "id": "E-mypy-6121-copy.c9678a9d",
      "acceptance": [
        "M10-03.A1"
      ],
      "kind": "behavior",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m10/mypy_runs.py",
        "%TEMP%/m10-qt6121/Scripts/python.exe",
        "docs/delivery/reports/m10/mypy-6121-wayland-copy.log",
        "--root",
        "%TEMP%/m10probe/wcopy"
      ],
      "method": "mypy for linux, win32 and darwin with the throwaway venv's PyQt6 6.12.1 stubs on a scratch copy of the final chatmon/ and pyproject.toml with the integration note's changes to layer.py and penguin.py applied (wayland-files-qt6121.diff): no issues in 70 files on each; then the shared venv's 6.11 stubs on the same copy: none either.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/mypy-6121-wayland-copy.log",
        "sha256": "1becada573c205c7dc925122d292876c890392535d83cdd7865cc601d4dc3663"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "e9a7e11d8a806144ca3ba837d4e7d2d1ea2d5a9f31f8462c24228b96f7b6eddd"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "eea305a08e3d5539258148b2bcb424971b5b99b7352b02273dc7823ea7c67508"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "539cc6e36fbb2a4c9087ded0fe23df91c1cab864f83a8246651ccb5f9b2866ad"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "a08f4083367cf24d7f24bdef5ad57f7278ac72443a4b150ecffeec7ac9173590"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "92e78ff220c4adf2bd3a48b4340a3e5cd3107ad517442c03c33a0b641d680e87"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "57c7e766ae1363dc2ff4deae52b3497f5667cb791ee7a796cd7b7f218dba2c93"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "88eba42ee487cc12ef34144c1e8b5ba4d8e81e4b73c346a051fc2a7ce682c501"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "49eea3fb007441614be3175d28d3d8819ffed95c94fa55a2e848948543cababf"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "c5a4bdd645c2acf29c8036724d12eb4b35d966878560f63ca77cb93fdd86bc7b"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "6a8ebada5c700063ebe9580ecba664012f4ae38843007070f445a6c2771ed81c"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "3cf6ee06d581a446d3e38948ee6dca818e586959cd70c63bb5db22498bb832dd"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "bc9070b1bc8259512adb12fbb872e8246801213b071242a7162c4aabda26b912"
        },
        {
          "path": "chatmon/qtsignal.py",
          "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "e951e136e4a2c89c6b660ac8e4af02078d92fd8f6baf83bba9e7c1ba8c0434f7"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "589baea64239425f4ca99bee706bfdb3d908043d00795011e98e4c8ea1cf4d85"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "7fc4b92b45f08189111888c993ad1e6ef92e8ca553f95a8c61b5f99258ce87c4"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        }
      ],
      "scope_sha256": "c9678a9dafa54474a9f2b17a6123e0b1c8c05e96e33400e395198bbe1fb9b888",
      "red": null,
      "reason": "Bound to an earlier scope (the plan or a file it covers changed since); the check was run or reviewed again on the current scope as E-mypy-6121-copy. Next action: none."
    },
    {
      "id": "E-suite.e55f1557",
      "acceptance": [
        "M10-01.A1",
        "M10-02.A1",
        "M10-02.A2",
        "M10-03.A2"
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
      "method": "The whole suite on the final tree in the shared venv (real Qt objects offscreen, every warning an error): it runs the lock tests, the build's and i18n's new tests, and every test of a module whose signals moved to chatmon/qtsignal.py.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/suite-final.log",
        "sha256": "69214d49a814d0d0a6c7203be9147e2513bbdf00c356930c4f357fbd4c2999d1"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "e9a7e11d8a806144ca3ba837d4e7d2d1ea2d5a9f31f8462c24228b96f7b6eddd"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "eea305a08e3d5539258148b2bcb424971b5b99b7352b02273dc7823ea7c67508"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "539cc6e36fbb2a4c9087ded0fe23df91c1cab864f83a8246651ccb5f9b2866ad"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "a08f4083367cf24d7f24bdef5ad57f7278ac72443a4b150ecffeec7ac9173590"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "92e78ff220c4adf2bd3a48b4340a3e5cd3107ad517442c03c33a0b641d680e87"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
        },
        {
          "path": "chatmon/i18n.py",
          "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "57c7e766ae1363dc2ff4deae52b3497f5667cb791ee7a796cd7b7f218dba2c93"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "88eba42ee487cc12ef34144c1e8b5ba4d8e81e4b73c346a051fc2a7ce682c501"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "49eea3fb007441614be3175d28d3d8819ffed95c94fa55a2e848948543cababf"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "c5a4bdd645c2acf29c8036724d12eb4b35d966878560f63ca77cb93fdd86bc7b"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "6a8ebada5c700063ebe9580ecba664012f4ae38843007070f445a6c2771ed81c"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "3cf6ee06d581a446d3e38948ee6dca818e586959cd70c63bb5db22498bb832dd"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "bc9070b1bc8259512adb12fbb872e8246801213b071242a7162c4aabda26b912"
        },
        {
          "path": "chatmon/qtsignal.py",
          "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "e951e136e4a2c89c6b660ac8e4af02078d92fd8f6baf83bba9e7c1ba8c0434f7"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "589baea64239425f4ca99bee706bfdb3d908043d00795011e98e4c8ea1cf4d85"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "7fc4b92b45f08189111888c993ad1e6ef92e8ca553f95a8c61b5f99258ce87c4"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "81a5cddbc39774996891111e8fa77911be56008e1f2d06609fa5fe867bd74dff"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "af1dc11bd8f63827bd4e5cf4b4f124b3bc7fb60000f9377ea96b804a68a81afa"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "4d340c2aa6c3165e315ce83d10d52e5e40f1e3d30b9ba13e3dcc5176b58ed3f7"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "d5ccbdca187a3daefcae4c556348984bb0abbef04646072d5dce67b24f53445a"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e7923dce3696b85dc93b177e154d62a323504d56697385d085f8768449d8af2b"
        }
      ],
      "scope_sha256": "e55f15575043c5f6a07c093415d34eb58d2bd59e28182ce3c466db110796c59d",
      "red": null,
      "reason": "Bound to an earlier scope (the plan or a file it covers changed since); the check was run or reviewed again on the current scope as E-suite. Next action: none."
    },
    {
      "id": "E-howto.c9678a9d",
      "acceptance": [
        "M10-03.A3"
      ],
      "kind": "manual",
      "status": "stale",
      "command": [],
      "method": "Review of CONTRIBUTING.md's how-to for the next stubs and of the integration note's CI entry, line by line against the commands this work ran (mypy_runs.py with the throwaway venv; uv's compile with and without --exclude-newer) and the logs they wrote.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m10/howto-review.md",
        "sha256": "8ec08b4f8ebe35b10fab547fc8e1520bb4708c3ce595372792eedf07566277d8"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "e9a7e11d8a806144ca3ba837d4e7d2d1ea2d5a9f31f8462c24228b96f7b6eddd"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "eea305a08e3d5539258148b2bcb424971b5b99b7352b02273dc7823ea7c67508"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "539cc6e36fbb2a4c9087ded0fe23df91c1cab864f83a8246651ccb5f9b2866ad"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "a08f4083367cf24d7f24bdef5ad57f7278ac72443a4b150ecffeec7ac9173590"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "92e78ff220c4adf2bd3a48b4340a3e5cd3107ad517442c03c33a0b641d680e87"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "57c7e766ae1363dc2ff4deae52b3497f5667cb791ee7a796cd7b7f218dba2c93"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "88eba42ee487cc12ef34144c1e8b5ba4d8e81e4b73c346a051fc2a7ce682c501"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "49eea3fb007441614be3175d28d3d8819ffed95c94fa55a2e848948543cababf"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "c5a4bdd645c2acf29c8036724d12eb4b35d966878560f63ca77cb93fdd86bc7b"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "6a8ebada5c700063ebe9580ecba664012f4ae38843007070f445a6c2771ed81c"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "3cf6ee06d581a446d3e38948ee6dca818e586959cd70c63bb5db22498bb832dd"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "bc9070b1bc8259512adb12fbb872e8246801213b071242a7162c4aabda26b912"
        },
        {
          "path": "chatmon/qtsignal.py",
          "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "e951e136e4a2c89c6b660ac8e4af02078d92fd8f6baf83bba9e7c1ba8c0434f7"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "589baea64239425f4ca99bee706bfdb3d908043d00795011e98e4c8ea1cf4d85"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "7fc4b92b45f08189111888c993ad1e6ef92e8ca553f95a8c61b5f99258ce87c4"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        }
      ],
      "scope_sha256": "c9678a9dafa54474a9f2b17a6123e0b1c8c05e96e33400e395198bbe1fb9b888",
      "red": null,
      "reason": "Bound to an earlier scope (the plan or a file it covers changed since); the check was run or reviewed again on the current scope as E-howto. Next action: none."
    },
    {
      "id": "E-red-M10-01-comtypes-on-every-platform.6e5e20a4",
      "acceptance": [
        "M10-01.A1"
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
        "tests/test_requirements.py::test_the_windows_test_legs_install_the_screen_readers_ui_automation_client"
      ],
      "method": "Red drill M10-01-comtypes-on-every-platform through tests/drills/run.py in a temporary copy: green, packaging/requirements-test.txt mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/drills.log",
        "sha256": "4ad0c473b52a34ddea5887f9862987cee9c98013df2d3aed3cb0e911e0846fdb"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "af1dc11bd8f63827bd4e5cf4b4f124b3bc7fb60000f9377ea96b804a68a81afa"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e7923dce3696b85dc93b177e154d62a323504d56697385d085f8768449d8af2b"
        }
      ],
      "scope_sha256": "6e5e20a40b9138ce63daca35e58b416b0d533fd0ef8b1f02f838394a2a671d35",
      "red": {
        "mutation": "M10-01-comtypes-on-every-platform: in packaging/requirements-test.txt, \"comtypes==1.4.17 ; sys_platform == 'win32' \\\\\" became 'comtypes==1.4.17 \\\\'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "requirements-test.txt installs comtypes on ['win32', 'linux', 'darwin'], not on Windows alone",
        "observed_diagnostic": "E           AssertionError: requirements-test.txt installs comtypes on ['win32', 'linux', 'darwin'], not on Windows alone: comtypes==1.4.17",
        "before": [
          {
            "path": "packaging/requirements-test.txt",
            "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
          }
        ],
        "mutated": [
          {
            "path": "packaging/requirements-test.txt",
            "sha256": "751fb1f89357494005610a336325ba5e0cdbf208cce6e3cb0f6050deeba63226"
          }
        ],
        "after": [
          {
            "path": "packaging/requirements-test.txt",
            "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
          }
        ]
      },
      "reason": "Bound to an earlier scope (the plan or a file it covers changed since); the check was run or reviewed again on the current scope as E-red-M10-01-comtypes-on-every-platform. Next action: none."
    },
    {
      "id": "E-red-M10-01-comtypes-left-out-of-the-dev-lock.6e5e20a4",
      "acceptance": [
        "M10-01.A1"
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
        "tests/test_requirements.py::test_the_windows_test_legs_install_the_screen_readers_ui_automation_client",
        "tests/test_requirements.py::test_each_lock_holds_the_versions_its_in_file_names"
      ],
      "method": "Red drill M10-01-comtypes-left-out-of-the-dev-lock through tests/drills/run.py in a temporary copy: green, packaging/requirements-dev.txt mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/drills.log",
        "sha256": "4ad0c473b52a34ddea5887f9862987cee9c98013df2d3aed3cb0e911e0846fdb"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "af1dc11bd8f63827bd4e5cf4b4f124b3bc7fb60000f9377ea96b804a68a81afa"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e7923dce3696b85dc93b177e154d62a323504d56697385d085f8768449d8af2b"
        }
      ],
      "scope_sha256": "6e5e20a40b9138ce63daca35e58b416b0d533fd0ef8b1f02f838394a2a671d35",
      "red": {
        "mutation": "M10-01-comtypes-left-out-of-the-dev-lock: in packaging/requirements-dev.txt, \"comtypes==1.4.17 ; sys_platform == 'win32' \\\\\" became \"comtypez==1.4.17 ; sys_platform == 'win32' \\\\\"",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "requirements-dev.txt doesn't lock comtypes",
        "observed_diagnostic": "E           AssertionError: requirements-dev.txt doesn't lock comtypes",
        "before": [
          {
            "path": "packaging/requirements-dev.txt",
            "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
          }
        ],
        "mutated": [
          {
            "path": "packaging/requirements-dev.txt",
            "sha256": "175f9524053c95f13d54ca20991379d6a5e578b95b6d3b990bb48675856edaea"
          }
        ],
        "after": [
          {
            "path": "packaging/requirements-dev.txt",
            "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
          }
        ]
      },
      "reason": "Bound to an earlier scope (the plan or a file it covers changed since); the check was run or reviewed again on the current scope as E-red-M10-01-comtypes-left-out-of-the-dev-lock. Next action: none."
    },
    {
      "id": "E-red-M10-02-english-carries-qts-english.ed979ee5",
      "acceptance": [
        "M10-02.A1"
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
        "tests/test_packaging.py::test_the_installers_carry_qts_own_words_for_each_language_chatmon_speaks_and_no_other"
      ],
      "method": "Red drill M10-02-english-carries-qts-english through tests/drills/run.py in a temporary copy: green, packaging/build.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/drills.log",
        "sha256": "4ad0c473b52a34ddea5887f9862987cee9c98013df2d3aed3cb0e911e0846fdb"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "81a5cddbc39774996891111e8fa77911be56008e1f2d06609fa5fe867bd74dff"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "4d340c2aa6c3165e315ce83d10d52e5e40f1e3d30b9ba13e3dcc5176b58ed3f7"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "d5ccbdca187a3daefcae4c556348984bb0abbef04646072d5dce67b24f53445a"
        }
      ],
      "scope_sha256": "ed979ee531435f3405cdcd71a55fab6f369b98dda7ce347c80f0eadc4c8fd468",
      "red": {
        "mutation": "M10-02-english-carries-qts-english: in packaging/build.py, '    for code in i18n.available(LOCALE)[1:]:' became '    for code in i18n.available(LOCALE):'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "English alone: Qt's own language",
        "observed_diagnostic": ">       assert build.qt_translations() == [], \"English alone: Qt's own language\"",
        "before": [
          {
            "path": "packaging/build.py",
            "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
          }
        ],
        "mutated": [
          {
            "path": "packaging/build.py",
            "sha256": "63b6b4a866a98aad2c901e68666424a5896748ccc5984a988b3f9e0a564308f3"
          }
        ],
        "after": [
          {
            "path": "packaging/build.py",
            "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
          }
        ]
      },
      "reason": "Bound to an earlier scope (the plan or a file it covers changed since); the check was run or reviewed again on the current scope as E-red-M10-02-english-carries-qts-english. Next action: none."
    },
    {
      "id": "E-red-M10-02-pyinstaller-keeps-every-language.ed979ee5",
      "acceptance": [
        "M10-02.A1"
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
        "tests/test_packaging.py::test_the_installers_carry_qts_own_words_for_each_language_chatmon_speaks_and_no_other"
      ],
      "method": "Red drill M10-02-pyinstaller-keeps-every-language through tests/drills/run.py in a temporary copy: green, packaging/build.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/drills.log",
        "sha256": "4ad0c473b52a34ddea5887f9862987cee9c98013df2d3aed3cb0e911e0846fdb"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "81a5cddbc39774996891111e8fa77911be56008e1f2d06609fa5fe867bd74dff"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "4d340c2aa6c3165e315ce83d10d52e5e40f1e3d30b9ba13e3dcc5176b58ed3f7"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "d5ccbdca187a3daefcae4c556348984bb0abbef04646072d5dce67b24f53445a"
        }
      ],
      "scope_sha256": "ed979ee531435f3405cdcd71a55fab6f369b98dda7ce347c80f0eadc4c8fd468",
      "red": {
        "mutation": "M10-02-pyinstaller-keeps-every-language: in packaging/build.py, '    kept = [d for d in datas if not (Path(d[0]).parent == i18n.QT_FROZEN and Path(d[0]).suffix == \".qm\")]' became '    kept = list(datas)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "none of Qt's translations, and everything else kept",
        "observed_diagnostic": ">       assert build.pyinstaller_datas(hooked + own) == own, \"none of Qt's translations, and everything else kept\"",
        "before": [
          {
            "path": "packaging/build.py",
            "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
          }
        ],
        "mutated": [
          {
            "path": "packaging/build.py",
            "sha256": "80f79a525b7231a42d1565b378bd665291ef130023cdeefc24243e530bc5cd8c"
          }
        ],
        "after": [
          {
            "path": "packaging/build.py",
            "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
          }
        ]
      },
      "reason": "Bound to an earlier scope (the plan or a file it covers changed since); the check was run or reviewed again on the current scope as E-red-M10-02-pyinstaller-keeps-every-language. Next action: none."
    },
    {
      "id": "E-red-M10-02-nuitka-left-without-them.ed979ee5",
      "acceptance": [
        "M10-02.A1"
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
        "tests/test_packaging.py::test_the_installers_carry_qts_own_words_for_each_language_chatmon_speaks_and_no_other"
      ],
      "method": "Red drill M10-02-nuitka-left-without-them through tests/drills/run.py in a temporary copy: green, packaging/build.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/drills.log",
        "sha256": "4ad0c473b52a34ddea5887f9862987cee9c98013df2d3aed3cb0e911e0846fdb"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "81a5cddbc39774996891111e8fa77911be56008e1f2d06609fa5fe867bd74dff"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "4d340c2aa6c3165e315ce83d10d52e5e40f1e3d30b9ba13e3dcc5176b58ed3f7"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "d5ccbdca187a3daefcae4c556348984bb0abbef04646072d5dce67b24f53445a"
        }
      ],
      "scope_sha256": "ed979ee531435f3405cdcd71a55fab6f369b98dda7ce347c80f0eadc4c8fd468",
      "red": {
        "mutation": "M10-02-nuitka-left-without-them: in packaging/build.py, '\"--noinclude-qt-translations\", *nuitka_qt_translations(),' became '\"--noinclude-qt-translations\",'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "AssertionError: assert [] == ['--include-d",
        "observed_diagnostic": "E       AssertionError: assert [] == ['--include-d...ase_pt_BR.qm']",
        "before": [
          {
            "path": "packaging/build.py",
            "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
          }
        ],
        "mutated": [
          {
            "path": "packaging/build.py",
            "sha256": "cd45467f066cdc09218d9fa42977c7087024e72aaaecfea3c0383a017ac37f01"
          }
        ],
        "after": [
          {
            "path": "packaging/build.py",
            "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
          }
        ]
      },
      "reason": "Bound to an earlier scope (the plan or a file it covers changed since); the check was run or reviewed again on the current scope as E-red-M10-02-nuitka-left-without-them. Next action: none."
    },
    {
      "id": "E-red-M10-02-frozen-app-folder-never-looked-in.ed979ee5",
      "acceptance": [
        "M10-02.A2"
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
        "tests/test_i18n.py::test_an_installers_app_finds_qts_own_words_in_its_own_folder"
      ],
      "method": "Red drill M10-02-frozen-app-folder-never-looked-in through tests/drills/run.py in a temporary copy: green, chatmon/i18n.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/drills.log",
        "sha256": "4ad0c473b52a34ddea5887f9862987cee9c98013df2d3aed3cb0e911e0846fdb"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "81a5cddbc39774996891111e8fa77911be56008e1f2d06609fa5fe867bd74dff"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "4d340c2aa6c3165e315ce83d10d52e5e40f1e3d30b9ba13e3dcc5176b58ed3f7"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "d5ccbdca187a3daefcae4c556348984bb0abbef04646072d5dce67b24f53445a"
        }
      ],
      "scope_sha256": "ed979ee531435f3405cdcd71a55fab6f369b98dda7ce347c80f0eadc4c8fd468",
      "red": {
        "mutation": "M10-02-frozen-app-folder-never-looked-in: in chatmon/i18n.py, '    if paths.frozen():' became '    if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "Qt's own folder first",
        "observed_diagnostic": ">       assert i18n.qt_folders(QtCore) == [str(elsewhere), str(app / i18n.QT_FROZEN)], \"Qt's own folder first\"",
        "before": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "51efe7298d1bc7a6fd66c4fcc3bebefb82aee6ea089cfaa7a90fb13bfd83b609"
          }
        ],
        "after": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
          }
        ]
      },
      "reason": "Bound to an earlier scope (the plan or a file it covers changed since); the check was run or reviewed again on the current scope as E-red-M10-02-frozen-app-folder-never-looked-in. Next action: none."
    },
    {
      "id": "E-red-M10-02-app-folder-before-qts.ed979ee5",
      "acceptance": [
        "M10-02.A2"
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
        "tests/test_i18n.py::test_an_installers_app_finds_qts_own_words_in_its_own_folder"
      ],
      "method": "Red drill M10-02-app-folder-before-qts through tests/drills/run.py in a temporary copy: green, chatmon/i18n.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/drills.log",
        "sha256": "4ad0c473b52a34ddea5887f9862987cee9c98013df2d3aed3cb0e911e0846fdb"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "81a5cddbc39774996891111e8fa77911be56008e1f2d06609fa5fe867bd74dff"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "4d340c2aa6c3165e315ce83d10d52e5e40f1e3d30b9ba13e3dcc5176b58ed3f7"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "d5ccbdca187a3daefcae4c556348984bb0abbef04646072d5dce67b24f53445a"
        }
      ],
      "scope_sha256": "ed979ee531435f3405cdcd71a55fab6f369b98dda7ce347c80f0eadc4c8fd468",
      "red": {
        "mutation": "M10-02-app-folder-before-qts: in chatmon/i18n.py, '        folders.append(str(_APP_FOLDER / QT_FROZEN))' became '        folders.insert(0, str(_APP_FOLDER / QT_FROZEN))'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "Qt's own folder first",
        "observed_diagnostic": ">       assert i18n.qt_folders(QtCore) == [str(elsewhere), str(app / i18n.QT_FROZEN)], \"Qt's own folder first\"",
        "before": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "7ea6af071b6b4d872b65a32713625d574e2c4c71204297fbf1b75123f2771f12"
          }
        ],
        "after": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
          }
        ]
      },
      "reason": "Bound to an earlier scope (the plan or a file it covers changed since); the check was run or reviewed again on the current scope as E-red-M10-02-app-folder-before-qts. Next action: none."
    },
    {
      "id": "E-red-M10-02-translator-only-asks-qt.ed979ee5",
      "acceptance": [
        "M10-02.A2"
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
        "tests/test_i18n.py::test_an_installers_app_finds_qts_own_words_in_its_own_folder"
      ],
      "method": "Red drill M10-02-translator-only-asks-qt through tests/drills/run.py in a temporary copy: green, chatmon/i18n.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/drills.log",
        "sha256": "4ad0c473b52a34ddea5887f9862987cee9c98013df2d3aed3cb0e911e0846fdb"
      },
      "inputs": [
        {
          "path": "chatmon/i18n.py",
          "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/build.py",
          "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
        },
        {
          "path": "packaging/chatmon.spec",
          "sha256": "81a5cddbc39774996891111e8fa77911be56008e1f2d06609fa5fe867bd74dff"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_i18n.py",
          "sha256": "4d340c2aa6c3165e315ce83d10d52e5e40f1e3d30b9ba13e3dcc5176b58ed3f7"
        },
        {
          "path": "tests/test_packaging.py",
          "sha256": "d5ccbdca187a3daefcae4c556348984bb0abbef04646072d5dce67b24f53445a"
        }
      ],
      "scope_sha256": "ed979ee531435f3405cdcd71a55fab6f369b98dda7ce347c80f0eadc4c8fd468",
      "red": {
        "mutation": "M10-02-translator-only-asks-qt: in chatmon/i18n.py, '    translator = qt_translator(qtcore, code, qt_folders(qtcore))' became '    translator = qt_translator(qtcore, code, [_qt_library_folder(qtcore)])'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert 'Cancel' == 'Abbrechen'",
        "observed_diagnostic": "E       AssertionError: assert 'Cancel' == 'Abbrechen'",
        "before": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "19f39bc92cd43e4425fdab768d158b49d97ba14c22346c134bea86ee1a3c9323"
          }
        ],
        "after": [
          {
            "path": "chatmon/i18n.py",
            "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
          }
        ]
      },
      "reason": "Bound to an earlier scope (the plan or a file it covers changed since); the check was run or reviewed again on the current scope as E-red-M10-02-translator-only-asks-qt. Next action: none."
    },
    {
      "id": "E-red-M10-03-alias-not-pyqts-signal.c9678a9d",
      "acceptance": [
        "M10-03.A2"
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
        "tests/test_platform_events.py::test_each_workspace_notification_is_its_own_signal"
      ],
      "method": "Red drill M10-03-alias-not-pyqts-signal through tests/drills/run.py in a temporary copy: green, chatmon/qtsignal.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/drills.log",
        "sha256": "4ad0c473b52a34ddea5887f9862987cee9c98013df2d3aed3cb0e911e0846fdb"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "e9a7e11d8a806144ca3ba837d4e7d2d1ea2d5a9f31f8462c24228b96f7b6eddd"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "eea305a08e3d5539258148b2bcb424971b5b99b7352b02273dc7823ea7c67508"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "539cc6e36fbb2a4c9087ded0fe23df91c1cab864f83a8246651ccb5f9b2866ad"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "a08f4083367cf24d7f24bdef5ad57f7278ac72443a4b150ecffeec7ac9173590"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "92e78ff220c4adf2bd3a48b4340a3e5cd3107ad517442c03c33a0b641d680e87"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "57c7e766ae1363dc2ff4deae52b3497f5667cb791ee7a796cd7b7f218dba2c93"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "88eba42ee487cc12ef34144c1e8b5ba4d8e81e4b73c346a051fc2a7ce682c501"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "49eea3fb007441614be3175d28d3d8819ffed95c94fa55a2e848948543cababf"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "c5a4bdd645c2acf29c8036724d12eb4b35d966878560f63ca77cb93fdd86bc7b"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "6a8ebada5c700063ebe9580ecba664012f4ae38843007070f445a6c2771ed81c"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "3cf6ee06d581a446d3e38948ee6dca818e586959cd70c63bb5db22498bb832dd"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "bc9070b1bc8259512adb12fbb872e8246801213b071242a7162c4aabda26b912"
        },
        {
          "path": "chatmon/qtsignal.py",
          "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "e951e136e4a2c89c6b660ac8e4af02078d92fd8f6baf83bba9e7c1ba8c0434f7"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "589baea64239425f4ca99bee706bfdb3d908043d00795011e98e4c8ea1cf4d85"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "7fc4b92b45f08189111888c993ad1e6ef92e8ca553f95a8c61b5f99258ce87c4"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        }
      ],
      "scope_sha256": "c9678a9dafa54474a9f2b17a6123e0b1c8c05e96e33400e395198bbe1fb9b888",
      "red": {
        "mutation": "M10-03-alias-not-pyqts-signal: in chatmon/qtsignal.py, '= QtCore.pyqtSignal' became '= lambda *types, **named: QtCore.pyqtSignal()'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_each_workspace_notification_is_its_own_signal",
        "observed_diagnostic": "_____________ test_each_workspace_notification_is_its_own_signal ______________",
        "before": [
          {
            "path": "chatmon/qtsignal.py",
            "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/qtsignal.py",
            "sha256": "24ddab68965c23c232333bead93acddf23d5887716f93418a095604ff14e9293"
          }
        ],
        "after": [
          {
            "path": "chatmon/qtsignal.py",
            "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
          }
        ]
      },
      "reason": "Bound to an earlier scope (the plan or a file it covers changed since); the check was run or reviewed again on the current scope as E-red-M10-03-alias-not-pyqts-signal. Next action: none."
    },
    {
      "id": "E-red-M10-01-announcement-not-important.6e5e20a4",
      "acceptance": [
        "M10-01.A2"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:\\Users\\Randy\\AppData\\Local\\Temp/m10-ci-test/Scripts/python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_platform_events.py::test_a_ui_automation_client_hears_the_announcement"
      ],
      "method": "Red drill M10-01-announcement-not-important through tests/drills/run.py in a temporary copy: green, chatmon/winuia.py mutated once and the named tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back (SHA-256 checked) and green again.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/drills-ci-venv.log",
        "sha256": "1a1c65c8b823f5a08ef62b2c01b2550ab5efee1b181d65082ea88fbab80ec108"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements-dev.txt",
          "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
        },
        {
          "path": "packaging/requirements-test.in",
          "sha256": "af1dc11bd8f63827bd4e5cf4b4f124b3bc7fb60000f9377ea96b804a68a81afa"
        },
        {
          "path": "packaging/requirements-test.txt",
          "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        },
        {
          "path": "tests/test_requirements.py",
          "sha256": "e7923dce3696b85dc93b177e154d62a323504d56697385d085f8768449d8af2b"
        }
      ],
      "scope_sha256": "6e5e20a40b9138ce63daca35e58b416b0d533fd0ef8b1f02f838394a2a671d35",
      "red": {
        "mutation": "M10-01-announcement-not-important: in chatmon/winuia.py, 'IMPORTANT_ALL if important else ALL, words, activity)' became 'ALL if important else ALL, words, activity)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "'processing': 2",
        "observed_diagnostic": "E       AssertionError: [{'kind': 4, 'processing': 2, 'words': 'Reminder. Stretch your legs.', 'activity': 'chatmon.announcement'}]",
        "before": [
          {
            "path": "chatmon/winuia.py",
            "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/winuia.py",
            "sha256": "d0f20c188adee9c4e4544b8d6c6331e577add8d787893e83a3eb0870bb498e60"
          }
        ],
        "after": [
          {
            "path": "chatmon/winuia.py",
            "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
          }
        ]
      },
      "reason": "Bound to an earlier scope (the plan or a file it covers changed since); the check was run or reviewed again on the current scope as E-red-M10-01-announcement-not-important. Next action: none."
    },
    {
      "id": "E-red-gate-signal-from-qtcore.c9678a9d",
      "acceptance": [
        "M10-03.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m10/gate_drills.py"
      ],
      "method": "Gate drill signal-from-qtcore (gate_drills.py) in a temporary copy of chatmon/ and pyproject.toml: mypy with PyQt6 6.12.1's stubs green, then failing on one change and naming Missing named argument \"arguments\" for \"pyqtSignal\", then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/gate-drills.log",
        "sha256": "e2a2db7422740a2337c2bc752fcd15add429d0be55b403a4939fdfd962ae8649"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "e9a7e11d8a806144ca3ba837d4e7d2d1ea2d5a9f31f8462c24228b96f7b6eddd"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "eea305a08e3d5539258148b2bcb424971b5b99b7352b02273dc7823ea7c67508"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "539cc6e36fbb2a4c9087ded0fe23df91c1cab864f83a8246651ccb5f9b2866ad"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "a08f4083367cf24d7f24bdef5ad57f7278ac72443a4b150ecffeec7ac9173590"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "92e78ff220c4adf2bd3a48b4340a3e5cd3107ad517442c03c33a0b641d680e87"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "57c7e766ae1363dc2ff4deae52b3497f5667cb791ee7a796cd7b7f218dba2c93"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "88eba42ee487cc12ef34144c1e8b5ba4d8e81e4b73c346a051fc2a7ce682c501"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "49eea3fb007441614be3175d28d3d8819ffed95c94fa55a2e848948543cababf"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "c5a4bdd645c2acf29c8036724d12eb4b35d966878560f63ca77cb93fdd86bc7b"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "6a8ebada5c700063ebe9580ecba664012f4ae38843007070f445a6c2771ed81c"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "3cf6ee06d581a446d3e38948ee6dca818e586959cd70c63bb5db22498bb832dd"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "bc9070b1bc8259512adb12fbb872e8246801213b071242a7162c4aabda26b912"
        },
        {
          "path": "chatmon/qtsignal.py",
          "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "e951e136e4a2c89c6b660ac8e4af02078d92fd8f6baf83bba9e7c1ba8c0434f7"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "589baea64239425f4ca99bee706bfdb3d908043d00795011e98e4c8ea1cf4d85"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "7fc4b92b45f08189111888c993ad1e6ef92e8ca553f95a8c61b5f99258ce87c4"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        }
      ],
      "scope_sha256": "c9678a9dafa54474a9f2b17a6123e0b1c8c05e96e33400e395198bbe1fb9b888",
      "red": {
        "mutation": "signal-from-qtcore: in chatmon/hotkey.py, 'from .qtsignal import pyqtSignal' became 'from PyQt6.QtCore import pyqtSignal'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "Missing named argument \"arguments\" for \"pyqtSignal\"",
        "observed_diagnostic": "chatmon\\hotkey.py:460: error: Missing named argument \"arguments\" for \"pyqtSignal\"  [call-arg]",
        "before": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "f9a2a1065975eefef7e1bb6961c4e67268b322891fb32269185b15eb3975cba5"
          }
        ],
        "after": [
          {
            "path": "chatmon/hotkey.py",
            "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
          }
        ]
      },
      "reason": "Bound to an earlier scope (the plan or a file it covers changed since); the check was run or reviewed again on the current scope as E-red-gate-signal-from-qtcore. Next action: none."
    },
    {
      "id": "E-red-gate-parent-unignored.c9678a9d",
      "acceptance": [
        "M10-03.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m10/gate_drills.py"
      ],
      "method": "Gate drill parent-unignored (gate_drills.py) in a temporary copy of chatmon/ and pyproject.toml: mypy with PyQt6 6.12.1's stubs green, then failing on one change and naming Argument 1 to \"__init__\" of \"QObject\" has incompatible type, then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/gate-drills.log",
        "sha256": "e2a2db7422740a2337c2bc752fcd15add429d0be55b403a4939fdfd962ae8649"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "e9a7e11d8a806144ca3ba837d4e7d2d1ea2d5a9f31f8462c24228b96f7b6eddd"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "eea305a08e3d5539258148b2bcb424971b5b99b7352b02273dc7823ea7c67508"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "539cc6e36fbb2a4c9087ded0fe23df91c1cab864f83a8246651ccb5f9b2866ad"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "a08f4083367cf24d7f24bdef5ad57f7278ac72443a4b150ecffeec7ac9173590"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "92e78ff220c4adf2bd3a48b4340a3e5cd3107ad517442c03c33a0b641d680e87"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "57c7e766ae1363dc2ff4deae52b3497f5667cb791ee7a796cd7b7f218dba2c93"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "88eba42ee487cc12ef34144c1e8b5ba4d8e81e4b73c346a051fc2a7ce682c501"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "49eea3fb007441614be3175d28d3d8819ffed95c94fa55a2e848948543cababf"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "c5a4bdd645c2acf29c8036724d12eb4b35d966878560f63ca77cb93fdd86bc7b"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "6a8ebada5c700063ebe9580ecba664012f4ae38843007070f445a6c2771ed81c"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "3cf6ee06d581a446d3e38948ee6dca818e586959cd70c63bb5db22498bb832dd"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "bc9070b1bc8259512adb12fbb872e8246801213b071242a7162c4aabda26b912"
        },
        {
          "path": "chatmon/qtsignal.py",
          "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "e951e136e4a2c89c6b660ac8e4af02078d92fd8f6baf83bba9e7c1ba8c0434f7"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "589baea64239425f4ca99bee706bfdb3d908043d00795011e98e4c8ea1cf4d85"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "7fc4b92b45f08189111888c993ad1e6ef92e8ca553f95a8c61b5f99258ce87c4"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        }
      ],
      "scope_sha256": "c9678a9dafa54474a9f2b17a6123e0b1c8c05e96e33400e395198bbe1fb9b888",
      "red": {
        "mutation": "parent-unignored: in chatmon/updates.py, '        super().__init__(parent)  # type: ignore[arg-type]' became '        super().__init__(parent)  # noqa: drill'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "Argument 1 to \"__init__\" of \"QObject\" has incompatible type",
        "observed_diagnostic": "chatmon\\updates.py:366: error: Argument 1 to \"__init__\" of \"QObject\" has incompatible type \"QObject | None\"; expected \"Updater\"  [arg-type]",
        "before": [
          {
            "path": "chatmon/updates.py",
            "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/updates.py",
            "sha256": "9ea84025e524efca7c04d4d8d8ba071a623118d385d1e2f92a479f87a4563552"
          }
        ],
        "after": [
          {
            "path": "chatmon/updates.py",
            "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
          }
        ]
      },
      "reason": "Bound to an earlier scope (the plan or a file it covers changed since); the check was run or reviewed again on the current scope as E-red-gate-parent-unignored. Next action: none."
    },
    {
      "id": "E-red-gate-constructor-untyped.c9678a9d",
      "acceptance": [
        "M10-03.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m10/gate_drills.py"
      ],
      "method": "Gate drill constructor-untyped (gate_drills.py) in a temporary copy of chatmon/ and pyproject.toml: mypy with PyQt6 6.12.1's stubs green, then failing on one change and naming Need type annotation for \"bus\", then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/gate-drills.log",
        "sha256": "e2a2db7422740a2337c2bc752fcd15add429d0be55b403a4939fdfd962ae8649"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "e9a7e11d8a806144ca3ba837d4e7d2d1ea2d5a9f31f8462c24228b96f7b6eddd"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "eea305a08e3d5539258148b2bcb424971b5b99b7352b02273dc7823ea7c67508"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "539cc6e36fbb2a4c9087ded0fe23df91c1cab864f83a8246651ccb5f9b2866ad"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "a08f4083367cf24d7f24bdef5ad57f7278ac72443a4b150ecffeec7ac9173590"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "92e78ff220c4adf2bd3a48b4340a3e5cd3107ad517442c03c33a0b641d680e87"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "57c7e766ae1363dc2ff4deae52b3497f5667cb791ee7a796cd7b7f218dba2c93"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "88eba42ee487cc12ef34144c1e8b5ba4d8e81e4b73c346a051fc2a7ce682c501"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "49eea3fb007441614be3175d28d3d8819ffed95c94fa55a2e848948543cababf"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "c5a4bdd645c2acf29c8036724d12eb4b35d966878560f63ca77cb93fdd86bc7b"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "6a8ebada5c700063ebe9580ecba664012f4ae38843007070f445a6c2771ed81c"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "3cf6ee06d581a446d3e38948ee6dca818e586959cd70c63bb5db22498bb832dd"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "bc9070b1bc8259512adb12fbb872e8246801213b071242a7162c4aabda26b912"
        },
        {
          "path": "chatmon/qtsignal.py",
          "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "e951e136e4a2c89c6b660ac8e4af02078d92fd8f6baf83bba9e7c1ba8c0434f7"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "589baea64239425f4ca99bee706bfdb3d908043d00795011e98e4c8ea1cf4d85"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "7fc4b92b45f08189111888c993ad1e6ef92e8ca553f95a8c61b5f99258ce87c4"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        }
      ],
      "scope_sha256": "c9678a9dafa54474a9f2b17a6123e0b1c8c05e96e33400e395198bbe1fb9b888",
      "red": {
        "mutation": "constructor-untyped: in chatmon/a11y.py, 'bus: QDBusConnection = QDBusConnection.sessionBus()' became 'bus = QDBusConnection.sessionBus()'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "Need type annotation for \"bus\"",
        "observed_diagnostic": "chatmon\\a11y.py:123: error: Need type annotation for \"bus\"  [var-annotated]",
        "before": [
          {
            "path": "chatmon/a11y.py",
            "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/a11y.py",
            "sha256": "234231e6fc1bd5ef0f899479a8d7887611f7cb94857296908656661fe54d1a4d"
          }
        ],
        "after": [
          {
            "path": "chatmon/a11y.py",
            "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
          }
        ]
      },
      "reason": "Bound to an earlier scope (the plan or a file it covers changed since); the check was run or reviewed again on the current scope as E-red-gate-constructor-untyped. Next action: none."
    },
    {
      "id": "E-red-gate-null-image-unchecked.c9678a9d",
      "acceptance": [
        "M10-03.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m10/gate_drills.py"
      ],
      "method": "Gate drill null-image-unchecked (gate_drills.py) in a temporary copy of chatmon/ and pyproject.toml: mypy with PyQt6 6.12.1's stubs green, then failing on one change and naming Item \"None\" of \"voidptr | None\" has no attribute \"asstring\", then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/gate-drills.log",
        "sha256": "e2a2db7422740a2337c2bc752fcd15add429d0be55b403a4939fdfd962ae8649"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "e9a7e11d8a806144ca3ba837d4e7d2d1ea2d5a9f31f8462c24228b96f7b6eddd"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "eea305a08e3d5539258148b2bcb424971b5b99b7352b02273dc7823ea7c67508"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "539cc6e36fbb2a4c9087ded0fe23df91c1cab864f83a8246651ccb5f9b2866ad"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "a08f4083367cf24d7f24bdef5ad57f7278ac72443a4b150ecffeec7ac9173590"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "92e78ff220c4adf2bd3a48b4340a3e5cd3107ad517442c03c33a0b641d680e87"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "57c7e766ae1363dc2ff4deae52b3497f5667cb791ee7a796cd7b7f218dba2c93"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "88eba42ee487cc12ef34144c1e8b5ba4d8e81e4b73c346a051fc2a7ce682c501"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "49eea3fb007441614be3175d28d3d8819ffed95c94fa55a2e848948543cababf"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "c5a4bdd645c2acf29c8036724d12eb4b35d966878560f63ca77cb93fdd86bc7b"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "6a8ebada5c700063ebe9580ecba664012f4ae38843007070f445a6c2771ed81c"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "3cf6ee06d581a446d3e38948ee6dca818e586959cd70c63bb5db22498bb832dd"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "bc9070b1bc8259512adb12fbb872e8246801213b071242a7162c4aabda26b912"
        },
        {
          "path": "chatmon/qtsignal.py",
          "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "e951e136e4a2c89c6b660ac8e4af02078d92fd8f6baf83bba9e7c1ba8c0434f7"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "589baea64239425f4ca99bee706bfdb3d908043d00795011e98e4c8ea1cf4d85"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "7fc4b92b45f08189111888c993ad1e6ef92e8ca553f95a8c61b5f99258ce87c4"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        }
      ],
      "scope_sha256": "c9678a9dafa54474a9f2b17a6123e0b1c8c05e96e33400e395198bbe1fb9b888",
      "red": {
        "mutation": "null-image-unchecked: in chatmon/sprites.py, '    if bits is None:  # a null image: no rows' became '    if False:  # a null image: no rows'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "Item \"None\" of \"voidptr | None\" has no attribute \"asstring\"",
        "observed_diagnostic": "chatmon\\sprites.py:74: error: Item \"None\" of \"voidptr | None\" has no attribute \"asstring\"  [union-attr]",
        "before": [
          {
            "path": "chatmon/sprites.py",
            "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sprites.py",
            "sha256": "131a4a806923f35c4adc26d7d2b493cafd6aaa30cb89b2bdc98bf20602b91f4b"
          }
        ],
        "after": [
          {
            "path": "chatmon/sprites.py",
            "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
          }
        ]
      },
      "reason": "Bound to an earlier scope (the plan or a file it covers changed since); the check was run or reviewed again on the current scope as E-red-gate-null-image-unchecked. Next action: none."
    },
    {
      "id": "E-red-gate-alias-mistyped.c9678a9d",
      "acceptance": [
        "M10-03.A1"
      ],
      "kind": "red",
      "status": "stale",
      "command": [
        "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe",
        "docs/delivery/reports/m10/gate_drills.py"
      ],
      "method": "Gate drill alias-mistyped (gate_drills.py) in a temporary copy of chatmon/ and pyproject.toml: mypy with PyQt6 6.11's stubs green, then failing on one change and naming Incompatible types in assignment, then green again with the file's bytes put back.",
      "environment": {
        "platform": "windows",
        "tools": {
          "PyQt6": "6.11.0",
          "PyQt6-next": "6.12.1",
          "Qt": "6.11.2",
          "mypy": "2.4.1",
          "pytest": "9.2.0",
          "python": "3.14.10",
          "ruff": "0.17.4",
          "uv": "0.12.7"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m10/gate-drills.log",
        "sha256": "e2a2db7422740a2337c2bc752fcd15add429d0be55b403a4939fdfd962ae8649"
      },
      "inputs": [
        {
          "path": "CONTRIBUTING.md",
          "sha256": "e9a7e11d8a806144ca3ba837d4e7d2d1ea2d5a9f31f8462c24228b96f7b6eddd"
        },
        {
          "path": "chatmon/a11y.py",
          "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
        },
        {
          "path": "chatmon/app.py",
          "sha256": "eea305a08e3d5539258148b2bcb424971b5b99b7352b02273dc7823ea7c67508"
        },
        {
          "path": "chatmon/brains.py",
          "sha256": "539cc6e36fbb2a4c9087ded0fe23df91c1cab864f83a8246651ccb5f9b2866ad"
        },
        {
          "path": "chatmon/bubble.py",
          "sha256": "a08f4083367cf24d7f24bdef5ad57f7278ac72443a4b150ecffeec7ac9173590"
        },
        {
          "path": "chatmon/chatswin.py",
          "sha256": "92e78ff220c4adf2bd3a48b4340a3e5cd3107ad517442c03c33a0b641d680e87"
        },
        {
          "path": "chatmon/hotkey.py",
          "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
        },
        {
          "path": "chatmon/keychain.py",
          "sha256": "57c7e766ae1363dc2ff4deae52b3497f5667cb791ee7a796cd7b7f218dba2c93"
        },
        {
          "path": "chatmon/linuxsession.py",
          "sha256": "88eba42ee487cc12ef34144c1e8b5ba4d8e81e4b73c346a051fc2a7ce682c501"
        },
        {
          "path": "chatmon/macnative.py",
          "sha256": "49eea3fb007441614be3175d28d3d8819ffed95c94fa55a2e848948543cababf"
        },
        {
          "path": "chatmon/menus.py",
          "sha256": "c5a4bdd645c2acf29c8036724d12eb4b35d966878560f63ca77cb93fdd86bc7b"
        },
        {
          "path": "chatmon/packagekit.py",
          "sha256": "6a8ebada5c700063ebe9580ecba664012f4ae38843007070f445a6c2771ed81c"
        },
        {
          "path": "chatmon/portal.py",
          "sha256": "3cf6ee06d581a446d3e38948ee6dca818e586959cd70c63bb5db22498bb832dd"
        },
        {
          "path": "chatmon/presence.py",
          "sha256": "bc9070b1bc8259512adb12fbb872e8246801213b071242a7162c4aabda26b912"
        },
        {
          "path": "chatmon/qtsignal.py",
          "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
        },
        {
          "path": "chatmon/settingswin.py",
          "sha256": "e951e136e4a2c89c6b660ac8e4af02078d92fd8f6baf83bba9e7c1ba8c0434f7"
        },
        {
          "path": "chatmon/sound.py",
          "sha256": "589baea64239425f4ca99bee706bfdb3d908043d00795011e98e4c8ea1cf4d85"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
        },
        {
          "path": "chatmon/updates.py",
          "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
        },
        {
          "path": "chatmon/wintoast.py",
          "sha256": "7fc4b92b45f08189111888c993ad1e6ef92e8ca553f95a8c61b5f99258ce87c4"
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
          "path": "docs/delivery/m4a-platform-awareness.md",
          "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
        },
        {
          "path": "docs/delivery/m6a-ci-tooling.md",
          "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
        },
        {
          "path": "docs/delivery/m6b-static-analysis-logging.md",
          "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
        },
        {
          "path": "docs/delivery/m8-translation.md",
          "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
        },
        {
          "path": "packaging/requirements-build.txt",
          "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
        },
        {
          "path": "packaging/requirements-dev.in",
          "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
        },
        {
          "path": "packaging/requirements.txt",
          "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
        },
        {
          "path": "pyproject.toml",
          "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
        }
      ],
      "scope_sha256": "c9678a9dafa54474a9f2b17a6123e0b1c8c05e96e33400e395198bbe1fb9b888",
      "red": {
        "mutation": "alias-mistyped: in chatmon/qtsignal.py, '= QtCore.pyqtSignal' became '= QtCore.pyqtSlot'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "Incompatible types in assignment",
        "observed_diagnostic": "chatmon\\qtsignal.py:15: error: Incompatible types in assignment (expression has type \"def pyqtSlot(*types: Any, name: str | None = ..., result: str | None = ...) -> Callable[[FuncT], FuncT]\", variable has type \"Callable[..., pyqtSignal]\")  [assignment]",
        "before": [
          {
            "path": "chatmon/qtsignal.py",
            "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/qtsignal.py",
            "sha256": "704e3d0da9eef6f21940603196403dc04548e941ca0bfc31a046a21813741665"
          }
        ],
        "after": [
          {
            "path": "chatmon/qtsignal.py",
            "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
          }
        ]
      },
      "reason": "Bound to an earlier scope (the plan or a file it covers changed since); the check was run or reviewed again on the current scope as E-red-gate-alias-mistyped. Next action: none."
    }
  ],
  "checkpoint": {
    "scope_sha256": "9130daf8ba42d6fea1f889a520c950eaffd04692dfb5bd007e5e6f1ae80b3cb9",
    "inputs": [
      {
        "path": "CONTRIBUTING.md",
        "sha256": "e9a7e11d8a806144ca3ba837d4e7d2d1ea2d5a9f31f8462c24228b96f7b6eddd"
      },
      {
        "path": "chatmon/a11y.py",
        "sha256": "51de316d33d458c3dcd2636d1fb230bcbc53ce1b461d0efd2f714f45c161f184"
      },
      {
        "path": "chatmon/app.py",
        "sha256": "eea305a08e3d5539258148b2bcb424971b5b99b7352b02273dc7823ea7c67508"
      },
      {
        "path": "chatmon/brains.py",
        "sha256": "539cc6e36fbb2a4c9087ded0fe23df91c1cab864f83a8246651ccb5f9b2866ad"
      },
      {
        "path": "chatmon/bubble.py",
        "sha256": "a08f4083367cf24d7f24bdef5ad57f7278ac72443a4b150ecffeec7ac9173590"
      },
      {
        "path": "chatmon/chatswin.py",
        "sha256": "92e78ff220c4adf2bd3a48b4340a3e5cd3107ad517442c03c33a0b641d680e87"
      },
      {
        "path": "chatmon/hotkey.py",
        "sha256": "c9aca0f64359fc006ea11263ec214bf3033e4080ca3dd5644ff69e46cccfbcbd"
      },
      {
        "path": "chatmon/i18n.py",
        "sha256": "6370e91e9ed30c86febada42a4b8677521cb0f4343a3e6fb9901f61c3a5fae83"
      },
      {
        "path": "chatmon/keychain.py",
        "sha256": "57c7e766ae1363dc2ff4deae52b3497f5667cb791ee7a796cd7b7f218dba2c93"
      },
      {
        "path": "chatmon/linuxsession.py",
        "sha256": "88eba42ee487cc12ef34144c1e8b5ba4d8e81e4b73c346a051fc2a7ce682c501"
      },
      {
        "path": "chatmon/macnative.py",
        "sha256": "49eea3fb007441614be3175d28d3d8819ffed95c94fa55a2e848948543cababf"
      },
      {
        "path": "chatmon/menus.py",
        "sha256": "c5a4bdd645c2acf29c8036724d12eb4b35d966878560f63ca77cb93fdd86bc7b"
      },
      {
        "path": "chatmon/packagekit.py",
        "sha256": "6a8ebada5c700063ebe9580ecba664012f4ae38843007070f445a6c2771ed81c"
      },
      {
        "path": "chatmon/portal.py",
        "sha256": "3cf6ee06d581a446d3e38948ee6dca818e586959cd70c63bb5db22498bb832dd"
      },
      {
        "path": "chatmon/presence.py",
        "sha256": "bc9070b1bc8259512adb12fbb872e8246801213b071242a7162c4aabda26b912"
      },
      {
        "path": "chatmon/qtsignal.py",
        "sha256": "aa4984a544701256262fd1078688508cd87f725b8107cc0bfb01b03cf21a5cbf"
      },
      {
        "path": "chatmon/settingswin.py",
        "sha256": "e951e136e4a2c89c6b660ac8e4af02078d92fd8f6baf83bba9e7c1ba8c0434f7"
      },
      {
        "path": "chatmon/sound.py",
        "sha256": "589baea64239425f4ca99bee706bfdb3d908043d00795011e98e4c8ea1cf4d85"
      },
      {
        "path": "chatmon/sprites.py",
        "sha256": "f822aae7b4821644299b0df500f01e1401e290d17f83444d497038d21c62e0f5"
      },
      {
        "path": "chatmon/updates.py",
        "sha256": "470061d34c8bc8dd49b3102bfde9b9f56121eea1d75c42665afd69c824698e05"
      },
      {
        "path": "chatmon/wintoast.py",
        "sha256": "7fc4b92b45f08189111888c993ad1e6ef92e8ca553f95a8c61b5f99258ce87c4"
      },
      {
        "path": "chatmon/winuia.py",
        "sha256": "14c8d4086dc2de82c97d49b89075e3e55b649dffb4e72956bb431b5c483f09ea"
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
        "path": "docs/delivery/m4a-platform-awareness.md",
        "sha256": "48ef63f9f36ad23b92414585b8c04779eb502fcade3913e7e723638816771fcd"
      },
      {
        "path": "docs/delivery/m6a-ci-tooling.md",
        "sha256": "e40e1df52e3502e1bc198347036c610d935976607ea009993383406ecfe173ed"
      },
      {
        "path": "docs/delivery/m6b-static-analysis-logging.md",
        "sha256": "043f4b3f21d3fa4376641bf16b6dc76122a6bbef1ab9f58de805d34a42c00a2f"
      },
      {
        "path": "docs/delivery/m8-translation.md",
        "sha256": "45eb28e92f18de998b3ef44b3d94b202c1186c62a55113e7adfae60d4b0fd010"
      },
      {
        "path": "packaging/build.py",
        "sha256": "3184c599c5e3e7f1d2d9e05b2d92df27a719f4f5eaca62656b12bd4aafbbc489"
      },
      {
        "path": "packaging/chatmon.spec",
        "sha256": "81a5cddbc39774996891111e8fa77911be56008e1f2d06609fa5fe867bd74dff"
      },
      {
        "path": "packaging/requirements-build.txt",
        "sha256": "68ae8a8476dff8846ca80a3ba3396142630add768f6e5d98208e7d82db66a85c"
      },
      {
        "path": "packaging/requirements-dev.in",
        "sha256": "8829bc721a697970c48e89bd9a2a75ef8853d56bc9d541beec012339db60ef8f"
      },
      {
        "path": "packaging/requirements-dev.txt",
        "sha256": "b86886c4f5f4e8998ea2d2d8e3e611dddd41ab1d45c747bf93ae032e5c6adb07"
      },
      {
        "path": "packaging/requirements-test.in",
        "sha256": "af1dc11bd8f63827bd4e5cf4b4f124b3bc7fb60000f9377ea96b804a68a81afa"
      },
      {
        "path": "packaging/requirements-test.txt",
        "sha256": "d5befda1ab649c1dd0b4e91209101fb5699b531112871d2b31adaf1307b91a4b"
      },
      {
        "path": "packaging/requirements.txt",
        "sha256": "db6d6894bc841f393f1c02b77ae2b9ffb4fcf39de52782c193dae9c5a697e937"
      },
      {
        "path": "pyproject.toml",
        "sha256": "660fbb06e26d65f74193a50e6b89fe6b80c59994d4f5a4eb8dcac6a0c8bb8601"
      },
      {
        "path": "tests/conftest.py",
        "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
      },
      {
        "path": "tests/drills/run.py",
        "sha256": "a0f4774c4a0ffebcd1bcf2da357d76c8044ff96ca0c9c08a9dfec052151914c5"
      },
      {
        "path": "tests/test_i18n.py",
        "sha256": "4d340c2aa6c3165e315ce83d10d52e5e40f1e3d30b9ba13e3dcc5176b58ed3f7"
      },
      {
        "path": "tests/test_packaging.py",
        "sha256": "d5ccbdca187a3daefcae4c556348984bb0abbef04646072d5dce67b24f53445a"
      },
      {
        "path": "tests/test_platform_events.py",
        "sha256": "ed105111d8091deb0fb66ab5fab9d661a564673142a8e67ec416f275508c0bd4"
      },
      {
        "path": "tests/test_requirements.py",
        "sha256": "e7923dce3696b85dc93b177e154d62a323504d56697385d085f8768449d8af2b"
      },
      {
        "path": "tests/uia_client.py",
        "sha256": "1e958e5590f4c71302a1622442d9fc02c70029c02df05c60c328497a41e978ef"
      }
    ],
    "environment": {
      "platform": "windows",
      "tools": {
        "PyQt6": "6.11.0",
        "PyQt6-next": "6.12.1",
        "Qt": "6.11.2",
        "mypy": "2.4.1",
        "pytest": "9.2.0",
        "python": "3.14.10",
        "ruff": "0.17.4",
        "uv": "0.12.7"
      }
    },
    "verified_tasks": [
      "T1-comtypes",
      "T2-qt-translations",
      "T3-qt612-types"
    ],
    "pending_operations": [],
    "next_action": "Coordinator: apply the layer.py and penguin.py changes in the integration note after the wayland worker merges, and add the 6.12.1 types entry to ci.yml once 6.12.1 is two weeks old (2026-11-28).",
    "source_revision": "d15d7a99da491da4b2edbaf7a3455d98cef2fa2d"
  }
}
```
