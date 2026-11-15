# M10 readiness review

A review of the three follow-ups the coordinator handed M10 on `fb19cb9` (0.10.0 merged, PR #18 open): comtypes for
the Windows test legs ([M4A's integration note](../../m4a-platform-awareness.md#integration-notes)), Qt's own
translations in the installed apps ([M8's note for the coordinator](../../m8-translation.md#for-the-coordinator)),
and mypy with PyQt6 6.12's stubs ([M6B, integration note 3](../../m6b-static-analysis-logging.md#integration-notes)).
It reviews the requirements and what they rest on, not the code: the receipts in the plan's ledger are what show the
code works. Everything below was read or run on `fb19cb9` before anything changed.

## The follow-ups, re-checked on fb19cb9

| Item | Handed over as | Found on fb19cb9 | Verdict |
|---|---|---|---|
| M10-01 | the UI Automation end-to-end test skips in CI: no comtypes | `tests/test_platform_events.py::test_a_ui_automation_client_hears_the_announcement` calls `pytest.importorskip("comtypes")`; no lock or extra names comtypes; every pip test leg installs `requirements-test.txt` only (`ci.yml` lines 128 and 176). The shared venv has comtypes 1.5.0 by hand, which is why the test runs here and not in CI. | Real |
| M10-02 | `--noinclude-qt-translations`; a shipped language would leave Qt's buttons in English | Read in the locked tools' own sources (downloaded with their lock hashes into a scratch folder, not run). **Nuitka 4.3.1** (`plugins/standard/PySidePyQtPlugin.py`) copies Qt's translations only inside `_handleWebEngineDataFiles`, for QtWebEngine, which Chatmon doesn't use: the Windows app carries none either way. **PyInstaller 6.22.3** (`utils/hooks/qt/__init__.py`, and `_modules_info.py`: QtCore's translations are `qt` and `qtbase`) collects every `qt_*.qm` and `qtbase_*.qm`, and each used module's (`qtmultimedia_*`), into `PyQt6/Qt6/translations`, and its runtime hook (`pyi_rth_pyqt6.py`) gives PyQt6 the embedded qt.conf that points `QLibraryInfo` there: the macOS app carries all of Qt's languages, which nothing loads. `i18n._install_qt_translation` looks only in `QLibraryInfo`'s TranslationsPath. | Real: Windows would show Qt's words in English; macOS ships about 100 files it never reads |
| M10-03 | about a hundred mypy errors with PyQt6 6.12's stubs, mostly `pyqtSignal` | In a throwaway venv (`%TEMP%\m10-qt6121`, PyQt6 6.12.1, mypy 2.4.1, installed with hashes): 113 errors in 20 files on each of linux, win32 and darwin. 63 are `Missing named argument "arguments" for "pyqtSignal"` (6.12.1's stub makes `arguments` keyword-only with no default); 28 `Need type annotation` (static constructors typed `-> typing.Self`, which a static method can't bind); 19 `arg-type` (parameters typed `typing.Self` that take any QObject or None: a QObject's parent, `installEventFilter`, `setParent`); and one each of redundant-cast (`QMenu.addMenu` now returns Self), union-attr (`QImage.constBits()` now optional) and redundant-expr (`QWidget.childAt` now never None, in penguin.py). The stubs use `typing.Self` 567 times in QtCore.pyi alone, 0 times in 6.11's and 6.12.0's. **PyQt6 6.12.0** (in `%TEMP%\m10-qt612`, from a lock made with the two-week rule) can't be checked at all: its `QtDBus.pyi` has `*args: typing.Any, /` (lines 59, 66 and 68), a syntax error that stops mypy before it reads any module. | Real, for 6.12.1; 6.12.0 is an upstream stub that no change in Chatmon can make pass |

Release dates, from PyPI's JSON: PyQt6 6.12.0 2026-10-28, 6.12.1 2026-11-14 (today); comtypes 1.4.17 2026-09-21,
1.5.0 2026-11-09.

## Decisions

| # | Question | Decision |
|---|---|---|
| D1 | Which comtypes | 1.4.17: the newest before 2026-10-31, the `--exclude-newer` date the locks already use (two weeks before today). 1.5.0, the shared venv's, is five days old. |
| D2 | Where comtypes goes | `requirements-test.in` with `; sys_platform == 'win32'`, so only Windows legs install it; `requirements-dev.in` includes the test list, so the dev lock and the `dev` extra take it too (`tests/test_requirements.py` requires all three to agree). The `test` extra gains `comtypes; sys_platform == 'win32'`, as M4A suggested. `ci.yml` needs no change: its Windows legs already install `requirements-test.txt`. |
| D3 | The lock command | `uv pip compile <list>.in -o <list>.txt --universal --python-version 3.11 --generate-hashes --exclude-newer 2026-10-31`, run in `packaging/`, as CONTRIBUTING.md documents. Re-run on the unchanged lists it reproduces every line of both locks but the header, which now records `--exclude-newer` (the old headers left it out; the resolution is the same). |
| D4 | Keeping comtypes in | A test in `tests/test_requirements.py` checks the test and dev locks hold comtypes for Windows alone; without it, losing the pin would only turn the end-to-end test back into a skip. |
| D5 | Which Qt file serves a language | The one Qt itself loads: `QTranslator.load(QLocale(code), "qtbase", "_", folder)`, the call i18n makes at run time, made by the build in the same function (`i18n.qt_translator`). So "pt" ships `qtbase_pt_BR.qm`, "zh" `qtbase_zh_CN.qm`, "de_AT" `qtbase_de.qm` (all checked against Qt 6.11.2), and the frozen app finds the same file. English is Qt's own language: nothing. A language Qt doesn't translate (Esperanto) adds nothing, and the build says so. |
| D6 | Which languages | Those `i18n.available()` lists: a `chatmon/locale/<lang>.po` whose name is a language tag. Only English ships, so today both builds carry no Qt translation at all. |
| D7 | Where they go in a frozen app | `PyQt6/Qt6/translations/` under the folder that holds the `chatmon` package (Nuitka's dist folder, PyInstaller's `_MEIPASS`): the wheel's own layout, where PyInstaller's qt.conf points `QLibraryInfo`. Defined once, as `i18n.QT_FROZEN`, and used by build.py, the spec and the lookup. |
| D8 | The lookup | `QLibraryInfo`'s TranslationsPath first (pip's PyQt6; a Linux distribution's Qt, which the .deb and .rpm use, so they find the system's own translations), then, in a frozen app only (`paths.frozen()`), the app's own `QT_FROZEN` folder, for Nuitka, whose PyQt6 may not point Qt there. Nothing found: Qt's words stay English, as today. |
| D9 | macOS | The spec keeps PyInstaller's data files but for Qt's translations, which it narrows to D5's files (`build.pyinstaller_datas`), adding any the hooks didn't collect. |
| D10 | Linux | Nothing bundled (the packages use the system's PyQt6). Recommending the distribution's translation package (`qt6-translations-l10n`, `qt6-qttranslations`) in `nfpm.yaml` is for its owner, once a language ships: a note. |
| D11 | Which 6.12 | 6.12.1. 6.12.0 can't pass (its QtDBus stub doesn't parse), and the errors M6B measured are 6.12.1's. The fix must keep 6.11 passing too, since that's what CI locks. |
| D12 | The signal stub bug | One typed alias, `chatmon/qtsignal.py`: `pyqtSignal: Callable[..., QtCore.pyqtSignal] = QtCore.pyqtSignal`, the same object at run time. Modules import it from there instead of `PyQt6.QtCore`; their declarations don't change. One place explains the bug; 63 per-line ignores would have said it 63 times. |
| D13 | Self-typed parameters | A per-line `# type: ignore[arg-type]` with the reason, as `sysnotify.py` already has for its parent: the argument is right and the stub wrong, and a cast would hide a real mistake on that line. |
| D14 | Static constructors returning an unbound Self | The variable is typed (`bus: QDBusConnection = QDBusConnection.sessionBus()`), as `sysnotify.py` and `report.py` already do: true under both stubs, and no ignore. |
| D15 | The three one-offs | `constBits()`: a real check for None (a null image has no bits). `addMenu`'s cast, now redundant: a per-line `# type: ignore[return-value]` for 6.11's optional result, which Qt never returns. `childAt` in penguin.py: the wayland worker's file (D17). |
| D16 | A CI entry for 6.12 | Not now. The rule is a release at least two weeks old, hash-locked: 6.12.0 qualifies and can't pass; 6.12.1 qualifies from 2026-11-28. CONTRIBUTING.md says how to check against 6.12.1 in a venv of its own, and the plan gives the coordinator the list and the `types` job's matrix entry for when it can be locked. |
| D17 | The wayland worker's files | `layer.py` and `penguin.py` have 14 of the 113 errors per platform (2 and 12), of the same kinds. They're not edited here: the changes are listed for the coordinator and checked in a scratch copy, where mypy then passes everything on all three platforms with both stubs. |
| D18 | Dependabot | It will offer PyQt6 6.12.0 for the shipped Qt now (past its 14-day cooldown). Its `types` jobs would fail on 6.12.0's QtDBus stub: a note to wait for 6.12.1. |
| D19 | An upstream report | Searched; none found for 6.12.1's `Self` or `arguments`. The comments name the stub's mistake instead of a link, and the plan has a draft report for the owner to send (it needs his mailing-list account). |

## Failure behaviour, terminology and coverage

- **Failure behaviour.** The build with a language Qt has no translation for, or with a Qt that has no translations
  folder, carries none for it and says so, and goes on. A frozen app with no Qt translation for the language shows
  Qt's words in English, as today. A Windows leg without comtypes would still skip the end-to-end test, which is why
  D4's test guards the lock. mypy with 6.12.0 fails in PyQt6's own stub, not Chatmon's code.
- **Terms.** *Qt's own words*: the strings in Qt's dialogs and widgets (`qtbase_<lang>.qm`); *frozen*: an installer's
  build (Nuitka on Windows, PyInstaller on macOS), as `paths.frozen()` decides; *next stubs*: PyQt6 6.12.1's.
- **Coverage.** Every acceptance criterion has an owning task and behaviour checks; the automated ones have red
  drills (pytest assertions through `tests/drills/run.py`, mypy through `gate_drills.py`, which the drill harness
  can't run). The how-to in CONTRIBUTING.md is a manual check, compared with the commands this work ran.
- **Conflicts.** None between the brief and the roadmap's rules: comtypes is test-only (owner decision: test-only
  additions are fine); no runtime dependency; no file of the wayland worker's (`layer.py`, `wayland.py`, `xkb.py`,
  `penguin.py`, `stagemenu.py`, `clickthrough.py`, `ci.yml`) is changed.
- **Out of scope.** README.md and `chatmon/changelog.md` (notes in the plan); `nfpm.yaml` (D10); `ci.yml` (D16).
