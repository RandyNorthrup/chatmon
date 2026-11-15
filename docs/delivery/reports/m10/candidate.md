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

New code with its own responsibility: `chatmon/qtsignal.py` (the one place the signal stub bug is handled), the two
build functions (what the installers carry), and `reports/m10/mypy_runs.py` and `gate_drills.py` (evidence tools).

## Results

(Filled in as the checks run.)

## Integration notes

(Filled in as the work lands.)

## Changelog notes

(Filled in as the work lands.)

## README notes

(Filled in as the work lands.)

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
      "packaging/requirements-dev.in"
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "reason": null
    }
  ],
  "checkpoint": null
}
```
